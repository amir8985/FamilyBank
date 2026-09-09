import secrets
import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer
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


def _new_public_id() -> str:
    return secrets.token_hex(8)


class Kid(UUIDPrimaryKeyMixin, CreatedAtMixin, Base):
    __tablename__ = "kids"

    family_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("families.id", ondelete="CASCADE"), index=True
    )
    name: Mapped[str]
    avatar_color: Mapped[str] = mapped_column(default="amber")

    # Opaque, unguessable per-kid handle used in the kid app's URLs
    # (`/kid/kids/<public_id>`) instead of the primary key — so no
    # internal id, and nothing enumerable, is ever exposed in a link the
    # kid keeps. Backend routes accept it in place of the UUID for a kid
    # session (see app/api/deps._resolve_kid).
    public_id: Mapped[str] = mapped_column(
        unique=True, index=True, default=_new_public_id
    )

    # Bumped only by the parent's explicit "sign <name> out of all
    # devices" action (routes_kid_auth) — NOT by an ordinary claim, so a
    # kid can add a second device (phone + laptop) off the same invite
    # without knocking the first offline. A kid session JWT embeds the
    # value it was minted with; deps._enforce_kid_scope 401s a token
    # whose value no longer matches.
    token_version: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    # True once at least one device has claimed a session and the parent
    # hasn't since signed them all out. Drives the Settings UI (whether to
    # offer the "sign out of all devices" button).
    sessions_active: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)


class KidInvite(UUIDPrimaryKeyMixin, CreatedAtMixin, Base):
    """A parent-generated "add a device" hand-off for one kid. Carries a
    high-entropy claim token (in the link) and a short PIN (spoken aloud,
    out of band) so a link that leaks into the wrong chat is useless on
    its own.

    One row per kid at most — generating a new invite replaces the old.
    **Multi-use within its window**: the kid can claim it on their phone
    AND their laptop (and a spare) — every claim mints a session; none
    invalidates another. It stops working once `expires_at` passes, after
    `failed_attempts` wrong PINs, or once a fresh invite replaces it.
    `first_claimed_at` is informational only (never blocks a claim).

    Only hashes are stored: claim_token is high-entropy so a plain
    SHA-256 is enough for lookup + comparison; the 6-digit PIN gets
    PBKDF2 with a per-row salt (still cheap to brute-force in the
    abstract, which is exactly why failed_attempts caps it).
    """

    __tablename__ = "kid_invites"

    kid_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("kids.id", ondelete="CASCADE"), unique=True, index=True
    )
    claim_token_hash: Mapped[str] = mapped_column(index=True)
    pin_salt: Mapped[str]
    pin_hash: Mapped[str]
    failed_attempts: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    first_claimed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), default=None)
