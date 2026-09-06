"""Request timing + logging: a structured stdout line for every request
(cheap, always on, viewable in Render's log tail), plus a best-effort
`request_logs` row (see app/models/request_log.py) so latency can actually
be queried/aggregated across users once there's real production traffic —
this is what the "Status" entry for this feature is trying to diagnose.

Deliberately a raw ASGI middleware, not `BaseHTTPMiddleware` — the latter
buffers the whole response through an in-memory stream per request, which
is itself a measurable overhead. A timing middleware shouldn't be the
thing that makes requests slower.
"""

import asyncio
import json
import logging
import time
import uuid

from jose import JWTError, jwt
from starlette.types import ASGIApp, Receive, Scope, Send

from app.core import query_timing
from app.core.config import get_settings
from app.core.db import SessionLocal
from app.models.request_log import RequestLog

logger = logging.getLogger("app.requests")
settings = get_settings()

_persist_enabled = True


def set_persist_enabled(value: bool) -> None:
    """Test-only switch (see tests/conftest.py's autouse fixture).

    This middleware writes through its own connection (`SessionLocal`),
    not the request-scoped session tests override via `get_db` — so
    without this, every request made during the test suite would insert a
    real, never-rolled-back row into the shared dev/test database. Off by
    default in tests; on everywhere else.
    """
    global _persist_enabled
    _persist_enabled = value


def _decode_bearer(header_value: str | None) -> tuple[uuid.UUID | None, uuid.UUID | None]:
    """Best-effort decode — never raises. A missing/expired/malformed
    token just means this request's log row has no user/family attributed
    to it; the request itself is handled (or rejected) by the route's own
    auth dependency regardless.
    """
    if not header_value or not header_value.lower().startswith("bearer "):
        return None, None
    token = header_value[7:]
    try:
        payload = jwt.decode(
            token, settings.backend_jwt_secret, algorithms=[settings.backend_jwt_algorithm]
        )
        return uuid.UUID(payload["sub"]), uuid.UUID(payload["family_id"])
    except (JWTError, KeyError, ValueError):
        return None, None


async def persist_request_log(entry: dict) -> None:
    if not _persist_enabled:
        return
    try:
        async with SessionLocal() as session:
            session.add(RequestLog(**entry))
            await session.commit()
    except Exception:
        # Logging must never be the reason a request fails.
        logger.warning("failed to persist request log", exc_info=True)


_background_tasks: set[asyncio.Task] = set()


def spawn_persist_request_log(entry: dict) -> None:
    """Fire-and-forget persist_request_log — a response must never block on
    the log INSERT (see the middleware below for why). Tracked in
    _background_tasks and detached via a done-callback per asyncio's own
    warning that a Task with no other reference can be garbage-collected
    mid-flight; persist_request_log already swallows its own errors, so
    there's nothing further to do once it finishes.
    """
    task = asyncio.create_task(persist_request_log(entry))
    _background_tasks.add(task)
    task.add_done_callback(_background_tasks.discard)


class RequestLoggingMiddleware:
    def __init__(self, app: ASGIApp):
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        start = time.perf_counter()
        query_timing.start_tracking()
        status_holder: dict[str, int | None] = {"code": None}

        async def send_wrapper(message: dict) -> None:
            if message["type"] == "http.response.start":
                status_holder["code"] = message["status"]
            await send(message)

        # Look for just the one header we need rather than decoding and
        # dict-ing every header on every request — same reasoning as
        # skipping BaseHTTPMiddleware above.
        auth_header = next(
            (value.decode("latin-1") for key, value in scope.get("headers", []) if key.lower() == b"authorization"),
            None,
        )
        user_id, family_id = _decode_bearer(auth_header)

        error: str | None = None
        try:
            await self.app(scope, receive, send_wrapper)
        except Exception as exc:
            error = repr(exc)[:2000]
            raise
        finally:
            duration_ms = (time.perf_counter() - start) * 1000
            # Starlette's router sets scope["route"] in place once a route
            # matches, so it's visible here after self.app(...) returns —
            # the *template* path (e.g. "/kids/{kid_id}/debt") groups
            # stats correctly instead of fragmenting by every real UUID.
            route = scope.get("route")
            path = route.path if route is not None else scope.get("path", "")
            entry = {
                "request_id": uuid.uuid4(),
                "source": "server",
                "method": scope.get("method", ""),
                "path": path,
                "status_code": status_holder["code"] or (500 if error else None),
                "duration_ms": duration_ms,
                "family_id": family_id,
                "user_id": user_id,
                "error": error,
            }
            # db_query_count/db_time_ms are diagnostic-only (stdout, not
            # persisted — request_logs has no columns for them) — the gap
            # between duration_ms and db_time_ms is time spent NOT running
            # a query: Python processing, external calls, or waiting for a
            # connection to free up.
            db_query_count, db_time_ms = query_timing.get_query_stats()
            log_line = {**entry, "db_query_count": db_query_count, "db_time_ms": round(db_time_ms, 1)}
            logger.info(json.dumps(log_line, default=str))
            spawn_persist_request_log(entry)
