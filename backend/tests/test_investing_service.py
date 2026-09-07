"""These cover the exact logic that broke in production: the enum
value_callable mismatch, the func.case() typo, and the transaction/
autobegin commit bug (see buy/sell below — if that regresses, holdings
silently stop persisting even though the API response looks fine)."""

from datetime import datetime, timedelta, timezone
from decimal import Decimal

import pytest
from sqlalchemy import select

from app.models.catalog import AssetKind, PriceTick
from app.models.debt_transaction import DebtTransactionType
from app.models.investment import InvestmentLot
from app.models.kid import Kid
from app.services import debts_db_service, investing_service


async def _make_kid(db_session, family, name="Kid") -> Kid:
    kid = Kid(family_id=family.id, name=name, avatar_color="amber")
    db_session.add(kid)
    await db_session.flush()
    return kid


async def _fund(db_session, kid, amount: str):
    await debts_db_service.record_transaction(db_session, kid.id, DebtTransactionType.ADD, Decimal(amount))


async def _only_lot_id(db_session, kid):
    lot = await db_session.scalar(select(InvestmentLot).where(InvestmentLot.kid_id == kid.id))
    return lot.id


async def _add_tick(db_session, symbol: str, price: str, when: datetime):
    db_session.add(PriceTick(symbol=symbol, observed_at=when, price=Decimal(price), currency="USD"))
    await db_session.flush()


async def test_buy_persists_holding_and_debits_cash(db_session, family, seeded_asset):
    kid = await _make_kid(db_session, family)
    await _fund(db_session, kid, "1000")

    txn = await investing_service.buy(db_session, kid, "USD", "TEST", Decimal("2"))
    assert txn.units == Decimal("2")

    # Re-read from the DB rather than trusting the returned object, since
    # the original bug made the API response look right while nothing
    # actually persisted.
    portfolio = await investing_service.get_portfolio(db_session, kid, "USD")
    assert portfolio["holdings"][0]["symbol"] == "TEST"
    assert portfolio["holdings"][0]["units"] == Decimal("2")
    assert await debts_db_service.get_balance(db_session, kid.id) == Decimal("800")  # 1000 - 2*100

    # The debt row the buy writes must be flagged so the history screen
    # can show "Bought" instead of a generic "Deducted" — see
    # test_currency_change.py's history-rendering tests for the reverse
    # case (a manual deduct must NOT be flagged this way).
    rows = await debts_db_service.list_transactions(db_session, kid.id)
    buy_row = next(r for r in rows if r.note and r.note.startswith("Bought"))
    assert buy_row.is_investment is True


async def test_buy_rejects_insufficient_funds(db_session, family, seeded_asset):
    kid = await _make_kid(db_session, family)
    await _fund(db_session, kid, "50")  # not enough for even 1 unit at $100

    with pytest.raises(investing_service.InvestingError, match="Insufficient"):
        await investing_service.buy(db_session, kid, "USD", "TEST", Decimal("1"))

    # A failed buy must not have debited anything.
    assert await debts_db_service.get_balance(db_session, kid.id) == Decimal("50")


async def test_buy_unknown_symbol_rejected(db_session, family):
    kid = await _make_kid(db_session, family)
    await _fund(db_session, kid, "1000")
    with pytest.raises(investing_service.InvestingError, match="Unknown symbol"):
        await investing_service.buy(db_session, kid, "USD", "NOPE", Decimal("1"))


async def test_buy_rejects_cleanly_when_fx_rate_is_missing(db_session, family, seeded_asset):
    """"ZZZ" isn't a real currency, so it's guaranteed to have no cached
    rate (see test_portfolio_survives_missing_fx_rate's use of the same
    trick). Previously this path raised a bare ValueError from
    fx_service.convert() — a subclass check (`except InvestingError`)
    doesn't catch its own parent class, so this crashed as an unhandled
    500 instead of the clean 400 every other rejection here gets."""
    kid = await _make_kid(db_session, family)
    await _fund(db_session, kid, "1000")
    with pytest.raises(investing_service.InvestingError, match="No cached FX rate"):
        await investing_service.buy(db_session, kid, "ZZZ", "TEST", Decimal("1"))


