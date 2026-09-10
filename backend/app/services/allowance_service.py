"""Recurring allowance ("pocket money" / דמי כיס) — a parent sets a
weekly or monthly amount for a kid and it lands in their normal cash
balance on schedule.

Unlike savings/boost (stateless, recomputed on every read), an allowance
payout is a real one-time ledger write: a `debt_transactions` ADD row
flagged `is_allowance`. So a payment shows up in the balance everywhere
and in the existing history screen with no extra plumbing.

Payouts are settled *lazily*: `settle_due` is called whenever anyone
looks at allowance data (kid app home, parent settings) and once per
price-refresh cycle (`scheduler.jobs.run_refresh`). There is no
per-payment cron. Any period whose `next_run_at` has passed is paid and
the clock advanced one period at a time, capped so an app left closed
for a year doesn't dump a year of back-pay in one lump.
"""

import calendar
import logging
import uuid
from datetime import datetime, timedelta, timezone
from decimal import ROUND_HALF_UP, Decimal

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import SessionLocal
from app.models.allowance import Allowance, AllowanceCadence
from app.models.debt_transaction import DebtTransaction, DebtTransactionType
from app.models.family import Family
from app.models.kid import Kid
from app.services import debts_db_service, fx_service

RECENT_PAYMENTS_LIMIT = 6

logger = logging.getLogger("familybank.allowance")

_CENTS = Decimal("0.01")

# Most missed periods a single settle pass will pay out. A weekly
# allowance left unsettled for >1 year hits this; anything past it is
# fast-forwarded (clock advanced, nothing paid) rather than dumped as
# back-pay the parent never expected.
MAX_CATCHUP_PERIODS = 60

# Postgres advisory-lock namespace for "settling an allowance" — paired
# with a per-kid key so two concurrent settle attempts for the same kid
# serialize (the loser skips) without blocking settles for other kids.
# Transaction-scoped (`_xact_`): released automatically on commit/rollback,
# so a request session and the test suite's rolled-back transaction both
# clean up on their own.
_LOCK_NAMESPACE = 511_553_760


class AllowanceError(ValueError):
    pass


def _kid_lock_key(kid_id: uuid.UUID) -> int:
    # Low 31 bits → always a positive int4 (Postgres advisory locks take
    # two int4s).
    return kid_id.int & 0x7FFFFFFF


def _midnight(d: datetime) -> datetime:
    return d.replace(hour=0, minute=0, second=0, microsecond=0)


def _advance(dt: datetime, cadence: AllowanceCadence) -> datetime:
    """One period forward from `dt`. Weekly = +7 days. Monthly = same
    day-of-month next month (payday is 1..28, so it always exists)."""
    if cadence == AllowanceCadence.WEEKLY:
        return dt + timedelta(days=7)
    year = dt.year + (1 if dt.month == 12 else 0)
    month = 1 if dt.month == 12 else dt.month + 1
    day = min(dt.day, calendar.monthrange(year, month)[1])
    return dt.replace(year=year, month=month, day=day)


def first_run_at(now: datetime, cadence: AllowanceCadence, payday: int) -> datetime:
    """The first payday strictly in the future — a new allowance never
    pays out the instant it's created."""
    if cadence == AllowanceCadence.WEEKLY:
        days_ahead = (payday - now.weekday()) % 7
        candidate = _midnight(now) + timedelta(days=days_ahead)
    else:
        candidate = _midnight(now).replace(day=min(payday, calendar.monthrange(now.year, now.month)[1]))
    if candidate <= now:
        candidate = _advance(candidate, cadence)
        if cadence == AllowanceCadence.MONTHLY:
            # _advance may have clamped a short month (e.g. Feb) — re-seat
            # on the real payday now that we're in the next month.
            candidate = candidate.replace(
                day=min(payday, calendar.monthrange(candidate.year, candidate.month)[1])
            )
    return candidate


