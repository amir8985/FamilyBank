import uuid
from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, Field


class SavingsPlanCreate(BaseModel):
    name: str = Field(min_length=1, max_length=60)
    monthly_rate: Decimal = Field(gt=0, le=100)
    lock_months: int = Field(default=0, ge=0, le=120)


class SavingsPlanUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=60)
    monthly_rate: Decimal | None = Field(default=None, gt=0, le=100)
    lock_months: int | None = Field(default=None, ge=0, le=120)
    is_active: bool | None = None


class SavingsPlanOut(BaseModel):
    id: uuid.UUID
    name: str
    monthly_rate: Decimal
    annual_rate: Decimal
    lock_months: int
    is_active: bool
    open_deposit_count: int
    preset_key: str | None = None


class SavingsPresetOut(BaseModel):
    key: str
    name: str
    monthly_rate: Decimal
    annual_rate: Decimal
    lock_months: int
    kind: str


class SavingsPresetToggle(BaseModel):
    key: str
    active: bool


class SavingsCashOutRequest(BaseModel):
    kind: str  # "flexible" | "locked"


class SavingsCashOutResult(BaseModel):
    closed_count: int
    total_paid: Decimal
    currency: str


class DepositablePlanOut(BaseModel):
    id: uuid.UUID
    name: str
    monthly_rate: Decimal
    annual_rate: Decimal
    lock_months: int


class SavingsDepositOut(BaseModel):
    deposit_id: uuid.UUID
    plan_name: str
    monthly_rate: Decimal
    annual_rate: Decimal
    lock_months: int
    is_locked: bool
    matures_at: datetime | None
    is_matured: bool
    principal: Decimal
    current_value: Decimal
    accrued_interest: Decimal
    currency: str
    opened_at: datetime


class SavingsOverviewOut(BaseModel):
    savings_value: Decimal
    deposits: list[SavingsDepositOut]
    plans: list[DepositablePlanOut]


class SavingsPointOut(BaseModel):
    observed_at: datetime
    value: Decimal


class SavingsDepositDetailOut(SavingsDepositOut):
    is_open: bool
    closed_at: datetime | None
    series: list[SavingsPointOut]
    series_currency: str


class SavingsDepositRequest(BaseModel):
    plan_id: uuid.UUID
    amount: Decimal = Field(gt=0)
