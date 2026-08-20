import asyncio
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api import (
    routes_auth,
    routes_catalog,
    routes_debt,
    routes_family,
    routes_internal,
    routes_investing,
    routes_kids,
)
from app.core.config import get_settings
from app.scheduler.loop import run_forever

settings = get_settings()

# Makes the scheduler's "starting" / "refresh complete" / "refresh failed"
# log lines actually show up — without this, INFO records propagate to a
# root logger with no handler and are silently dropped.
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")


@asynccontextmanager
async def lifespan(app: FastAPI):
    task = None
    if settings.scheduler_enabled:
        task = asyncio.create_task(run_forever())
    yield
    if task is not None:
        task.cancel()


app = FastAPI(title="FamilyBank API", version="1.0.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(routes_auth.router)
app.include_router(routes_kids.router)
app.include_router(routes_debt.router)
app.include_router(routes_investing.router)
app.include_router(routes_catalog.router)
app.include_router(routes_family.router)
app.include_router(routes_internal.router)


@app.get("/health")
async def health() -> dict:
    return {"status": "ok"}
