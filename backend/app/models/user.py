import uuid

from sqlalchemy import ForeignKey
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base
from app.models.base import CreatedAtMixin, UUIDPrimaryKeyMixin


class User(UUIDPrimaryKeyMixin, CreatedAtMixin, Base):
    """A parent account. v1: Google OAuth only, one parent per family."""

    __tablename__ = "users"

    family_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("families.id", ondelete="CASCADE"), index=True
    )
    email: Mapped[str] = mapped_column(unique=True, index=True)
    google_sub: Mapped[str] = mapped_column(unique=True, index=True)
    name: Mapped[str | None] = mapped_column(default=None)
