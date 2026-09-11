"""Recurring allowance / pocket money — a parent sets a weekly or
monthly amount for a kid and it lands in their normal cash balance on
schedule.

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

import logging
import uuid
from datetime import datetime, timedelta, timezone
from decimal import ROUND_HALF_UP, Decimal

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import aliased

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
    day-of-month next month — `dt.day` is always a payday (1..28, enforced
    by validate_payday), which every month has."""
    if cadence == AllowanceCadence.WEEKLY:
        return dt + timedelta(days=7)
    year = dt.year + (1 if dt.month == 12 else 0)
    month = 1 if dt.month == 12 else dt.month + 1
    return dt.replace(year=year, month=month)


def first_run_at(now: datetime, cadence: AllowanceCadence, payday: int) -> datetime:
    """The first payday strictly in the future — a new allowance never
    pays out the instant it's created."""
    if cadence == AllowanceCadence.WEEKLY:
        days_ahead = (payday - now.weekday()) % 7
        candidate = _midnight(now) + timedelta(days=days_ahead)
    else:
        candidate = _midnight(now).replace(day=payday)  # payday is 1..28
    if candidate <= now:
        candidate = _advance(candidate, cadence)
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


async def _settle(
    session: AsyncSession, allowance: Allowance, family_currency: str, now: datetime
) -> int:
    """Pay out every period that's come due for one already-loaded
    allowance. Returns the number of payouts made. Caller commits.

    A per-kid advisory lock means a second concurrent settle for the same
    kid backs off (returns 0) instead of double-paying — the two callers
    that race are the inline settle on a read and the refresh-cycle sweep.
    """
    if allowance.next_run_at > now:
        return 0

    got_lock = await session.scalar(
        select(func.pg_try_advisory_xact_lock(_LOCK_NAMESPACE, _kid_lock_key(allowance.kid_id)))
    )
    if not got_lock:
        return 0

    # Re-read after taking the lock — the settle that beat us to it may
    # have already advanced the clock.
    await session.refresh(allowance)
    if allowance.next_run_at > now:
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
            allowance.kid_id,
            MAX_CATCHUP_PERIODS,
            allowance.next_run_at.isoformat(),
        )

    await session.flush()
    return paid


async def settle_due(
    session: AsyncSession, kid: Kid, family_currency: str, now: datetime | None = None
) -> int:
    """Load one kid's allowance and settle anything due. Caller commits."""
    allowance = await get_allowance(session, kid.id)
    if allowance is None:
        return 0
    return await _settle(session, allowance, family_currency, now or datetime.now(timezone.utc))


async def _recent_payments_by_kid(
    session: AsyncSession, kid_ids: list[uuid.UUID]
) -> dict[uuid.UUID, list[DebtTransaction]]:
    """Last RECENT_PAYMENTS_LIMIT allowance payouts for each kid, in one
    query (a per-kid window) instead of one query per kid."""
    if not kid_ids:
        return {}
    rn = func.row_number().over(
        partition_by=DebtTransaction.kid_id,
        order_by=DebtTransaction.created_at.desc(),
    ).label("rn")
    ranked = (
        select(DebtTransaction, rn)
        .where(DebtTransaction.kid_id.in_(kid_ids), DebtTransaction.is_allowance)
        .subquery()
    )
    ranked_txn = aliased(DebtTransaction, ranked)
    rows = await session.scalars(
        select(ranked_txn)
        .where(ranked.c.rn <= RECENT_PAYMENTS_LIMIT)
        .order_by(ranked.c.created_at.desc())
    )
    out: dict[uuid.UUID, list[DebtTransaction]] = {kid_id: [] for kid_id in kid_ids}
    for row in rows:
        out[row.kid_id].append(row)
    return out


def _view_dict(
    kid: Kid, allowance: Allowance | None, payments: list[DebtTransaction], family_currency: str
) -> dict:
    view: dict = {
        "kid_id": kid.id,
        "kid_name": kid.name,
        "configured": allowance is not None,
        "recent_payments": [
            {"amount": p.amount, "currency": family_currency, "paid_at": p.created_at}
            for p in payments
        ],
    }
    if allowance is not None:
        view.update(
            amount=allowance.amount,
            currency=allowance.currency,
            cadence=allowance.cadence,
            payday=allowance.payday,
            next_payday=allowance.next_run_at,
            last_paid_at=allowance.last_paid_at,
        )
    return view


async def build_view(session: AsyncSession, kid: Kid, family: Family) -> dict:
    """Settle anything due, then assemble one kid's allowance summary +
    recent payouts. Caller commits (settle may have written rows)."""
    allowance = await get_allowance(session, kid.id)
    if allowance is not None:
        await _settle(session, allowance, family.base_currency, datetime.now(timezone.utc))
    payments = (await _recent_payments_by_kid(session, [kid.id]))[kid.id]
    return _view_dict(kid, allowance, payments, family.base_currency)


async def build_family_views(session: AsyncSession, family: Family, kids: list[Kid]) -> list[dict]:
    """Same as build_view for every kid in the family, but batched — two
    queries (all allowances, all recent payouts) plus the settle work,
    not ~3 sequential round-trips per kid (the Neon-latency N+1 pattern
    CLAUDE.md's perf section warns against)."""
    kid_ids = [k.id for k in kids]
    allowances = {
        a.kid_id: a
        for a in await session.scalars(select(Allowance).where(Allowance.kid_id.in_(kid_ids)))
    }
    now = datetime.now(timezone.utc)
    for kid in kids:
        allowance = allowances.get(kid.id)
        if allowance is not None:
            await _settle(session, allowance, family.base_currency, now)
    payments = await _recent_payments_by_kid(session, kid_ids)
    return [
        _view_dict(kid, allowances.get(kid.id), payments.get(kid.id, []), family.base_currency)
        for kid in kids
    ]


_sweep_enabled = True


def set_sweep_enabled(value: bool) -> None:
    """Test-only switch (see tests/conftest.py's autouse fixture). The
    refresh-cycle sweep opens its own SessionLocal and really commits, so
    it must be off for the suite — the same reason the price staleness
    fallback is."""
    global _sweep_enabled
    _sweep_enabled = value


async def settle_all_due() -> int:
    """Sweep every allowance in every family that has a payout due —
    called once per price-refresh cycle (scheduler.jobs.run_refresh) so
    balances shown on /home stay current even when nobody opens an
    allowance screen. Opens its own session and commits. Returns the
    total payouts made.
    """
    if not _sweep_enabled:
        return 0

    total = 0
    async with SessionLocal() as session:
        now = datetime.now(timezone.utc)
        rows = await session.execute(
            select(Allowance, Family.base_currency)
            .join(Kid, Kid.id == Allowance.kid_id)
            .join(Family, Family.id == Kid.family_id)
            .where(Allowance.next_run_at <= now)
        )
        due = rows.all()
        for allowance, base_currency in due:
            try:
                total += await _settle(session, allowance, base_currency, now)
                # Commit per kid: one kid's failure (or a missing FX rate)
                # doesn't roll back the others, and the per-kid advisory
                # lock is released rather than held for the whole sweep.
                await session.commit()
            except Exception:
                logger.exception("Allowance sweep failed for kid %s", allowance.kid_id)
                await session.rollback()
    if total:
        logger.info("Allowance sweep paid out %d installment(s) across %d kid(s)", total, len(due))
    return total
