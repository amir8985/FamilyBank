"""Google's own servers verify the ID token (google_id_token.verify_oauth2_token)
— that's the one external boundary this suite can't safely call for real
(no way to mint a genuine Google-signed token in a test, and scripted
calls to Google's endpoints are themselves the kind of thing that gets
flagged). Everything on our side of that boundary is tested for real by
monkeypatching just that one function.
"""

from sqlalchemy import select

from app.models.family import Family
from app.models.user import User


def _fake_verify(claims: dict):
    def _verify(raw_id_token: str) -> dict:
        return claims

    return _verify


async def test_first_sign_in_creates_family_and_user(client, db_session, monkeypatch):
    monkeypatch.setattr(
        "app.api.routes_auth.verify_google_id_token",
        _fake_verify({"email": "new-parent@example.com", "sub": "google-sub-123"}),
    )

    resp = await client.post("/auth/sync", json={"id_token": "whatever"})
    assert resp.status_code == 200
    body = resp.json()
    assert body["email"] == "new-parent@example.com"
    assert body["base_currency"] == "USD"  # v1 default
    assert "session_token" in body

    user = await db_session.scalar(select(User).where(User.google_sub == "google-sub-123"))
    assert user is not None
    assert user.consent_accepted_at is not None  # stamped at signup, front-end gates the button
    family = await db_session.get(Family, user.family_id)
    assert family is not None
    assert family.onboarding_completed is False  # new family needs onboarding


async def test_second_sign_in_reuses_existing_family(client, db_session, monkeypatch):
    claims = {"email": "returning-parent@example.com", "sub": "google-sub-456"}
    monkeypatch.setattr("app.api.routes_auth.verify_google_id_token", _fake_verify(claims))

    first = await client.post("/auth/sync", json={"id_token": "whatever"})
    second = await client.post("/auth/sync", json={"id_token": "whatever-again"})

    assert first.json()["family_id"] == second.json()["family_id"]
    assert first.json()["user_id"] == second.json()["user_id"]

    users = list(await db_session.scalars(select(User).where(User.google_sub == "google-sub-456")))
    assert len(users) == 1  # not duplicated on repeat sign-in


async def test_invalid_google_token_is_rejected(client, monkeypatch):
    def _raise(raw_id_token: str):
        raise ValueError("Token has wrong audience")

    monkeypatch.setattr("app.api.routes_auth.verify_google_id_token", _raise)

    resp = await client.post("/auth/sync", json={"id_token": "bad"})
    assert resp.status_code == 401


async def test_sync_response_missing_email_rejected(client, monkeypatch):
    monkeypatch.setattr(
        "app.api.routes_auth.verify_google_id_token", _fake_verify({"sub": "no-email-sub"})
    )
    resp = await client.post("/auth/sync", json={"id_token": "whatever"})
    assert resp.status_code == 400
