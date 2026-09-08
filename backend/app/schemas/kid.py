import uuid
from datetime import datetime
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
    # When the scheduler last refreshed the prices behind the kids'
    # portfolio values (spec 4.3 — batch updated ~5x/day). Lets the
    # frontend treat this payload as a cache good until the next refresh
    # rather than re-fetching on every navigation. None before the first
    # scheduler run.
    prices_as_of: datetime | None = None
