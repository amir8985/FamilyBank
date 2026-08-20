from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase

from app.core.config import get_settings

settings = get_settings()

engine = create_async_engine(settings.database_url, pool_pre_ping=True)
SessionLocal = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)


class Base(DeclarativeBase):
    pass


async def get_db() -> AsyncIterator[AsyncSession]:
    async with SessionLocal() as session:
        yield session


@asynccontextmanager
async def transaction(session: AsyncSession) -> AsyncIterator[AsyncSession]:
    """Wrap a block of writes in a single atomic transaction.

    Buy/sell and debt updates touch multiple tables (debt ledger +
    holdings + transaction log) and must not partially commit.
    """
    if session.in_transaction():
        # Nested call within an already-open transaction (e.g. a route
        # that opens one and calls two services) — just reuse it.
        yield session
        return
    async with session.begin():
        yield session