def validate_payday(cadence: AllowanceCadence, payday: int) -> None:
    if cadence == AllowanceCadence.WEEKLY and not (0 <= payday <= 6):
        raise AllowanceError("Weekly payday must be a weekday (0=Monday .. 6=Sunday)")
    if cadence == AllowanceCadence.MONTHLY and not (1 <= payday <= 28):
        raise AllowanceError("Monthly payday must be a day of the month between 1 and 28")


async def get_allowance(session: AsyncSession, kid_id: uuid.UUID) -> Allowance | None:
    return await session.scalar(select(Allowance).where(Allowance.kid_id == kid_id))


async def upsert_allowance(
    session: AsyncSession,
    kid: Kid,
    family: Family,
    *,
    amount: Decimal,
    cadence: AllowanceCadence,
    payday: int,
    is_active: bool,
) -> Allowance:
    if amount <= 0:
        raise AllowanceError("Amount must be greater than zero")
    validate_payday(cadence, payday)
    amount = amount.quantize(_CENTS, rounding=ROUND_HALF_UP)
    now = datetime.now(timezone.utc)

    existing = await get_allowance(session, kid.id)
    if existing is None:
        allowance = Allowance(
            kid_id=kid.id,
            amount=amount,
            currency=family.base_currency,
            cadence=cadence,
            payday=payday,
            is_active=is_active,
            next_run_at=first_run_at(now, cadence, payday),
        )
        session.add(allowance)
        await session.flush()
        return allowance

    # Re-anchor the schedule only when the cadence or payday actually
    # changes — a plain amount edit keeps the existing next payday, so the
    # kid isn't pushed a week/month further out every time a parent nudges
    # the number.
    if existing.cadence != cadence or existing.payday != payday:
        existing.next_run_at = first_run_at(now, cadence, payday)
    existing.amount = amount
    existing.currency = family.base_currency
    existing.cadence = cadence
    existing.payday = payday
    existing.is_active = is_active
    await session.flush()
    return existing


async def delete_allowance(session: AsyncSession, kid_id: uuid.UUID) -> None:
    existing = await get_allowance(session, kid_id)
    if existing is not None:
        await session.delete(existing)
        await session.flush()


async def _pay_once(
    session: AsyncSession, allowance: Allowance, family_currency: str, settled_at: datetime
) -> bool:
    """Write one allowance payout. Returns False (and pays nothing) if the
    amount can't be converted to the family's current currency yet — the
    caller leaves next_run_at untouched so it retries next time."""
    try:
        payout = await fx_service.convert(session, allowance.amount, allowance.currency, family_currency)
    except ValueError:
        logger.warning(
            "Allowance for kid %s: no FX rate %s→%s yet, skipping this payout",
            allowance.kid_id,
            allowance.currency,
            family_currency,
        )
        return False
    payout = payout.quantize(_CENTS, rounding=ROUND_HALF_UP)
    if payout <= 0:
        return False
    await debts_db_service.record_transaction(
        session,
        allowance.kid_id,
        DebtTransactionType.ADD,
        payout,
        note=f"{allowance.cadence.value.capitalize()} allowance",
        is_allowance=True,
    )
    allowance.last_paid_at = settled_at
    return True


