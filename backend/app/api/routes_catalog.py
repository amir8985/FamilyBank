from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_family
from app.core.db import get_db
from app.models.family import Family
from app.schemas.investing import AssetDetailOut, AssetOut
from app.services import investing_service

router = APIRouter(prefix="/catalog", tags=["catalog"])


@router.get("", response_model=list[AssetOut])
async def list_catalog(
    family: Family = Depends(get_family), db: AsyncSession = Depends(get_db)
) -> list[AssetOut]:
    ctx = await investing_service.load_price_context(db)
    rows = investing_service.list_catalog(ctx, family.base_currency)
    return [AssetOut(**r) for r in rows]


@router.get("/{symbol}", response_model=AssetDetailOut)
async def get_asset(
    symbol: str, family: Family = Depends(get_family), db: AsyncSession = Depends(get_db)
) -> AssetDetailOut:
    data = await investing_service.get_asset_detail(db, symbol, family.base_currency)
    if data is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Unknown symbol")
    return AssetDetailOut(**data)
