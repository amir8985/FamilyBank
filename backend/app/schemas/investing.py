import uuid
from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, Field, model_validator

from app.models.catalog import AssetKind
from app.models.investment import InvestmentTransactionType


class AssetOut(BaseModel):
    symbol: str
    display_name: str
    kind: AssetKind
    description: str
    price: Decimal | None = None
    price_currency: str | None = None
    day_change_pct: Decimal | None = None
    # When the scheduler last refreshed this price — prices are batch
    # updated 4-5x/day (spec 4.3), never truly live, so the frontend
    # shows this instead of claiming "live".
    price_updated_at: datetime | None = None


class AssetDetailOut(AssetOut):
    # The currency the raw price is actually quoted in (e.g. USD for
    # AAPL) — shown as a caption alongside the already-converted `price`.
    native_currency: str | None = None
    # Native-currency lookback history — spec 2.4 keeps the chart
    # unconverted, only the live price/buy amounts are converted.
    history: list[dict]


class HoldingOut(BaseModel):
    symbol: str
    display_name: str
    units: Decimal
    current_value: Decimal
    day_change_pct: Decimal | None
    # Total return since this holding's average cost basis — currency-
    # agnostic (both current price and avg_cost are in the same native
    # currency for the symbol, so FX cancels out). Shown instead of
    # day_change_pct in the holdings list, since "how has MY investment
    # done" matters more there than today's wiggle.
    since_purchase_pct: Decimal | None


class PortfolioOut(BaseModel):
    kid_id: uuid.UUID
    kid_name: str
    cash_available: Decimal
    holdings_value: Decimal
    total_value: Decimal
    total_day_change_amount: Decimal
    total_day_change_pct: Decimal | None
    holdings: list[HoldingOut]


class BuySellQuoteRequest(BaseModel):
    """Live preview while the user is typing on the buy screen — either
    field drives the other, per the handoff's amount/units toggle."""

    symbol: str
    amount: Decimal | None = Field(default=None, gt=0)
    units: Decimal | None = Field(default=None, gt=0)

    @model_validator(mode="after")
    def one_of_amount_or_units(self) -> "BuySellQuoteRequest":
        if (self.amount is None) == (self.units is None):
            raise ValueError("Provide exactly one of amount or units")
        return self


class BuySellQuoteResponse(BaseModel):
    symbol: str
    units: Decimal
    cost: Decimal
    price_per_unit: Decimal
    currency: str
    cash_available_after: Decimal


class BuyRequest(BaseModel):
    symbol: str
    units: Decimal = Field(gt=0)


class SellRequest(BaseModel):
    symbol: str
    units: Decimal = Field(gt=0)


class InvestmentTransactionOut(BaseModel):
    id: uuid.UUID
    symbol: str
    type: InvestmentTransactionType
    units: Decimal
    price: Decimal
    price_currency: str
    created_at: datetime
