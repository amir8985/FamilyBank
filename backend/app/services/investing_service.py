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
from datetime import datetime, timezone
from decimal import ROUND_HALF_UP, Decimal

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import transaction
from app.models.catalog import AssetCatalog, AssetKind, PriceCache
from app.models.debt_transaction import DebtTransactionType
from app.models.investment import (
    InvestmentHolding,
    InvestmentLot,
    InvestmentTransaction,
    InvestmentTransactionType,
)
from app.models.family import Family
from app.models.kid import Kid
from app.services import boost_service, debts_db_service, fx_service, savings_service
from app.services.fx_service import RateTable


class InvestingError(ValueError):
    pass


@dataclass
class PriceContext:
    catalog: dict[str, AssetCatalog]
    prices: dict[str, PriceCache]
    rates: RateTable

    @property
    def prices_as_of(self) -> datetime | None:
        """When the scheduler last refreshed prices — every row a refresh
        touches gets the same timestamp (see scheduler/jobs._write_prices),
        so the newest `updated_at` is "when a refresh last completed."
        Surfaced on read responses so the frontend can cache price-derived
        data with confidence: it only goes stale every ~5h (spec 4.3)."""
        return max((p.updated_at for p in self.prices.values()), default=None)


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

    # One LEFT JOIN instead of two separate SELECTs — a symbol can exist
    # in the catalog with no PriceCache row yet (just added, scheduler
    # hasn't run), hence the outer join rather than an inner one. Each
    # round-trip to Neon costs ~300-450ms in production (see the
    # observability-logging investigation), so cutting a query here isn't
    # just tidiness — on a cold cache (TTL expiry or a scheduler refresh)
    # this is on the critical path of nearly every read endpoint in the app.
    catalog: dict[str, AssetCatalog] = {}
    prices: dict[str, PriceCache] = {}
    rows = await session.execute(select(AssetCatalog, PriceCache).outerjoin(PriceCache, PriceCache.symbol == AssetCatalog.symbol))
    for asset, price in rows:
        catalog[asset.symbol] = asset
        if price is not None:
            prices[asset.symbol] = price

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
    session: AsyncSession,
    kid: Kid,
    family_currency: str,
    symbol: str,
    units: Decimal,
    boost_buffer_rate: Decimal | None = None,
) -> InvestmentTransaction:
    """Every buy creates a new, independent InvestmentLot — never blended
    into an existing one, even for a second purchase of the same symbol
    (see models/investment.py's InvestmentLot docstring). InvestmentHolding
    (the old avg-cost model) is no longer written to by new buys; it
    stays only so kids' pre-existing holdings from before this feature
    remain sellable via sell()'s legacy path."""
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

        session.add(
            InvestmentLot(
                kid_id=kid.id,
                symbol=symbol,
                units=units,
                purchase_price=price.price,
                purchase_currency=price.currency,
                purchased_at=datetime.now(timezone.utc),
                buffer_rate=boost_buffer_rate,
            )
        )

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
    session: AsyncSession,
    kid: Kid,
    family_currency: str,
    symbol: str | None = None,
    units: Decimal | None = None,
    lot_id: uuid.UUID | None = None,
) -> InvestmentTransaction:
    """Two paths: selling a lot (lot_id + units — partial sells reduce
    the lot's units at its own locked-in rate, no merging/FIFO across
    *different* lots) or the legacy path (symbol+units, against
    InvestmentHolding's avg-cost blend, for positions bought before this
    feature existed)."""
    if lot_id is not None:
        if units is None:
            raise InvestingError("units is required when selling a lot")
        return await _sell_lot(session, kid, family_currency, lot_id, units)
    if symbol is None or units is None:
        raise InvestingError("Provide either lot_id, or both symbol and units")

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


async def _sell_lot(
    session: AsyncSession, kid: Kid, family_currency: str, lot_id: uuid.UUID, units: Decimal
) -> InvestmentTransaction:
    async with transaction(session):
        lot = await session.scalar(
            select(InvestmentLot).where(
                InvestmentLot.id == lot_id, InvestmentLot.kid_id == kid.id, InvestmentLot.is_open
            )
        )
        if lot is None or lot.units < units:
            raise InvestingError("Cannot sell more units than are held in this lot")

        synthetic_price = await boost_service.compute_lot_value(session, lot)
        proceeds_family = await fx_service.convert(
            session, synthetic_price * units, lot.purchase_currency, family_currency
        )

        await debts_db_service.record_transaction(
            session,
            kid.id,
            DebtTransactionType.ADD,
            proceeds_family,
            note=f"Sold {units} units of {lot.symbol}",
            is_investment=True,
        )

        lot.units -= units
        if lot.units == 0:
            lot.is_open = False
            lot.sold_at = datetime.now(timezone.utc)
            lot.sale_value = synthetic_price
            lot.sale_currency = lot.purchase_currency

        txn = InvestmentTransaction(
            kid_id=kid.id,
            symbol=lot.symbol,
            units=units,
            price=synthetic_price,
            price_currency=lot.purchase_currency,
            type=InvestmentTransactionType.SELL,
        )
        session.add(txn)
        await session.flush()
        return txn


