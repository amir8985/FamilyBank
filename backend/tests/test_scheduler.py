"""app/scheduler/loop.py + jobs.py's last_refresh_at(): the fix for a
real production bug (see CLAUDE.md's observability-logging entry) — the
scheduler used to run an immediate refresh on every process start
regardless of how recently one had actually completed, so a host that
redeploys often (this one does) re-triggered the ~10s refresh window far
more often than the intended "4-5x/day", each time slowing down whoever
was using the app at that exact moment.

last_refresh_at() deliberately uses its own connection (SessionLocal),
not the request-scoped session other tests override — see
request_logging.py for the same pattern — so its test writes/cleans up
directly against the shared dev/test DB rather than relying on a
per-test rolled-back transaction.
"""

from datetime import datetime, timedelta, timezone
from decimal import Decimal
from unittest.mock import AsyncMock

import pytest
from sqlalchemy import delete

from app.core.db import SessionLocal
from app.models.catalog import AssetCatalog, AssetKind, PriceCache
from app.scheduler import jobs, loop

_TEST_SYMBOL = "__SCHEDULER_TEST__"


class _StopLoop(Exception):
    """Sentinel to break out of run_forever's `while True` after one pass."""


async def _delete_test_row() -> None:
    async with SessionLocal() as session:
        await session.execute(delete(PriceCache).where(PriceCache.symbol == _TEST_SYMBOL))
        await session.execute(delete(AssetCatalog).where(AssetCatalog.symbol == _TEST_SYMBOL))
        await session.commit()


async def test_last_refresh_at_reflects_the_newest_price_row():
    stamp = datetime.now(timezone.utc)
    await _delete_test_row()
    try:
        async with SessionLocal() as session:
            # price_cache.symbol has a real FK to asset_catalog.
            session.add(
                AssetCatalog(
                    symbol=_TEST_SYMBOL, display_name="Scheduler Test", kind=AssetKind.STOCK, description="",
                )
            )
            session.add(
                PriceCache(
                    symbol=_TEST_SYMBOL, price=Decimal("1.00"), currency="USD",
                    updated_at=stamp, history_json=[],
                )
            )
            await session.commit()

        last = await jobs.last_refresh_at()
        assert last is not None
        assert last >= stamp
    finally:
        await _delete_test_row()


async def test_run_forever_skips_immediate_refresh_when_recently_run(monkeypatch):
    recent = datetime.now(timezone.utc) - timedelta(minutes=1)
    monkeypatch.setattr(loop, "last_refresh_at", AsyncMock(return_value=recent))
    run_refresh_mock = AsyncMock()
    monkeypatch.setattr(loop, "run_refresh", run_refresh_mock)

    sleep_calls: list[float] = []

    async def fake_sleep(seconds: float) -> None:
        sleep_calls.append(seconds)
        raise _StopLoop

    monkeypatch.setattr(loop.asyncio, "sleep", fake_sleep)

    with pytest.raises(_StopLoop):
        await loop.run_forever()

    run_refresh_mock.assert_not_called()
    assert len(sleep_calls) == 1
    # ~5h interval minus the 1 minute already elapsed — not the full interval.
    interval_seconds = loop.settings.scheduler_interval_hours * 3600
    assert 0 < sleep_calls[0] < interval_seconds


async def test_run_forever_runs_immediately_when_never_refreshed(monkeypatch):
    monkeypatch.setattr(loop, "last_refresh_at", AsyncMock(return_value=None))
    run_refresh_mock = AsyncMock()
    monkeypatch.setattr(loop, "run_refresh", run_refresh_mock)

    sleep_calls: list[float] = []

    async def fake_sleep(seconds: float) -> None:
        sleep_calls.append(seconds)
        raise _StopLoop

    monkeypatch.setattr(loop.asyncio, "sleep", fake_sleep)

    with pytest.raises(_StopLoop):
        await loop.run_forever()

    run_refresh_mock.assert_called_once()
    assert sleep_calls == [loop.settings.scheduler_interval_hours * 3600]
