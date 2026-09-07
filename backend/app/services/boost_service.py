"""Computes a boosted investment_lot's synthetic value/trajectory.

No persisted checkpoint or accrued-factor column anywhere — every call
here recomputes a lot's whole trajectory from its immutable purchase
facts plus the shared, scheduler-written price_ticks history. That's a
deliberate simplification given the scale this app runs at (at most a
couple dozen open lots per kid, a few thousand ticks/year per symbol —
see CLAUDE.md): a full recompute on every read is cheap enough that
there's no need for mutable per-lot state, which also means there's
nothing to race on and nothing a kid could game by reading more or less
often (see docstring on the formula below).
"""

from datetime import datetime
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.catalog import PriceTick
from app.models.investment import InvestmentLot

# Hours in a month, for prorating a *monthly* buffer rate by real elapsed
# time between ticks — not hours in a year. The scheduler's tick spacing
# is irregular (it's a relative sleep loop that can also stop entirely
# while the backend process is idle — see scheduler/loop.py), so the
# bonus per tick must scale with actual elapsed time, not an assumed
# fixed number of ticks/day.
HOURS_PER_MONTH = Decimal("730.5")  # 365.25 * 24 / 12


def _walk(
    purchase_price: Decimal,
    purchased_at: datetime,
    buffer_rate: Decimal | None,
    ticks: list[tuple[datetime, Decimal]],
) -> list[tuple[datetime, Decimal]]:
    """Pure — the actual boost formula, kept separate from the DB query
    below so it's directly unit-testable.

    Walks real price ticks pairwise from the purchase price forward. On
    every tick where the real price rose, a bonus proportional to the
    real elapsed hours since the previous tick is added to that tick's
    return; a tick where the price fell (or didn't move) gets no bonus,
    but still advances the walk — so a boost is never "owed" retroactively
    to a later up-tick. Because this only ever depends on the shared,
    scheduler-written tick history (never on when this function happens
    to be called), a kid checking every 5 minutes computes the exact same
    value as a kid checking every 5 days.
    """
    monthly_fraction = (buffer_rate / 100) if buffer_rate else Decimal("0")

    points = [(purchased_at, purchase_price)]
    prev_real_price = purchase_price
    prev_t = purchased_at

    for observed_at, real_price in ticks:
        if prev_real_price > 0:
            real_return = (real_price - prev_real_price) / prev_real_price
        else:
            real_return = Decimal("0")

        bonus = Decimal("0")
        if monthly_fraction > 0 and real_return > 0:
            elapsed_hours = Decimal((observed_at - prev_t).total_seconds()) / Decimal(3600)
            bonus = (elapsed_hours / HOURS_PER_MONTH) * monthly_fraction

        effective_return = real_return + bonus
        points.append((observed_at, points[-1][1] * (1 + effective_return)))

        prev_real_price = real_price
        prev_t = observed_at

    return points


async def _load_ticks_since(
    session: AsyncSession, symbol: str, since: datetime, until: datetime | None
) -> list[tuple[datetime, Decimal]]:
    stmt = select(PriceTick.observed_at, PriceTick.price).where(
        PriceTick.symbol == symbol, PriceTick.observed_at > since
    )
    if until is not None:
        stmt = stmt.where(PriceTick.observed_at <= until)
    rows = await session.execute(stmt.order_by(PriceTick.observed_at.asc()))
    return [(observed_at, price) for observed_at, price in rows]


async def compute_lot_series(
    session: AsyncSession, lot: InvestmentLot, until: datetime | None = None
) -> list[tuple[datetime, Decimal]]:
    """The lot's whole synthetic price trajectory since purchase, one
    point per real tick — this is exactly what a "since purchase" graph
    plots; compute_lot_value below is just this series' last point.

    `until` caps the walk at a specific moment — pass a closed lot's
    `sold_at` so its history stays frozen at the moment it was actually
    sold, rather than continuing to "move" with ticks that happened
    after the kid no longer held it. Leave it None for an open lot,
    where "now" (i.e. every tick that exists) is exactly what should
    be shown."""
    ticks = await _load_ticks_since(session, lot.symbol, lot.purchased_at, until)
    return _walk(lot.purchase_price, lot.purchased_at, lot.buffer_rate, ticks)


async def compute_lot_value(session: AsyncSession, lot: InvestmentLot) -> Decimal:
    """Current per-unit synthetic price, in the lot's native (purchase)
    currency — convert to family currency at the call site, same as
    every other price in this app."""
    series = await compute_lot_series(session, lot)
    return series[-1][1]
