import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import KidAndFamily, get_family, get_kid_and_family
from app.core.db import get_db
from app.models.family import Family
from app.models.savings import SavingsPlan
from app.schemas.savings import (
    SavingsDepositDetailOut,
    SavingsDepositRequest,
    SavingsOverviewOut,
    SavingsCashOutResult,
    SavingsPlanCreate,
    SavingsPlanOut,
    SavingsPlanUpdate,
    SavingsPresetOut,
    SavingsPresetToggle,
    PlanDepositOut,
)
from app.services import savings_service

router = APIRouter(tags=["savings"])


async def _plan_out(db: AsyncSession, plan: SavingsPlan, counts: dict[uuid.UUID, int] | None = None) -> SavingsPlanOut:
    if counts is None:
        counts = await savings_service.open_deposit_counts(db, plan.family_id)
    return SavingsPlanOut(
        id=plan.id,
        name=plan.name,
        monthly_rate=plan.monthly_rate,
        annual_rate=savings_service.annual_rate(plan.monthly_rate),
        lock_months=plan.lock_months,
        is_active=plan.is_active,
        open_deposit_count=counts.get(plan.id, 0),
        preset_key=plan.preset_key,
    )


async def _get_owned_plan(db: AsyncSession, family: Family, plan_id: uuid.UUID) -> SavingsPlan:
    plan = await db.get(SavingsPlan, plan_id)
    if plan is None or plan.family_id != family.id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Savings plan not found")
    return plan


@router.get("/family/savings-plans", response_model=list[SavingsPlanOut])
async def list_savings_plans(
    family: Family = Depends(get_family), db: AsyncSession = Depends(get_db)
) -> list[SavingsPlanOut]:
    plans = list(
        await db.scalars(
            select(SavingsPlan)
            .where(SavingsPlan.family_id == family.id)
            .order_by(SavingsPlan.is_active.desc(), SavingsPlan.lock_months, SavingsPlan.created_at)
        )
    )
    counts = await savings_service.open_deposit_counts(db, family.id)
    return [await _plan_out(db, p, counts) for p in plans]


@router.post("/family/savings-plans", response_model=SavingsPlanOut, status_code=201)
async def create_savings_plan(
    body: SavingsPlanCreate, family: Family = Depends(get_family), db: AsyncSession = Depends(get_db)
) -> SavingsPlanOut:
    plan = SavingsPlan(
        family_id=family.id,
        name=body.name.strip(),
        monthly_rate=body.monthly_rate,
        lock_months=body.lock_months,
    )
    db.add(plan)
    await db.commit()
    await db.refresh(plan)
    return await _plan_out(db, plan)


@router.get("/family/savings-presets", response_model=list[SavingsPresetOut])
async def list_savings_presets(family: Family = Depends(get_family)) -> list[SavingsPresetOut]:
    return [SavingsPresetOut(**p) for p in savings_service.preset_catalog()]


@router.post("/family/savings-presets", status_code=204)
async def toggle_savings_preset(
    body: SavingsPresetToggle, family: Family = Depends(get_family), db: AsyncSession = Depends(get_db)
) -> None:
    try:
        if body.active:
            await savings_service.activate_preset(db, family.id, body.key)
        else:
            await savings_service.deactivate_preset(db, family.id, body.key)
    except savings_service.SavingsError as exc:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, str(exc)) from exc
    await db.commit()


@router.get("/family/savings-plans/{plan_id}/deposits", response_model=list[PlanDepositOut])
async def list_plan_deposits(
    plan_id: uuid.UUID, family: Family = Depends(get_family), db: AsyncSession = Depends(get_db)
) -> list[PlanDepositOut]:
    plan = await _get_owned_plan(db, family, plan_id)
    rows = await savings_service.plan_deposit_breakdown(db, plan, family.base_currency)
    return [PlanDepositOut(**r) for r in rows]


@router.post("/family/savings-plans/{plan_id}/cash-out", response_model=SavingsCashOutResult)
async def cash_out_plan(
    plan_id: uuid.UUID, family: Family = Depends(get_family), db: AsyncSession = Depends(get_db)
) -> SavingsCashOutResult:
    plan = await _get_owned_plan(db, family, plan_id)
    result = await savings_service.cash_out_plan(db, plan, family.base_currency)
    await db.commit()
    return SavingsCashOutResult(**result)


