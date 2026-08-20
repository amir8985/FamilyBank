from fastapi import APIRouter, Depends, Header, HTTPException, status
from sqlalchemy import delete
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_family
from app.core.config import get_settings
from app.core.db import get_db
from app.models.family import Family
from app.models.kid import Kid
from app.scheduler.jobs import run_refresh

router = APIRouter(prefix="/internal", tags=["internal"])
settings = get_settings()


@router.post("/refresh")
async def trigger_refresh(x_scheduler_secret: str = Header(default="")) -> dict:
    """Hit by an external cron trigger (Vercel Cron / Railway Cron, per
    architecture 5.5) 4-5x/day — not a long-running worker process."""
    if x_scheduler_secret != settings.internal_scheduler_secret:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Bad scheduler secret")
    await run_refresh()
    return {"status": "ok"}


@router.post("/dev-reset")
async def dev_reset(
    family: Family = Depends(get_family), db: AsyncSession = Depends(get_db)
) -> dict:
    """Dev-only: wipes the CALLER'S OWN family back to a fresh,
    un-onboarded state (deletes all kids — cascades their debt/investment
    history — and resets currency + onboarding_completed) so the sign-in
    → onboarding → home flow can be re-tested from scratch without
    creating a new Google account. Gated by DEV_MODE so this can never be
    reachable in a real deployment, and scoped to `get_family`'s own
    family so it can never touch anyone else's data even in dev.
    """
    if not settings.dev_mode:
        raise HTTPException(status.HTTP_404_NOT_FOUND)

    await db.execute(delete(Kid).where(Kid.family_id == family.id))
    family.base_currency = settings.default_base_currency
    family.onboarding_completed = False
    await db.commit()
    return {"status": "ok"}
