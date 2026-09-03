from decimal import Decimal

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_family, get_kid
from app.core.db import get_db
from app.models.debt_transaction import DebtTransaction
from app.models.family import Family
from app.models.kid import Kid
from app.schemas.debt import DebtTransactionCreate, DebtTransactionOut, DebtUpdateResult
from app.services import debts_db_service

router = APIRouter(prefix="/kids/{kid_id}/debt", tags=["debt"])


def _to_out(
    txn: DebtTransaction, currency: str, previous_currency: str, balance_before: Decimal, balance_after: Decimal
) -> DebtTransactionOut:
    return DebtTransactionOut(
        id=txn.id,
        type=txn.type,
        amount=txn.amount,
        note=txn.note,
        is_adjustment=txn.is_adjustment,
        is_investment=txn.is_investment,
        currency=currency,
        previous_currency=previous_currency,
        balance_before=balance_before,
        balance_after=balance_after,
        created_at=txn.created_at,
    )


@router.get("", response_model=list[DebtTransactionOut])
async def list_debt_transactions(
    kid: Kid = Depends(get_kid), family: Family = Depends(get_family), db: AsyncSession = Depends(get_db)
) -> list[DebtTransactionOut]:
    rows = await debts_db_service.list_transactions_with_currency(db, kid.id, family.base_currency)
    return [_to_out(r.txn, r.currency, r.previous_currency, r.balance_before, r.balance_after) for r in rows]


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
        transaction=_to_out(txn, family.base_currency, family.base_currency, balance_before, new_balance),
        new_balance=new_balance,
    )