async def test_buying_twice_creates_two_separate_lots(db_session, family, seeded_asset):
    """Every buy() creates its own independent InvestmentLot now — even a
    second purchase of the same symbol never blends into the first one
    (see models/investment.py's InvestmentLot docstring)."""
    kid = await _make_kid(db_session, family)
    await _fund(db_session, kid, "1000")
    await investing_service.buy(db_session, kid, "USD", "TEST", Decimal("1"))  # at $100
    await investing_service.buy(db_session, kid, "USD", "TEST", Decimal("1"))  # at $100 again

    portfolio = await investing_service.get_portfolio(db_session, kid, "USD")
    assert len(portfolio["holdings"]) == 2
    assert all(h["units"] == Decimal("1") for h in portfolio["holdings"])
    assert all(h["lot_id"] is not None for h in portfolio["holdings"])
    assert len({h["lot_id"] for h in portfolio["holdings"]}) == 2


async def test_sell_lot_partial_credits_cash_and_reduces_units(db_session, family, seeded_asset):
    kid = await _make_kid(db_session, family)
    await _fund(db_session, kid, "1000")
    await investing_service.buy(db_session, kid, "USD", "TEST", Decimal("3"))
    lot_id = await _only_lot_id(db_session, kid)

    await investing_service.sell(db_session, kid, "USD", lot_id=lot_id, units=Decimal("1"))

    portfolio = await investing_service.get_portfolio(db_session, kid, "USD")
    assert portfolio["holdings"][0]["units"] == Decimal("2")
    # 1000 - 300 (buy 3) + 100 (sell 1, no ticks yet so still $100/unit) = 800
    assert await debts_db_service.get_balance(db_session, kid.id) == Decimal("800")


async def test_selling_entire_lot_removes_it(db_session, family, seeded_asset):
    kid = await _make_kid(db_session, family)
    await _fund(db_session, kid, "1000")
    await investing_service.buy(db_session, kid, "USD", "TEST", Decimal("1"))
    lot_id = await _only_lot_id(db_session, kid)

    await investing_service.sell(db_session, kid, "USD", lot_id=lot_id, units=Decimal("1"))

    portfolio = await investing_service.get_portfolio(db_session, kid, "USD")
    assert portfolio["holdings"] == []

    lot = await db_session.get(InvestmentLot, lot_id)
    assert lot.is_open is False
    assert lot.sold_at is not None


async def test_sell_lot_rejects_more_than_held(db_session, family, seeded_asset):
    kid = await _make_kid(db_session, family)
    await _fund(db_session, kid, "1000")
    await investing_service.buy(db_session, kid, "USD", "TEST", Decimal("1"))
    lot_id = await _only_lot_id(db_session, kid)

    with pytest.raises(investing_service.InvestingError, match="Cannot sell"):
        await investing_service.sell(db_session, kid, "USD", lot_id=lot_id, units=Decimal("2"))


async def test_buy_locks_in_family_boost_buffer_rate_on_the_lot(db_session, family, seeded_asset):
    kid = await _make_kid(db_session, family)
    await _fund(db_session, kid, "1000")
    await investing_service.buy(
        db_session, kid, "USD", "TEST", Decimal("1"), boost_buffer_rate=Decimal("3.000")
    )

    lot = await db_session.scalar(select(InvestmentLot).where(InvestmentLot.kid_id == kid.id))
    assert lot.buffer_rate == Decimal("3.000")

    # Buying again with no rate passed (boost off) must not retroactively
    # touch the first lot's already-locked rate.
    await investing_service.buy(db_session, kid, "USD", "TEST", Decimal("1"), boost_buffer_rate=None)
    lots = list(await db_session.scalars(select(InvestmentLot).where(InvestmentLot.kid_id == kid.id)))
    rates = {lot.buffer_rate for lot in lots}
    assert rates == {Decimal("3.000"), None}


