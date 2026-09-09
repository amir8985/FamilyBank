"""Kid-facing login (spec 4.1 v2): a parent generates a per-kid invite
(link + spoken PIN), the kid claims it on each device (multi-use within
the window), and that session is hard-scoped to exactly one kid —
trade-only, never Settings, never a sibling's data. The parent's
"sign out of all devices" is the revocation lever.
"""

from datetime import datetime, timedelta, timezone
from decimal import Decimal

import pytest

from sqlalchemy import select

from app.core.security import issue_kid_session_token
from app.models.kid import Kid, KidInvite
from app.models.savings import SavingsPlan


@pytest.fixture
async def kid(db_session, family):
    k = Kid(family_id=family.id, name="Maya", avatar_color="amber")
    db_session.add(k)
    await db_session.flush()
    return k


def kid_headers(kid: Kid) -> dict[str, str]:
    return {"Authorization": f"Bearer {issue_kid_session_token(kid.id, kid.family_id, kid.token_version)}"}


async def _make_invite(client, auth_headers, kid: Kid) -> dict:
    resp = await client.post(f"/kids/{kid.id}/invite", headers=auth_headers)
    assert resp.status_code == 201, resp.text
    return resp.json()


# --- invite generation -------------------------------------------------

async def test_parent_generates_an_invite_with_link_and_pin(client, kid, auth_headers):
    body = await _make_invite(client, auth_headers, kid)
    assert "/kid/join/" in body["claim_url"]
    assert len(body["pin"]) == 6 and body["pin"].isdigit()
    assert "expires_at" in body


async def test_regenerating_replaces_the_previous_invite(client, kid, auth_headers, db_session):
    first = await _make_invite(client, auth_headers, kid)
    second = await _make_invite(client, auth_headers, kid)
    assert first["claim_url"] != second["claim_url"]
    rows = (await db_session.scalars(select(KidInvite).where(KidInvite.kid_id == kid.id))).all()
    assert len(rows) == 1  # only the latest survives


async def test_invite_generation_is_parent_only(client, kid):
    resp = await client.post(f"/kids/{kid.id}/invite", headers=kid_headers(kid))
    assert resp.status_code == 403


async def test_invite_status_reports_pending_and_sessions(client, kid, auth_headers):
    status = (await client.get(f"/kids/{kid.id}/invite", headers=auth_headers)).json()
    assert status == {"has_pending_invite": False, "sessions_active": False, "expires_at": None}

    await _make_invite(client, auth_headers, kid)
    status = (await client.get(f"/kids/{kid.id}/invite", headers=auth_headers)).json()
    assert status["has_pending_invite"] is True
    assert status["sessions_active"] is False


# --- claiming ---------------------------------------------------------

def _token_from_url(claim_url: str) -> str:
    return claim_url.rsplit("/", 1)[1]


