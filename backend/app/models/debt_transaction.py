import enum
import uuid
from decimal import Decimal

from sqlalchemy import ForeignKey, Numeric
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
    type: Mapped[DebtTransactionType] = mapped_column(SAEnum(DebtTransactionType, name="debt_transaction_type"))
    note: Mapped[str | None] = mapped_column(default=None)
