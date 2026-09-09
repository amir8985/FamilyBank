import uuid
from dataclasses import dataclass

from fastapi import Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import get_db
from app.core.security import AuthContext, get_current_auth
from app.models.family import Family
from app.models.kid import Kid

# A kid session JWT whose `tv` no longer matches kids.token_version — the
# parent hit "sign out of all devices". Distinct message (and 401, not
# 404) so the kid app can tell "you were signed out, ask a parent" apart
# from a genuine not-found.
_STALE_KID_SESSION = "Session expired — ask a parent for a new link"


def require_parent(auth: AuthContext = Depends(get_current_auth)) -> AuthContext:
    """Guard for routes a kid session must never reach — anything under
    Settings, adding/removing money or kids, managing savings plans,
    generating invites. Kid-reachable routes (portfolio, buy/sell,
    savings deposit/withdraw, history) don't use this; their scoping
    comes from get_kid/get_kid_and_family instead.
    """
    if auth.is_kid:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "This action is for parents only")
    return auth


async def _load_family(auth: AuthContext, db: AsyncSession) -> Family:
    family = await db.get(Family, auth.family_id)
    if family is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Family not found")
    return family


async def get_family(
    auth: AuthContext = Depends(get_current_auth), db: AsyncSession = Depends(get_db)
) -> Family:
    # Almost no kid-reachable route resolves the family this way — kid
    # routes go through get_kid_and_family, which stays scoped to the one
    # kid. So a kid token here nearly always means a route it has no
    # business calling (Settings, /home, savings-plan management): reject
    # it once, here, instead of guarding each of those routes separately.
    # The lone exception is the read-only catalog (needs only
    # base_currency) — that uses get_family_currency below.
    if auth.is_kid:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "This action is for parents only")
    return await _load_family(auth, db)


async def get_family_currency(
    auth: AuthContext = Depends(get_current_auth), db: AsyncSession = Depends(get_db)
) -> Family:
    """Like get_family but allows a kid token — for read-only endpoints
    that need nothing from the family but its display currency (the asset
    catalog). Still scoped: auth.family_id comes from the verified token.
    """
    return await _load_family(auth, db)


@dataclass
class KidAndFamily:
    kid: Kid
    family: Family


async def _resolve_kid_and_family(db: AsyncSession, ref: str, auth: AuthContext) -> KidAndFamily:
    """Turn the `{kid_id}` path segment into a (kid, family), enforcing
    architecture 5.5 isolation. THE single place this happens — `get_kid`,
    `get_kid_and_family` and `get_current_kid` all route through here, so
    there's one thing to audit. One JOIN, one round-trip (the production
    perf notes: don't split it back into point-lookups).

    - Parent token: `ref` must be a real kid UUID in this family; a
      foreign or bogus id 404s, never leaks.
    - Kid token: the token itself names the kid; `ref` is cosmetic (the
      kid's opaque `public_id` in the URL). It must still name *this*
      kid — the kid's own UUID or public_id — so a hand-edited cross-kid
      URL 404s just like the parent case. The token version must also
      still be current, and the kid must still belong to the token's
      family (redundant with a signed JWT, kept for defence in depth).
    """
    if auth.is_kid:
        target_id = auth.kid_id
    else:
        try:
            target_id = uuid.UUID(ref)
        except ValueError as exc:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "Kid not found") from exc

    row = (
        await db.execute(
            select(Kid, Family).join(Family, Family.id == Kid.family_id).where(Kid.id == target_id)
        )
    ).first()

    if auth.is_kid:
        # A valid kid JWT whose kid/family is gone → "you were signed out"
        if row is None:
            raise HTTPException(status.HTTP_401_UNAUTHORIZED, _STALE_KID_SESSION)
        kid, family = row
        if kid.token_version != auth.token_version or kid.family_id != auth.family_id:
            raise HTTPException(status.HTTP_401_UNAUTHORIZED, _STALE_KID_SESSION)
        if ref != str(kid.id) and ref != kid.public_id:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "Kid not found")
        return KidAndFamily(kid=kid, family=family)

    if row is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Kid not found")
    kid, family = row
    if kid.family_id != auth.family_id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Kid not found")
    return KidAndFamily(kid=kid, family=family)


async def get_kid(
    kid_id: str,
    auth: AuthContext = Depends(get_current_auth),
    db: AsyncSession = Depends(get_db),
) -> Kid:
    return (await _resolve_kid_and_family(db, kid_id, auth)).kid


async def get_kid_and_family(
    kid_id: str,
    auth: AuthContext = Depends(get_current_auth),
    db: AsyncSession = Depends(get_db),
) -> KidAndFamily:
    """For routes that need *both* (debt, investing)."""
    return await _resolve_kid_and_family(db, kid_id, auth)


async def get_current_kid(
    auth: AuthContext = Depends(get_current_auth),
    db: AsyncSession = Depends(get_db),
) -> KidAndFamily:
    """Resolve the kid + family from a kid session token alone (no path
    kid_id) — for GET /kid/me, which the kid app calls to seed itself.
    Rejects a parent token outright.
    """
    if not auth.is_kid or auth.kid_id is None:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "This endpoint is for kid sessions")
    return await _resolve_kid_and_family(db, str(auth.kid_id), auth)
