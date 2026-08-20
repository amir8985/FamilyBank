"""The allowance/debt ledger — near-direct port per spec 2.2. A kid's
cash balance is always derived as the signed sum of `debt_transactions`,
never stored redundantly, so buy/sell (which also write rows here) can
never drift out of sync with it.
"""

import uuid
from decimal import Decimal

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.debt_transaction import DebtTransaction, DebtTransactionType


async def get_balance(session: AsyncSession, kid_id: uuid.UUID) -> Decimal:
    signed = func.sum(
        func.case(
            (DebtTransaction.type == DebtTransactionType.ADD, DebtTransaction.amount),
            else_=-DebtTransaction.amount,
        )
    )
    total = await session.scalar(select(signed).where(DebtTransaction.kid_id == kid_id))
    return total or Decimal("0")


async def list_transactions(session: AsyncSession, kid_id: uuid.UUID) -> list[DebtTransaction]:
    result = await session.scalars(
        select(DebtTransaction)
        .where(DebtTransaction.kid_id == kid_id)
        .order_by(DebtTransaction.created_at.desc())
    )
    return list(result)


async def record_transaction(
    session: AsyncSession,
    kid_id: uuid.UUID,
    type: DebtTransactionType,
    amount: Decimal,
    note: str | None = None,
) -> DebtTransaction:
    txn = DebtTransaction(kid_id=kid_id, type=type, amount=amount, note=note)
    session.add(txn)
    await session.flush()
    return txn
