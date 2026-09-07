"""boost_service._walk is the actual boost math — the asymmetry (bonus
only on up-ticks), the elapsed-time proration (not a fixed count per
day), and the fact it's a pure recompute with no persisted checkpoint
are all real product decisions from the boosted-stocks-and-interest
design discussion, not implementation details — see CLAUDE.md."""

from datetime import datetime, timedelta, timezone
from decimal import Decimal

from app.services.boost_service import HOURS_PER_MONTH, _walk

T0 = datetime(2026, 1, 1, tzinfo=timezone.utc)


def test_no_buffer_rate_is_just_the_real_price_path():
    ticks = [(T0 + timedelta(hours=5), Decimal("110")), (T0 + timedelta(hours=10), Decimal("90"))]
    points = _walk(Decimal("100"), T0, None, ticks)
    assert [v for _, v in points] == [Decimal("100"), Decimal("110"), Decimal("90")]


def test_bonus_applies_only_on_up_ticks():
    """One up-tick and one down-tick, same elapsed time and a 12%/month
    rate — the down-tick must track the real price exactly, with no
    bonus attached to it."""
    monthly_rate = Decimal("12")  # 12%/month, so 1%/month per HOURS_PER_MONTH/12 hours — pick round numbers
    elapsed = HOURS_PER_MONTH  # exactly one month, so the bonus is exactly monthly_rate% on the up-tick
    ticks = [
        (T0 + timedelta(hours=float(elapsed)), Decimal("110")),  # real return +10%, bonus applies
    ]
    points = _walk(Decimal("100"), T0, monthly_rate, ticks)
    # (1 + 0.10 + 0.12) * 100 = 122
    assert points[-1][1] == Decimal("122.00")

    ticks_down = [
        (T0 + timedelta(hours=float(elapsed)), Decimal("90")),  # real return -10%, no bonus
    ]
    points_down = _walk(Decimal("100"), T0, monthly_rate, ticks_down)
    assert points_down[-1][1] == Decimal("90")  # exactly the real price, no bonus attached


def test_bonus_is_prorated_by_real_elapsed_time_not_a_fixed_count():
    """Half a month's worth of elapsed time gets half the monthly bonus —
    this is what makes the boost correct regardless of how irregularly
    the scheduler actually ticks (see scheduler/loop.py)."""
    monthly_rate = Decimal("12")
    half_month_hours = HOURS_PER_MONTH / 2
    ticks = [(T0 + timedelta(hours=float(half_month_hours)), Decimal("101"))]  # tiny up-move
    points = _walk(Decimal("100"), T0, monthly_rate, ticks)
    # real_return = 0.01, bonus = 0.5 * 0.12 = 0.06 -> effective 0.07
    assert points[-1][1] == Decimal("107.00")


def test_boost_never_retroactively_owed_to_a_later_up_tick():
    """A down-tick advances the walk's checkpoint even though it gets no
    bonus itself — a later up-tick's bonus is based on elapsed time since
    that down-tick, not since the last up-tick."""
    monthly_rate = Decimal("12")
    down_at = T0 + timedelta(hours=float(HOURS_PER_MONTH))
    up_at = down_at + timedelta(hours=float(HOURS_PER_MONTH))
    ticks = [(down_at, Decimal("90")), (up_at, Decimal("99"))]  # -10% then +10%
    points = _walk(Decimal("100"), T0, monthly_rate, ticks)
    assert points[1][1] == Decimal("90.00")  # down-tick: no bonus, boosted value == real value
    # up-tick: real_return = (99-90)/90 = 0.10 (one full month elapsed since the down-tick) + 0.12
    # bonus, compounded onto the *previous boosted value* (90.00, same as real here since the
    # down-tick got no bonus) — not onto the raw real price at the up-tick (99).
    assert points[2][1] == Decimal("90.00") * Decimal("1.22")


async def test_compute_lot_series_reads_shared_price_ticks(db_session, family, seeded_asset):
    from datetime import datetime as dt

    from app.models.investment import InvestmentLot
    from app.services import boost_service

    now = dt.now(timezone.utc)
    lot = InvestmentLot(
        kid_id=None,
        symbol="TEST",
        units=Decimal("1"),
        purchase_price=Decimal("100"),
        purchase_currency="USD",
        purchased_at=now,
        buffer_rate=None,
    )
    # kid_id isn't read by compute_lot_series — only symbol/purchased_at/
    # purchase_price/buffer_rate matter, so a bare (unattached) lot works
    # fine here without needing a real kid fixture.
    await _add_tick(db_session, "TEST", "105", now + timedelta(hours=1))

    series = await boost_service.compute_lot_series(db_session, lot)
    assert len(series) == 2
    assert series[0] == (now, Decimal("100"))
    assert series[1][1] == Decimal("105")


async def _add_tick(db_session, symbol: str, price: str, when: datetime):
    from app.models.catalog import PriceTick

    db_session.add(PriceTick(symbol=symbol, observed_at=when, price=Decimal(price), currency="USD"))
    await db_session.flush()
