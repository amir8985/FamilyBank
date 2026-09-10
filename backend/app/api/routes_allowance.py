from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import KidAndFamily, get_family, get_kid_and_family, require_parent
from app.core.db import get_db
from app.models.family import Family
from app.models.kid import Kid
from app.schemas.allowance import (
    AllowanceOut,
    AllowanceUpsert,
    BulkAllowanceUpsert,
    FamilyAllowancesOut,
)
from app.services import allowance_service

router = APIRouter(tags=["allowance"])


@router.get("/kids/{kid_id}/allowance", response_model=AllowanceOut)
async def get_kid_allowance(
    kid_family: KidAndFamily = Depends(get_kid_and_family),
    db: AsyncSession = Depends(get_db),
) -> AllowanceOut:
    """The kid's allowance summary — amount, schedule, last/next payday,
    recent payouts. Reachable by the kid themselves or their parent.
    Settles anything due first."""
    view = await allowance_service.build_view(db, kid_family.kid, kid_family.family)
    await db.commit()
    return AllowanceOut(**view)


@router.put(
    "/kids/{kid_id}/allowance",
    response_model=AllowanceOut,
    dependencies=[Depends(require_parent)],
)
async def upsert_kid_allowance(
    body: AllowanceUpsert,
    kid_family: KidAndFamily = Depends(get_kid_and_family),
    db: AsyncSession = Depends(get_db),
) -> AllowanceOut:
    try:
        await allowance_service.upsert_allowance(
            db,
            kid_family.kid,
            kid_family.family,
            amount=body.amount,
            cadence=body.cadence,
            payday=body.payday,
        )
    except allowance_service.AllowanceError as exc:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, str(exc)) from exc
    await db.commit()
    view = await allowance_service.build_view(db, kid_family.kid, kid_family.family)
    await db.commit()
    return AllowanceOut(**view)


@router.delete(
    "/kids/{kid_id}/allowance",
    status_code=204,
    dependencies=[Depends(require_parent)],
)
async def delete_kid_allowance(
    kid_family: KidAndFamily = Depends(get_kid_and_family),
    db: AsyncSession = Depends(get_db),
) -> None:
    await allowance_service.delete_allowance(db, kid_family.kid.id)
    await db.commit()


async def _family_view(db: AsyncSession, family: Family) -> FamilyAllowancesOut:
    kids = list(
        await db.scalars(select(Kid).where(Kid.family_id == family.id).order_by(Kid.created_at))
    )
    views = await allowance_service.build_family_views(db, family, kids)
    await db.commit()
    return FamilyAllowancesOut(
        base_currency=family.base_currency, kids=[AllowanceOut(**v) for v in views]
    )


@router.get("/family/allowances", response_model=FamilyAllowancesOut)
async def list_family_allowances(
    family: Family = Depends(get_family), db: AsyncSession = Depends(get_db)
) -> FamilyAllowancesOut:
    return await _family_view(db, family)


@router.post("/family/allowances", response_model=FamilyAllowancesOut)
async def set_family_allowance(
    body: BulkAllowanceUpsert,
    family: Family = Depends(get_family),
    db: AsyncSession = Depends(get_db),
) -> FamilyAllowancesOut:
    """Apply one allowance to every kid in the family at once."""
    kids = list(await db.scalars(select(Kid).where(Kid.family_id == family.id)))
    if not kids:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Add a kid first")
    try:
        for kid in kids:
            await allowance_service.upsert_allowance(
                db,
                kid,
                family,
                amount=body.amount,
                cadence=body.cadence,
                payday=body.payday,
            )
    except allowance_service.AllowanceError as exc:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, str(exc)) from exc
    await db.commit()
    return await _family_view(db, family)