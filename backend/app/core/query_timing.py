"""Per-request DB query timing — attaches directly to SQLAlchemy's own
query-execution events, so a request's total duration can be broken down
into "time actually spent running queries" vs. everything else (Python
processing, external calls, waiting on a connection), instead of
guessing from end-to-end totals. This is what the
observability-logging investigation escalated to once request-level
timing alone couldn't explain the numbers.

Works for the async engine too: SQLAlchemy's asyncio support wraps the
same Core engine internally (via greenlet), so these are the same
`before_cursor_execute`/`after_cursor_execute`/`connect` events either way.
"""

import contextvars
import logging
import time

from sqlalchemy import event
from sqlalchemy.engine import Engine

logger = logging.getLogger("app.db")

_query_durations_ms: contextvars.ContextVar[list[float] | None] = contextvars.ContextVar(
    "query_durations_ms", default=None
)
# Wall-clock time (time.perf_counter()) the request started, and how long
# after that the *first* query's cursor actually began executing — the
# request_logging middleware's own comment already names the candidates
# for the gap between duration_ms and db_time_ms ("Python processing,
# external calls, or waiting for a connection to free up"); this narrows
# it down. Everything before the first query — FastAPI/dependency
# resolution, and critically, the connection pool checkout (including a
# brand-new physical connection's full TCP+TLS+auth handshake if none was
# available) — lands in this number and nowhere else, since
# before_cursor_execute only fires once a connection is already in hand.
_request_start: contextvars.ContextVar[float | None] = contextvars.ContextVar(
    "request_start", default=None
)
_time_to_first_query_ms: contextvars.ContextVar[float | None] = contextvars.ContextVar(
    "time_to_first_query_ms", default=None
)


def start_tracking(request_start: float | None = None) -> None:
    """Called once per request (see request_logging.py) — starts a fresh
    per-request accumulator in this asyncio Task's context. `request_start`
    (the same time.perf_counter() value the middleware timed the whole
    request from) is what time-to-first-query is measured against."""
    _query_durations_ms.set([])
    _request_start.set(request_start)
    _time_to_first_query_ms.set(None)


def get_query_stats() -> tuple[int, float, float | None]:
    """(query_count, total_ms, time_to_first_query_ms) for the current
    request — the last is None if no query ran, or tracking was never
    started. (0, 0.0, None) in that latter case."""
    durations = _query_durations_ms.get()
    if durations is None:
        return 0, 0.0, None
    return len(durations), sum(durations), _time_to_first_query_ms.get()


@event.listens_for(Engine, "before_cursor_execute")
def _before_cursor_execute(conn, cursor, statement, parameters, context, executemany):
    now = time.perf_counter()
    context._query_timing_start = now

    durations = _query_durations_ms.get()
    request_start = _request_start.get()
    if durations is not None and not durations and request_start is not None:
        # First query of this request — everything up to this point
        # (dependency resolution, connection pool checkout, a fresh
        # connection's handshake if one was needed) is captured here.
        _time_to_first_query_ms.set((now - request_start) * 1000)


@event.listens_for(Engine, "after_cursor_execute")
def _after_cursor_execute(conn, cursor, statement, parameters, context, executemany):
    duration_ms = (time.perf_counter() - context._query_timing_start) * 1000
    durations = _query_durations_ms.get()
    if durations is not None:
        durations.append(duration_ms)
    if duration_ms > 300:
        # Logged immediately, not just folded into a request-level total,
        # so one bad query is traceable to its actual SQL.
        one_line = " ".join(str(statement).split())
        logger.warning("slow query (%.1fms): %s", duration_ms, one_line[:300])


@event.listens_for(Engine, "connect")
def _on_new_physical_connection(dbapi_connection, connection_record):
    # Fires only when SQLAlchemy opens a brand-new physical connection
    # (a real TCP+TLS+Postgres-auth handshake) — never on a connection
    # reused from the pool. If this shows up on every request instead of
    # rarely, the pool isn't actually being reused and every query is
    # paying a full fresh-connection handshake on top of normal latency.
    logger.info("db: established a new physical connection (not reused from pool)")
