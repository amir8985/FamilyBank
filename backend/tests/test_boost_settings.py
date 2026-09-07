"""Family.boost_buffer_rate can only be set/changed while every kid in
the family holds zero stock — legacy avg-cost holdings or open lots
alike. This is what guarantees every lot open at any given moment shares
the exact same rate (see models/family.py's docstring) — deliberately no
mid-holding rate change to reason about."""

from decimal import Decimal

from app.models.investment import InvestmentHolding
from app.models.kid import Kid
from app.services import debts_db_service, investing_service
from app.services.debts_db_service import DebtTransactionType


async def _make_kid(db_session, family, name="Kid") -> Kid:
    kid = Kid(family_id=family.id, name=name, avatar_color="amber")
    db_session.add(kid)
    await db_session.flush()
    return kid


async def test_can_set_boost_when_no_kid_holds_anything(client, auth_headers, family, db_session):
    await _make_kid(db_session, family)

    resp = await client.patch("/family/settings/boost-buffer-rate", headers=auth_headers, json={"rate": 3.0})
    assert resp.status_code == 200
    assert Decimal(resp.json()["boost_buffer_rate"]) == Decimal("3.0")


async def test_cannot_set_boost_while_a_kid_holds_an_open_lot(
    client, auth_headers, family, db_session, seeded_asset
):
    kid = await _make_kid(db_session, family)
    await debts_db_service.record_transaction(db_session, kid.id, DebtTransactionType.ADD, Decimal("1000"))
    await investing_service.buy(db_session, kid, "USD", "TEST", Decimal("1"))
    await db_session.commit()

    resp = await client.patch("/family/settings/boost-buffer-rate", headers=auth_headers, json={"rate": 3.0})
    assert resp.status_code == 409


async def test_cannot_set_boost_while_a_kid_holds_a_legacy_avg_cost_holding(
    client, auth_headers, family, db_session, seeded_asset
):
    kid = await _make_kid(db_session, family)
    db_session.add(
        InvestmentHolding(
            kid_id=kid.id, symbol="TEST", units=Decimal("1"), avg_cost=Decimal("100"), avg_cost_currency="USD"
        )
    )
    await db_session.commit()

    resp = await client.patch("/family/settings/boost-buffer-rate", headers=auth_headers, json={"rate": 3.0})
    assert resp.status_code == 409


async def test_can_change_boost_once_every_kid_has_sold_everything(
    client, auth_headers, family, db_session, seeded_asset
):
    kid = await _make_kid(db_session, family)
    await debts_db_service.record_transaction(db_session, kid.id, DebtTransactionType.ADD, Decimal("1000"))
    txn = await investing_service.buy(db_session, kid, "USD", "TEST", Decimal("1"))
    await db_session.commit()

    from sqlalchemy import select

    from app.models.investment import InvestmentLot

    lot = await db_session.scalar(select(InvestmentLot).where(InvestmentLot.kid_id == kid.id))
    await investing_service.sell(db_session, kid, "USD", lot_id=lot.id, units=Decimal("1"))
    await db_session.commit()

    resp = await client.patch("/family/settings/boost-buffer-rate", headers=auth_headers, json={"rate": 3.0})
    assert resp.status_code == 200


async def test_turning_boost_off_is_also_gated_by_open_positions(
    client, auth_headers, family, db_session, seeded_asset
):
    kid = await _make_kid(db_session, family)
    # Set the boost on first, while nothing is held — same guard applies
    # either direction.
    setup = await client.patch("/family/settings/boost-buffer-rate", headers=auth_headers, json={"rate": 3.0})
    assert setup.status_code == 200

    await debts_db_service.record_transaction(db_session, kid.id, DebtTransactionType.ADD, Decimal("1000"))
    await investing_service.buy(db_session, kid, "USD", "TEST", Decimal("1"), boost_buffer_rate=Decimal("3.0"))
    await db_session.commit()

    resp = await client.patch("/family/settings/boost-buffer-rate", headers=auth_headers, json={"rate": None})
    assert resp.status_code == 409


