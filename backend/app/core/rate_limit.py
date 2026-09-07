"""A minimal in-memory, per-IP sliding-window rate limiter.

Built specifically for POST /internal/client-metrics — the one endpoint
in this app with no auth requirement, no shared secret, and no cap of
any kind (see its docstring in routes_internal.py and CLAUDE.md's
"Known limitation, not addressed" entry). Anyone on the internet can
already reach it; without this, a flood of POSTs grows `request_logs`
and costs real Neon storage/compute with nothing to stop it.

Deliberately simple, not a generic rate-limiting framework: in-process
memory, not Redis or any shared store, so this only limits *this one
process's* view of each IP. Fine for the app's current single-instance
deployment (see render.yaml); if this backend ever runs as more than
one instance, each instance enforces the cap independently, which still
bounds worst-case load per instance even though it can't coordinate a
single global limit across them. Revisit with a shared store (Redis)
if/when that becomes the deployment shape.
"""

import time
from collections import defaultdict

_WINDOW_SECONDS = 60.0
_MAX_REQUESTS_PER_WINDOW = 30

_hits: dict[str, list[float]] = defaultdict(list)


def _prune(now: float) -> None:
    # Runs on every call rather than on a timer — cheap at this app's
    # scale (unique concurrent IPs, not total requests, bounds the work),
    # and avoids needing a background task just to stop this dict from
    # growing forever as new IPs show up over the process's lifetime.
    stale_keys = []
    for ip, timestamps in _hits.items():
        fresh = [t for t in timestamps if now - t < _WINDOW_SECONDS]
        if fresh:
            _hits[ip] = fresh
        else:
            stale_keys.append(ip)
    for ip in stale_keys:
        del _hits[ip]


def is_rate_limited(client_ip: str) -> bool:
    """True if `client_ip` has already made _MAX_REQUESTS_PER_WINDOW+
    calls in the last _WINDOW_SECONDS — the caller should reject the
    request (429) without recording this attempt as a new hit."""
    now = time.monotonic()
    _prune(now)
    return len(_hits[client_ip]) >= _MAX_REQUESTS_PER_WINDOW


def record_hit(client_ip: str) -> None:
    _hits[client_ip].append(time.monotonic())


def clear_rate_limit_state() -> None:
    """Test-only: `_hits` is module-level, process-lifetime state (same
    class of thing as investing_service's price-context cache — see
    CLAUDE.md's "Lessons learned"), and httpx's ASGITransport gives every
    test request the same fake client address by default. Without
    resetting this between tests, one test hitting the limit would
    silently poison every later test's ability to call this endpoint at
    all — see tests/conftest.py's db_session fixture."""
    _hits.clear()
