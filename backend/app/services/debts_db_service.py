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


async def apply_currency_conversion(
    session: AsyncSession,
    kid_id: uuid.UUID,
    from_currency: str,
    to_currency: str,
    rate: Decimal,
) -> DebtTransaction | None:
    """Called when a family changes its base currency (routes_family.py).
    Existing rows are never rewritten — each one keeps the nominal amount
    it was recorded with, preserving history — instead this adds one
    adjustment row so the running balance (a signed sum of every row,
    see get_balance) comes out correctly converted. Returns None if the
    converted balance doesn't change (a zero balance, or a rate close
    enough to 1 that the delta rounds to nothing), since an adjustment
    row would be a no-op.
    """
    balance = await get_balance(session, kid_id)
    delta = (balance * rate - balance).quantize(Decimal("0.01"))
    if delta == 0:
        return None
    txn_type = DebtTransactionType.ADD if delta > 0 else DebtTransactionType.DEDUCT
    note = f"Currency changed: {from_currency} → {to_currency} (rate {rate:.4f})"
    return await record_transaction(session, kid_id, txn_type, abs(delta), note)
