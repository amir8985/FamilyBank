"""Investing service — extended per architecture 5.2 with family_id
scoping (enforced by callers passing an already-scoped Kid), read-time FX
conversion via fx_service, and atomic buy()/sell() (architecture:
"worth closing this gap now that it's a public multi-tenant app").

Read paths (get_portfolio/list_catalog/get_family_home) batch their
catalog/price/FX lookups into a handful of queries total instead of one
per asset/holding — that N+1 pattern was making /home and /catalog take
2+ seconds each against Neon's network latency.
"""

import time
import uuid
from dataclasses import dataclass
from decimal import ROUND_HALF_UP, Decimal

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import transaction
from app.models.catalog import AssetCatalog, AssetKind, PriceCache
from app.models.debt_transaction import DebtTransactionType
from app.models.investment import InvestmentHolding, InvestmentTransaction, InvestmentTransactionType
from app.models.kid import Kid
from app.services import debts_db_service, fx_service
from app.services.fx_service import RateTable


class InvestingError(ValueError):
    pass


@dataclass
class PriceContext:
    catalog: dict[str, AssetCatalog]
    prices: dict[str, PriceCache]
    rates: RateTable


# In-process cache — the catalog/price/FX data is global (not per-family)
# and the scheduler only refreshes it every few hours (spec 4.3), so
# there's no reason every single request should re-fetch it from Neon.
# This is the read side of exactly the flow described in spec 2.4: the
# scheduler pulls raw prices + FX rates a few times a day and stores
# them; every request just reads that cache and converts to the
# requesting family's currency — cheap, in-memory, no extra network hop.
# TTL is a safety net in case something writes to these tables outside
# the scheduler; `clear_price_context_cache()` (called at the end of
# every scheduler run) is what actually keeps this fresh in practice.
_PRICE_CONTEXT_TTL_SECONDS = 300
_price_context_cache: tuple[PriceContext, float] | None = None


def clear_price_context_cache() -> None:
    global _price_context_cache
    _price_context_cache = None


async def load_price_context(session: AsyncSession) -> PriceContext:
    """The whole asset catalog + price cache + FX table, cached
    in-process — callers that need more than one asset's price should
    load this once and reuse it rather than querying per-symbol."""
    global _price_context_cache

    now = time.monotonic()
    if _price_context_cache is not None:
        ctx, cached_at = _price_context_cache
        if now - cached_at < _PRICE_CONTEXT_TTL_SECONDS:
            return ctx

    catalog_rows = await session.scalars(select(AssetCatalog))
    catalog = {a.symbol: a for a in catalog_rows}

    price_rows = await session.scalars(select(PriceCache))
    prices = {p.symbol: p for p in price_rows}

    rates = await fx_service.load_all_rates(session)

    ctx = PriceContext(catalog=catalog, prices=prices, rates=rates)
    _price_context_cache = (ctx, now)
    return ctx


def _day_change(price: PriceCache) -> Decimal | None:
    history = price.history_json or []
    if len(history) < 2:
        return None
    prev_close = Decimal(str(history[-2]["close"]))
    if prev_close <= 0:
        return None
    return (price.price - prev_close) / prev_close * 100


def _catalog_sort_key(asset: AssetCatalog) -> tuple[int, str]:
    # Baskets before individual stocks (spec's kid-facing catalog should
    # lead with the simpler, diversified options), alphabetical within
    # each group.
    return (0 if asset.kind == AssetKind.BASKET else 1, asset.display_name)


def unit_step_for_price(price_per_unit: Decimal) -> Decimal:
    """The tradable unit granularity for a given price — a "nice" step so
    a single unit costs something sensible (between 1 and 10 in the
    family's currency): a $2000 stock trades in steps of 0.001, a $5
    stock in steps of 1. Mirrors the original project's
    `_unit_step_for_price` (spec section 6); the frontend's
    `defaultUnitStep` (lib/format.ts) uses the identical algorithm for
    the buy screen's +/- stepper, so the UI's step always matches what
    the backend will actually round to.
    """
    if price_per_unit <= 0:
        return Decimal("1")
    step = Decimal("1")
    if price_per_unit * step > 10:
        while price_per_unit * step > 10:
            step /= 10
    else:
        while price_per_unit * step < 1:
            step *= 10
    return step


def round_to_step(value: Decimal, step: Decimal) -> Decimal:
    """Snaps to the nearest multiple of `step`, minimum one step — never
    zero, and never a finer-grained fraction than the asset actually
    trades in (spec: if the step for a stock is 0.01, buying 0.001 of it
    isn't offered, even if that's what a raw amount/price division would
    produce)."""
    if value <= 0:
        return step
    multiples = (value / step).quantize(Decimal("1"), rounding=ROUND_HALF_UP)
    rounded = multiples * step
    return rounded if rounded > 0 else step


