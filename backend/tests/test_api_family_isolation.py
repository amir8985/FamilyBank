"""Architecture 5.5 flags this as THE thing to stress-test: a kid_id (or
any other resource) from one family must never be reachable through
another family's session — not a 200 with wrong data, not even a 403
that leaks existence. It should 404, exactly as if the resource didn't
exist at all.
"""

from app.core.security import issue_session_token
from app.models.family import Family
from app.models.kid import Kid
from app.models.user import User


async def _second_family_headers(db_session) -> dict[str, str]:
    other_family = Family(base_currency="EUR", onboarding_completed=True)
    db_session.add(other_family)
    await db_session.flush()
    other_user = User(family_id=other_family.id, email="other@example.com", google_sub="other-sub")
    db_session.add(other_user)
    await db_session.flush()
    token = issue_session_token(other_user.id, other_family.id, other_user.email)
    return {"Authorization": f"Bearer {token}"}


async def test_cannot_view_another_familys_kid_portfolio(client, db_session, family, auth_headers):
    kid = Kid(family_id=family.id, name="Belongs To Family A", avatar_color="amber")
    db_session.add(kid)
    await db_session.flush()

    other_headers = await _second_family_headers(db_session)
    resp = await client.get(f"/kids/{kid.id}/portfolio", headers=other_headers)
    assert resp.status_code == 404


async def test_cannot_add_debt_to_another_familys_kid(client, db_session, family, auth_headers):
    kid = Kid(family_id=family.id, name="Belongs To Family A", avatar_color="amber")
    db_session.add(kid)
    await db_session.flush()

    other_headers = await _second_family_headers(db_session)
    resp = await client.post(
        f"/kids/{kid.id}/debt", headers=other_headers, json={"type": "add", "amount": 100}
    )
    assert resp.status_code == 404


async def test_cannot_buy_for_another_familys_kid(client, db_session, family, auth_headers, seeded_asset):
    kid = Kid(family_id=family.id, name="Belongs To Family A", avatar_color="amber")
    db_session.add(kid)
    await db_session.flush()

    other_headers = await _second_family_headers(db_session)
    resp = await client.post(
        f"/kids/{kid.id}/buy", headers=other_headers, json={"symbol": "TEST", "units": 1}
    )
    assert resp.status_code == 404


async def test_cannot_delete_another_familys_kid(client, db_session, family, auth_headers):
    kid = Kid(family_id=family.id, name="Belongs To Family A", avatar_color="amber")
    db_session.add(kid)
    await db_session.flush()

    other_headers = await _second_family_headers(db_session)
    resp = await client.delete(f"/kids/{kid.id}", headers=other_headers)
    assert resp.status_code == 404

    # Confirm it really wasn't deleted.
    still_there = await client.get("/home", headers=auth_headers)
    assert any(k["id"] == str(kid.id) for k in still_there.json()["kids"])


async def test_home_only_shows_own_familys_kids(client, db_session, family, auth_headers):
    mine = Kid(family_id=family.id, name="Mine", avatar_color="amber")
    db_session.add(mine)
    await db_session.flush()

    other_family = Family(base_currency="EUR", onboarding_completed=True)
    db_session.add(other_family)
    await db_session.flush()
    not_mine = Kid(family_id=other_family.id, name="NotMine", avatar_color="teal")
    db_session.add(not_mine)
    await db_session.flush()

    resp = await client.get("/home", headers=auth_headers)
    names = [k["name"] for k in resp.json()["kids"]]
    assert names == ["Mine"]


async def test_missing_bearer_token_is_rejected(client):
    resp = await client.get("/home")
    assert resp.status_code == 401


async def test_garbage_bearer_token_is_rejected(client):
    resp = await client.get("/home", headers={"Authorization": "Bearer not-a-real-token"})
    assert resp.status_code == 401
