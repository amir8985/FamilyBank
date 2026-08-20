from fastapi import APIRouter, Header, HTTPException, status

from app.core.config import get_settings
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
