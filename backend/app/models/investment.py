import enum
import uuid
from datetime import datetime
from decimal import Decimal

from sqlalchemy import DateTime, ForeignKey, Numeric, UniqueConstraint, func
from sqlalchemy import Enum as SAEnum
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base
from app.models.base import CreatedAtMixin, UUIDPrimaryKeyMixin


class InvestmentTransactionType(str, enum.Enum):
    BUY = "buy"
    SELL = "sell"


class InvestmentHolding(UUIDPrimaryKeyMixin, CreatedAtMixin, Base):
    __tablename__ = "investment_holdings"
    __table_args__ = (UniqueConstraint("kid_id", "symbol", name="uq_holding_kid_symbol"),)

    kid_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("kids.id", ondelete="CASCADE"), index=True
    )
    symbol: Mapped[str] = mapped_column(ForeignKey("asset_catalog.symbol"), index=True)
    units: Mapped[Decimal] = mapped_column(Numeric(20, 8))
    avg_cost: Mapped[Decimal] = mapped_column(Numeric(14, 4))
    avg_cost_currency: Mapped[str]
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )


class InvestmentLot(UUIDPrimaryKeyMixin, CreatedAtMixin, Base):
    """One purchase = one permanent, independent instance — never blended
    with another purchase of the same symbol the way InvestmentHolding's
    avg_cost is. Every new buy (see investing_service.buy()) creates one
    of these; InvestmentHolding is no longer written to by new buys, but
    stays in place so kids' pre-existing avg-cost holdings remain
    sellable. Selling can be partial (reduces `units`, stays open) or
    full (closes the lot) — see investing_service._sell_lot — but two
    lots are never merged back together even if they're the same symbol.

    buffer_rate is locked in at purchase and never changes for this lot's
    lifetime (Family.boost_buffer_rate can only change while every kid's
    holdings are empty — see routes_family.py's guard — so this is always
    exactly what the family rate was at the moment of purchase, boosted
    or not: NULL/0 for a family with boost off).

    No stored checkpoint or accrued-factor column — boost_service
    recomputes this lot's whole synthetic trajectory from purchased_at to
    now on every read, by walking price_ticks. Deliberately simple given
    the scale (at most a couple dozen open lots per kid, a few thousand
    ticks/year per symbol) — see CLAUDE.md for the reasoning."""

    __tablename__ = "investment_lots"

    kid_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("kids.id", ondelete="CASCADE"), index=True
    )
    symbol: Mapped[str] = mapped_column(ForeignKey("asset_catalog.symbol"), index=True)
    units: Mapped[Decimal] = mapped_column(Numeric(20, 8))
    purchase_price: Mapped[Decimal] = mapped_column(Numeric(14, 4))
    purchase_currency: Mapped[str]
    purchased_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    buffer_rate: Mapped[Decimal | None] = mapped_column(Numeric(6, 3), nullable=True)
    is_open: Mapped[bool] = mapped_column(default=True, index=True)
    sold_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    sale_value: Mapped[Decimal | None] = mapped_column(Numeric(14, 4), nullable=True)
    sale_currency: Mapped[str | None] = mapped_column(nullable=True)


class InvestmentTransaction(UUIDPrimaryKeyMixin, CreatedAtMixin, Base):
    __tablename__ = "investment_transactions"

    kid_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("kids.id", ondelete="CASCADE"), index=True
    )
    symbol: Mapped[str] = mapped_column(ForeignKey("asset_catalog.symbol"), index=True)
    units: Mapped[Decimal] = mapped_column(Numeric(20, 8))
    price: Mapped[Decimal] = mapped_column(Numeric(14, 4))
    price_currency: Mapped[str]
    type: Mapped[InvestmentTransactionType] = mapped_column(
        SAEnum(
            InvestmentTransactionType,
            name="investment_transaction_type",
            values_callable=lambda e: [m.value for m in e],
        )
    )
