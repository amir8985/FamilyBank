"""FX rate fetch + cache. Refreshed on the same scheduler pass as prices
(spec 2.4) rather than a separate daily job.

Convention: a cached row (base_currency=X, quote_currency=Y, rate=r) means
"1 unit of X is worth r units of Y". `convert()` reads that row to turn an
amount priced in X into Y.
"""

from datetime import datetime, timezone
from decimal import Decimal

import httpx
from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.catalog import FxRateCache
from app.services.price_client import fetch_quote


def _yahoo_fx_symbol(base: str, quote: str) -> str:
    return f"{base}{quote}=X"


async def refresh_fx_rates(
    session: AsyncSession, client: httpx.AsyncClient, pairs: set[tuple[str, str]]
) -> None:
    now = datetime.now(timezone.utc)
    for base, quote in pairs:
        if base == quote:
            continue
        try:
            quote_data = await fetch_quote(client, _yahoo_fx_symbol(base, quote))
        except Exception:
            # Don't let one bad pair block the rest of the scheduler run;
            # the cached row just goes stale until the next pass.
            continue

        stmt = (
            insert(FxRateCache)
            .values(
                base_currency=base,
                quote_currency=quote,
                rate=Decimal(str(quote_data["price"])),
                updated_at=now,
            )
            .on_conflict_do_update(
                index_elements=["base_currency", "quote_currency"],
                set_={"rate": Decimal(str(quote_data["price"])), "updated_at": now},
            )
        )
        await session.execute(stmt)


async def get_rate(session: AsyncSession, base: str, quote: str) -> Decimal:
    if base == quote:
        return Decimal("1")
    row = await session.scalar(
        select(FxRateCache).where(
            FxRateCache.base_currency == base, FxRateCache.quote_currency == quote
        )
    )
    if row is None:
        # Fall back to the inverse pair if that's the one cached.
        inverse = await session.scalar(
            select(FxRateCache).where(
                FxRateCache.base_currency == quote, FxRateCache.quote_currency == base
            )
        )
        if inverse is not None and inverse.rate:
            return Decimal("1") / inverse.rate
        raise ValueError(f"No cached FX rate for {base}->{quote}")
    return row.rate


async def convert(session: AsyncSession, amount: Decimal, base: str, quote: str) -> Decimal:
    rate = await get_rate(session, base, quote)
    return amount * rate
