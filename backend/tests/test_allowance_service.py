"""allowance_service unit tests — the schedule math and the lazy
settle-on-read payout loop (no cron)."""

from datetime import datetime, timedelta, timezone
from decimal import Decimal

import pytest

from app.models.allowance import Allowance, AllowanceCadence
from app.models.kid import Kid
from app.services import allowance_service, debts_db_service, fx_service
from app.services.debts_db_service import DebtTransactionType


async def _kid(db_session, family, name="Kid") -> Kid:
    kid = Kid(family_id=family.id, name=name, avatar_color="amber")
    db_session.add(kid)
    await db_session.flush()
    return kid


# --- schedule math ---------------------------------------------------

def test_weekly_first_run_is_the_next_matching_weekday_in_the_future():
    # A Thursday (weekday 3), 14:00
    now = datetime(2026, 9, 10, 14, 0, tzinfo=timezone.utc)
    # Next Monday (0)
    nxt = allowance_service.first_run_at(now, AllowanceCadence.WEEKLY, 0)
    assert nxt == datetime(2026, 9, 14, 0, 0, tzinfo=timezone.utc)
    assert nxt.weekday() == 0


def test_weekly_first_run_when_today_is_payday_skips_to_next_week():
    now = datetime(2026, 9, 10, 14, 0, tzinfo=timezone.utc)  # Thursday
    nxt = allowance_service.first_run_at(now, AllowanceCadence.WEEKLY, 3)
    assert nxt == datetime(2026, 9, 17, 0, 0, tzinfo=timezone.utc)


def test_monthly_first_run_picks_this_month_or_next():
    now = datetime(2026, 9, 10, 14, 0, tzinfo=timezone.utc)
    assert allowance_service.first_run_at(now, AllowanceCadence.MONTHLY, 15) == datetime(
        2026, 9, 15, 0, 0, tzinfo=timezone.utc
    )
    # payday already passed this month → next month
    assert allowance_service.first_run_at(now, AllowanceCadence.MONTHLY, 5) == datetime(
        2026, 10, 5, 0, 0, tzinfo=timezone.utc
    )


def test_monthly_advance_across_year_boundary():
    dec = datetime(2026, 12, 5, 0, 0, tzinfo=timezone.utc)
    assert allowance_service._advance(dec, AllowanceCadence.MONTHLY) == datetime(
        2027, 1, 5, 0, 0, tzinfo=timezone.utc
    )


def test_validate_payday_rejects_out_of_range():
    with pytest.raises(allowance_service.AllowanceError):
        allowance_service.validate_payday(AllowanceCadence.WEEKLY, 9)
    with pytest.raises(allowance_service.AllowanceError):
        allowance_service.validate_payday(AllowanceCadence.MONTHLY, 0)


# --- settle_due ----------------------------------------------------

async def test_new_allowance_does_not_pay_immediately(db_session, family):
    kid = await _kid(db_session, family)
    await allowance_service.upsert_allowance(
        db_session, kid, family, amount=Decimal("10"), cadence=AllowanceCadence.WEEKLY,
        payday=0,
    )
    paid = await allowance_service.settle_due(db_session, kid, family.base_currency)
    assert paid == 0
    assert await debts_db_service.get_balance(db_session, kid.id) == Decimal("0.00")


async def test_settle_pays_each_missed_period_and_advances(db_session, family):
    kid = await _kid(db_session, family)
    allowance = await allowance_service.upsert_allowance(
        db_session, kid, family, amount=Decimal("10"), cadence=AllowanceCadence.WEEKLY,
        payday=0,
    )
    # Pretend 3 weekly paydays have passed.
    allowance.next_run_at = datetime.now(timezone.utc) - timedelta(days=15)
    await db_session.flush()

    paid = await allowance_service.settle_due(db_session, kid, family.base_currency)
    assert paid == 3
    assert await debts_db_service.get_balance(db_session, kid.id) == Decimal("30.00")
    assert allowance.next_run_at > datetime.now(timezone.utc)
    assert allowance.last_paid_at is not None

    rows = await debts_db_service.list_transactions(db_session, kid.id)
    assert all(r.is_allowance and r.note == "Weekly allowance" and r.type == DebtTransactionType.ADD for r in rows)


