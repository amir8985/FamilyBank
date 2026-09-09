from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import KidAndFamily, get_current_kid, get_kid, require_parent
from app.core.config import get_settings
from app.core.db import get_db
from app.core.rate_limit import is_rate_limited, record_hit
from app.core.security import issue_kid_session_token
from app.models.family import Family
from app.models.kid import Kid
from app.schemas.kid_auth import (
    KidClaimRequest,
    KidClaimResponse,
    KidInviteOut,
    KidInviteStatusOut,
    KidMeOut,
)
from app.services import kid_auth_service

router = APIRouter(tags=["kid-auth"])
settings = get_settings()


@router.get(
    "/kids/{kid_id}/invite",
    response_model=KidInviteStatusOut,
    dependencies=[Depends(require_parent)],
)
async def get_kid_invite_status(
    kid: Kid = Depends(get_kid), db: AsyncSession = Depends(get_db)
) -> KidInviteStatusOut:
    has_pending, sessions_active, expires_at = await kid_auth_service.get_invite_status(db, kid)
    return KidInviteStatusOut(
        has_pending_invite=has_pending, sessions_active=sessions_active, expires_at=expires_at
    )


@router.post(
    "/kids/{kid_id}/invite",
    response_model=KidInviteOut,
    status_code=201,
    dependencies=[Depends(require_parent)],
)
async def create_kid_invite(
    kid: Kid = Depends(get_kid), db: AsyncSession = Depends(get_db)
) -> KidInviteOut:
    """Parent generates (or regenerates) the invite for one kid. The PIN
    is returned here once and only stored hashed — the parent reads it to
    the kid out loud, separately from the link. The link is multi-use
    within its window (phone + laptop)."""
    claim_token, pin, expires_at = await kid_auth_service.create_invite(db, kid)
    await db.commit()
    return KidInviteOut(
        claim_url=f"{settings.frontend_origin}/kid/join/{claim_token}",
        pin=pin,
        expires_at=expires_at,
    )


@router.post(
    "/kids/{kid_id}/sign-out-all",
    status_code=204,
    dependencies=[Depends(require_parent)],
)
async def sign_out_all_devices(
    kid: Kid = Depends(get_kid), db: AsyncSession = Depends(get_db)
) -> None:
    """Parent-triggered: invalidate every device this kid is signed in on
    (a lost phone). The kid then needs a fresh link to sign back in."""
    await kid_auth_service.sign_out_all(db, kid)
    await db.commit()


@router.post("/kid-auth/claim", response_model=KidClaimResponse)
async def claim_kid_invite(
    body: KidClaimRequest, request: Request, db: AsyncSession = Depends(get_db)
) -> KidClaimResponse:
    """Unauthenticated: the kid presents the claim token (from the link)
    plus the PIN. On success they get a long-lived kid session token —
    the same link works again on their other devices. Per-invite
    wrong-PIN lockout lives in the service; this adds a coarse per-IP
    ceiling so nobody can grind through many claim tokens at once.
    """
    client_ip = request.client.host if request.client else "unknown"
    rl_key = f"kid-claim:{client_ip}"
    if is_rate_limited(rl_key):
        raise HTTPException(
            status.HTTP_429_TOO_MANY_REQUESTS, "Too many attempts — wait a minute and try again."
        )
    record_hit(rl_key)

    try:
        kid = await kid_auth_service.claim(db, body.claim_token, body.pin)
    except kid_auth_service.KidAuthError as exc:
        # Commit even on failure: a wrong PIN bumped failed_attempts and
        # losing that would defeat the lockout.
        await db.commit()
        raise HTTPException(status.HTTP_400_BAD_REQUEST, exc.message) from exc

    family = await db.get(Family, kid.family_id)
    await db.commit()

    token = issue_kid_session_token(kid.id, kid.family_id, kid.token_version)
    return KidClaimResponse(
        session_token=token,
        kid_id=kid.id,
        public_id=kid.public_id,
        kid_name=kid.name,
        avatar_color=kid.avatar_color,
        base_currency=family.base_currency if family else settings.default_base_currency,
    )


@router.get("/kid/me", response_model=KidMeOut)
async def get_kid_me(kid_family: KidAndFamily = Depends(get_current_kid)) -> KidMeOut:
    """The kid app calls this to seed itself — identity + family currency,
    resolved from the session token alone."""
    kid, family = kid_family.kid, kid_family.family
    return KidMeOut(
        kid_id=kid.id,
        public_id=kid.public_id,
        name=kid.name,
        avatar_color=kid.avatar_color,
        family_id=family.id,
        base_currency=family.base_currency,
    )
