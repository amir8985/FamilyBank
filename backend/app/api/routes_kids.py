import uuid
from decimal import Decimal

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_family, get_kid
from app.core.db import get_db
from app.core.security import AuthContext, get_current_auth
from app.models.family import Family
from app.models.kid import AVATAR_PALETTE, Kid
from app.schemas.kid import FamilyHome, KidCreate, KidSummary
from app.services import debts_db_service, investing_service

router = APIRouter(tags=["kids"])


@router.get("/home", response_model=FamilyHome)
async def get_family_home(
    family: Family = Depends(get_family), db: AsyncSession = Depends(get_db)
) -> FamilyHome:
    kids = (await db.scalars(select(Kid).where(Kid.family_id == family.id).order_by(Kid.created_at))).all()
    kid_ids = [kid.id for kid in kids]

    # Everything below is 3 fixed queries total (context) + 2 batched
    # queries (balances, holdings) regardless of how many kids/holdings
    # there are — was previously 1 + N*(1 + M) queries per kid/holding.
    ctx = await investing_service.load_price_context(db)
    balances = await debts_db_service.get_balances(db, kid_ids)
    holdings_by_kid = await investing_service.get_holdings_by_kid(db, kid_ids)

    summaries = []
    total_owed = Decimal("0")
    total_invested = Decimal("0")
    for kid in kids:
        cash = balances[kid.id]
        portfolio = investing_service.compute_portfolio(kid, cash, holdings_by_kid[kid.id], ctx, family.base_currency)
        total_owed += cash
        total_invested += portfolio["holdings_value"]
        summaries.append(
            KidSummary(
                id=kid.id,
                name=kid.name,
                avatar_color=kid.avatar_color,
                cash_balance=cash,
                portfolio_value=portfolio["holdings_value"],
                portfolio_day_change_pct=portfolio["total_day_change_pct"],
            )
        )

    return FamilyHome(
        base_currency=family.base_currency, total_owed=total_owed, total_invested=total_invested, kids=summaries
    )


@router.post("/kids", response_model=KidSummary, status_code=201)
async def create_kid(
    body: KidCreate,
    auth: AuthContext = Depends(get_current_auth),
    db: AsyncSession = Depends(get_db),
) -> KidSummary:
    count = len((await db.scalars(select(Kid.id).where(Kid.family_id == auth.family_id))).all())
    color = AVATAR_PALETTE[count % len(AVATAR_PALETTE)]

    kid = Kid(family_id=auth.family_id, name=body.name, avatar_color=color)
    db.add(kid)
    await db.commit()
    await db.refresh(kid)

    return KidSummary(
        id=kid.id,
        name=kid.name,
        avatar_color=kid.avatar_color,
        cash_balance=0,
        portfolio_value=0,
        portfolio_day_change_pct=None,
    )


@router.delete("/kids/{kid_id}", status_code=204)
async def delete_kid(kid: Kid = Depends(get_kid), db: AsyncSession = Depends(get_db)) -> None:
    await db.delete(kid)
    await db.commit()
