from decimal import Decimal

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import KidAndFamily, get_kid_and_family
from app.core.db import get_db
from app.models.debt_transaction import DebtTransaction, DebtTransactionType
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
        is_savings=txn.is_savings,
        currency=currency,
        previous_currency=previous_currency,
        balance_before=balance_before,
        balance_after=balance_after,
        created_at=txn.created_at,
    )


@router.get("", response_model=list[DebtTransactionOut])
async def list_debt_transactions(
    kid_family: KidAndFamily = Depends(get_kid_and_family), db: AsyncSession = Depends(get_db)
) -> list[DebtTransactionOut]:
    kid, family = kid_family.kid, kid_family.family
    rows = await debts_db_service.list_transactions_with_currency(db, kid.id, family.base_currency)
    return [_to_out(r.txn, r.currency, r.previous_currency, r.balance_before, r.balance_after) for r in rows]


@router.post("", response_model=DebtUpdateResult, status_code=201)
async def update_debt(
    body: DebtTransactionCreate,
    kid_family: KidAndFamily = Depends(get_kid_and_family),
    db: AsyncSession = Depends(get_db),
) -> DebtUpdateResult:
    kid, family = kid_family.kid, kid_family.family
    balance_before = await debts_db_service.get_balance(db, kid.id)
    txn = await debts_db_service.record_transaction(db, kid.id, body.type, body.amount, body.note)
    await db.commit()
    # new_balance = balance_before ± what was just recorded, computed in
    # Python instead of a second full-ledger SUM query — get_balance is a
    # SUM(...) over every one of this kid's debt_transactions rows, so
    # re-running it here cost a full extra round-trip (measured at
    # ~1.1s in production — see CLAUDE.md) for a number this handler
    # already knows exactly. Also more correct, not just faster: a
    # second SUM could reflect a *different* write landing between this
    # commit and that query (e.g. a concurrent buy/sell for the same
    # kid), which would silently mislabel this response's "new balance"
    # with a number this transaction didn't actually produce.
    new_balance = balance_before + (body.amount if body.type == DebtTransactionType.ADD else -body.amount)
    return DebtUpdateResult(
        transaction=_to_out(txn, family.base_currency, family.base_currency, balance_before, new_balance),
        new_balance=new_balance,
    )
