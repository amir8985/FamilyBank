from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_family
from app.core.db import get_db
from app.models.family import Family
from app.models.kid import AVATAR_PALETTE, Kid

router = APIRouter(prefix="/family", tags=["family"])


class FamilySettingsOut(BaseModel):
    base_currency: str
    onboarding_completed: bool


class FamilySettingsUpdate(BaseModel):
    base_currency: str = Field(min_length=3, max_length=3)


class OnboardingRequest(BaseModel):
    base_currency: str = Field(min_length=3, max_length=3)
    # Kid names are optional — a parent can skip and use "+ Add a kid" later.
    kid_names: list[str] = Field(default_factory=list, max_length=20)


@router.get("/settings", response_model=FamilySettingsOut)
async def get_settings_route(family: Family = Depends(get_family)) -> FamilySettingsOut:
    return FamilySettingsOut(
        base_currency=family.base_currency, onboarding_completed=family.onboarding_completed
    )


@router.patch("/settings", response_model=FamilySettingsOut)
async def update_settings(
    body: FamilySettingsUpdate,
    family: Family = Depends(get_family),
    db: AsyncSession = Depends(get_db),
) -> FamilySettingsOut:
    family.base_currency = body.base_currency.upper()
    await db.commit()
    return FamilySettingsOut(
        base_currency=family.base_currency, onboarding_completed=family.onboarding_completed
    )


@router.post("/onboarding", response_model=FamilySettingsOut)
async def complete_onboarding(
    body: OnboardingRequest,
    family: Family = Depends(get_family),
    db: AsyncSession = Depends(get_db),
) -> FamilySettingsOut:
    """Spec 2.1's signup step: pick a base currency and optionally add the
    first kids, in one call, before ever reaching the home screen."""
    family.base_currency = body.base_currency.upper()
    family.onboarding_completed = True

    for i, name in enumerate(n.strip() for n in body.kid_names if n.strip()):
        db.add(Kid(family_id=family.id, name=name, avatar_color=AVATAR_PALETTE[i % len(AVATAR_PALETTE)]))

    await db.commit()
    return FamilySettingsOut(
        base_currency=family.base_currency, onboarding_completed=family.onboarding_completed
    )
