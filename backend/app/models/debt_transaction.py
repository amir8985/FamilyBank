import enum
import uuid
from decimal import Decimal

from sqlalchemy import Boolean, ForeignKey, Numeric
from sqlalchemy import Enum as SAEnum
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base
from app.models.base import CreatedAtMixin, UUIDPrimaryKeyMixin


class DebtTransactionType(str, enum.Enum):
    ADD = "add"
    DEDUCT = "deduct"


class DebtTransaction(UUIDPrimaryKeyMixin, CreatedAtMixin, Base):
    """The allowance/debt ledger. A kid's cash balance is the signed sum
    of these rows — buy/sell also write rows here (see investing_service)
    so the ledger stays the single source of truth for "what's owed".
    """

    __tablename__ = "debt_transactions"

    kid_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("kids.id", ondelete="CASCADE"), index=True
    )
    amount: Mapped[Decimal] = mapped_column(Numeric(14, 2))
    type: Mapped[DebtTransactionType] = mapped_column(
        # values_callable: bind/compare by .value ("add"/"deduct", matching
        # the Postgres enum labels) instead of SQLAlchemy's default of the
        # Python member .name ("ADD"/"DEDUCT"), which the DB enum rejects.
        SAEnum(DebtTransactionType, name="debt_transaction_type", values_callable=lambda e: [m.value for m in e])
    )
    note: Mapped[str | None] = mapped_column(default=None)
    # True only for the auto-generated currency-conversion row (see
    # debts_db_service.apply_currency_conversion) — lets the frontend
    # render it as a recalculation rather than a real add/deduct, since
    # nothing was actually given or taken away (history.tsx).
    is_adjustment: Mapped[bool] = mapped_column(Boolean, default=False)
