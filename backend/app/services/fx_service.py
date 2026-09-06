"""FX rate fetch + cache. Refreshed on the same scheduler pass as prices
(spec 2.4) rather than a separate daily job.

Convention: a cached row (base_currency=X, quote_currency=Y, rate=r) means
"1 unit of X is worth r units of Y". `convert()` reads that row to turn an
amount priced in X into Y.
"""

from datetime import datetime
from decimal import Decimal

import httpx
from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.catalog import FxRateCache
from app.services.price_client import fetch_quote


def _yahoo_fx_symbol(base: str, quote: str) -> str:
    return f"{base}{quote}=X"


async def fetch_fx_rates(
    client: httpx.AsyncClient, pairs: set[tuple[str, str]]
) -> list[tuple[str, str, Decimal]]:
    """Fetches every pair's rate from Yahoo — no DB session involved (see
    scheduler/jobs.py's _fetch_prices for why that matters)."""
    rates = []
    for base, quote in pairs:
        if base == quote:
            continue
        try:
            quote_data = await fetch_quote(client, _yahoo_fx_symbol(base, quote))
        except Exception:
            # Don't let one bad pair block the rest of the scheduler run;
            # the cached row just goes stale until the next pass.
            continue
        rates.append((base, quote, Decimal(str(quote_data["price"]))))
    return rates


async def write_fx_rates(
    session: AsyncSession, rates: list[tuple[str, str, Decimal]], now: datetime
) -> None:
    for base, quote, rate in rates:
        stmt = (
            insert(FxRateCache)
            .values(base_currency=base, quote_currency=quote, rate=rate, updated_at=now)
            .on_conflict_do_update(
                index_elements=["base_currency", "quote_currency"],
                set_={"rate": rate, "updated_at": now},
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
    if row is not None:
        return row.rate

    # Fall back to the inverse pair if that's the one cached.
    inverse = await session.scalar(
        select(FxRateCache).where(
            FxRateCache.base_currency == quote, FxRateCache.quote_currency == base
        )
    )
    if inverse is not None and inverse.rate:
        return Decimal("1") / inverse.rate

    # Neither leg is cached directly — the scheduler only ever caches
    # pairs against USD (see scheduler/jobs.py), so any other pair has
    # to triangulate through it rather than fail outright.
    if base != "USD" and quote != "USD":
        try:
            base_to_usd = await get_rate(session, base, "USD")
            usd_to_quote = await get_rate(session, "USD", quote)
            return base_to_usd * usd_to_quote
        except ValueError:
            pass

    raise ValueError(f"No cached FX rate for {base}->{quote}")


async def convert(session: AsyncSession, amount: Decimal, base: str, quote: str) -> Decimal:
    rate = await get_rate(session, base, quote)
    return amount * rate


RateTable = dict[tuple[str, str], Decimal]


async def load_all_rates(session: AsyncSession) -> RateTable:
    """One query for every cached FX rate — used by list/portfolio views
    that need to convert many prices at once, so they don't run one FX
    query per asset/holding (that N+1 pattern is what made /home and
    /catalog take 2+ seconds each against Neon's network latency)."""
    rows = await session.execute(select(FxRateCache.base_currency, FxRateCache.quote_currency, FxRateCache.rate))
    return {(base, quote): rate for base, quote, rate in rows}


def rate_from_table(rates: RateTable, base: str, quote: str) -> Decimal | None:
    if base == quote:
        return Decimal("1")
    if (base, quote) in rates:
        return rates[(base, quote)]
    inverse = rates.get((quote, base))
    if inverse:
        return Decimal("1") / inverse

    # Same triangulation fallback as get_rate() — see its comment.
    if base != "USD" and quote != "USD":
        base_to_usd = rate_from_table(rates, base, "USD")
        usd_to_quote = rate_from_table(rates, "USD", quote)
        if base_to_usd is not None and usd_to_quote is not None:
            return base_to_usd * usd_to_quote

    return None


def convert_from_table(rates: RateTable, amount: Decimal, base: str, quote: str) -> Decimal | None:
    rate = rate_from_table(rates, base, quote)
    return amount * rate if rate is not None else None
