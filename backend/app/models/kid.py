import uuid

from sqlalchemy import ForeignKey
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base
from app.models.base import CreatedAtMixin, UUIDPrimaryKeyMixin

# Decorative avatar colors cycled through as kids are added, matching the
# handoff's per-kid avatar tints (amber/teal/violet/...).
AVATAR_PALETTE = [
    "amber",
    "teal",
    "violet",
    "rose",
    "sky",
    "lime",
]


class Kid(UUIDPrimaryKeyMixin, CreatedAtMixin, Base):
    __tablename__ = "kids"

    family_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("families.id", ondelete="CASCADE"), index=True
    )
    name: Mapped[str]
    avatar_color: Mapped[str] = mapped_column(default="amber")
