from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.db import get_db, transaction
from app.core.security import issue_session_token, verify_google_id_token
from app.models.family import Family
from app.models.user import User
from app.schemas.auth import GoogleSyncRequest, SessionResponse

router = APIRouter(prefix="/auth", tags=["auth"])
settings = get_settings()


@router.post("/sync", response_model=SessionResponse)
async def sync_google_session(
    body: GoogleSyncRequest, db: AsyncSession = Depends(get_db)
) -> SessionResponse:
    """Called by the frontend right after NextAuth completes Google
    sign-in. Verifies Google's own ID token (so this backend never has to
    trust the frontend's word for who the user is), then finds-or-creates
    the parent's family on first login (spec 2.1: one parent per family
    in v1) and returns a backend-issued session JWT for subsequent calls.
    """
    try:
        claims = verify_google_id_token(body.id_token)
    except ValueError as exc:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, f"Invalid Google ID token: {exc}") from exc

    email = claims.get("email")
    google_sub = claims.get("sub")
    if not email or not google_sub:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Google token missing email/sub")

    async with transaction(db):
        user = await db.scalar(select(User).where(User.google_sub == google_sub))
        if user is None:
            family = Family(base_currency=settings.default_base_currency)
            db.add(family)
            await db.flush()
            user = User(
                family_id=family.id,
                email=email,
                google_sub=google_sub,
                name=claims.get("name"),
            )
            db.add(user)
            await db.flush()
        else:
            family = await db.get(Family, user.family_id)

    token = issue_session_token(user.id, user.family_id, user.email)
    return SessionResponse(
        session_token=token,
        family_id=str(user.family_id),
        user_id=str(user.id),
        email=user.email,
        base_currency=family.base_currency,
    )
