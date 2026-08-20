from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.family import Family


async def test_family_fixture_creates_and_rolls_back(db_session: AsyncSession, family: Family):
    found = await db_session.get(Family, family.id)
    assert found is not None
    assert found.base_currency == "USD"


async def test_client_hits_real_app(client, auth_headers):
    resp = await client.get("/family/settings", headers=auth_headers)
    assert resp.status_code == 200
    assert resp.json() == {"base_currency": "USD", "onboarding_completed": True}


async def test_rollback_actually_isolates(db_session: AsyncSession):
    # If a previous test's rollback failed, this symbol would already exist.
    from app.models.catalog import AssetCatalog

    existing = await db_session.scalar(select(AssetCatalog).where(AssetCatalog.symbol == "TEST"))
    assert existing is None
