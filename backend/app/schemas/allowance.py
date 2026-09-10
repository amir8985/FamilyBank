import uuid
from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, Field

from app.models.allowance import AllowanceCadence


class AllowanceUpsert(BaseModel):
    amount: Decimal = Field(gt=0, le=1_000_000)
    cadence: AllowanceCadence
    # Weekly: 0=Monday .. 6=Sunday. Monthly: 1..28.
    payday: int = Field(ge=0, le=28)


class BulkAllowanceUpsert(AllowanceUpsert):
    """Same shape as AllowanceUpsert — applied to every kid in the family
    in one call (the "set the same allowance for everyone" action)."""


class AllowancePaymentOut(BaseModel):
    amount: Decimal
    currency: str
    paid_at: datetime


class AllowanceOut(BaseModel):
    kid_id: uuid.UUID
    kid_name: str
    configured: bool
    is_active: bool
    amount: Decimal | None = None
    currency: str | None = None
    cadence: AllowanceCadence | None = None
    payday: int | None = None
    next_payday: datetime | None = None
    last_paid_at: datetime | None = None
    # Most recent allowance payouts, newest first — the kid's "when did I
    # last get it" list. Empty until the first payout.
    recent_payments: list[AllowancePaymentOut] = []


class FamilyAllowancesOut(BaseModel):
    base_currency: str
    kids: list[AllowanceOut]