async def test_sell_rejects_more_than_held(db_session, family, seeded_asset):
    kid = await _make_kid(db_session, family)
    await _fund(db_session, kid, "1000")
    await investing_service.buy(db_session, kid, "USD", "TEST", Decimal("1"))

    with pytest.raises(investing_service.InvestingError, match="Cannot sell"):
        await investing_service.sell(db_session, kid, "USD", "TEST", Decimal("2"))


async def test_sell_with_no_holding_rejected(db_session, family, seeded_asset):
    kid = await _make_kid(db_session, family)
    with pytest.raises(investing_service.InvestingError, match="Cannot sell"):
        await investing_service.sell(db_session, kid, "USD", "TEST", Decimal("1"))


async def test_quote_purchase_amount_mode_computes_units(db_session, family, seeded_asset):
    kid = await _make_kid(db_session, family)
    await _fund(db_session, kid, "1000")
    quote = await investing_service.quote_purchase(db_session, kid, "USD", "TEST", Decimal("50"), None)
    assert quote["units"] == Decimal("0.5")  # $50 / $100 per unit
    assert quote["cash_available_after"] == Decimal("950")


async def test_quote_purchase_units_mode_computes_cost(db_session, family, seeded_asset):
    kid = await _make_kid(db_session, family)
    await _fund(db_session, kid, "1000")
    quote = await investing_service.quote_purchase(db_session, kid, "USD", "TEST", None, Decimal("2"))
    assert quote["cost"] == Decimal("200")


def test_unit_step_for_price_targets_1_to_10_range():
    assert investing_service.unit_step_for_price(Decimal("2000")) == Decimal("0.001")
    assert investing_service.unit_step_for_price(Decimal("789")) == Decimal("0.01")
    assert investing_service.unit_step_for_price(Decimal("5")) == Decimal("1")
    assert investing_service.unit_step_for_price(Decimal("0.5")) == Decimal("10")


def test_round_to_step_snaps_to_nearest_multiple():
    assert investing_service.round_to_step(Decimal("0.019011"), Decimal("0.01")) == Decimal("0.02")
    assert investing_service.round_to_step(Decimal("0.014"), Decimal("0.01")) == Decimal("0.01")
    assert investing_service.round_to_step(Decimal("0"), Decimal("0.01")) == Decimal("0.01")  # never zero


async def test_quote_purchase_snaps_amount_to_unit_step_and_recomputes_real_cost(db_session, family):
    """The exact bug reported: requesting "$15 of a stock" must not
    silently produce an arbitrary fractional unit count that costs
    exactly $15 — it should snap to the asset's real tradable step (0.02
    units here, not 0.019) and report what that actually costs (which
    is *not* the original $15)."""
    from datetime import datetime, timezone

    from app.models.catalog import AssetCatalog, PriceCache

    asset = AssetCatalog(symbol="EXPENSIVE", display_name="Expensive Co", kind=AssetKind.STOCK, description="")
    db_session.add(asset)
    db_session.add(
        PriceCache(
            symbol="EXPENSIVE", price=Decimal("789.00"), currency="USD",
            updated_at=datetime.now(timezone.utc), history_json=[],
        )
    )
    await db_session.flush()

    kid = await _make_kid(db_session, family)
    await _fund(db_session, kid, "1000")

    quote = await investing_service.quote_purchase(db_session, kid, "USD", "EXPENSIVE", Decimal("15"), None)
    assert quote["units"] == Decimal("0.02")
    assert quote["cost"] == Decimal("15.78")
    assert quote["cost"] != Decimal("15")


async def test_day_change_pct_computed_from_lot_ticks(db_session, family, seeded_asset):
    """A lot's day_change_pct comes from its own boosted-series' last two
    points (boost_service), not PriceCache's history_json sparkline —
    since_purchase_pct/get_portfolio no longer read live PriceCache at
    all for a lot (see boost_service's module docstring)."""
    kid = await _make_kid(db_session, family)
    await _fund(db_session, kid, "1000")
    await investing_service.buy(db_session, kid, "USD", "TEST", Decimal("1"))  # bought at $100
    now = datetime.now(timezone.utc)  # comfortably after purchased_at

    await _add_tick(db_session, "TEST", "90", now + timedelta(seconds=1))
    await _add_tick(db_session, "TEST", "100", now + timedelta(hours=5))  # +11.11% vs the previous tick

    portfolio = await investing_service.get_portfolio(db_session, kid, "USD")
    pct = portfolio["holdings"][0]["day_change_pct"]
    assert pct is not None
    assert round(pct, 2) == Decimal("11.11")


