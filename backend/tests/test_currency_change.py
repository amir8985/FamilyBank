"""Currency-change correctness: switching a family's base_currency must
actually convert existing balances at today's rate, not just relabel
them (the bug that motivated this — see CLAUDE.md / the currency-change
feature). Investment holdings need no special handling here since they
already store their own currency and convert at read time; these tests
mainly cover the debt ledger side plus the preview/warning endpoint and
the FX-cache-completeness fix that makes both possible.
"""

from datetime import datetime, timedelta, timezone
from decimal import Decimal

from sqlalchemy import delete, or_
from sqlalchemy.dialects.postgresql import insert

from app.models.catalog import FxRateCache
from app.models.debt_transaction import DebtTransaction, DebtTransactionType
from app.models.kid import Kid
from app.services import debts_db_service, investing_service


async def _make_kid(db_session, family, name="Kid") -> Kid:
    kid = Kid(family_id=family.id, name=name, avatar_color="amber")
    db_session.add(kid)
    await db_session.flush()
    return kid


async def _fund(db_session, kid, amount: str):
    await debts_db_service.record_transaction(db_session, kid.id, DebtTransactionType.ADD, Decimal(amount))


async def _fund_in_the_past(db_session, kid, amount: str):
    # Postgres's now() (the created_at server default) returns the
    # *transaction's* start time, and this whole test runs inside one
    # outer transaction (see conftest.py) — so a row inserted this way
    # and one inserted later via the API in the same test would get an
    # identical created_at, making their relative order ambiguous. Real
    # requests are separate transactions with genuinely distinct times;
    # this only matters for tests that depend on chronological order.
    txn = DebtTransaction(
        kid_id=kid.id,
        type=DebtTransactionType.ADD,
        amount=Decimal(amount),
        created_at=datetime.now(timezone.utc) - timedelta(minutes=5),
    )
    db_session.add(txn)
    await db_session.flush()
    return txn


async def _seed_rate(db_session, base: str, quote: str, rate: str):
    # Upsert, not a plain insert: the shared dev/test DB this suite runs
    # against (see CLAUDE.md) already has real scheduler-cached rows for
    # common pairs like USD/ILS, so a bare INSERT can collide with one.
    now = datetime.now(timezone.utc)
    stmt = (
        insert(FxRateCache)
        .values(base_currency=base, quote_currency=quote, rate=Decimal(rate), updated_at=now)
        .on_conflict_do_update(
            index_elements=["base_currency", "quote_currency"],
            set_={"rate": Decimal(rate), "updated_at": now},
        )
    )
    await db_session.execute(stmt)
    await db_session.flush()


async def _clear_rate(db_session, base: str, quote: str):
    """Deletes any cached row for this pair in either direction, within
    the test's own (rolled-back) transaction — needed because this suite
    runs against the shared dev/test DB (see CLAUDE.md), where the real
    scheduler may have already cached a pair a test needs to assume is
    *not* cached, e.g. to exercise the "no rate available" or
    "must triangulate" paths deterministically."""
    await db_session.execute(
        delete(FxRateCache).where(
            or_(
                (FxRateCache.base_currency == base) & (FxRateCache.quote_currency == quote),
                (FxRateCache.base_currency == quote) & (FxRateCache.quote_currency == base),
            )
        )
    )
    await db_session.flush()


async def test_changing_currency_converts_balance_not_just_relabels_it(client, db_session, family, auth_headers):
    kid = await _make_kid(db_session, family)
    await _fund(db_session, kid, "36")  # family starts in USD per the `family` fixture
    await _seed_rate(db_session, "USD", "ILS", "3.6")

    resp = await client.patch("/family/settings", headers=auth_headers, json={"base_currency": "ILS"})
    assert resp.status_code == 200
    assert resp.json()["base_currency"] == "ILS"

    # 36 USD -> 129.6 ILS, not still "36".
    assert await debts_db_service.get_balance(db_session, kid.id) == Decimal("129.60")


async def test_conversion_adds_adjustment_row_without_rewriting_history(client, db_session, family, auth_headers):
    kid = await _make_kid(db_session, family)
    await _fund(db_session, kid, "10")
    await _seed_rate(db_session, "USD", "EUR", "0.9")

    resp = await client.patch("/family/settings", headers=auth_headers, json={"base_currency": "EUR"})
    assert resp.status_code == 200

    rows = await debts_db_service.list_transactions(db_session, kid.id)
    assert len(rows) == 2
    original = next(r for r in rows if not r.is_adjustment)
    assert original.amount == Decimal("10") and original.note is None  # untouched
    adjustment = next(r for r in rows if r.is_adjustment)
    assert adjustment.type == DebtTransactionType.DEDUCT  # 10 -> 9, a decrease
    assert "USD" in adjustment.note and "EUR" in adjustment.note


async def test_zero_balance_kid_gets_no_adjustment_row(client, db_session, family, auth_headers):
    kid = await _make_kid(db_session, family)  # never funded
    await _seed_rate(db_session, "USD", "EUR", "0.9")

    resp = await client.patch("/family/settings", headers=auth_headers, json={"base_currency": "EUR"})
    assert resp.status_code == 200
    assert await debts_db_service.list_transactions(db_session, kid.id) == []


async def test_same_currency_is_a_no_op(client, db_session, family, auth_headers):
    kid = await _make_kid(db_session, family)
    await _fund(db_session, kid, "10")

    # No FX rate seeded at all — must not even attempt a lookup for a no-op change.
    resp = await client.patch("/family/settings", headers=auth_headers, json={"base_currency": "USD"})
    assert resp.status_code == 200
    assert await debts_db_service.get_balance(db_session, kid.id) == Decimal("10")


