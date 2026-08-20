import uuid

from fastapi import Depends, HTTPException, status
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