async def quote_purchase(
    session: AsyncSession,
    kid: Kid,
    family_currency: str,
    symbol: str,
    amount: Decimal | None,
    units: Decimal | None,
) -> dict:
    # Reuses the same in-process price/FX cache the read-only screens use
    # (load_price_context) instead of live per-call queries — both already
    # reflect the same last-scheduler-refresh snapshot, so this loses no
    # accuracy while cutting several sequential DB round-trips per call
    # (each one measured at ~400ms+ in production — see the
    # observability-logging investigation this followed from).
    ctx = await load_price_context(session)
    price = ctx.prices.get(symbol)
    if price is None:
        raise InvestingError(f"No cached price for {symbol} yet")
    price_in_family = fx_service.convert_from_table(ctx.rates, price.price, price.currency, family_currency)
    if price_in_family is None or price_in_family <= 0:
        raise InvestingError("Invalid price")

    # Snap to the asset's real tradable granularity (see unit_step_for_price)
    # — requesting "$15 of AMZN" doesn't buy exactly $15 worth at some
    # arbitrary fractional unit count; it buys the nearest whole step
    # (e.g. 0.02 units), and the actual cost — e.g. $15.91 — is what gets
    # shown and charged, not the originally requested amount.
    step = unit_step_for_price(price_in_family)
    raw_units = units if units is not None else amount / price_in_family
    units = round_to_step(raw_units, step)
    amount = (units * price_in_family).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)

    cash = await debts_db_service.get_balance(session, kid.id)
    return {
        "symbol": symbol,
        "units": units,
        "cost": amount,
        "price_per_unit": price_in_family,
        "currency": family_currency,
        "cash_available_after": cash - amount,
    }


async def buy(
    session: AsyncSession, kid: Kid, family_currency: str, symbol: str, units: Decimal
) -> InvestmentTransaction:
    async with transaction(session):
        ctx = await load_price_context(session)
        if symbol not in ctx.catalog:
            raise InvestingError(f"Unknown symbol {symbol}")

        price = ctx.prices.get(symbol)
        if price is None:
            raise InvestingError(f"No cached price for {symbol} yet")
        cost_family = fx_service.convert_from_table(ctx.rates, price.price * units, price.currency, family_currency)
        if cost_family is None:
            raise InvestingError(f"No cached FX rate for {price.currency}->{family_currency}")

        cash = await debts_db_service.get_balance(session, kid.id)
        if cost_family > cash:
            raise InvestingError("Insufficient cash available")

        await debts_db_service.record_transaction(
            session,
            kid.id,
            DebtTransactionType.DEDUCT,
            cost_family,
            note=f"Bought {units} units of {symbol}",
            is_investment=True,
        )

        holding = await session.scalar(
            select(InvestmentHolding).where(
                InvestmentHolding.kid_id == kid.id, InvestmentHolding.symbol == symbol
            )
        )
        if holding is None:
            holding = InvestmentHolding(
                kid_id=kid.id,
                symbol=symbol,
                units=units,
                avg_cost=price.price,
                avg_cost_currency=price.currency,
            )
            session.add(holding)
        else:
            total_cost = holding.avg_cost * holding.units + price.price * units
            new_units = holding.units + units
            holding.avg_cost = total_cost / new_units
            holding.units = new_units

        txn = InvestmentTransaction(
            kid_id=kid.id,
            symbol=symbol,
            units=units,
            price=price.price,
            price_currency=price.currency,
            type=InvestmentTransactionType.BUY,
        )
        session.add(txn)
        await session.flush()
        return txn


async def sell(
    session: AsyncSession, kid: Kid, family_currency: str, symbol: str, units: Decimal
) -> InvestmentTransaction:
    async with transaction(session):
        holding = await session.scalar(
            select(InvestmentHolding).where(
                InvestmentHolding.kid_id == kid.id, InvestmentHolding.symbol == symbol
            )
        )
        if holding is None or holding.units < units:
            raise InvestingError("Cannot sell more units than are held")

        ctx = await load_price_context(session)
        price = ctx.prices.get(symbol)
        if price is None:
            raise InvestingError(f"No cached price for {symbol} yet")
        proceeds_family = fx_service.convert_from_table(ctx.rates, price.price * units, price.currency, family_currency)
        if proceeds_family is None:
            raise InvestingError(f"No cached FX rate for {price.currency}->{family_currency}")

        await debts_db_service.record_transaction(
            session,
            kid.id,
            DebtTransactionType.ADD,
            proceeds_family,
            note=f"Sold {units} units of {symbol}",
            is_investment=True,
        )

        holding.units -= units
        if holding.units == 0:
            await session.delete(holding)

        txn = InvestmentTransaction(
            kid_id=kid.id,
            symbol=symbol,
            units=units,
            price=price.price,
            price_currency=price.currency,
            type=InvestmentTransactionType.SELL,
        )
        session.add(txn)
        await session.flush()
        return txn