async def test_settle_is_idempotent_within_a_period(db_session, family):
    kid = await _kid(db_session, family)
    allowance = await allowance_service.upsert_allowance(
        db_session, kid, family, amount=Decimal("10"), cadence=AllowanceCadence.WEEKLY,
        payday=0,
    )
    allowance.next_run_at = datetime.now(timezone.utc) - timedelta(days=1)
    await db_session.flush()

    assert await allowance_service.settle_due(db_session, kid, family.base_currency) == 1
    assert await allowance_service.settle_due(db_session, kid, family.base_currency) == 0
    assert await debts_db_service.get_balance(db_session, kid.id) == Decimal("10.00")


async def test_settle_skips_an_inactive_row(db_session, family):
    # The UI has no "pause" — an allowance is created or removed — but the
    # `is_active` guard stays as defence in case a row is ever flagged off.
    kid = await _kid(db_session, family)
    allowance = await allowance_service.upsert_allowance(
        db_session, kid, family, amount=Decimal("10"), cadence=AllowanceCadence.WEEKLY,
        payday=0,
    )
    allowance.is_active = False
    allowance.next_run_at = datetime.now(timezone.utc) - timedelta(days=30)
    await db_session.flush()
    assert await allowance_service.settle_due(db_session, kid, family.base_currency) == 0
    assert await debts_db_service.get_balance(db_session, kid.id) == Decimal("0.00")


async def test_long_gap_is_capped_not_dumped(db_session, family):
    kid = await _kid(db_session, family)
    allowance = await allowance_service.upsert_allowance(
        db_session, kid, family, amount=Decimal("5"), cadence=AllowanceCadence.WEEKLY,
        payday=0,
    )
    # 5 years of unsettled weekly paydays.
    allowance.next_run_at = datetime.now(timezone.utc) - timedelta(days=365 * 5)
    await db_session.flush()

    paid = await allowance_service.settle_due(db_session, kid, family.base_currency)
    assert paid == allowance_service.MAX_CATCHUP_PERIODS
    assert allowance.next_run_at > datetime.now(timezone.utc)


async def test_amount_edit_keeps_the_existing_next_payday(db_session, family):
    kid = await _kid(db_session, family)
    a1 = await allowance_service.upsert_allowance(
        db_session, kid, family, amount=Decimal("10"), cadence=AllowanceCadence.MONTHLY,
        payday=15,
    )
    original = a1.next_run_at
    a2 = await allowance_service.upsert_allowance(
        db_session, kid, family, amount=Decimal("25"), cadence=AllowanceCadence.MONTHLY,
        payday=15,
    )
    assert a2.next_run_at == original
    assert a2.amount == Decimal("25.00")


async def test_cadence_change_reanchors_the_schedule(db_session, family):
    kid = await _kid(db_session, family)
    a1 = await allowance_service.upsert_allowance(
        db_session, kid, family, amount=Decimal("10"), cadence=AllowanceCadence.MONTHLY,
        payday=15,
    )
    original = a1.next_run_at
    a2 = await allowance_service.upsert_allowance(
        db_session, kid, family, amount=Decimal("10"), cadence=AllowanceCadence.WEEKLY,
        payday=2,
    )
    assert a2.next_run_at != original
    assert a2.cadence == AllowanceCadence.WEEKLY


async def test_payout_converts_from_set_time_currency(db_session, family):
    """Amount is stored in the currency it was set in; a later family
    currency change is handled by converting at payout, not by rewriting
    the allowance."""
    kid = await _kid(db_session, family)  # family is USD
    allowance = await allowance_service.upsert_allowance(
        db_session, kid, family, amount=Decimal("10"), cadence=AllowanceCadence.WEEKLY,
        payday=0,
    )
    allowance.next_run_at = datetime.now(timezone.utc) - timedelta(days=1)
    await db_session.flush()

    # Cache a USD→EUR rate and settle against a EUR family currency.
    await fx_service.write_fx_rates(
        db_session, [("USD", "EUR", Decimal("0.90"))], datetime.now(timezone.utc)
    )
    paid = await allowance_service.settle_due(db_session, kid, "EUR")
    assert paid == 1
    assert await debts_db_service.get_balance(db_session, kid.id) == Decimal("9.00")
