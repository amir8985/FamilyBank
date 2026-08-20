from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_kid
from app.core.db import get_db
from app.models.kid import Kid
from app.schemas.debt import DebtTransactionCreate, DebtTransactionOut, DebtUpdateResult
from app.services import debts_db_service

router = APIRouter(prefix="/kids/{kid_id}/debt", tags=["debt"])


@router.get("", response_model=list[DebtTransactionOut])
async def list_debt_transactions(
    kid: Kid = Depends(get_kid), db: AsyncSession = Depends(get_db)
) -> list[DebtTransactionOut]:
    rows = await debts_db_service.list_transactions(db, kid.id)
    return [DebtTransactionOut.model_validate(r, from_attributes=True) for r in rows]


@router.post("", response_model=DebtUpdateResult, status_code=201)
async def update_debt(
    body: DebtTransactionCreate,
    kid: Kid = Depends(get_kid),
    db: AsyncSession = Depends(get_db),
) -> DebtUpdateResult:
    txn = await debts_db_service.record_transaction(db, kid.id, body.type, body.amount, body.note)
    await db.commit()
    new_balance = await debts_db_service.get_balance(db, kid.id)
    return DebtUpdateResult(
        transaction=DebtTransactionOut.model_validate(txn, from_attributes=True),
        new_balance=new_balance,
    )
