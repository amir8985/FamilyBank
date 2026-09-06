import json
import logging
import uuid

from fastapi import APIRouter, Depends, Header, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy import delete
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_family
from app.core.config import get_settings
from app.core.db import get_db
from app.core.request_logging import spawn_persist_request_log
from app.core.security import AuthContext, get_current_auth_optional
from app.models.family import Family
from app.models.kid import Kid
from app.scheduler.jobs import run_refresh

router = APIRouter(prefix="/internal", tags=["internal"])
settings = get_settings()
requests_logger = logging.getLogger("app.requests")


class ClientMetricIn(BaseModel):
    # The frontend route/action being timed (e.g. "/home", not a raw
    # third-party URL) — kept short and free-text since the set of
    # screens/actions will keep growing.
    path: str = Field(max_length=256)
    method: str = Field(default="GET", max_length=16)
    duration_ms: float = Field(ge=0)
    status_code: int | None = None
    # e.g. "fetch failed", a thrown error's message — never a stack trace.
    detail: str | None = Field(default=None, max_length=512)


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


@router.post("/client-metrics")
async def report_client_metric(
    payload: ClientMetricIn,
    auth: AuthContext | None = Depends(get_current_auth_optional),
) -> dict:
    """Frontend-reported timing (see frontend/src/lib/api.ts's request()) —
    logged the same way as a backend request (see app/core/request_logging.py)
    so slow-client vs. slow-server can actually be told apart. Auth is
    optional: a metric from a signed-out screen (e.g. the sign-in page
    itself) is still worth logging, just without a family/user attached.
    """
    entry = {
        "request_id": uuid.uuid4(),
        "source": "client",
        "method": payload.method,
        "path": payload.path,
        "status_code": payload.status_code,
        "duration_ms": payload.duration_ms,
        "family_id": auth.family_id if auth else None,
        "user_id": auth.user_id if auth else None,
        "error": payload.detail,
    }
    requests_logger.info(json.dumps(entry, default=str))
    spawn_persist_request_log(entry)
    return {"status": "ok"}
