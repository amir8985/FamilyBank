from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_family, get_kid
from app.core.db import get_db
from app.models.family import Family
from app.models.kid import Kid
from app.schemas.debt import DebtTransactionCreate, DebtTransactionOut, DebtUpdateResult
from app.services import debts_db_service

router = APIRouter(prefix="/kids/{kid_id}/debt", tags=["debt"])


@router.get("", response_model=list[DebtTransactionOut])
async def list_debt_transactions(
    kid: Kid = Depends(get_kid), family: Family = Depends(get_family), db: AsyncSession = Depends(get_db)
) -> list[DebtTransactionOut]:
    rows = await debts_db_service.list_transactions_with_currency(db, kid.id, family.base_currency)
    return [
        DebtTransactionOut(
            id=r.txn.id,
            type=r.txn.type,
            amount=r.txn.amount,
            note=r.txn.note,
            is_adjustment=r.txn.is_adjustment,
            is_investment=r.txn.is_investment,
            currency=r.currency,
            previous_currency=r.previous_currency,
            balance_before=r.balance_before,
            balance_after=r.balance_after,
            created_at=r.txn.created_at,
        )
        for r in rows
    ]


@router.post("", response_model=DebtUpdateResult, status_code=201)
async def update_debt(
    body: DebtTransactionCreate,
    kid: Kid = Depends(get_kid),
    family: Family = Depends(get_family),
    db: AsyncSession = Depends(get_db),
) -> DebtUpdateResult:
    balance_before = await debts_db_service.get_balance(db, kid.id)
    txn = await debts_db_service.record_transaction(db, kid.id, body.type, body.amount, body.note)
    await db.commit()
    new_balance = await debts_db_service.get_balance(db, kid.id)
    return DebtUpdateResult(
        transaction=DebtTransactionOut(
            id=txn.id,
            type=txn.type,
            amount=txn.amount,
            note=txn.note,
            is_adjustment=txn.is_adjustment,
            is_investment=txn.is_investment,
            currency=family.base_currency,
            previous_currency=family.base_currency,
            balance_before=balance_before,
            balance_after=new_balance,
            created_at=txn.created_at,
        ),
        new_balance=new_balance,
    )
