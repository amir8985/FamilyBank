"""The one global scheduler job (architecture 5.3): refreshes price_cache
and fx_rates_cache together, 4-5x/day, for every symbol once — never
per-family, never per-request (spec 4.3).
"""

import logging
from datetime import datetime, timezone
from decimal import Decimal

import httpx
from sqlalchemy import func, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.currencies import SUPPORTED_CURRENCIES
from app.core.db import SessionLocal
from app.models.catalog import AssetCatalog, PriceCache
from app.services import fx_service
from app.services.investing_service import clear_price_context_cache
from app.services.price_client import PriceFetchError, fetch_quote

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


async def run_refresh() -> None:
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

    logger.info(
        "Scheduler refresh complete: %d symbols, %d FX pairs, at %s",
        len(symbols),
        len(pairs),
        datetime.now(timezone.utc),
    )
