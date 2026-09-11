"""The one global scheduler job (architecture 5.3): refreshes price_cache
and fx_rates_cache together, 4-5x/day, for every symbol once — never
per-family, never per-request (spec 4.3).
"""

import asyncio
import logging
from datetime import datetime, timedelta, timezone
from decimal import Decimal

import httpx
from sqlalchemy import delete, func, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.currencies import SUPPORTED_CURRENCIES
from app.core.db import SessionLocal
from app.models.catalog import AssetCatalog, PriceCache, PriceTick
from app.models.request_log import RequestLog
from app.services import allowance_service, fx_service
from app.services.investing_service import clear_price_context_cache
from app.services.price_client import PriceFetchError, fetch_quote

settings = get_settings()

logger = logging.getLogger("familybank.scheduler")


async def last_refresh_at() -> datetime | None:
    """Newest `price_cache.updated_at` across every symbol — every row a
    refresh touches gets the same timestamp (see _fetch_prices), so this
    is exactly "when did a refresh last actually complete." None before
    the very first refresh has ever run.
    """
    async with SessionLocal() as session:
        return await session.scalar(select(func.max(PriceCache.updated_at)))


async def _fetch_prices(client: httpx.AsyncClient, symbols: list[str]) -> list[tuple[str, dict]]:
    """Fetches every symbol's quote from Yahoo — deliberately holds no DB
    session while doing this (a previous version did, and held one
    connection idle from the pool for the whole ~10s this loop takes,
    which measurably slowed down concurrent user requests needing a
    connection during that window — see the observability-logging
    investigation this followed from).
    """
    quotes = []
    for symbol in symbols:
        try:
            data = await fetch_quote(client, symbol)
        except (PriceFetchError, httpx.HTTPError) as exc:
            logger.warning("Price fetch failed for %s: %s", symbol, exc)
            continue
        quotes.append((symbol, data))
    return quotes


async def _write_prices(
    session: AsyncSession, quotes: list[tuple[str, dict]], now: datetime
) -> None:
    for symbol, data in quotes:
        stmt = (
            insert(PriceCache)
            .values(
                symbol=symbol,
                price=Decimal(str(data["price"])),
                currency=data["currency"],
                updated_at=now,
                history_json=data["history"],
            )
            .on_conflict_do_update(
                index_elements=["symbol"],
                set_={
                    "price": Decimal(str(data["price"])),
                    "currency": data["currency"],
                    "updated_at": now,
                    "history_json": data["history"],
                },
            )
        )
        await session.execute(stmt)

        # Append-only, unlike the upsert above — boost_service needs every
        # past tick to reconstruct a boosted lot's trajectory, not just
        # the current price (see models/catalog.py's PriceTick docstring).
        session.add(
            PriceTick(
                symbol=symbol,
                observed_at=now,
                price=Decimal(str(data["price"])),
                currency=data["currency"],
            )
        )


# A single fixed key for Postgres' session-level advisory lock, namespaced
# to "the price/FX refresh job". pg_try_advisory_lock is non-blocking:
# whoever holds it is refreshing right now, everyone else backs off. This
# makes it safe for more than one trigger to fire close together — the
# in-process loop and the /internal/refresh cron overlapping during a
# deploy cutover, a Cloud Scheduler retry landing on top of the original,
# or the staleness fallback racing the cron — without double-hitting Yahoo
# or writing duplicate price_ticks rows (the one non-idempotent part of a
# refresh; PriceCache/FxRateCache are upserts).
_REFRESH_LOCK_KEY = 4_150_237_918


async def run_refresh() -> None:
    """Public entry — acquires the advisory lock, then runs _run_refresh()
    exactly once. A second caller while one is in flight logs and returns
    immediately rather than blocking or double-running.
    """
    async with SessionLocal() as lock_session:
        # The lock is bound to this connection, so lock_session has to stay
        # open (and hold the connection) for the whole refresh — a commit
        # here would return the connection to the pool and the unlock in
        # `finally` would then run on a different one. That means ~10s of
        # idle-in-transaction on one connection a few times a day, which is
        # a non-issue at this scale (one connection out of 15, no vacuum
        # pressure worth speaking of).
        acquired = await lock_session.scalar(select(func.pg_try_advisory_lock(_REFRESH_LOCK_KEY)))
        if not acquired:
            logger.info("Price/FX refresh already running on another trigger — skipping this one")
            return
        try:
            await _run_refresh()
        finally:
            await lock_session.scalar(select(func.pg_advisory_unlock(_REFRESH_LOCK_KEY)))