async def test_since_purchase_pct_reflects_total_return_not_last_tick_change(db_session, family, seeded_asset):
    kid = await _make_kid(db_session, family)
    await _fund(db_session, kid, "1000")
    await investing_service.buy(db_session, kid, "USD", "TEST", Decimal("1"))  # bought at $100
    now = datetime.now(timezone.utc)  # comfortably after purchased_at

    await _add_tick(db_session, "TEST", "150", now + timedelta(seconds=1))  # real price rises to $150

    portfolio = await investing_service.get_portfolio(db_session, kid, "USD")
    since_purchase = portfolio["holdings"][0]["since_purchase_pct"]
    assert round(since_purchase, 2) == Decimal("50.00")  # (150-100)/100 * 100


async def test_list_catalog_orders_baskets_before_stocks(db_session, family, seeded_asset, seeded_basket):
    ctx = await investing_service.load_price_context(db_session)
    rows = investing_service.list_catalog(ctx, "USD")
    kinds = [r["kind"] for r in rows]
    first_stock_index = kinds.index(AssetKind.STOCK)
    last_basket_index = len(kinds) - 1 - kinds[::-1].index(AssetKind.BASKET)
    assert last_basket_index < first_stock_index


async def test_portfolio_survives_missing_fx_rate(db_session, family):
    """A holding priced in a currency with no cached rate to the family's
    currency must be skipped, not crash the whole portfolio (see the
    EUR->ILS incident this regression-tests)."""
    from datetime import datetime, timezone

    from app.models.catalog import AssetCatalog, PriceCache

    # "ZZZ" is not a real currency, so it's guaranteed to have no cached
    # rate — unlike EUR/USD/ILS, which the real scheduler already
    # populates in this shared dev database, so asserting their *absence*
    # would be flaky.
    asset = AssetCatalog(symbol="ZZZASSET", display_name="Fake Currency Thing", kind=AssetKind.STOCK, description="")
    db_session.add(asset)
    db_session.add(
        PriceCache(
            symbol="ZZZASSET", price=Decimal("10"), currency="ZZZ", updated_at=datetime.now(timezone.utc),
            history_json=[],
        )
    )
    await db_session.flush()

    kid = await _make_kid(db_session, family)
    from app.models.investment import InvestmentHolding

    db_session.add(
        InvestmentHolding(kid_id=kid.id, symbol="ZZZASSET", units=Decimal("1"), avg_cost=Decimal("10"), avg_cost_currency="ZZZ")
    )
    await db_session.flush()

    portfolio = await investing_service.get_portfolio(db_session, kid, "USD")
    assert portfolio["holdings"] == []
    assert portfolio["total_value"] == Decimal("0.00")


async def test_list_investment_transactions_orders_most_recent_first(db_session, family, seeded_asset):
    from datetime import datetime, timedelta, timezone

    from app.models.investment import InvestmentTransaction, InvestmentTransactionType

    kid = await _make_kid(db_session, family)
    now = datetime.now(timezone.utc)
    # Explicit, distinct timestamps — real created_at values come from
    # separate HTTP requests/transactions in production and are never
    # tied, but asserting that here would depend on wall-clock timing.
    older = InvestmentTransaction(
        kid_id=kid.id, symbol="TEST", units=Decimal("1"), price=Decimal("100"), price_currency="USD",
        type=InvestmentTransactionType.BUY, created_at=now - timedelta(minutes=5),
    )
    newer = InvestmentTransaction(
        kid_id=kid.id, symbol="TEST", units=Decimal("1"), price=Decimal("100"), price_currency="USD",
        type=InvestmentTransactionType.SELL, created_at=now,
    )
    db_session.add_all([older, newer])
    await db_session.flush()

    rows = await investing_service.list_investment_transactions(db_session, kid.id)
    assert [r.id for r in rows] == [newer.id, older.id]


