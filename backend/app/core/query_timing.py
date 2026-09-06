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


def start_tracking() -> None:
    """Called once per request (see request_logging.py) — starts a fresh
    per-request accumulator in this asyncio Task's context."""
    _query_durations_ms.set([])


def get_query_stats() -> tuple[int, float]:
    """(query_count, total_ms) spent actually running queries during the
    current request. (0, 0.0) if tracking was never started for it."""
    durations = _query_durations_ms.get()
    if durations is None:
        return 0, 0.0
    return len(durations), sum(durations)


@event.listens_for(Engine, "before_cursor_execute")
def _before_cursor_execute(conn, cursor, statement, parameters, context, executemany):
    context._query_timing_start = time.perf_counter()


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