async def test_unsupported_currency_rejected(client, auth_headers):
    resp = await client.patch("/family/settings", headers=auth_headers, json={"base_currency": "XYZ"})
    assert resp.status_code == 422


async def test_unresolvable_rate_returns_409_and_leaves_currency_unchanged(client, db_session, family, auth_headers):
    # Force the "nothing cached" state regardless of whatever the real
    # scheduler has already populated in this shared dev/test DB.
    await _clear_rate(db_session, "USD", "JPY")
    resp = await client.patch("/family/settings", headers=auth_headers, json={"base_currency": "JPY"})
    assert resp.status_code == 409

    settings_resp = await client.get("/family/settings", headers=auth_headers)
    assert settings_resp.json()["base_currency"] == "USD"


async def test_triangulates_through_usd_when_no_direct_pair_cached(client, db_session, family, auth_headers):
    # Family starts in EUR; only EUR->USD and USD->GBP are cached, so
    # converting EUR->GBP has to triangulate through USD.
    family.base_currency = "EUR"
    await db_session.flush()
    kid = await _make_kid(db_session, family)
    await _fund(db_session, kid, "100")
    # Force "no direct pair" regardless of what the real scheduler has
    # already cached for EUR<->GBP in this shared dev/test DB.
    await _clear_rate(db_session, "EUR", "GBP")
    await _seed_rate(db_session, "EUR", "USD", "1.1")
    await _seed_rate(db_session, "USD", "GBP", "0.8")

    resp = await client.patch("/family/settings", headers=auth_headers, json={"base_currency": "GBP"})
    assert resp.status_code == 200
    # 100 EUR -> 110 USD -> 88 GBP
    assert await debts_db_service.get_balance(db_session, kid.id) == Decimal("88.00")


async def test_preview_shows_converted_totals_without_committing_anything(
    client, db_session, family, auth_headers
):
    kid = await _make_kid(db_session, family)
    await _fund(db_session, kid, "36")
    await _seed_rate(db_session, "USD", "ILS", "3.6")

    resp = await client.get("/family/settings/currency-preview?to=ILS", headers=auth_headers)
    assert resp.status_code == 200
    body = resp.json()
    assert body["from_currency"] == "USD"
    assert body["to_currency"] == "ILS"
    assert body["kids"][0]["old_cash_balance"] == "36.00"
    assert body["kids"][0]["new_cash_balance"] == "129.60"

    # Preview must not have changed anything.
    assert family.base_currency == "USD"
    assert await debts_db_service.get_balance(db_session, kid.id) == Decimal("36")


async def test_preview_same_currency_rejected(client, auth_headers):
    resp = await client.get("/family/settings/currency-preview?to=USD", headers=auth_headers)
    assert resp.status_code == 400


async def test_preview_unsupported_currency_rejected(client, auth_headers):
    resp = await client.get("/family/settings/currency-preview?to=XYZ", headers=auth_headers)
    assert resp.status_code == 422


async def test_investment_value_reprices_automatically_after_currency_change(
    client, db_session, family, auth_headers, seeded_asset
):
    """Unlike debts, holdings already store their own currency and convert
    at read time — this just confirms that still works once the family's
    currency changes, given the FX-completeness fix makes the rate available."""
    kid = await _make_kid(db_session, family)
    await _fund(db_session, kid, "1000")
    await investing_service.buy(db_session, kid, "USD", "TEST", Decimal("2"))  # 2 units @ $100
    await db_session.commit()

    await _seed_rate(db_session, "USD", "ILS", "3.6")
    resp = await client.patch("/family/settings", headers=auth_headers, json={"base_currency": "ILS"})
    assert resp.status_code == 200

    portfolio = await investing_service.get_portfolio(db_session, kid, "ILS")
    assert portfolio["holdings"][0]["current_value"] == Decimal("720.00")  # 2*100 USD -> ILS


async def test_history_shows_each_row_in_the_currency_it_was_actually_recorded_in(
    client, db_session, family, auth_headers
):
    """The bug a parent actually hit: after converting, an old 200 EUR
    deposit was displayed with a ILS symbol as if 200 ILS had been added.
    debts_db_service.list_transactions_with_currency (via GET .../debt)
    must tag every row with the currency it was really recorded in, not
    the family's currency today."""
    kid = await _make_kid(db_session, family)
    family.base_currency = "EUR"
    await db_session.flush()
    await _fund_in_the_past(db_session, kid, "200")  # 200 EUR
    await _clear_rate(db_session, "EUR", "ILS")
    await _seed_rate(db_session, "EUR", "ILS", "3.5")

    resp = await client.patch("/family/settings", headers=auth_headers, json={"base_currency": "ILS"})
    assert resp.status_code == 200

    resp = await client.get(f"/kids/{kid.id}/debt", headers=auth_headers)
    assert resp.status_code == 200
    rows = {r["is_adjustment"]: r for r in resp.json()}

    original = rows[False]
    assert original.get("is_investment") is False
    assert original["amount"] == "200.00"
    assert original["currency"] == "EUR"  # not ILS, even though that's current now
    assert original["balance_before"] == "0.00" and original["previous_currency"] == "EUR"
    assert original["balance_after"] == "200.00"

    adjustment = rows[True]
    assert adjustment["currency"] == "ILS"
    assert adjustment["previous_currency"] == "EUR"
    assert adjustment["balance_before"] == "200.00"  # 200 EUR
    assert adjustment["balance_after"] == "700.00"  # 200 EUR -> 700 ILS at rate 3.5
