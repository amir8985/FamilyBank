import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import KidAndFamily, get_kid, get_kid_and_family
from app.core.db import get_db
from app.models.kid import Kid
from app.schemas.investing import (
    BuyRequest,
    BuySellQuoteRequest,
    BuySellQuoteResponse,
    InvestmentTransactionOut,
    LotDetailOut,
    PortfolioOut,
    SellRequest,
)
from app.services import investing_service

router = APIRouter(prefix="/kids/{kid_id}", tags=["investing"])


@router.get("/portfolio", response_model=PortfolioOut)
async def get_portfolio(
    kid_family: KidAndFamily = Depends(get_kid_and_family),
    db: AsyncSession = Depends(get_db),
) -> PortfolioOut:
    data = await investing_service.get_portfolio(db, kid_family.kid, kid_family.family.base_currency)
    data["boost_buffer_rate"] = kid_family.family.boost_buffer_rate
    return PortfolioOut(**data)


@router.get("/investment-transactions", response_model=list[InvestmentTransactionOut])
async def list_investment_transactions(
    kid: Kid = Depends(get_kid), db: AsyncSession = Depends(get_db)
) -> list[InvestmentTransactionOut]:
    rows = await investing_service.list_investment_transactions(db, kid.id)
    return [InvestmentTransactionOut.model_validate(r, from_attributes=True) for r in rows]


@router.post("/quote", response_model=BuySellQuoteResponse)
async def quote_purchase(
    body: BuySellQuoteRequest,
    kid_family: KidAndFamily = Depends(get_kid_and_family),
    db: AsyncSession = Depends(get_db),
) -> BuySellQuoteResponse:
    kid, family = kid_family.kid, kid_family.family
    try:
        data = await investing_service.quote_purchase(
            db, kid, family.base_currency, body.symbol, body.amount, body.units
        )
    except investing_service.InvestingError as exc:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, str(exc)) from exc
    return BuySellQuoteResponse(**data)


@router.post("/buy", response_model=InvestmentTransactionOut, status_code=201)
async def buy(
    body: BuyRequest,
    kid_family: KidAndFamily = Depends(get_kid_and_family),
    db: AsyncSession = Depends(get_db),
) -> InvestmentTransactionOut:
    kid, family = kid_family.kid, kid_family.family
    try:
        txn = await investing_service.buy(
            db, kid, family.base_currency, body.symbol, body.units, boost_buffer_rate=family.boost_buffer_rate
        )
    except investing_service.InvestingError as exc:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, str(exc)) from exc
    # buy()'s internal db.transaction() only opens a real transaction if
    # one wasn't already running (see db.py) — since get_kid_and_family
    # already autobegin one, this commit is what actually persists it.
    await db.commit()
    return InvestmentTransactionOut.model_validate(txn, from_attributes=True)


@router.post("/sell", response_model=InvestmentTransactionOut, status_code=201)
async def sell(
    body: SellRequest,
    kid_family: KidAndFamily = Depends(get_kid_and_family),
    db: AsyncSession = Depends(get_db),
) -> InvestmentTransactionOut:
    kid, family = kid_family.kid, kid_family.family
    try:
        txn = await investing_service.sell(
            db, kid, family.base_currency, symbol=body.symbol, units=body.units, lot_id=body.lot_id
        )
    except investing_service.InvestingError as exc:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, str(exc)) from exc
    await db.commit()  # see buy() above for why this is needed, not redundant
    return InvestmentTransactionOut.model_validate(txn, from_attributes=True)


@router.post("/sell-all", response_model=list[InvestmentTransactionOut])
async def sell_all(
    kid_family: KidAndFamily = Depends(get_kid_and_family),
    db: AsyncSession = Depends(get_db),
) -> list[InvestmentTransactionOut]:
    kid, family = kid_family.kid, kid_family.family
    txns = await investing_service.sell_all(db, kid, family.base_currency)
    await db.commit()  # see buy() above for why this is needed, not redundant
    return [InvestmentTransactionOut.model_validate(t, from_attributes=True) for t in txns]


@router.get("/lots/{lot_id}", response_model=LotDetailOut)
async def get_lot_detail(
    lot_id: uuid.UUID,
    kid: Kid = Depends(get_kid),
    db: AsyncSession = Depends(get_db),
) -> LotDetailOut:
    data = await investing_service.get_lot_detail(db, kid, lot_id)
    if data is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Lot not found")
    return LotDetailOut(**data)