async def _run_refresh() -> None:
    logger.info("Scheduler refresh starting")

    async with SessionLocal() as session:
        symbols = list((await session.scalars(select(AssetCatalog.symbol))).all())

    # Every external call (prices, then FX) happens with no DB session
    # open at all — see _fetch_prices' docstring for why that matters.
    async with httpx.AsyncClient() as client:
        quotes = await _fetch_prices(client, symbols)
        native_currencies = {data["currency"] for _, data in quotes}

        # Every currency the Settings picker offers, not just ones a
        # family currently uses — otherwise the first family to pick a
        # currency nobody's used yet has no cached rate to convert
        # into (the bug that motivated this).
        base_currencies = set(SUPPORTED_CURRENCIES)
        pairs = {
            (native, base)
            for native in native_currencies
            for base in base_currencies
            if native != base
        }
        fx_quotes = await fx_service.fetch_fx_rates(client, pairs)

    now = datetime.now(timezone.utc)
    async with SessionLocal() as session:
        await _write_prices(session, quotes, now)
        await fx_service.write_fx_rates(session, fx_quotes, now)
        await session.commit()

    # So requests right after a refresh see the new prices immediately,
    # rather than waiting out the safety-net TTL (investing_service.py).
    clear_price_context_cache()

    # Piggyback the recurring-allowance sweep on this cadence (like the
    # request_logs cleanup below) — no separate cron needed. It's a
    # best-effort backstop: allowance data is also settled inline whenever
    # a kid or parent opens an allowance screen.
    try:
        await allowance_service.settle_all_due()
    except Exception:
        logger.exception("Allowance sweep failed during refresh — will retry next cycle")

    deleted = await cleanup_old_request_logs()

    logger.info(
        "Scheduler refresh complete: %d symbols, %d FX pairs, %d old request_logs rows pruned, at %s",
        len(symbols),
        len(pairs),
        deleted,
        datetime.now(timezone.utc),
    )


async def cleanup_old_request_logs() -> int:
    """Prunes request_logs rows older than settings.request_log_retention_days
    — nothing else ever deletes from this table (see the setting's own
    docstring for why that's a problem at real traffic volumes). Piggybacks
    on the price/FX refresh cadence (called from run_refresh) rather than
    needing its own schedule; a plain indexed DELETE (created_at has its
    own index — see RequestLog.__table_args__) is cheap enough not to
    warrant one. Returns the number of rows deleted, for the log line.
    """
    cutoff = datetime.now(timezone.utc) - timedelta(days=settings.request_log_retention_days)
    async with SessionLocal() as session:
        result = await session.execute(delete(RequestLog).where(RequestLog.created_at < cutoff))
        await session.commit()
        return result.rowcount or 0


# Keeps a reference to each in-flight fallback task — asyncio can garbage-
# collect a task nothing else holds mid-execution (its own docs warn about
# this; same pattern as request_logging.spawn_persist_request_log).
_stale_refresh_tasks: set[asyncio.Task] = set()

_stale_fallback_enabled = True


def set_stale_fallback_enabled(value: bool) -> None:
    """Test-only switch (see tests/conftest.py's autouse fixture). The
    fallback fires a real run_refresh() — its own connection, real Yahoo
    calls, a real (non-rolled-back) commit — so it must be off for the
    suite, where /home and /catalog get hit constantly against a shared
    dev DB whose prices are often stale.
    """
    global _stale_fallback_enabled
    _stale_fallback_enabled = value


def spawn_refresh_if_stale(prices_as_of: datetime | None) -> None:
    """Best-effort catch-up refresh, triggered from a user-facing read
    (/home, /catalog) when the cached prices look too old — insurance for
    a missed external cron run when SCHEDULER_ENABLED is false.

    `prices_as_of` is the timestamp the caller already has in hand from
    PriceContext, so the common (fresh) path costs zero extra queries.
    run_refresh() self-guards with an advisory lock, so this racing the
    real cron (or a second reader racing this) can't double-run — the
    loser returns immediately.

    Fire-and-forget: the triggering request returns right away with the
    slightly-stale data rather than waiting out the ~10s refresh. On a
    scale-to-zero host the task can be cut short if the instance is torn
    down mid-run — acceptable for a fallback (the external cron is the
    real mechanism, a monitoring alert is the real "cron died" signal),
    but it's why this must not become the primary refresh path.
    """
    if not _stale_fallback_enabled:
        return

    threshold = timedelta(hours=settings.refresh_staleness_threshold_hours)
    if prices_as_of is not None and datetime.now(timezone.utc) - prices_as_of < threshold:
        return

    logger.warning(
        "Prices last refreshed %s (threshold %.0fh) — triggering a fallback refresh",
        prices_as_of.isoformat() if prices_as_of else "never",
        settings.refresh_staleness_threshold_hours,
    )
    task = asyncio.create_task(run_refresh())
    _stale_refresh_tasks.add(task)
    task.add_done_callback(_stale_refresh_tasks.discard)
