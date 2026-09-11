import enum
import uuid
from datetime import datetime
from decimal import Decimal

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Integer, Numeric
from sqlalchemy import Enum as SAEnum
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base
from app.models.base import CreatedAtMixin, UUIDPrimaryKeyMixin


class AllowanceCadence(str, enum.Enum):
    WEEKLY = "weekly"
    MONTHLY = "monthly"


class Allowance(UUIDPrimaryKeyMixin, CreatedAtMixin, Base):
    """A recurring cash payment a parent sets up for one kid — pocket
    money / allowance. At most one per kid (a kid either has an
    allowance or doesn't); regenerating just updates this row.

    It is deliberately *not* a wallet or a compounding balance: each
    payout is a plain `debt_transactions` ADD row (flagged is_allowance),
    so an allowance payment lands in the kid's normal cash balance and
    shows up everywhere a balance already does, including the existing
    balance-history screen. Nothing here is recomputed on read the way
    savings/boost are — a payout is a real, one-time ledger write.

    Payouts are settled lazily (allowance_service.settle_due): whenever
    someone looks at allowance data, or the price-refresh job runs, any
    period whose `next_run_at` has passed is paid and the clock advanced.
    There is no per-payment scheduled job.
    """

    __tablename__ = "allowances"
    __table_args__ = (
        CheckConstraint("payday >= 0 AND payday <= 28", name="ck_allowances_payday_range"),
    )

    kid_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("kids.id", ondelete="CASCADE"), unique=True, index=True
    )

    amount: Mapped[Decimal] = mapped_column(Numeric(14, 2))
    # Family currency at the time the parent set the amount — converted to
    # the family's current currency at payout time (same approach as
    # SavingsDeposit.currency / InvestmentLot.purchase_currency), so a
    # later currency change never silently relabels the amount and the
    # currency-change path needs no allowance-specific handling.
    currency: Mapped[str]

    cadence: Mapped[AllowanceCadence] = mapped_column(
        SAEnum(
            AllowanceCadence,
            name="allowance_cadence",
            values_callable=lambda e: [m.value for m in e],
        )
    )
    # Weekly: day of week, Monday=0 .. Sunday=6 (matches datetime.weekday()).
    # Monthly: day of month, 1..28 (28 so every month has one).
    payday: Mapped[int] = mapped_column(Integer)

    # When the next payout is due. Advanced one period at a time as
    # payouts are settled. Set on creation to the first upcoming payday
    # (a new allowance does not pay immediately).
    next_run_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    # When the most recent payout actually happened — NULL until the
    # first one. Shown to the kid ("last payment") and the parent.
    last_paid_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True, default=None
    )
