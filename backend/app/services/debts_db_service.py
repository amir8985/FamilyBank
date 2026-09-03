"""The allowance/debt ledger — near-direct port per spec 2.2. A kid's
cash balance is always derived as the signed sum of `debt_transactions`,
never stored redundantly, so buy/sell (which also write rows here) can
never drift out of sync with it.
"""

import uuid
from decimal import Decimal
from typing import NamedTuple

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


class AnnotatedTransaction(NamedTuple):
    txn: DebtTransaction
    currency: str  # currency `txn.amount` and `balance_after` are in
    previous_currency: str  # currency `balance_before` is in (differs from `currency` only on the row where a conversion just happened)
    balance_before: Decimal
    balance_after: Decimal


async def list_transactions_with_currency(
    session: AsyncSession, kid_id: uuid.UUID, current_currency: str
) -> list[AnnotatedTransaction]:
    """Annotates each row (routes_debt.py) with the currency it was
    actually recorded in and the running balance before/after it.

    A row's raw `amount` has no currency of its own — it's implicitly
    "whatever the family's currency was at the time" (see the model's
    docstring) — so after a currency change, naively formatting every
    row with the family's *current* currency mislabels every older row
    (a 200 EUR deposit reads as "200 ILS" once the family switches to
    ILS). Walking oldest-to-newest and flipping the tracked currency at
    each is_adjustment row (which records its own from/to) recovers the
    real currency for every row instead.
    """
    rows_desc = await list_transactions(session, kid_id)
    rows_asc = list(reversed(rows_desc))

    first_adjustment = next((r for r in rows_asc if r.is_adjustment), None)
    currency = first_adjustment.from_currency if first_adjustment else current_currency

    balance = Decimal("0.00")
    annotated: list[AnnotatedTransaction] = []
    for txn in rows_asc:
        previous_currency = currency
        balance_before = balance
        if txn.is_adjustment:
            currency = txn.to_currency
        signed = txn.amount if txn.type == DebtTransactionType.ADD else -txn.amount
        balance = balance + signed
        annotated.append(AnnotatedTransaction(txn, currency, previous_currency, balance_before, balance))

    annotated.reverse()
    return annotated


async def record_transaction(
    session: AsyncSession,
    kid_id: uuid.UUID,
    type: DebtTransactionType,
    amount: Decimal,
    note: str | None = None,
    is_adjustment: bool = False,
    is_investment: bool = False,
    from_currency: str | None = None,
    to_currency: str | None = None,
) -> DebtTransaction:
    txn = DebtTransaction(
        kid_id=kid_id,
        type=type,
        amount=amount,
        note=note,
        is_adjustment=is_adjustment,
        is_investment=is_investment,
        from_currency=from_currency,
        to_currency=to_currency,
    )
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
    return await record_transaction(
        session,
        kid_id,
        txn_type,
        abs(delta),
        note,
        is_adjustment=True,
        from_currency=from_currency,
        to_currency=to_currency,
    )
