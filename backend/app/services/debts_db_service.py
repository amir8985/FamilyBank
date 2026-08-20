"""The allowance/debt ledger — near-direct port per spec 2.2. A kid's
cash balance is always derived as the signed sum of `debt_transactions`,
never stored redundantly, so buy/sell (which also write rows here) can
never drift out of sync with it.
"""

import uuid
from decimal import Decimal

from sqlalchemy import case, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.debt_transaction import DebtTransaction, DebtTransactionType


def _signed_amount():
    return case(
        (DebtTransaction.type == DebtTransactionType.ADD, DebtTransaction.amount),
        else_=-DebtTransaction.amount,
    )


async def get_balance(session: AsyncSession, kid_id: uuid.UUID) -> Decimal:
    total = await session.scalar(
        select(func.sum(_signed_amount())).where(DebtTransaction.kid_id == kid_id)
    )
    return total if total is not None else Decimal("0.00")


async def get_balances(session: AsyncSession, kid_ids: list[uuid.UUID]) -> dict[uuid.UUID, Decimal]:
    """Batched version of get_balance — one query for every kid on the
    home screen instead of one query per kid (see routes_kids.py)."""
    if not kid_ids:
        return {}
    rows = await session.execute(
        select(DebtTransaction.kid_id, func.sum(_signed_amount()))
        .where(DebtTransaction.kid_id.in_(kid_ids))
        .group_by(DebtTransaction.kid_id)
    )
    balances = {kid_id: total for kid_id, total in rows}
    return {kid_id: balances.get(kid_id, Decimal("0.00")) for kid_id in kid_ids}


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
