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
from app.core.request_logging import RequestLoggingMiddleware
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


app = FastAPI(
    title="FamilyBank API",
    version="1.4.0",
    lifespan=lifespan,
    # Swagger/ReDoc/schema map out the whole API surface (including
    # /internal/* route names) to anyone who visits them — harmless
    # against a properly-auth'd API, but no reason to hand it out
    # publicly either. Same dev_mode gate as the other dev-only surface
    # (routes_internal.dev_reset).
    docs_url="/docs" if settings.dev_mode else None,
    redoc_url="/redoc" if settings.dev_mode else None,
    openapi_url="/openapi.json" if settings.dev_mode else None,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
# Added after CORSMiddleware so it's the outermost layer (Starlette wraps
# in reverse order of add_middleware calls) — times the whole request,
# CORS handling included.
app.add_middleware(RequestLoggingMiddleware)

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