async def sell_all(session: AsyncSession, kid: Kid, family_currency: str) -> list[InvestmentTransaction]:
    """Sells every open position for a kid — every open lot in full, plus
    any pre-existing legacy avg-cost holding — in one call. Backs the
    kid-facing "Sell everything" button, and is also the easiest way for
    a parent to satisfy has_open_positions's guard (change the boost
    rate) without hunting down each holding individually."""
    txns: list[InvestmentTransaction] = []

    lots = list(
        await session.scalars(
            select(InvestmentLot).where(InvestmentLot.kid_id == kid.id, InvestmentLot.is_open)
        )
    )
    for lot in lots:
        txns.append(await _sell_lot(session, kid, family_currency, lot.id, lot.units))

    legacy_holdings = list(
        await session.scalars(select(InvestmentHolding).where(InvestmentHolding.kid_id == kid.id))
    )
    for holding in legacy_holdings:
        txns.append(await sell(session, kid, family_currency, symbol=holding.symbol, units=holding.units))

    return txns


async def apply_boost_rate_change_with_rebuy(session: AsyncSession, family: Family, new_rate: Decimal | None) -> None:
    """Sells every kid's entire portfolio, changes the family's boost
    rate, then rebuys each kid the exact same positions (symbol + units)
    they held — the only way to change an *already-open* lot's rate,
    since a lot's buffer_rate locks in at purchase (see InvestmentLot's
    docstring) and Family.boost_buffer_rate can only change while no kid
    holds anything (routes_family.py's guard). Backs the "sell
    everything and rebuy" quick action offered when that guard blocks a
    parent — see routes_family.py's sell_and_rebuy endpoint.

    Every sell()/buy() call here uses its own SAVEPOINT (see
    core.db.transaction), and this function does not commit — the
    caller's single outer commit makes the whole operation atomic: if
    any step fails (e.g. a symbol's price went missing), everything
    rolls back together, never leaving the family half-migrated.
    """
    kids = list(await session.scalars(select(Kid).where(Kid.family_id == family.id)))

    # Snapshot every position *before* selling anything, so a later
    # sell()/rebuy for one kid can't be confused by an in-progress
    # change to another.
    positions: list[tuple[Kid, str, Decimal]] = []
    for kid in kids:
        lots = list(
            await session.scalars(
                select(InvestmentLot).where(InvestmentLot.kid_id == kid.id, InvestmentLot.is_open)
            )
        )
        positions.extend((kid, lot.symbol, lot.units) for lot in lots)
        legacy_holdings = list(
            await session.scalars(select(InvestmentHolding).where(InvestmentHolding.kid_id == kid.id))
        )
        positions.extend((kid, holding.symbol, holding.units) for holding in legacy_holdings)

    for kid in kids:
        await sell_all(session, kid, family.base_currency)

    family.boost_buffer_rate = new_rate

    # Every sale for every kid is already settled by this point, so each
    # kid's cash balance already reflects all of their own proceeds —
    # rebuying can't run short partway through regardless of order.
    for kid, symbol, units in positions:
        await buy(session, kid, family.base_currency, symbol, units, boost_buffer_rate=new_rate)


async def has_open_positions(session: AsyncSession, kid_ids: list[uuid.UUID]) -> bool:
    """True if any of these kids holds any stock at all — legacy
    avg-cost holdings or open lots. Backs the guard that only allows
    setting/changing Family.boost_buffer_rate while every kid's holdings
    are empty (routes_family.py) — see the model docstring for why."""
    if not kid_ids:
        return False
    legacy = await session.scalar(
        select(InvestmentHolding.id).where(InvestmentHolding.kid_id.in_(kid_ids)).limit(1)
    )
    if legacy is not None:
        return True
    lot = await session.scalar(
        select(InvestmentLot.id)
        .where(InvestmentLot.kid_id.in_(kid_ids), InvestmentLot.is_open)
        .limit(1)
    )
    return lot is not None


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
        "prices_as_of": ctx.prices_as_of,
    }


