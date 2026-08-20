"""Investing service — extended per architecture 5.2 with family_id
scoping (enforced by callers passing an already-scoped Kid), read-time FX
conversion via fx_service, and atomic buy()/sell() (architecture:
"worth closing this gap now that it's a public multi-tenant app").
"""

import uuid
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import transaction
from app.models.catalog import AssetCatalog, PriceCache
from app.models.debt_transaction import DebtTransactionType
from app.models.investment import InvestmentHolding, InvestmentTransaction, InvestmentTransactionType
from app.models.kid import Kid
from app.services import debts_db_service, fx_service


class InvestingError(ValueError):
    pass


async def _get_price(session: AsyncSession, symbol: str) -> PriceCache:
    price = await session.get(PriceCache, symbol)
    if price is None:
        raise InvestingError(f"No cached price for {symbol} yet")
    return price


async def _price_in_currency(session: AsyncSession, price: PriceCache, target_currency: str) -> Decimal:
    return await fx_service.convert(session, price.price, price.currency, target_currency)


async def quote_purchase(
    session: AsyncSession,
    kid: Kid,
    family_currency: str,
    symbol: str,
    amount: Decimal | None,
    units: Decimal | None,
) -> dict:
    price = await _get_price(session, symbol)
    price_in_family = await _price_in_currency(session, price, family_currency)
    if price_in_family <= 0:
        raise InvestingError("Invalid price")

    if units is None:
        units = amount / price_in_family
    else:
        amount = units * price_in_family

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
        catalog_entry = await session.get(AssetCatalog, symbol)
        if catalog_entry is None:
            raise InvestingError(f"Unknown symbol {symbol}")

        price = await _get_price(session, symbol)
        cost_family = await fx_service.convert(session, price.price * units, price.currency, family_currency)

        cash = await debts_db_service.get_balance(session, kid.id)
        if cost_family > cash:
            raise InvestingError("Insufficient cash available")

        await debts_db_service.record_transaction(
            session,
            kid.id,
            DebtTransactionType.DEDUCT,
            cost_family,
            note=f"Bought {units} units of {symbol}",
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

        price = await _get_price(session, symbol)
        proceeds_family = await fx_service.convert(session, price.price * units, price.currency, family_currency)

        await debts_db_service.record_transaction(
            session,
            kid.id,
            DebtTransactionType.ADD,
            proceeds_family,
            note=f"Sold {units} units of {symbol}",
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


async def get_portfolio(session: AsyncSession, kid: Kid, family_currency: str) -> dict:
    cash = await debts_db_service.get_balance(session, kid.id)

    holdings_rows = await session.scalars(
        select(InvestmentHolding).where(InvestmentHolding.kid_id == kid.id)
    )
    holdings_out = []
    holdings_value = Decimal("0")
    total_day_change = Decimal("0")

    for holding in holdings_rows:
        catalog_entry = await session.get(AssetCatalog, holding.symbol)
        price = await session.get(PriceCache, holding.symbol)
        if price is None:
            continue

        current_value = await fx_service.convert(
            session, price.price * holding.units, price.currency, family_currency
        )
        holdings_value += current_value

        day_change_pct = None
        history = price.history_json or []
        if len(history) >= 2:
            prev_close = Decimal(str(history[-2]["close"]))
            if prev_close > 0:
                day_change_pct = (price.price - prev_close) / prev_close * 100
                day_change_native = (price.price - prev_close) * holding.units
                total_day_change += await fx_service.convert(
                    session, day_change_native, price.currency, family_currency
                )

        holdings_out.append(
            {
                "symbol": holding.symbol,
                "display_name": catalog_entry.display_name if catalog_entry else holding.symbol,
                "units": holding.units,
                "current_value": current_value,
                "day_change_pct": day_change_pct,
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


async def list_catalog(session: AsyncSession, family_currency: str) -> list[dict]:
    catalog_rows = await session.scalars(select(AssetCatalog))
    out = []
    for asset in catalog_rows:
        price = await session.get(PriceCache, asset.symbol)
        price_family = None
        day_change_pct = None
        if price is not None:
            price_family = await _price_in_currency(session, price, family_currency)
            history = price.history_json or []
            if len(history) >= 2:
                prev_close = Decimal(str(history[-2]["close"]))
                if prev_close > 0:
                    day_change_pct = (price.price - prev_close) / prev_close * 100
        out.append(
            {
                "symbol": asset.symbol,
                "display_name": asset.display_name,
                "kind": asset.kind,
                "description": asset.description,
                "price": price_family,
                "price_currency": family_currency if price_family is not None else None,
                "day_change_pct": day_change_pct,
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
    if price is not None:
        price_family = await _price_in_currency(session, price, family_currency)
        history = price.history_json or []
        if len(history) >= 2:
            prev_close = Decimal(str(history[-2]["close"]))
            if prev_close > 0:
                day_change_pct = (price.price - prev_close) / prev_close * 100
    return {
        "symbol": asset.symbol,
        "display_name": asset.display_name,
        "kind": asset.kind,
        "description": asset.description,
        "price": price_family,
        "price_currency": family_currency if price_family is not None else None,
        "native_currency": price.currency if price is not None else None,
        "day_change_pct": day_change_pct,
        "history": history,
    }