async def test_claim_with_correct_pin_returns_a_kid_session(client, kid, auth_headers, db_session):
    invite = await _make_invite(client, auth_headers, kid)
    resp = await client.post(
        "/kid-auth/claim",
        json={"claim_token": _token_from_url(invite["claim_url"]), "pin": invite["pin"]},
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["kid_id"] == str(kid.id)
    assert body["public_id"] == kid.public_id
    assert body["kid_name"] == "Maya"
    assert body["base_currency"] == "USD"

    # a plain claim does NOT bump token_version (additive — another device)
    await db_session.refresh(kid)
    assert kid.token_version == 0
    assert kid.sessions_active is True

    # the returned token works — and the kid's own public_id resolves in URLs
    hdr = {"Authorization": f"Bearer {body['session_token']}"}
    assert (await client.get("/kid/me", headers=hdr)).json()["kid_id"] == str(kid.id)
    assert (await client.get(f"/kids/{kid.public_id}/portfolio", headers=hdr)).status_code == 200


async def test_claim_is_multi_use_within_its_window(client, kid, auth_headers):
    invite = await _make_invite(client, auth_headers, kid)
    token = _token_from_url(invite["claim_url"])
    # phone
    first = await client.post("/kid-auth/claim", json={"claim_token": token, "pin": invite["pin"]})
    assert first.status_code == 200
    # laptop — same link, still works, and the first session is unaffected
    second = await client.post("/kid-auth/claim", json={"claim_token": token, "pin": invite["pin"]})
    assert second.status_code == 200
    for body in (first.json(), second.json()):
        hdr = {"Authorization": f"Bearer {body['session_token']}"}
        assert (await client.get("/kid/me", headers=hdr)).status_code == 200


async def test_sign_out_all_devices_revokes_every_session(client, kid, auth_headers, db_session):
    invite = await _make_invite(client, auth_headers, kid)
    token = _token_from_url(invite["claim_url"])
    s1 = (await client.post("/kid-auth/claim", json={"claim_token": token, "pin": invite["pin"]})).json()
    s2 = (await client.post("/kid-auth/claim", json={"claim_token": token, "pin": invite["pin"]})).json()
    h1 = {"Authorization": f"Bearer {s1['session_token']}"}
    h2 = {"Authorization": f"Bearer {s2['session_token']}"}
    assert (await client.get("/kid/me", headers=h1)).status_code == 200

    out = await client.post(f"/kids/{kid.id}/sign-out-all", headers=auth_headers)
    assert out.status_code == 204

    assert (await client.get("/kid/me", headers=h1)).status_code == 401
    assert (await client.get("/kid/me", headers=h2)).status_code == 401
    await db_session.refresh(kid)
    assert kid.sessions_active is False

    # sign-out-all is parent-only (403 for a kid token; or 401 since the
    # kid token we hold is now revoked — either way, denied)
    assert (await client.post(f"/kids/{kid.id}/sign-out-all", headers=h1)).status_code in (401, 403)


async def test_wrong_pin_is_rejected_and_burns_after_max_attempts(client, kid, auth_headers):
    invite = await _make_invite(client, auth_headers, kid)
    token = _token_from_url(invite["claim_url"])
    for _ in range(5):
        bad = await client.post("/kid-auth/claim", json={"claim_token": token, "pin": "000000"})
        assert bad.status_code == 400
    # now burned — even the correct PIN no longer works
    good = await client.post("/kid-auth/claim", json={"claim_token": token, "pin": invite["pin"]})
    assert good.status_code == 400


async def test_expired_invite_cannot_be_claimed(client, kid, auth_headers, db_session):
    invite = await _make_invite(client, auth_headers, kid)
    row = await db_session.scalar(select(KidInvite).where(KidInvite.kid_id == kid.id))
    row.expires_at = datetime.now(timezone.utc) - timedelta(hours=1)
    await db_session.flush()
    resp = await client.post(
        "/kid-auth/claim",
        json={"claim_token": _token_from_url(invite["claim_url"]), "pin": invite["pin"]},
    )
    assert resp.status_code == 400


async def test_unknown_claim_token_is_rejected(client):
    resp = await client.post("/kid-auth/claim", json={"claim_token": "nope", "pin": "123456"})
    assert resp.status_code == 400


# --- token_version revocation ---------------------------------------

async def test_stale_token_version_is_401(client, kid, db_session):
    headers = kid_headers(kid)
    assert (await client.get("/kid/me", headers=headers)).status_code == 200
    kid.token_version += 1
    await db_session.flush()
    assert (await client.get("/kid/me", headers=headers)).status_code == 401
    assert (await client.get(f"/kids/{kid.public_id}/portfolio", headers=headers)).status_code == 401


# --- what a kid session CAN do --------------------------------------

async def test_kid_can_read_its_own_portfolio_history_and_catalog(client, kid, seeded_asset):
    headers = kid_headers(kid)
    assert (await client.get(f"/kids/{kid.id}/portfolio", headers=headers)).status_code == 200
    assert (await client.get(f"/kids/{kid.id}/debt", headers=headers)).status_code == 200
    assert (await client.get(f"/kids/{kid.id}/investment-transactions", headers=headers)).status_code == 200
    assert (await client.get(f"/kids/{kid.id}/savings", headers=headers)).status_code == 200
    assert (await client.get("/catalog", headers=headers)).status_code == 200


async def test_kid_can_trade_within_its_own_balance(client, kid, auth_headers, seeded_asset):
    # fund the kid first (parent action)
    await client.post(f"/kids/{kid.id}/debt", headers=auth_headers, json={"type": "add", "amount": 500})
    headers = kid_headers(kid)
    buy = await client.post(f"/kids/{kid.id}/buy", headers=headers, json={"symbol": "TEST", "units": 1})
    assert buy.status_code == 201, buy.text
    # sell by lot (buys create per-lot positions now — see boost feature)
    portfolio = (await client.get(f"/kids/{kid.id}/portfolio", headers=headers)).json()
    lot_id = portfolio["holdings"][0]["lot_id"]
    sell = await client.post(
        f"/kids/{kid.id}/sell", headers=headers, json={"lot_id": lot_id, "units": 1}
    )
    assert sell.status_code == 201, sell.text


async def test_kid_can_move_cash_into_and_out_of_savings(client, kid, auth_headers, db_session):
    await client.post(f"/kids/{kid.id}/debt", headers=auth_headers, json={"type": "add", "amount": 200})
    plan = SavingsPlan(family_id=kid.family_id, name="Piggy", monthly_rate=Decimal("1.0"), lock_months=0)
    db_session.add(plan)
    await db_session.flush()

    headers = kid_headers(kid)
    dep = await client.post(
        f"/kids/{kid.id}/savings/deposit", headers=headers, json={"plan_id": str(plan.id), "amount": 50}
    )
    assert dep.status_code == 201, dep.text
    deposit_id = dep.json()["deposit_id"]
    wd = await client.post(f"/kids/{kid.id}/savings/{deposit_id}/withdraw", headers=headers)
    assert wd.status_code == 200, wd.text


# --- what a kid session CANNOT do ---------------------------------

async def test_kid_cannot_add_money_to_its_own_balance(client, kid):
    resp = await client.post(
        f"/kids/{kid.id}/debt", headers=kid_headers(kid), json={"type": "add", "amount": 100}
    )
    assert resp.status_code == 403


async def test_kid_cannot_reach_settings_or_family_wide_endpoints(client, kid):
    headers = kid_headers(kid)
    assert (await client.get("/home", headers=headers)).status_code == 403
    assert (await client.get("/family/settings", headers=headers)).status_code == 403
    assert (await client.patch("/family/settings", headers=headers, json={"base_currency": "EUR"})).status_code == 403
    assert (await client.post("/kids", headers=headers, json={"name": "Sibling"})).status_code == 403
    assert (await client.delete(f"/kids/{kid.id}", headers=headers)).status_code == 403
    assert (await client.get("/family/savings-plans", headers=headers)).status_code == 403


async def test_kid_cannot_touch_a_siblings_data(client, db_session, family, kid):
    sibling = Kid(family_id=family.id, name="Noam", avatar_color="teal")
    db_session.add(sibling)
    await db_session.flush()

    headers = kid_headers(kid)  # Maya's session
    for ref in (str(sibling.id), sibling.public_id):
        assert (await client.get(f"/kids/{ref}/portfolio", headers=headers)).status_code == 404
        assert (await client.get(f"/kids/{ref}/debt", headers=headers)).status_code == 404
        assert (
            await client.post(f"/kids/{ref}/buy", headers=headers, json={"symbol": "TEST", "units": 1})
        ).status_code == 404


async def test_kid_me_rejects_a_parent_token(client, auth_headers):
    assert (await client.get("/kid/me", headers=auth_headers)).status_code == 403


async def test_parent_token_still_works_everywhere(client, kid, auth_headers):
    # regression guard: the require_parent / get_family changes must not
    # have broken the parent's own access.
    assert (await client.get("/home", headers=auth_headers)).status_code == 200
    assert (await client.get(f"/kids/{kid.id}/portfolio", headers=auth_headers)).status_code == 200
    assert (await client.get("/family/settings", headers=auth_headers)).status_code == 200
