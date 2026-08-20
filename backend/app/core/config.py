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

    # Shared secret the scheduler's cron trigger must present.
    internal_scheduler_secret: str

    cors_origins: str = "http://localhost:3000"

    default_base_currency: str = "ILS"

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()
