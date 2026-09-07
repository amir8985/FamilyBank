"""Savings plans — a kid moves cash into a parent-defined plan and it
compounds at a fixed monthly rate.

Like boost_service, this holds no per-deposit running total: a deposit's
current value is recomputed from principal + rate + opened_at on every
read. Interest only ever grows (no down-ticks to worry about), so the
math is a plain compounding curve rather than a tick walk.

A deposit is never partially withdrawn — withdraw_deposit closes the
whole thing and pays principal + accrued interest back to the cash
ledger. Locked deposits (lock_months > 0) can't be withdrawn until
matures_at; after that they keep compounding at the same rate until the
kid withdraws.
"""

import uuid
from datetime import datetime, timedelta, timezone
from decimal import ROUND_HALF_UP, Decimal

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.debt_transaction import DebtTransactionType
from app.models.kid import Kid
from app.models.savings import SavingsDeposit, SavingsPlan
from app.services import debts_db_service, fx_service

# Same average-month length boost_service uses (365.25 / 12) — the rate
# is quoted per month, so both the maturity date and the daily
# compounding need a concrete month length to prorate against.
DAYS_PER_MONTH = Decimal("30.4375")

_CENTS = Decimal("0.01")


class SavingsError(ValueError):
    pass


def annual_rate(monthly_rate: Decimal) -> Decimal:
    """The compounded yearly equivalent of a monthly rate, as a percent —
    2%/month is ~26.8%/year, not 24%. Shown next to every rate the parent
    sets so a monthly figure can't be mistaken for a yearly one."""
    factor = (Decimal("1") + monthly_rate / 100) ** 12
    return ((factor - 1) * 100).quantize(Decimal("0.1"), rounding=ROUND_HALF_UP)


def _value_at(principal: Decimal, monthly_rate: Decimal, opened_at: datetime, at: datetime) -> Decimal:
    """Principal compounded continuously (daily, in practice) from
    opened_at to `at`. Never dips below principal — `at` before opened_at
    just returns the principal untouched."""
    elapsed_days = Decimal((at - opened_at).total_seconds()) / Decimal(86400)
    if elapsed_days <= 0 or monthly_rate <= 0:
        return principal
    months = elapsed_days / DAYS_PER_MONTH
    return principal * (Decimal("1") + monthly_rate / 100) ** months


def deposit_value(deposit: SavingsDeposit, now: datetime | None = None) -> Decimal:
    """Current value in the deposit's own (deposit-time) currency. A
    closed deposit is frozen at its recorded close_value."""
    if not deposit.is_open and deposit.close_value is not None:
        return deposit.close_value
    now = now or datetime.now(timezone.utc)
    return _value_at(deposit.principal, deposit.monthly_rate, deposit.opened_at, now)


def compute_series(
    deposit: SavingsDeposit, until: datetime | None = None, points: int = 40
) -> list[tuple[datetime, Decimal]]:
    """Evenly spaced points of the deposit's value from opened_at to now
    (or `until` / closed_at) — backs the growth chart, using the same
    _value_at the headline number does so the two can't disagree."""
    end = until or (deposit.closed_at if not deposit.is_open else None) or datetime.now(timezone.utc)
    if end <= deposit.opened_at:
        return [(deposit.opened_at, deposit.principal)]
    span = (end - deposit.opened_at) / (points - 1)
    return [
        (
            deposit.opened_at + span * i,
            _value_at(deposit.principal, deposit.monthly_rate, deposit.opened_at, deposit.opened_at + span * i),
        )
        for i in range(points)
    ]


def is_matured(deposit: SavingsDeposit, now: datetime | None = None) -> bool:
    if deposit.matures_at is None:
        return True
    return (now or datetime.now(timezone.utc)) >= deposit.matures_at


async def list_open_deposits(session: AsyncSession, kid_id: uuid.UUID) -> list[SavingsDeposit]:
    rows = await session.scalars(
        select(SavingsDeposit)
        .where(SavingsDeposit.kid_id == kid_id, SavingsDeposit.is_open)
        .order_by(SavingsDeposit.opened_at)
    )
    return list(rows)


async def active_plans(session: AsyncSession, family_id: uuid.UUID) -> list[SavingsPlan]:
    rows = await session.scalars(
        select(SavingsPlan)
        .where(SavingsPlan.family_id == family_id, SavingsPlan.is_active)
        .order_by(SavingsPlan.lock_months, SavingsPlan.created_at)
    )
    return list(rows)


async def open_deposit_counts(session: AsyncSession, family_id: uuid.UUID) -> dict[uuid.UUID, int]:
    """How many open deposits sit against each of a family's plans — used
    to warn the parent before they edit or delete one."""
    rows = await session.execute(
        select(SavingsDeposit.plan_id, func.count())
        .join(SavingsPlan, SavingsPlan.id == SavingsDeposit.plan_id)
        .where(SavingsPlan.family_id == family_id, SavingsDeposit.is_open)
        .group_by(SavingsDeposit.plan_id)
    )
    return {plan_id: count for plan_id, count in rows}


