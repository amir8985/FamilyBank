from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase

from app.core.config import get_settings

settings = get_settings()

engine = create_async_engine(
    settings.database_url,
    # pool_pre_ping issues an extra round-trip on every single checkout
    # to test the connection before use — measured at ~100-150ms added
    # per request against Neon (doubling latency for a trivial query).
    # pool_recycle guards against stale/dropped connections instead,
    # without paying that cost on every request.
    pool_pre_ping=False,
    pool_recycle=280,
)
SessionLocal = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)


class Base(DeclarativeBase):
    pass


async def get_db() -> AsyncIterator[AsyncSession]:
    async with SessionLocal() as session:
        yield session


@asynccontextmanager
async def transaction(session: AsyncSession) -> AsyncIterator[AsyncSession]:
    """Wrap a block of writes so they succeed or fail together.

    Buy/sell and debt updates touch multiple tables (debt ledger +
    holdings + transaction log) and must not partially commit.

    A FastAPI request session very often already has an open transaction
    by the time a service function runs — any `Depends(get_kid)` /
    `Depends(get_family)` already ran a `db.get(...)`, which SQLAlchemy's
    "autobegin" turns into an open transaction before the route body
    even starts. In that case this uses a SAVEPOINT (`begin_nested`)
    instead of a real `begin()` — a real `begin()` would be a no-op when
    one's already open, silently skipping the commit that's supposed to
    happen here, and leaving the caller solely responsible for the outer
    commit (routes still call `db.commit()` — see routes_investing.py).
    """
    if session.in_transaction():
        async with session.begin_nested():
            yield session
        return
    async with session.begin():
        yield session
