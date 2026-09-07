import uuid
from dataclasses import dataclass

from fastapi import Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import get_db
from app.core.security import AuthContext, get_current_auth
from app.models.family import Family
from app.models.kid import Kid


async def get_family(
    auth: AuthContext = Depends(get_current_auth), db: AsyncSession = Depends(get_db)
) -> Family:
    family = await db.get(Family, auth.family_id)
    if family is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Family not found")
    return family


async def get_kid(
    kid_id: uuid.UUID,
    auth: AuthContext = Depends(get_current_auth),
    db: AsyncSession = Depends(get_db),
) -> Kid:
    kid = await db.get(Kid, kid_id)
    # family_id check here is the one thing architecture 5.5 says to
    # stress-test: a kid_id from another family must 404, not leak data.
    if kid is None or kid.family_id != auth.family_id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Kid not found")
    return kid


@dataclass
class KidAndFamily:
    kid: Kid
    family: Family


async def get_kid_and_family(
    kid_id: uuid.UUID,
    auth: AuthContext = Depends(get_current_auth),
    db: AsyncSession = Depends(get_db),
) -> KidAndFamily:
    """For routes that need *both* (debt, investing) — was two separate
    point-lookups (get_kid + get_family, each its own round-trip to
    Neon); a kid always belongs to exactly one family, so one JOIN gets
    both rows in a single round-trip instead of two. Same
    tenant-isolation guarantee as get_kid — a kid_id from another family
    still 404s rather than ever returning that family's row (checked
    explicitly below, not just implied by the JOIN condition, so this
    reads the same way get_kid does and stays easy to audit against
    architecture 5.5's isolation requirement).
    """
    row = (
        await db.execute(
            select(Kid, Family).join(Family, Family.id == Kid.family_id).where(Kid.id == kid_id)
        )
    ).first()
    if row is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Kid not found")
    kid, family = row
    if kid.family_id != auth.family_id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Kid not found")
    return KidAndFamily(kid=kid, family=family)
