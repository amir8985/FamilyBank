"""Kid-facing login: the parent generates a per-kid invite (a link + a
spoken PIN), the kid claims it on each of their devices.

Design (see CLAUDE.md / spec 4.1 v2):
  - The claim token is high-entropy (in the link); the PIN is short and
    travels out of band (parent reads it aloud). A link leaking into the
    wrong chat is useless without the PIN.
  - One pending invite per kid; generating a new one replaces the old.
  - **Multi-use within its window**: the kid claims it on their phone
    and their laptop off the same link — each claim mints a session,
    none invalidates another. It stops working at `expires_at` (24h), or
    after `kid_claim_max_attempts` wrong PINs.
  - Revocation is an explicit parent action — `sign_out_all` bumps
    `kids.token_version`, which invalidates every device at once (for a
    lost phone). An ordinary claim does NOT bump it.

Only hashes are stored. The claim token gets a plain SHA-256 (already
high-entropy). The 6-digit PIN gets PBKDF2 with a per-row salt.
"""

import hashlib
import secrets
from datetime import datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.models.kid import Kid, KidInvite

settings = get_settings()

_PBKDF2_ITERATIONS = 100_000


class KidAuthError(Exception):
    """A bad claim attempt. `message` is safe to show the kid verbatim."""

    def __init__(self, message: str):
        super().__init__(message)
        self.message = message


def _hash_token(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


def _hash_pin(pin: str, salt_hex: str) -> str:
    return hashlib.pbkdf2_hmac(
        "sha256", pin.encode(), bytes.fromhex(salt_hex), _PBKDF2_ITERATIONS
    ).hex()


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _is_live(invite: KidInvite) -> bool:
    return (
        invite.expires_at > _now()
        and invite.failed_attempts < settings.kid_claim_max_attempts
    )


async def create_invite(db: AsyncSession, kid: Kid) -> tuple[str, str, datetime]:
    """Replace any existing invite for `kid` with a fresh one. Returns
    (claim_token, pin, expires_at) — the raw values exist only here, at
    generation time. Caller commits.
    """
    claim_token = secrets.token_urlsafe(32)
    pin = f"{secrets.randbelow(1_000_000):06d}"
    salt_hex = secrets.token_bytes(16).hex()
    expires_at = _now() + timedelta(hours=settings.kid_invite_ttl_hours)

    existing = await db.scalar(select(KidInvite).where(KidInvite.kid_id == kid.id))
    if existing is not None:
        await db.delete(existing)
        await db.flush()

    db.add(
        KidInvite(
            kid_id=kid.id,
            claim_token_hash=_hash_token(claim_token),
            pin_salt=salt_hex,
            pin_hash=_hash_pin(pin, salt_hex),
            expires_at=expires_at,
        )
    )
    await db.flush()
    return claim_token, pin, expires_at


async def get_invite_status(db: AsyncSession, kid: Kid) -> tuple[bool, bool, datetime | None]:
    """(has_pending_invite, sessions_active, pending_expires_at) for the
    Settings UI."""
    invite = await db.scalar(select(KidInvite).where(KidInvite.kid_id == kid.id))
    if invite is not None and _is_live(invite):
        return True, kid.sessions_active, invite.expires_at
    return False, kid.sessions_active, None


async def claim(db: AsyncSession, claim_token: str, pin: str) -> Kid:
    """Verify an invite + mark the kid as having active sessions, return
    the Kid. Raises KidAuthError on any failure. The caller must commit
    even on failure — a wrong PIN increments failed_attempts, and losing
    that would defeat the lockout. Does NOT bump token_version (a claim
    is additive — another device, same account).
    """
    invalid = KidAuthError("This link is no longer valid. Ask a parent for a new one.")
    burned = KidAuthError("Too many wrong tries on this link. Ask a parent for a new one.")

    invite = await db.scalar(
        select(KidInvite).where(KidInvite.claim_token_hash == _hash_token(claim_token))
    )
    if invite is None or invite.expires_at <= _now():
        raise invalid
    if invite.failed_attempts >= settings.kid_claim_max_attempts:
        raise burned

    if _hash_pin(pin, invite.pin_salt) != invite.pin_hash:
        invite.failed_attempts += 1
        await db.flush()
        left = settings.kid_claim_max_attempts - invite.failed_attempts
        if left <= 0:
            raise burned
        raise KidAuthError(f"Wrong PIN — {left} {'try' if left == 1 else 'tries'} left.")

    kid = await db.get(Kid, invite.kid_id)
    if kid is None:
        raise invalid

    if invite.first_claimed_at is None:
        invite.first_claimed_at = _now()
    kid.sessions_active = True
    await db.flush()
    return kid


async def sign_out_all(db: AsyncSession, kid: Kid) -> None:
    """Parent-triggered: invalidate every device this kid is signed in on
    (a lost phone). Bumps token_version so every existing kid JWT stops
    verifying. Caller commits."""
    kid.token_version += 1
    kid.sessions_active = False
    await db.flush()