async def _lot_entry(session: AsyncSession, lot: InvestmentLot, ctx: PriceContext, family_currency: str) -> dict | None:
    series = await boost_service.compute_lot_series(session, lot)
    synthetic_price = series[-1][1]
    current_value = fx_service.convert_from_table(
        ctx.rates, synthetic_price * lot.units, lot.purchase_currency, family_currency
    )
    if current_value is None:
        return None

    since_purchase_pct = None
    if lot.purchase_price > 0:
        since_purchase_pct = (synthetic_price - lot.purchase_price) / lot.purchase_price * 100

    # "Today's wiggle" for a lot is the change since its most recent real
    # tick, not a calendar day (ticks land every few hours — see
    # boost_service) — None until there's been at least one tick since
    # purchase to compare against.
    day_change_pct = None
    if len(series) >= 2 and series[-2][1] > 0:
        day_change_pct = (series[-1][1] - series[-2][1]) / series[-2][1] * 100

    catalog_entry = ctx.catalog.get(lot.symbol)
    return {
        "lot_id": lot.id,
        "symbol": lot.symbol,
        "display_name": catalog_entry.display_name if catalog_entry else lot.symbol,
        "units": lot.units,
        "current_value": current_value,
        "day_change_pct": day_change_pct,
        "since_purchase_pct": since_purchase_pct,
        "is_boosted": bool(lot.buffer_rate),
    }


async def get_portfolio(session: AsyncSession, kid: Kid, family_currency: str) -> dict:
    cash = await debts_db_service.get_balance(session, kid.id)
    legacy_holdings = list(
        await session.scalars(select(InvestmentHolding).where(InvestmentHolding.kid_id == kid.id))
    )
    lots = list(
        await session.scalars(
            select(InvestmentLot).where(InvestmentLot.kid_id == kid.id, InvestmentLot.is_open)
        )
    )
    ctx = await load_price_context(session)

    portfolio = compute_portfolio(kid, cash, legacy_holdings, ctx, family_currency)

    for lot in lots:
        entry = await _lot_entry(session, lot, ctx, family_currency)
        if entry is None:
            continue
        portfolio["holdings"].append(entry)
        portfolio["holdings_value"] += entry["current_value"]
        portfolio["total_value"] += entry["current_value"]

    savings = await savings_service.savings_value(session, kid.id, ctx.rates, family_currency)
    portfolio["savings_value"] = savings
    portfolio["total_value"] += savings

    return portfolio


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
    # Was 3 raw per-symbol queries (asset, price, FX rate) — the one read
    # path in this module that got missed when list_catalog/get_portfolio/
    # get_family_home were batched onto load_price_context (see module
    # docstring). Same global, scheduler-refreshed cache every other read
    # path already uses; nothing here is per-family, so there's no reason
    # this endpoint should pay its own network round-trips for it.
    ctx = await load_price_context(session)
    asset = ctx.catalog.get(symbol)
    if asset is None:
        return None
    price = ctx.prices.get(symbol)
    price_family = None
    day_change_pct = None
    history: list[dict] = []
    price_updated_at = None
    if price is not None:
        price_family = fx_service.convert_from_table(ctx.rates, price.price, price.currency, family_currency)
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


async def get_lot_detail(session: AsyncSession, kid: Kid, lot_id: uuid.UUID) -> dict | None:
    """Backs the kid-facing per-lot detail screen: the same walk used for
    the headline current_value also produces the full point series, so
    the graph and the number can never disagree with each other."""
    lot = await session.scalar(
        select(InvestmentLot).where(InvestmentLot.id == lot_id, InvestmentLot.kid_id == kid.id)
    )
    if lot is None:
        return None

    # A closed lot's history is frozen at the moment it was actually
    # sold — walking ticks past sold_at would make a "final history"
    # screen keep moving even though the kid no longer holds it, and
    # sale_value (captured at sale time in _sell_lot) is the exact,
    # already-computed answer rather than something to recompute.
    series = await boost_service.compute_lot_series(session, lot, until=lot.sold_at if not lot.is_open else None)
    current_value = lot.sale_value if not lot.is_open else series[-1][1]
    since_purchase_pct = None
    if lot.purchase_price > 0:
        since_purchase_pct = (current_value - lot.purchase_price) / lot.purchase_price * 100

    catalog_entry = await session.get(AssetCatalog, lot.symbol)
    return {
        "lot_id": lot.id,
        "symbol": lot.symbol,
        "display_name": catalog_entry.display_name if catalog_entry else lot.symbol,
        "description": catalog_entry.description if catalog_entry else "",
        "units": lot.units,
        "purchase_price": lot.purchase_price,
        "purchase_currency": lot.purchase_currency,
        "purchased_at": lot.purchased_at,
        "buffer_rate": lot.buffer_rate,
        "is_open": lot.is_open,
        "sold_at": lot.sold_at,
        "current_value": current_value,
        "since_purchase_pct": since_purchase_pct,
        "series": [{"observed_at": t, "value": v} for t, v in series],
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
