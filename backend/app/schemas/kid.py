import uuid
from decimal import Decimal

from pydantic import BaseModel, Field


class KidCreate(BaseModel):
    name: str = Field(min_length=1, max_length=60)


class KidSummary(BaseModel):
    id: uuid.UUID
    name: str
    avatar_color: str
    cash_balance: Decimal
    portfolio_value: Decimal
    portfolio_day_change_pct: Decimal | None


class FamilyHome(BaseModel):
    base_currency: str
    total_owed: Decimal
    total_invested: Decimal
    kids: list[KidSummary]
