from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_family
from app.core.db import get_db
from app.models.family import Family

router = APIRouter(prefix="/family", tags=["family"])


class FamilySettingsOut(BaseModel):
    base_currency: str


class FamilySettingsUpdate(BaseModel):
    base_currency: str = Field(min_length=3, max_length=3)


@router.get("/settings", response_model=FamilySettingsOut)
async def get_settings_route(family: Family = Depends(get_family)) -> FamilySettingsOut:
    return FamilySettingsOut(base_currency=family.base_currency)


@router.patch("/settings", response_model=FamilySettingsOut)
async def update_settings(
    body: FamilySettingsUpdate,
    family: Family = Depends(get_family),
    db: AsyncSession = Depends(get_db),
) -> FamilySettingsOut:
    family.base_currency = body.base_currency.upper()
    await db.commit()
    return FamilySettingsOut(base_currency=family.base_currency)
