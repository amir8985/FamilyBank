import uuid
from datetime import datetime
from decimal import Decimal

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, Numeric, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base
from app.models.base import CreatedAtMixin, UUIDPrimaryKeyMixin


class SavingsPlan(UUIDPrimaryKeyMixin, CreatedAtMixin, Base):
    """A parent-defined savings option a kid can move cash into. Two
    flavours, distinguished only by lock_months:
      - flexible (lock_months == 0): withdraw any time.
      - locked (lock_months > 0): can't withdraw until the deposit
        matures; after that it keeps compounding at the same rate until
        the kid withdraws.

    monthly_rate is a percentage per month (e.g. 2.000 == 2%/month),
    compounded daily on the kid side (see savings_service).

    Editing or deleting a plan never touches deposits already made into
    it — every SavingsDeposit snapshots the plan's terms at deposit time
    (see its docstring). is_active just controls whether the plan still
    shows up as a place to put *new* money.
    """

    __tablename__ = "savings_plans"

    family_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("families.id", ondelete="CASCADE"), index=True
    )
    name: Mapped[str]
    monthly_rate: Mapped[Decimal] = mapped_column(Numeric(6, 3))
    lock_months: Mapped[int] = mapped_column(Integer, default=0)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    # Set when the parent turned this on from a built-in preset (see
    # savings_service.PRESET_PLANS); NULL for a plan they typed in
    # themselves. At most one plan per family per preset_key.
    preset_key: Mapped[str | None] = mapped_column(nullable=True)


class SavingsDeposit(UUIDPrimaryKeyMixin, CreatedAtMixin, Base):
    """One move of cash into a savings plan — permanent and independent,
    the same way an InvestmentLot is (see models/investment.py). Never
    partially withdrawn: a withdrawal closes the whole deposit and pays
    principal + accrued interest back to the kid's cash ledger.

    plan_name / monthly_rate / lock_months are snapshots taken at deposit
    time — a later edit or delete of the parent's SavingsPlan leaves this
    deposit growing on exactly the terms it was opened under. plan_id is
    kept (ON DELETE SET NULL) only to group a kid's deposits by plan
    while the plan still exists.

    No persisted accrued-interest column: savings_service recomputes the
    whole value from principal + rate + opened_at on every read, same
    stateless approach as boost_service (cheap at this app's scale, and
    nothing for a kid to game by reading more or less often).
    """

    __tablename__ = "savings_deposits"

    kid_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("kids.id", ondelete="CASCADE"), index=True
    )
    plan_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("savings_plans.id", ondelete="SET NULL"), nullable=True
    )
    plan_name: Mapped[str]
    monthly_rate: Mapped[Decimal] = mapped_column(Numeric(6, 3))
    lock_months: Mapped[int] = mapped_column(Integer)

    principal: Mapped[Decimal] = mapped_column(Numeric(14, 2))
    # Family currency at deposit time — converted to the family's current
    # currency at read time (like InvestmentLot.purchase_currency), so a
    # later currency change doesn't silently relabel the amount.
    currency: Mapped[str]

    opened_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    # opened_at + lock_months; NULL for a flexible deposit.
    matures_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    is_open: Mapped[bool] = mapped_column(Boolean, default=True, index=True)
    closed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    close_value: Mapped[Decimal | None] = mapped_column(Numeric(14, 2), nullable=True)
    close_currency: Mapped[str | None] = mapped_column(nullable=True)
