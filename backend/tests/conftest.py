"""Test isolation strategy: every test runs inside one outer database
transaction that's rolled back at teardown, using SQLAlchemy's
`join_transaction_mode="create_savepoint"` so that even the app code's
own internal `session.commit()` calls (buy/sell, debt updates, ...) only
release/recreate a SAVEPOINT instead of actually committing. Nothing a
test does is ever visible to another connection or persists afterward —
this is safe to run against a real dev database (Postgres-specific
column types like the enums/UUID/JSONB mean SQLite isn't an option here).
"""

import uuid
from datetime import datetime, timedelta, timezone
from decimal import Decimal

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine

from app.core import request_logging
from app.core.config import get_settings
from app.core.db import get_db
from app.core.security import issue_session_token
from app.main import app
from app.models.catalog import AssetCatalog, AssetKind, PriceCache
from app.models.family import Family
from app.models.user import User
from app.services.investing_service import clear_price_context_cache

settings = get_settings()


@pytest.fixture(autouse=True)
def _no_request_log_persistence():
    # RequestLoggingMiddleware writes through its own connection
    # (SessionLocal), not the request-scoped session the `client` fixture
    # overrides below — left enabled, every request made during the test
    # suite would insert a real, never-rolled-back row into the shared
    # dev/test database. See request_logging.set_persist_enabled's docstring.
    request_logging.set_persist_enabled(False)
    yield
    request_logging.set_persist_enabled(True)


@pytest_asyncio.fixture
async def db_session():
    # investing_service caches the catalog/price/FX context in-process
    # (see its module docstring) — clear it so one test's seeded data
    # can't leak into another's cached read via a shared process-level
    # cache that outlives each test's rolled-back transaction.
    clear_price_context_cache()

    engine = create_async_engine(settings.database_url)
    connection = await engine.connect()
    trans = await connection.begin()
    session = AsyncSession(bind=connection, join_transaction_mode="create_savepoint", expire_on_commit=False)

    try:
        yield session
    finally:
        await session.close()
        await trans.rollback()
        await connection.close()
        await engine.dispose()
        clear_price_context_cache()


@pytest_asyncio.fixture
async def client(db_session: AsyncSession):
    async def _get_test_db():
        yield db_session

    app.dependency_overrides[get_db] = _get_test_db
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c
    app.dependency_overrides.clear()


@pytest_asyncio.fixture
async def family(db_session: AsyncSession) -> Family:
    fam = Family(base_currency="USD", onboarding_completed=True)
    db_session.add(fam)
    await db_session.flush()
    return fam


@pytest_asyncio.fixture
async def user(db_session: AsyncSession, family: Family) -> User:
    u = User(family_id=family.id, email="test@example.com", google_sub=f"sub-{uuid.uuid4()}", name="Test Parent")
    db_session.add(u)
    await db_session.flush()
    return u


@pytest.fixture
def auth_headers(user: User) -> dict[str, str]:
    token = issue_session_token(user.id, user.family_id, user.email)
    return {"Authorization": f"Bearer {token}"}


@pytest_asyncio.fixture
async def seeded_asset(db_session: AsyncSession) -> AssetCatalog:
    """One stock, priced in USD, with a cached price + 2-day history —
    everything buy()/sell()/quote/portfolio tests need."""
    asset = AssetCatalog(symbol="TEST", display_name="Test Co", kind=AssetKind.STOCK, description="A test stock.")
    db_session.add(asset)

    now = datetime.now(timezone.utc)
    price = PriceCache(
        symbol="TEST",
        price=Decimal("100.00"),
        currency="USD",
        updated_at=now,
        history_json=[
            {"date": (now - timedelta(days=1)).strftime("%Y-%m-%d"), "close": 90.0},
            {"date": now.strftime("%Y-%m-%d"), "close": 100.0},
        ],
    )
    db_session.add(price)
    # No same-currency FxRateCache row needed — rate_from_table/get_rate
    # short-circuit base==quote to 1.0 without a DB lookup.
    await db_session.flush()
    return asset


@pytest_asyncio.fixture
async def seeded_basket(db_session: AsyncSession) -> AssetCatalog:
    basket = AssetCatalog(symbol="TESTB", display_name="Test Basket", kind=AssetKind.BASKET, description="")
    db_session.add(basket)
    price = PriceCache(
        symbol="TESTB",
        price=Decimal("50.00"),
        currency="USD",
        updated_at=datetime.now(timezone.utc),
        history_json=[],
    )
    db_session.add(price)
    await db_session.flush()
    return basket
