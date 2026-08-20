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