def compute_portfolio(
    kid: Kid,
    cash: Decimal,
    holdings: list[InvestmentHolding],
    ctx: PriceContext,
    family_currency: str,
) -> dict:
    """Pure — no queries. Callers load `holdings`/`cash`/`ctx` themselves
    so get_family_home can reuse one PriceContext across every kid."""
    holdings_out = []
    holdings_value = Decimal("0")
    total_day_change = Decimal("0")

    for holding in holdings:
        price = ctx.prices.get(holding.symbol)
        if price is None:
            continue

        current_value = fx_service.convert_from_table(
            ctx.rates, price.price * holding.units, price.currency, family_currency
        )
        if current_value is None:
            # FX pair not cached yet (e.g. family just switched currency
            # ahead of the next scheduler run) — skip rather than error.
            continue
        holdings_value += current_value

        day_change_pct = _day_change(price)
        if day_change_pct is not None:
            history = price.history_json or []
            prev_close = Decimal(str(history[-2]["close"]))
            day_change_native = (price.price - prev_close) * holding.units
            day_change_family = fx_service.convert_from_table(
                ctx.rates, day_change_native, price.currency, family_currency
            )
            if day_change_family is not None:
                total_day_change += day_change_family

        since_purchase_pct = None
        if holding.avg_cost > 0:
            since_purchase_pct = (price.price - holding.avg_cost) / holding.avg_cost * 100

        catalog_entry = ctx.catalog.get(holding.symbol)
        holdings_out.append(
            {
                "symbol": holding.symbol,
                "display_name": catalog_entry.display_name if catalog_entry else holding.symbol,
                "units": holding.units,
                "current_value": current_value,
                "day_change_pct": day_change_pct,
                "since_purchase_pct": since_purchase_pct,
            }
        )

    total_value = cash + holdings_value
    prior_total = total_value - total_day_change
    total_day_change_pct = (total_day_change / prior_total * 100) if prior_total > 0 else None

    return {
        "kid_id": kid.id,
        "kid_name": kid.name,
        "cash_available": cash,
        "holdings_value": holdings_value,
        "total_value": total_value,
        "total_day_change_amount": total_day_change,
        "total_day_change_pct": total_day_change_pct,
        "holdings": holdings_out,
    }


async def get_portfolio(session: AsyncSession, kid: Kid, family_currency: str) -> dict:
    cash = await debts_db_service.get_balance(session, kid.id)
    holdings = list(
        await session.scalars(select(InvestmentHolding).where(InvestmentHolding.kid_id == kid.id))
    )
    ctx = await load_price_context(session)
    return compute_portfolio(kid, cash, holdings, ctx, family_currency)


async def get_holdings_by_kid(
    session: AsyncSession, kid_ids: list[uuid.UUID]
) -> dict[uuid.UUID, list[InvestmentHolding]]:
    if not kid_ids:
        return {}
    rows = await session.scalars(
        select(InvestmentHolding).where(InvestmentHolding.kid_id.in_(kid_ids))
    )
    by_kid: dict[uuid.UUID, list[InvestmentHolding]] = {kid_id: [] for kid_id in kid_ids}
    for holding in rows:
        by_kid[holding.kid_id].append(holding)
    return by_kid


def list_catalog(ctx: PriceContext, family_currency: str) -> list[dict]:
    out = []
    for asset in sorted(ctx.catalog.values(), key=_catalog_sort_key):
        price = ctx.prices.get(asset.symbol)
        price_family = None
        day_change_pct = None
        price_updated_at = None
        if price is not None:
            price_family = fx_service.convert_from_table(ctx.rates, price.price, price.currency, family_currency)
            day_change_pct = _day_change(price)
            price_updated_at = price.updated_at
        out.append(
            {
                "symbol": asset.symbol,
                "display_name": asset.display_name,
                "kind": asset.kind,
                "description": asset.description,
                "price": price_family,
                "price_currency": family_currency if price_family is not None else None,
                "day_change_pct": day_change_pct,
                "price_updated_at": price_updated_at,
            }
        )
    return out


async def get_asset_detail(session: AsyncSession, symbol: str, family_currency: str) -> dict | None:
    asset = await session.get(AssetCatalog, symbol)
    if asset is None:
        return None
    price = await session.get(PriceCache, symbol)
    price_family = None
    day_change_pct = None
    history: list[dict] = []
    price_updated_at = None
    if price is not None:
        try:
            price_family = await fx_service.convert(session, price.price, price.currency, family_currency)
        except ValueError:
            price_family = None
        day_change_pct = _day_change(price)
        history = price.history_json or []
        price_updated_at = price.updated_at
    return {
        "symbol": asset.symbol,
        "display_name": asset.display_name,
        "kind": asset.kind,
        "description": asset.description,
        "price": price_family,
        "price_currency": family_currency if price_family is not None else None,
        "native_currency": price.currency if price is not None else None,
        "day_change_pct": day_change_pct,
        "price_updated_at": price_updated_at,
        "history": history,
    }


async def list_investment_transactions(session: AsyncSession, kid_id: uuid.UUID) -> list[InvestmentTransaction]:
    """Buy/sell history for one kid — separate from debts_db_service's
    general debt ledger, for the kid's investment-only history view."""
    rows = await session.scalars(
        select(InvestmentTransaction)
        .where(InvestmentTransaction.kid_id == kid_id)
        .order_by(InvestmentTransaction.created_at.desc())
    )
    return list(rows)