def _deposit_entry(deposit: SavingsDeposit, rates: fx_service.RateTable, family_currency: str, now: datetime) -> dict:
    native_value = deposit_value(deposit, now)
    value = fx_service.convert_from_table(rates, native_value, deposit.currency, family_currency)
    principal = fx_service.convert_from_table(rates, deposit.principal, deposit.currency, family_currency)
    if value is None or principal is None:
        value = native_value
        principal = deposit.principal
        currency = deposit.currency
    else:
        currency = family_currency
    value = value.quantize(_CENTS, rounding=ROUND_HALF_UP)
    principal = principal.quantize(_CENTS, rounding=ROUND_HALF_UP)
    return {
        "deposit_id": deposit.id,
        "plan_name": deposit.plan_name,
        "monthly_rate": deposit.monthly_rate,
        "annual_rate": annual_rate(deposit.monthly_rate),
        "lock_months": deposit.lock_months,
        "is_locked": deposit.lock_months > 0,
        "matures_at": deposit.matures_at,
        "is_matured": is_matured(deposit, now),
        "principal": principal,
        "current_value": value,
        "accrued_interest": value - principal,
        "currency": currency,
        "opened_at": deposit.opened_at,
    }


async def build_overview(session: AsyncSession, kid: Kid, family_id: uuid.UUID, family_currency: str) -> dict:
    now = datetime.now(timezone.utc)
    deposits = await list_open_deposits(session, kid.id)
    plans = await active_plans(session, family_id)
    rates = await fx_service.load_all_rates(session)

    entries = [_deposit_entry(d, rates, family_currency, now) for d in deposits]
    total = sum((e["current_value"] for e in entries), Decimal("0.00"))
    return {
        "savings_value": total,
        "deposits": entries,
        "plans": [
            {
                "id": p.id,
                "name": p.name,
                "monthly_rate": p.monthly_rate,
                "annual_rate": annual_rate(p.monthly_rate),
                "lock_months": p.lock_months,
            }
            for p in plans
        ],
    }


async def savings_value(session: AsyncSession, kid_id: uuid.UUID, rates: fx_service.RateTable, family_currency: str) -> Decimal:
    """Total current value of a kid's open savings, in the family
    currency — for the portfolio headline. Takes a preloaded rate table
    so the portfolio path doesn't run its own FX query."""
    now = datetime.now(timezone.utc)
    total = Decimal("0.00")
    for deposit in await list_open_deposits(session, kid_id):
        native = deposit_value(deposit, now)
        converted = fx_service.convert_from_table(rates, native, deposit.currency, family_currency)
        total += (converted if converted is not None else native)
    return total.quantize(_CENTS, rounding=ROUND_HALF_UP)


async def get_deposit_detail(session: AsyncSession, kid: Kid, deposit_id: uuid.UUID, family_currency: str) -> dict | None:
    deposit = await session.scalar(
        select(SavingsDeposit).where(SavingsDeposit.id == deposit_id, SavingsDeposit.kid_id == kid.id)
    )
    if deposit is None:
        return None
    now = datetime.now(timezone.utc)
    rates = await fx_service.load_all_rates(session)
    entry = _deposit_entry(deposit, rates, family_currency, now)

    until = deposit.closed_at if not deposit.is_open else None
    series = compute_series(deposit, until=until)
    # Chart stays in the deposit's own currency, like the lot chart.
    entry["series"] = [{"observed_at": t, "value": v.quantize(_CENTS, rounding=ROUND_HALF_UP)} for t, v in series]
    entry["series_currency"] = deposit.currency
    entry["is_open"] = deposit.is_open
    entry["closed_at"] = deposit.closed_at
    return entry


async def create_deposit(
    session: AsyncSession, kid: Kid, plan: SavingsPlan, amount: Decimal, family_currency: str
) -> SavingsDeposit:
    if amount <= 0:
        raise SavingsError("Amount must be greater than zero")
    if not plan.is_active:
        raise SavingsError("That savings plan is no longer available")

    amount = amount.quantize(_CENTS, rounding=ROUND_HALF_UP)
    cash = await debts_db_service.get_balance(session, kid.id)
    if amount > cash:
        raise SavingsError("Not enough cash available")

    now = datetime.now(timezone.utc)
    matures_at = None
    if plan.lock_months > 0:
        matures_at = now + timedelta(days=float(DAYS_PER_MONTH) * plan.lock_months)

    await debts_db_service.record_transaction(
        session,
        kid.id,
        DebtTransactionType.DEDUCT,
        amount,
        note=f"Moved {amount} to savings ({plan.name})",
        is_savings=True,
    )

    deposit = SavingsDeposit(
        kid_id=kid.id,
        plan_id=plan.id,
        plan_name=plan.name,
        monthly_rate=plan.monthly_rate,
        lock_months=plan.lock_months,
        principal=amount,
        currency=family_currency,
        opened_at=now,
        matures_at=matures_at,
    )
    session.add(deposit)
    await session.flush()
    return deposit


async def withdraw_deposit(
    session: AsyncSession, kid: Kid, deposit_id: uuid.UUID, family_currency: str
) -> SavingsDeposit:
    deposit = await session.scalar(
        select(SavingsDeposit).where(
            SavingsDeposit.id == deposit_id, SavingsDeposit.kid_id == kid.id, SavingsDeposit.is_open
        )
    )
    if deposit is None:
        raise SavingsError("Savings deposit not found")

    now = datetime.now(timezone.utc)
    if not is_matured(deposit, now):
        raise SavingsError("This deposit is locked until it matures")

    native_value = deposit_value(deposit, now).quantize(_CENTS, rounding=ROUND_HALF_UP)
    payout = await fx_service.convert(session, native_value, deposit.currency, family_currency)
    payout = payout.quantize(_CENTS, rounding=ROUND_HALF_UP)

    await debts_db_service.record_transaction(
        session,
        kid.id,
        DebtTransactionType.ADD,
        payout,
        note=f"Savings payout ({deposit.plan_name})",
        is_savings=True,
    )

    deposit.is_open = False
    deposit.closed_at = now
    deposit.close_value = native_value
    deposit.close_currency = deposit.currency
    await session.flush()
    return deposit
