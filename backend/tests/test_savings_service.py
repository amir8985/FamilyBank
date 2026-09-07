"""savings_service is a stateless recompute like boost_service — a
deposit's value comes from principal + monthly_rate + opened_at, never a
stored running total. The rate/term are snapshotted onto the deposit at
creation so a later edit or delete of the parent's plan never changes
money already in it (see the model docstrings / CLAUDE.md)."""

from datetime import datetime, timedelta, timezone
from decimal import Decimal

import pytest

from app.models.kid import Kid
from app.models.savings import SavingsDeposit, SavingsPlan
from app.services import debts_db_service, savings_service
from app.services.debts_db_service import DebtTransactionType

T0 = datetime(2026, 1, 1, tzinfo=timezone.utc)


async def _kid(db_session, family, name="Kid") -> Kid:
    kid = Kid(family_id=family.id, name=name, avatar_color="amber")
    db_session.add(kid)
    await db_session.flush()
    return kid


async def _plan(db_session, family, *, rate="1.0", lock_months=0, name="Plan") -> SavingsPlan:
    plan = SavingsPlan(
        family_id=family.id, name=name, monthly_rate=Decimal(rate), lock_months=lock_months
    )
    db_session.add(plan)
    await db_session.flush()
    return plan


def test_annual_rate_compounds_not_a_naive_times_twelve():
    # 2%/month compounded is ~26.8%/year, definitely not 24%.
    assert savings_service.annual_rate(Decimal("2")) == Decimal("26.8")
    assert savings_service.annual_rate(Decimal("0")) == Decimal("0.0")


def test_value_at_is_principal_before_any_time_passes():
    assert savings_service._value_at(Decimal("100"), Decimal("5"), T0, T0) == Decimal("100")
    assert savings_service._value_at(Decimal("100"), Decimal("5"), T0, T0 - timedelta(days=1)) == Decimal("100")


def test_value_at_compounds_one_month_at_the_monthly_rate():
    one_month = T0 + timedelta(days=float(savings_service.DAYS_PER_MONTH))
    value = savings_service._value_at(Decimal("100"), Decimal("10"), T0, one_month)
    assert value == pytest.approx(Decimal("110"), abs=Decimal("0.01"))


async def test_create_deposit_moves_cash_out_of_the_ledger(db_session, family):
    kid = await _kid(db_session, family)
    await debts_db_service.record_transaction(db_session, kid.id, DebtTransactionType.ADD, Decimal("200"))
    plan = await _plan(db_session, family, rate="1.5")

    deposit = await savings_service.create_deposit(db_session, kid, plan, Decimal("50"), "USD")

    assert deposit.principal == Decimal("50.00")
    assert deposit.monthly_rate == Decimal("1.500")
    assert deposit.matures_at is None  # flexible
    assert await debts_db_service.get_balance(db_session, kid.id) == Decimal("150.00")


async def test_create_deposit_rejects_more_than_available_cash(db_session, family):
    kid = await _kid(db_session, family)
    await debts_db_service.record_transaction(db_session, kid.id, DebtTransactionType.ADD, Decimal("30"))
    plan = await _plan(db_session, family)

    with pytest.raises(savings_service.SavingsError):
        await savings_service.create_deposit(db_session, kid, plan, Decimal("50"), "USD")


async def test_create_deposit_rejects_an_inactive_plan(db_session, family):
    kid = await _kid(db_session, family)
    await debts_db_service.record_transaction(db_session, kid.id, DebtTransactionType.ADD, Decimal("100"))
    plan = await _plan(db_session, family)
    plan.is_active = False
    await db_session.flush()

    with pytest.raises(savings_service.SavingsError):
        await savings_service.create_deposit(db_session, kid, plan, Decimal("10"), "USD")


async def test_locked_deposit_cannot_be_withdrawn_before_it_matures(db_session, family):
    kid = await _kid(db_session, family)
    await debts_db_service.record_transaction(db_session, kid.id, DebtTransactionType.ADD, Decimal("100"))
    plan = await _plan(db_session, family, rate="2.0", lock_months=6)
    deposit = await savings_service.create_deposit(db_session, kid, plan, Decimal("100"), "USD")
    assert deposit.matures_at is not None

    with pytest.raises(savings_service.SavingsError):
        await savings_service.withdraw_deposit(db_session, kid, deposit.id, "USD")


async def test_matured_locked_deposit_pays_principal_plus_interest_back_to_cash(db_session, family):
    kid = await _kid(db_session, family)
    await debts_db_service.record_transaction(db_session, kid.id, DebtTransactionType.ADD, Decimal("100"))
    plan = await _plan(db_session, family, rate="10.0", lock_months=1)
    deposit = await savings_service.create_deposit(db_session, kid, plan, Decimal("100"), "USD")

    # Backdate so it's a month old and already matured — same effect as
    # waiting, without the wait.
    deposit.opened_at = datetime.now(timezone.utc) - timedelta(days=float(savings_service.DAYS_PER_MONTH))
    deposit.matures_at = datetime.now(timezone.utc) - timedelta(seconds=1)
    await db_session.flush()

    await savings_service.withdraw_deposit(db_session, kid, deposit.id, "USD")

    assert deposit.is_open is False
    assert deposit.close_value is not None
    balance = await debts_db_service.get_balance(db_session, kid.id)
    # ~10% earned on the $100 principal over one month.
    assert balance == pytest.approx(Decimal("110"), abs=Decimal("0.05"))


async def test_flexible_deposit_withdraws_any_time(db_session, family):
    kid = await _kid(db_session, family)
    await debts_db_service.record_transaction(db_session, kid.id, DebtTransactionType.ADD, Decimal("100"))
    plan = await _plan(db_session, family, rate="1.0", lock_months=0)
    deposit = await savings_service.create_deposit(db_session, kid, plan, Decimal("40"), "USD")

    await savings_service.withdraw_deposit(db_session, kid, deposit.id, "USD")
    assert deposit.is_open is False
    assert await debts_db_service.get_balance(db_session, kid.id) == pytest.approx(
        Decimal("100"), abs=Decimal("0.05")
    )


async def test_deposit_terms_survive_a_later_plan_edit(db_session, family):
    kid = await _kid(db_session, family)
    await debts_db_service.record_transaction(db_session, kid.id, DebtTransactionType.ADD, Decimal("100"))
    plan = await _plan(db_session, family, rate="1.0", lock_months=0)
    deposit = await savings_service.create_deposit(db_session, kid, plan, Decimal("50"), "USD")

    plan.monthly_rate = Decimal("9.9")
    plan.lock_months = 24
    await db_session.flush()

    fresh = await db_session.get(SavingsDeposit, deposit.id)
    assert fresh.monthly_rate == Decimal("1.000")
    assert fresh.lock_months == 0


async def test_portfolio_savings_value_reflects_open_deposits(db_session, family, seeded_asset):
    from app.services import investing_service

    kid = await _kid(db_session, family)
    await debts_db_service.record_transaction(db_session, kid.id, DebtTransactionType.ADD, Decimal("500"))
    plan = await _plan(db_session, family, rate="1.0")
    await savings_service.create_deposit(db_session, kid, plan, Decimal("120"), "USD")
    await db_session.commit()

    portfolio = await investing_service.get_portfolio(db_session, kid, "USD")
    assert portfolio["savings_value"] >= Decimal("120.00")
    assert portfolio["cash_available"] == Decimal("380.00")
