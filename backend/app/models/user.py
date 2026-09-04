import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey
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

    # Set once, at account creation, when the frontend's consent gate (the
    # checkbox in front of Google sign-in) was in front of the user. NULL
    # means the account predates that flow — not that consent was refused.
    consent_accepted_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), default=None
    )
