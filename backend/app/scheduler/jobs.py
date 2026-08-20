"""The one global scheduler job (architecture 5.3): refreshes price_cache
and fx_rates_cache together, 4-5x/day, for every symbol once — never
per-family, never per-request (spec 4.3).
"""

import logging
from datetime import datetime, timezone
from decimal import Decimal

import httpx
from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.currencies import SUPPORTED_CURRENCIES
from app.core.db import SessionLocal
from app.models.catalog import AssetCatalog, PriceCache
from app.services import fx_service
from app.services.investing_service import clear_price_context_cache
from app.services.price_client import PriceFetchError, fetch_quote

logger = logging.getLogger("familybank.scheduler")


async def _refresh_prices(session: AsyncSession, client: httpx.AsyncClient) -> set[str]:
    now = datetime.now(timezone.utc)
    symbols = (await session.scalars(select(AssetCatalog.symbol))).all()
    native_currencies: set[str] = set()

    for symbol in symbols:
        try:
            data = await fetch_quote(client, symbol)
        except (PriceFetchError, httpx.HTTPError) as exc:
            logger.warning("Price fetch failed for %s: %s", symbol, exc)
            continue

        native_currencies.add(data["currency"])
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

    return native_currencies


async def run_refresh() -> None:
    logger.info("Scheduler refresh starting")
    async with SessionLocal() as session:
        async with httpx.AsyncClient() as client:
            symbol_count = len((await session.scalars(select(AssetCatalog.symbol))).all())
            native_currencies = await _refresh_prices(session, client)
            await session.commit()

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
            await fx_service.refresh_fx_rates(session, client, pairs)
            await session.commit()

    # So requests right after a refresh see the new prices immediately,
    # rather than waiting out the safety-net TTL (investing_service.py).
    clear_price_context_cache()

    logger.info(
        "Scheduler refresh complete: %d symbols, %d FX pairs, at %s",
        symbol_count,
        len(pairs),
        datetime.now(timezone.utc),
    )
