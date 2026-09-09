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

import asyncio
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from unittest.mock import AsyncMock

import pytest
import pytest_asyncio
from sqlalchemy import delete, func, select

from app.core.db import SessionLocal, engine
from app.models.catalog import AssetCatalog, AssetKind, PriceCache
from app.models.request_log import RequestLog
from app.scheduler import jobs, loop

_TEST_SYMBOL = "__SCHEDULER_TEST__"
_TEST_PATH = "/__scheduler_cleanup_test__"


@pytest_asyncio.fixture(autouse=True)
async def _dispose_module_engine_pool():
    # app.core.db.engine (what SessionLocal is bound to) is a process-wide
    # singleton, but pytest-asyncio gives every test function its own
    # event loop, and an asyncpg connection is tied to the loop that
    # created it. Without this, a connection this file's tests pool (via
    # a direct `SessionLocal()` — see the module docstring) can get
    # handed back out to a *later* test's different loop and blow up with
    # "RuntimeError: Event loop is closed" on its first use — not a bug
    # in whichever test happens to draw the stale connection, so disposing
    # before and after each test (forcing a fresh, current-loop connection)
    # fixes it regardless of run order rather than papering over one test.
    await engine.dispose()
    yield
    await engine.dispose()


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


async def test_run_refresh_skips_body_when_advisory_lock_already_held(monkeypatch):
    inner = AsyncMock()
    monkeypatch.setattr(jobs, "_run_refresh", inner)

    # Hold the lock on this connection for the whole call — no commit, or
    # the session hands the connection (and the lock) back to the pool.
    async with SessionLocal() as holder:
        acquired = await holder.scalar(select(func.pg_try_advisory_lock(jobs._REFRESH_LOCK_KEY)))
        assert acquired is True
        try:
            await jobs.run_refresh()
            inner.assert_not_awaited()
        finally:
            await holder.scalar(select(func.pg_advisory_unlock(jobs._REFRESH_LOCK_KEY)))


async def test_run_refresh_runs_body_and_releases_lock_when_free(monkeypatch):
    inner = AsyncMock()
    monkeypatch.setattr(jobs, "_run_refresh", inner)

    await jobs.run_refresh()
    inner.assert_awaited_once()

    # Lock must be free again for the next trigger.
    async with SessionLocal() as session:
        reacquired = await session.scalar(select(func.pg_try_advisory_lock(jobs._REFRESH_LOCK_KEY)))
        assert reacquired is True
        await session.scalar(select(func.pg_advisory_unlock(jobs._REFRESH_LOCK_KEY)))
        await session.commit()


async def test_run_refresh_releases_lock_even_when_body_raises(monkeypatch):
    monkeypatch.setattr(jobs, "_run_refresh", AsyncMock(side_effect=RuntimeError("boom")))

    with pytest.raises(RuntimeError):
        await jobs.run_refresh()

    async with SessionLocal() as session:
        reacquired = await session.scalar(select(func.pg_try_advisory_lock(jobs._REFRESH_LOCK_KEY)))
        assert reacquired is True
        await session.scalar(select(func.pg_advisory_unlock(jobs._REFRESH_LOCK_KEY)))
        await session.commit()


async def test_spawn_refresh_if_stale_noop_when_prices_are_fresh(monkeypatch):
    monkeypatch.setattr(jobs, "_stale_fallback_enabled", True)
    triggered = AsyncMock()
    monkeypatch.setattr(jobs, "run_refresh", triggered)

    jobs.spawn_refresh_if_stale(datetime.now(timezone.utc))

    assert not jobs._stale_refresh_tasks
    triggered.assert_not_called()


async def test_spawn_refresh_if_stale_triggers_when_prices_are_old(monkeypatch):
    monkeypatch.setattr(jobs, "_stale_fallback_enabled", True)
    triggered = AsyncMock()
    monkeypatch.setattr(jobs, "run_refresh", triggered)

    stale = datetime.now(timezone.utc) - timedelta(
        hours=jobs.settings.refresh_staleness_threshold_hours + 1
    )
    jobs.spawn_refresh_if_stale(stale)

    await asyncio.gather(*list(jobs._stale_refresh_tasks))
    triggered.assert_awaited_once()


async def test_spawn_refresh_if_stale_triggers_when_never_refreshed(monkeypatch):
    monkeypatch.setattr(jobs, "_stale_fallback_enabled", True)
    triggered = AsyncMock()
    monkeypatch.setattr(jobs, "run_refresh", triggered)

    jobs.spawn_refresh_if_stale(None)

    await asyncio.gather(*list(jobs._stale_refresh_tasks))
    triggered.assert_awaited_once()


async def test_spawn_refresh_if_stale_is_a_noop_while_disabled(monkeypatch):
    monkeypatch.setattr(jobs, "_stale_fallback_enabled", False)
    triggered = AsyncMock()
    monkeypatch.setattr(jobs, "run_refresh", triggered)

    jobs.spawn_refresh_if_stale(None)

    assert not jobs._stale_refresh_tasks
    triggered.assert_not_called()


async def test_cleanup_old_request_logs_prunes_only_rows_past_retention():
    now = datetime.now(timezone.utc)
    old_row_id = None
    recent_row_id = None
    async with SessionLocal() as session:
        old_row = RequestLog(
            method="GET",
            path=_TEST_PATH,
            duration_ms=1.0,
            created_at=now - timedelta(days=jobs.settings.request_log_retention_days + 1),
        )
        recent_row = RequestLog(method="GET", path=_TEST_PATH, duration_ms=1.0, created_at=now)
        session.add_all([old_row, recent_row])
        await session.commit()
        old_row_id, recent_row_id = old_row.id, recent_row.id

    try:
        deleted = await jobs.cleanup_old_request_logs()
        assert deleted >= 1

        async with SessionLocal() as session:
            remaining_ids = set(
                (await session.scalars(select(RequestLog.id).where(RequestLog.path == _TEST_PATH))).all()
            )
        assert old_row_id not in remaining_ids
        assert recent_row_id in remaining_ids
    finally:
        async with SessionLocal() as session:
            await session.execute(delete(RequestLog).where(RequestLog.path == _TEST_PATH))
            await session.commit()