async def test_get_lot_detail_returns_series_matching_the_headline_value(db_session, family, seeded_asset):
    """The same walk backs both the number and the graph — see
    investing_service.get_lot_detail's docstring — so this asserts they
    can never disagree with each other."""
    kid = await _make_kid(db_session, family)
    await _fund(db_session, kid, "1000")
    await investing_service.buy(db_session, kid, "USD", "TEST", Decimal("2"))
    lot_id = await _only_lot_id(db_session, kid)
    now = datetime.now(timezone.utc)
    await _add_tick(db_session, "TEST", "120", now + timedelta(seconds=1))

    detail = await investing_service.get_lot_detail(db_session, kid, lot_id)
    assert detail is not None
    assert detail["symbol"] == "TEST"
    assert detail["description"] == "A test stock."
    assert detail["units"] == Decimal("2")
    assert detail["is_open"] is True
    assert round(detail["since_purchase_pct"], 2) == Decimal("20.00")
    assert len(detail["series"]) == 2
    assert detail["series"][-1]["value"] == detail["current_value"]


async def test_get_lot_detail_returns_none_for_another_kids_lot(db_session, family, seeded_asset):
    kid = await _make_kid(db_session, family)
    other_kid = await _make_kid(db_session, family, name="Other")
    await _fund(db_session, kid, "1000")
    await investing_service.buy(db_session, kid, "USD", "TEST", Decimal("1"))
    lot_id = await _only_lot_id(db_session, kid)

    assert await investing_service.get_lot_detail(db_session, other_kid, lot_id) is None


async def test_sell_all_closes_every_open_lot_and_legacy_holding(db_session, family, seeded_asset):
    from app.models.investment import InvestmentHolding

    kid = await _make_kid(db_session, family)
    await _fund(db_session, kid, "1000")
    # Two separate lots of the same symbol (never merged — see buy()'s
    # docstring) plus one pre-existing legacy avg-cost holding.
    await investing_service.buy(db_session, kid, "USD", "TEST", Decimal("1"))
    await investing_service.buy(db_session, kid, "USD", "TEST", Decimal("1"))
    db_session.add(
        InvestmentHolding(
            kid_id=kid.id, symbol="TEST", units=Decimal("1"), avg_cost=Decimal("100"), avg_cost_currency="USD"
        )
    )
    await db_session.flush()

    balance_before = await debts_db_service.get_balance(db_session, kid.id)
    txns = await investing_service.sell_all(db_session, kid, "USD")

    assert len(txns) == 3
    portfolio = await investing_service.get_portfolio(db_session, kid, "USD")
    assert portfolio["holdings"] == []
    # 3 units sold at $100 each ($100 real price, no boost since none was set).
    assert await debts_db_service.get_balance(db_session, kid.id) == balance_before + Decimal("300")


async def test_sell_all_is_a_no_op_for_a_kid_with_nothing(db_session, family):
    kid = await _make_kid(db_session, family)
    txns = await investing_service.sell_all(db_session, kid, "USD")
    assert txns == []


async def test_price_context_is_cached_across_calls(db_session, seeded_asset):
    ctx1 = await investing_service.load_price_context(db_session)
    assert "TEST" in ctx1.catalog

    # A second asset added after the first load shouldn't appear until
    # the cache is cleared — proves it's actually reusing the cached
    # object instead of re-querying every time.
    from app.models.catalog import AssetCatalog

    db_session.add(AssetCatalog(symbol="LATE", display_name="Late Co", kind=AssetKind.STOCK, description=""))
    await db_session.flush()

    ctx2 = await investing_service.load_price_context(db_session)
    assert ctx2 is ctx1  # same cached instance
    assert "LATE" not in ctx2.catalog

    investing_service.clear_price_context_cache()
    ctx3 = await investing_service.load_price_context(db_session)
    assert ctx3 is not ctx1
    assert "LATE" in ctx3.catalog