@router.patch("/family/savings-plans/{plan_id}", response_model=SavingsPlanOut)
async def update_savings_plan(
    plan_id: uuid.UUID,
    body: SavingsPlanUpdate,
    family: Family = Depends(get_family),
    db: AsyncSession = Depends(get_db),
) -> SavingsPlanOut:
    """Edits only affect *new* deposits — existing SavingsDeposits keep
    the terms they were opened with (see the model docstring)."""
    plan = await _get_owned_plan(db, family, plan_id)
    if body.name is not None:
        plan.name = body.name.strip()
    if body.monthly_rate is not None:
        plan.monthly_rate = body.monthly_rate
    if body.lock_months is not None:
        plan.lock_months = body.lock_months
    if body.is_active is not None:
        plan.is_active = body.is_active
    await db.commit()
    await db.refresh(plan)
    return await _plan_out(db, plan)


@router.delete("/family/savings-plans/{plan_id}", status_code=204)
async def delete_savings_plan(
    plan_id: uuid.UUID, family: Family = Depends(get_family), db: AsyncSession = Depends(get_db)
) -> None:
    """Deposits already in this plan are untouched — plan_id is set NULL
    on them and they keep compounding on their snapshotted terms. This
    just removes the plan as a destination for new money. The frontend
    warns the parent when open_deposit_count > 0 first."""
    plan = await _get_owned_plan(db, family, plan_id)
    await db.delete(plan)
    await db.commit()


@router.get("/kids/{kid_id}/savings", response_model=SavingsOverviewOut)
async def get_kid_savings(
    kid_family: KidAndFamily = Depends(get_kid_and_family), db: AsyncSession = Depends(get_db)
) -> SavingsOverviewOut:
    data = await savings_service.build_overview(
        db, kid_family.kid, kid_family.family.id, kid_family.family.base_currency
    )
    return SavingsOverviewOut(**data)


@router.get("/kids/{kid_id}/savings/{deposit_id}", response_model=SavingsDepositDetailOut)
async def get_kid_savings_deposit(
    deposit_id: uuid.UUID,
    kid_family: KidAndFamily = Depends(get_kid_and_family),
    db: AsyncSession = Depends(get_db),
) -> SavingsDepositDetailOut:
    data = await savings_service.get_deposit_detail(
        db, kid_family.kid, deposit_id, kid_family.family.base_currency
    )
    if data is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Savings deposit not found")
    return SavingsDepositDetailOut(**data)


@router.post("/kids/{kid_id}/savings/deposit", response_model=SavingsDepositDetailOut, status_code=201)
async def deposit_into_savings(
    body: SavingsDepositRequest,
    kid_family: KidAndFamily = Depends(get_kid_and_family),
    db: AsyncSession = Depends(get_db),
) -> SavingsDepositDetailOut:
    kid, family = kid_family.kid, kid_family.family
    plan = await _get_owned_plan(db, family, body.plan_id)
    try:
        deposit = await savings_service.create_deposit(db, kid, plan, body.amount, family.base_currency)
    except savings_service.SavingsError as exc:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, str(exc)) from exc
    await db.commit()
    data = await savings_service.get_deposit_detail(db, kid, deposit.id, family.base_currency)
    return SavingsDepositDetailOut(**data)


@router.post("/kids/{kid_id}/savings/{deposit_id}/withdraw", response_model=SavingsDepositDetailOut)
async def withdraw_from_savings(
    deposit_id: uuid.UUID,
    kid_family: KidAndFamily = Depends(get_kid_and_family),
    db: AsyncSession = Depends(get_db),
) -> SavingsDepositDetailOut:
    kid, family = kid_family.kid, kid_family.family
    try:
        await savings_service.withdraw_deposit(db, kid, deposit_id, family.base_currency)
    except savings_service.SavingsError as exc:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, str(exc)) from exc
    await db.commit()
    data = await savings_service.get_deposit_detail(db, kid, deposit_id, family.base_currency)
    return SavingsDepositDetailOut(**data)