async def test_sell_and_rebuy_changes_rate_and_replaces_the_holding(
    client, auth_headers, family, db_session, seeded_asset
):
    kid = await _make_kid(db_session, family)
    await debts_db_service.record_transaction(db_session, kid.id, DebtTransactionType.ADD, Decimal("1000"))
    await investing_service.buy(db_session, kid, "USD", "TEST", Decimal("2"), boost_buffer_rate=Decimal("3.0"))
    await db_session.commit()
    cash_before = await debts_db_service.get_balance(db_session, kid.id)

    resp = await client.post(
        "/family/settings/boost-buffer-rate/sell-and-rebuy", headers=auth_headers, json={"rate": 5.0}
    )
    assert resp.status_code == 200
    assert Decimal(resp.json()["boost_buffer_rate"]) == Decimal("5.0")

    portfolio = await investing_service.get_portfolio(db_session, kid, "USD")
    assert len(portfolio["holdings"]) == 1
    assert portfolio["holdings"][0]["units"] == Decimal("2")
    assert portfolio["holdings"][0]["is_boosted"] is True

    from sqlalchemy import select

    from app.models.investment import InvestmentLot

    new_lot = await db_session.scalar(
        select(InvestmentLot).where(InvestmentLot.kid_id == kid.id, InvestmentLot.is_open)
    )
    assert new_lot.buffer_rate == Decimal("5.000")

    # Sold at $100/unit, immediately rebought 2 units at the same $100 —
    # cash should net back out to (about) what it started at.
    cash_after = await debts_db_service.get_balance(db_session, kid.id)
    assert cash_after == cash_before


async def test_sell_and_rebuy_covers_every_kid_and_every_position_type(
    client, auth_headers, family, db_session, seeded_asset
):
    kid_a = await _make_kid(db_session, family, name="A")
    kid_b = await _make_kid(db_session, family, name="B")
    await debts_db_service.record_transaction(db_session, kid_a.id, DebtTransactionType.ADD, Decimal("1000"))
    await debts_db_service.record_transaction(db_session, kid_b.id, DebtTransactionType.ADD, Decimal("1000"))

    # kid_a: an open lot. kid_b: a pre-lot legacy avg-cost holding.
    await investing_service.buy(db_session, kid_a, "USD", "TEST", Decimal("1"))
    db_session.add(
        InvestmentHolding(
            kid_id=kid_b.id, symbol="TEST", units=Decimal("1"), avg_cost=Decimal("100"), avg_cost_currency="USD"
        )
    )
    await db_session.commit()

    resp = await client.post(
        "/family/settings/boost-buffer-rate/sell-and-rebuy", headers=auth_headers, json={"rate": 4.0}
    )
    assert resp.status_code == 200

    portfolio_a = await investing_service.get_portfolio(db_session, kid_a, "USD")
    portfolio_b = await investing_service.get_portfolio(db_session, kid_b, "USD")
    assert portfolio_a["holdings"][0]["units"] == Decimal("1")
    assert portfolio_a["holdings"][0]["is_boosted"] is True
    # kid_b's legacy holding was sold and rebought as a brand-new,
    # boosted lot — it's not a legacy holding anymore.
    assert portfolio_b["holdings"][0]["units"] == Decimal("1")
    assert portfolio_b["holdings"][0]["is_boosted"] is True
    assert portfolio_b["holdings"][0]["lot_id"] is not None


async def test_sell_and_rebuy_to_no_boost_turns_it_off(client, auth_headers, family, db_session, seeded_asset):
    kid = await _make_kid(db_session, family)
    # Set the family's rate for real first (not just pass one straight to
    # buy()) — otherwise family.boost_buffer_rate stays None, and the
    # endpoint's "rate == family.boost_buffer_rate" no-op check below
    # would short-circuit before doing anything, since None == None.
    setup = await client.patch("/family/settings/boost-buffer-rate", headers=auth_headers, json={"rate": 3.0})
    assert setup.status_code == 200
    await debts_db_service.record_transaction(db_session, kid.id, DebtTransactionType.ADD, Decimal("1000"))
    await investing_service.buy(db_session, kid, "USD", "TEST", Decimal("1"), boost_buffer_rate=Decimal("3.0"))
    await db_session.commit()

    resp = await client.post(
        "/family/settings/boost-buffer-rate/sell-and-rebuy", headers=auth_headers, json={"rate": None}
    )
    assert resp.status_code == 200
    assert resp.json()["boost_buffer_rate"] is None

    portfolio = await investing_service.get_portfolio(db_session, kid, "USD")
    assert portfolio["holdings"][0]["units"] == Decimal("1")
    assert portfolio["holdings"][0]["is_boosted"] is False
