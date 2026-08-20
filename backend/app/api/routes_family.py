import uuid
from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_family
from app.core.currencies import SUPPORTED_CURRENCIES
from app.core.db import get_db, transaction
from app.models.family import Family
from app.models.kid import AVATAR_PALETTE, Kid
from app.services import debts_db_service, fx_service

router = APIRouter(prefix="/family", tags=["family"])

# Shared by both the preview and the real change below — a rate lookup
# failure means the scheduler hasn't cached this pair yet (very unlikely
# after the fix in scheduler/jobs.py, but the change must never silently
# go through with the wrong balances if it somehow happens).
_RATE_UNAVAILABLE_DETAIL = (
    "Exchange rate not available yet for this currency — try again in a few minutes."
)


class FamilySettingsOut(BaseModel):
    base_currency: str
    onboarding_completed: bool


class FamilySettingsUpdate(BaseModel):
    base_currency: str = Field(min_length=3, max_length=3)


class OnboardingRequest(BaseModel):
    base_currency: str = Field(min_length=3, max_length=3)
    # Kid names are optional — a parent can skip and use "+ Add a kid" later.
    kid_names: list[str] = Field(default_factory=list, max_length=20)


class KidCurrencyPreview(BaseModel):
    kid_id: uuid.UUID
    name: str
    old_cash_balance: Decimal
    new_cash_balance: Decimal


class CurrencyChangePreviewOut(BaseModel):
    from_currency: str
    to_currency: str
    rate: Decimal
    kids: list[KidCurrencyPreview]


def _validated_currency(code: str) -> str:
    code = code.upper()
    if code not in SUPPORTED_CURRENCIES:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, f"Unsupported currency: {code}")
    return code


@router.get("/settings", response_model=FamilySettingsOut)
async def get_settings_route(family: Family = Depends(get_family)) -> FamilySettingsOut:
    return FamilySettingsOut(
        base_currency=family.base_currency, onboarding_completed=family.onboarding_completed
    )


@router.get("/settings/currency-preview", response_model=CurrencyChangePreviewOut)
async def preview_currency_change(
    to: str,
    family: Family = Depends(get_family),
    db: AsyncSession = Depends(get_db),
) -> CurrencyChangePreviewOut:
    """Powers the warning dialog: shows each kid's balance converted at
    today's rate *before* the parent commits to the change (spec ask —
    changing currency is rare and destructive enough that a silent,
    unexplained switch isn't acceptable)."""
    to_currency = _validated_currency(to)
    if to_currency == family.base_currency:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Already using that currency")

    try:
        rate = await fx_service.get_rate(db, family.base_currency, to_currency)
    except ValueError as exc:
        raise HTTPException(status.HTTP_409_CONFLICT, _RATE_UNAVAILABLE_DETAIL) from exc

    kids = (await db.scalars(select(Kid).where(Kid.family_id == family.id).order_by(Kid.created_at))).all()
    kid_previews = []
    for kid in kids:
        old_balance = await debts_db_service.get_balance(db, kid.id)
        new_balance = (old_balance * rate).quantize(Decimal("0.01"))
        kid_previews.append(
            KidCurrencyPreview(
                kid_id=kid.id, name=kid.name, old_cash_balance=old_balance, new_cash_balance=new_balance
            )
        )

    return CurrencyChangePreviewOut(
        from_currency=family.base_currency, to_currency=to_currency, rate=rate, kids=kid_previews
    )


@router.patch("/settings", response_model=FamilySettingsOut)
async def update_settings(
    body: FamilySettingsUpdate,
    family: Family = Depends(get_family),
    db: AsyncSession = Depends(get_db),
) -> FamilySettingsOut:
    new_currency = _validated_currency(body.base_currency)

    if new_currency != family.base_currency:
        try:
            rate = await fx_service.get_rate(db, family.base_currency, new_currency)
        except ValueError as exc:
            raise HTTPException(status.HTTP_409_CONFLICT, _RATE_UNAVAILABLE_DETAIL) from exc

        old_currency = family.base_currency
        async with transaction(db):
            kids = (await db.scalars(select(Kid).where(Kid.family_id == family.id))).all()
            for kid in kids:
                await debts_db_service.apply_currency_conversion(db, kid.id, old_currency, new_currency, rate)
            family.base_currency = new_currency

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
    family.base_currency = _validated_currency(body.base_currency)
    family.onboarding_completed = True

    for i, name in enumerate(n.strip() for n in body.kid_names if n.strip()):
        db.add(Kid(family_id=family.id, name=name, avatar_color=AVATAR_PALETTE[i % len(AVATAR_PALETTE)]))

    await db.commit()
    return FamilySettingsOut(
        base_currency=family.base_currency, onboarding_completed=family.onboarding_completed
    )
