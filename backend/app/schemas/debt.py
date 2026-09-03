import uuid
from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, Field

from app.models.debt_transaction import DebtTransactionType


class DebtTransactionCreate(BaseModel):
    type: DebtTransactionType
    amount: Decimal = Field(gt=0)
    note: str | None = Field(default=None, max_length=280)


class DebtTransactionOut(BaseModel):
    id: uuid.UUID
    type: DebtTransactionType
    amount: Decimal
    note: str | None
    is_adjustment: bool
    is_investment: bool
    currency: str
    previous_currency: str
    balance_before: Decimal
    balance_after: Decimal
    created_at: datetime


class DebtUpdateResult(BaseModel):
    transaction: DebtTransactionOut
    new_balance: Decimal
