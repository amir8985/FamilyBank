import enum
from datetime import datetime
from decimal import Decimal

from sqlalchemy import DateTime, ForeignKey, Numeric, UniqueConstraint
from sqlalchemy import Enum as SAEnum
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base
from app.models.base import UUIDPrimaryKeyMixin


class AssetKind(str, enum.Enum):
    STOCK = "stock"
    BASKET = "basket"


class AssetCatalog(Base):
    """Global reference data — not per-family. The ~25-symbol universe
    kids can buy into (spec section 3)."""

    __tablename__ = "asset_catalog"

    symbol: Mapped[str] = mapped_column(primary_key=True)
    display_name: Mapped[str]
    kind: Mapped[AssetKind] = mapped_column(
        SAEnum(AssetKind, name="asset_kind", values_callable=lambda e: [m.value for m in e])
    )
    description: Mapped[str] = mapped_column(default="")


class PriceTick(UUIDPrimaryKeyMixin, Base):
    """Append-only price history, shared globally across every family —
    same write cost as PriceCache (one row per symbol per scheduler
    refresh), never per-kid or per-lot. This is what boost_service walks
    to compute a boosted investment_lot's synthetic value: unlike
    PriceCache (overwritten every refresh, only ever "now"), this never
    loses a past tick, so a lot's whole since-purchase trajectory can be
    reconstructed on demand instead of needing a running checkpoint."""

    __tablename__ = "price_ticks"

    symbol: Mapped[str] = mapped_column(ForeignKey("asset_catalog.symbol"), index=True)
    observed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    price: Mapped[Decimal] = mapped_column(Numeric(14, 4))
    currency: Mapped[str]


class PriceCache(Base):
    """Global, shared across every family. Written only by the scheduler
    (app.scheduler.jobs), never by a request handler — see spec 4.3."""

    __tablename__ = "price_cache"

    symbol: Mapped[str] = mapped_column(primary_key=True)
    price: Mapped[Decimal] = mapped_column(Numeric(14, 4))
    currency: Mapped[str]
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    # [{"date": "YYYY-MM-DD", "close": 123.45}, ...] short lookback for the
    # buy-screen sparkline, in the symbol's native currency (spec 2.4).
    history_json: Mapped[list] = mapped_column(JSONB, default=list)


class FxRateCache(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "fx_rates_cache"
    __table_args__ = (UniqueConstraint("base_currency", "quote_currency", name="uq_fx_pair"),)

    base_currency: Mapped[str]
    quote_currency: Mapped[str]
    rate: Mapped[Decimal] = mapped_column(Numeric(18, 8))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