async def settle_due(
    session: AsyncSession, kid: Kid, family_currency: str, now: datetime | None = None
) -> int:
    """Pay out every period that's come due for one kid. Returns the
    number of payouts made. Caller commits.

    A per-kid advisory lock means a second concurrent settle for the same
    kid backs off (returns 0) instead of double-paying — the two callers
    that race are the inline settle on a read and the refresh-cycle sweep.
    """
    allowance = await get_allowance(session, kid.id)
    if allowance is None or not allowance.is_active:
        return 0

    now = now or datetime.now(timezone.utc)
    if allowance.next_run_at > now:
        return 0

    got_lock = await session.scalar(
        select(func.pg_try_advisory_xact_lock(_LOCK_NAMESPACE, _kid_lock_key(kid.id)))
    )
    if not got_lock:
        return 0

    # Re-read after taking the lock — the settle that beat us to it may
    # have already advanced the clock.
    await session.refresh(allowance)
    if not allowance.is_active or allowance.next_run_at > now:
        return 0

    paid = 0
    for _ in range(MAX_CATCHUP_PERIODS):
        if allowance.next_run_at > now:
            break
        if not await _pay_once(session, allowance, family_currency, now):
            return paid  # conversion not possible yet — try again next time
        allowance.next_run_at = _advance(allowance.next_run_at, allowance.cadence)
        paid += 1

    if allowance.next_run_at <= now:
        # Hit the catch-up cap — fast-forward past the backlog without
        # paying it (an app closed for a very long time shouldn't dump a
        # lump sum). Re-seat on the configured payday.
        allowance.next_run_at = first_run_at(now, allowance.cadence, allowance.payday)
        logger.warning(
            "Allowance for kid %s hit the %d-period catch-up cap — fast-forwarded to %s",
            kid.id,
            MAX_CATCHUP_PERIODS,
            allowance.next_run_at.isoformat(),
        )

    await session.flush()
    return paid


async def recent_payments(session: AsyncSession, kid_id: uuid.UUID) -> list[DebtTransaction]:
    rows = await session.scalars(
        select(DebtTransaction)
        .where(DebtTransaction.kid_id == kid_id, DebtTransaction.is_allowance)
        .order_by(DebtTransaction.created_at.desc())
        .limit(RECENT_PAYMENTS_LIMIT)
    )
    return list(rows)


async def build_view(session: AsyncSession, kid: Kid, family: Family) -> dict:
    """Settle anything due, then assemble the kid's allowance summary +
    recent payouts. Caller commits (settle may have written rows)."""
    await settle_due(session, kid, family.base_currency)

    allowance = await get_allowance(session, kid.id)
    payments = await recent_payments(session, kid.id)
    view: dict = {
        "kid_id": kid.id,
        "kid_name": kid.name,
        "configured": allowance is not None,
        "is_active": bool(allowance and allowance.is_active),
        "recent_payments": [
            {"amount": p.amount, "currency": family.base_currency, "paid_at": p.created_at}
            for p in payments
        ],
    }
    if allowance is not None:
        view.update(
            amount=allowance.amount,
            currency=allowance.currency,
            cadence=allowance.cadence,
            payday=allowance.payday,
            next_payday=allowance.next_run_at if allowance.is_active else None,
            last_paid_at=allowance.last_paid_at,
        )
    return view


_sweep_enabled = True


def set_sweep_enabled(value: bool) -> None:
    """Test-only switch (see tests/conftest.py's autouse fixture). The
    refresh-cycle sweep opens its own SessionLocal and really commits, so
    it must be off for the suite — the same reason the price staleness
    fallback is."""
    global _sweep_enabled
    _sweep_enabled = value


async def settle_all_due() -> int:
    """Sweep every active allowance in every family — called once per
    price-refresh cycle (scheduler.jobs.run_refresh) so balances shown on
    /home stay current even when nobody opens an allowance screen.
    Opens its own session and commits. Returns the total payouts made.
    """
    if not _sweep_enabled:
        return 0

    total = 0
    async with SessionLocal() as session:
        rows = await session.execute(
            select(Kid, Family)
            .join(Family, Family.id == Kid.family_id)
            .join(Allowance, Allowance.kid_id == Kid.id)
            .where(Allowance.is_active, Allowance.next_run_at <= datetime.now(timezone.utc))
        )
        pairs = rows.all()
        for kid, family in pairs:
            try:
                total += await settle_due(session, kid, family.base_currency)
                # Commit per kid: one kid's failure (or a missing FX rate)
                # doesn't roll back the others, and the per-kid advisory
                # lock is released rather than held for the whole sweep.
                await session.commit()
            except Exception:
                logger.exception("Allowance sweep failed for kid %s", kid.id)
                await session.rollback()
    if total:
        logger.info("Allowance sweep paid out %d installment(s) across %d kid(s)", total, len(pairs))
    return total
