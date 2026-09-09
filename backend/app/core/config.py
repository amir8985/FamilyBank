from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # Postgres connection string, asyncpg driver, e.g.:
    # postgresql+asyncpg://user:password@host:5432/dbname
    database_url: str

    # Must match the frontend's GOOGLE_CLIENT_ID — used to verify the
    # audience of Google ID tokens presented at /auth/sync.
    google_client_id: str

    # Signs the session JWTs this backend issues after a successful
    # Google sign-in. Frontend never sees this value.
    backend_jwt_secret: str
    backend_jwt_algorithm: str = "HS256"
    backend_jwt_ttl_days: int = 30
    # Kid session tokens live much longer than a parent's — a kid
    # re-authing means a parent has to generate and send a new link, so a
    # short TTL is all downside. Revocation is handled by kids.token_version
    # (bumped on every claim), not by expiry. ~1 year: a kid who uses the
    # app at all never hits it; one who hasn't opened it in a year getting
    # a fresh link is reasonable.
    kid_jwt_ttl_days: int = 365

    # Shared secret the scheduler's cron trigger must present.
    internal_scheduler_secret: str

    cors_origins: str = "http://localhost:3000"

    # Where the kid-facing app lives — used only to build the invite link
    # a parent shares (routes_kid_auth). Defaults to the first CORS origin
    # if left unset.
    frontend_base_url: str = ""

    # Kid invite (routes_kid_auth): how long a generated link + PIN stays
    # usable (it's multi-use within this window — phone + laptop off one
    # link), and how many wrong-PIN tries before it's burned and the
    # parent must generate a new one.
    kid_invite_ttl_hours: int = 24
    kid_claim_max_attempts: int = 5

    default_base_currency: str = "USD"

    # Gates dev-only endpoints (see routes_internal.py's /internal/dev-reset)
    # — must be explicitly true; never set this in a real deployment.
    dev_mode: bool = False

    # In-process price/FX refresh loop (see app/scheduler/loop.py). Runs
    # only while this process is alive, so it's the right mechanism for a
    # long-running deployment (local dev, Railway, ...) — a serverless
    # deployment (Vercel) has no long-running process to run this in and
    # should instead hit POST /internal/refresh from an external cron,
    # with this disabled to avoid refreshing twice.
    scheduler_enabled: bool = True
    scheduler_interval_hours: float = 5.0

    # Staleness fallback (see app/scheduler/jobs.spawn_refresh_if_stale):
    # when SCHEDULER_ENABLED is false and an *external* cron drives the
    # refresh (Cloud Scheduler → POST /internal/refresh), a user-facing
    # read (/home, /catalog) triggers a best-effort catch-up refresh if
    # the cached prices are older than this. Insurance for a missed cron
    # run — not the primary mechanism. Must sit well above the normal gap
    # between runs: the production Cloud Scheduler cron fires every 3h
    # (`1 */3 * * *` UTC), so ~10h ≈ 3 consecutive missed runs — clearly
    # abnormal, but far enough out that a single hiccup won't trip it.
    refresh_staleness_threshold_hours: float = 10.0

    # request_logs has no other retention mechanism — every backend
    # request and every client-reported metric writes a row (see
    # app/core/request_logging.py), and nothing ever deletes one. Fine at
    # today's traffic; at real scale (thousands of users) this table
    # grows forever, which costs real Neon storage and eventually slows
    # down the very diagnostic queries it exists to make possible. The
    # scheduler prunes rows older than this on every refresh cycle (see
    # app/scheduler/jobs.cleanup_old_request_logs).
    request_log_retention_days: int = 30

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]

    @property
    def frontend_origin(self) -> str:
        """Base URL for links pointed back at the web app. Explicit
        FRONTEND_BASE_URL wins; otherwise fall back to the first CORS
        origin (which in every real deployment is the web app)."""
        if self.frontend_base_url.strip():
            return self.frontend_base_url.strip().rstrip("/")
        origins = self.cors_origin_list
        return origins[0].rstrip("/") if origins else "http://localhost:3000"


@lru_cache
def get_settings() -> Settings:
    return Settings()
