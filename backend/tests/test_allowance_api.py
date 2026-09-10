"""Allowance HTTP surface: parent CRUD + bulk apply, kid can read their
own summary (and only their own), settle-on-read, tenant isolation."""

from datetime import datetime, timedelta, timezone
from decimal import Decimal

from sqlalchemy import select

from app.core.security import issue_kid_session_token, issue_session_token
from app.models.allowance import Allowance
from app.models.family import Family
from app.models.kid import Kid
from app.models.user import User


async def _kid(db_session, family, name="Maya") -> Kid:
    kid = Kid(family_id=family.id, name=name, avatar_color="amber")
    db_session.add(kid)
    await db_session.flush()
    return kid


def _kid_headers(kid: Kid) -> dict[str, str]:
    return {"Authorization": f"Bearer {issue_kid_session_token(kid.id, kid.family_id, kid.token_version)}"}


async def _second_family_headers(db_session) -> tuple[Family, dict[str, str]]:
    other = Family(base_currency="USD", onboarding_completed=True)
    db_session.add(other)
    await db_session.flush()
    user = User(family_id=other.id, email="other@example.com", google_sub="other-sub")
    db_session.add(user)
    await db_session.flush()
    return other, {"Authorization": f"Bearer {issue_session_token(user.id, other.id, user.email)}"}


async def test_parent_sets_and_reads_a_kids_allowance(client, auth_headers, family, db_session):
    kid = await _kid(db_session, family)
    resp = await client.put(
        f"/kids/{kid.id}/allowance",
        headers=auth_headers,
        json={"amount": 12.5, "cadence": "weekly", "payday": 0, "is_active": True},
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["configured"] is True
    assert body["is_active"] is True
    assert Decimal(body["amount"]) == Decimal("12.50")
    assert body["cadence"] == "weekly"
    assert body["next_payday"] is not None
    assert body["last_paid_at"] is None
    assert body["recent_payments"] == []


async def test_get_allowance_for_unconfigured_kid(client, auth_headers, family, db_session):
    kid = await _kid(db_session, family)
    body = (await client.get(f"/kids/{kid.id}/allowance", headers=auth_headers)).json()
    assert body["configured"] is False
    assert body["amount"] is None
    assert body["kid_name"] == "Maya"


async def test_update_then_delete(client, auth_headers, family, db_session):
    kid = await _kid(db_session, family)
    await client.put(
        f"/kids/{kid.id}/allowance",
        headers=auth_headers,
        json={"amount": 10, "cadence": "monthly", "payday": 1, "is_active": True},
    )
    upd = await client.put(
        f"/kids/{kid.id}/allowance",
        headers=auth_headers,
        json={"amount": 20, "cadence": "monthly", "payday": 1, "is_active": False},
    )
    assert Decimal(upd.json()["amount"]) == Decimal("20.00")
    assert upd.json()["is_active"] is False
    assert upd.json()["next_payday"] is None  # hidden while paused

    dele = await client.delete(f"/kids/{kid.id}/allowance", headers=auth_headers)
    assert dele.status_code == 204
    assert (await client.get(f"/kids/{kid.id}/allowance", headers=auth_headers)).json()["configured"] is False


async def test_bad_payday_is_rejected(client, auth_headers, family, db_session):
    kid = await _kid(db_session, family)
    resp = await client.put(
        f"/kids/{kid.id}/allowance",
        headers=auth_headers,
        json={"amount": 10, "cadence": "weekly", "payday": 20, "is_active": True},
    )
    assert resp.status_code == 400


async def test_kid_can_read_their_own_allowance_but_not_write(client, auth_headers, family, db_session):
    kid = await _kid(db_session, family)
    await client.put(
        f"/kids/{kid.id}/allowance",
        headers=auth_headers,
        json={"amount": 8, "cadence": "weekly", "payday": 0, "is_active": True},
    )

    read = await client.get(f"/kids/{kid.public_id}/allowance", headers=_kid_headers(kid))
    assert read.status_code == 200
    assert Decimal(read.json()["amount"]) == Decimal("8.00")

    write = await client.put(
        f"/kids/{kid.public_id}/allowance",
        headers=_kid_headers(kid),
        json={"amount": 100, "cadence": "weekly", "payday": 0, "is_active": True},
    )
    assert write.status_code == 403
    assert (await client.delete(f"/kids/{kid.public_id}/allowance", headers=_kid_headers(kid))).status_code == 403


async def test_kid_cannot_read_a_siblings_allowance(client, auth_headers, family, db_session):
    maya = await _kid(db_session, family, "Maya")
    noa = await _kid(db_session, family, "Noa")
    await client.put(
        f"/kids/{noa.id}/allowance",
        headers=auth_headers,
        json={"amount": 8, "cadence": "weekly", "payday": 0, "is_active": True},
    )
    # Maya's token, Noa's public_id in the path → 404 (deps isolation).
    resp = await client.get(f"/kids/{noa.public_id}/allowance", headers=_kid_headers(maya))
    assert resp.status_code == 404


async def test_allowance_is_tenant_isolated(client, auth_headers, family, db_session):
    kid = await _kid(db_session, family)
    _, other_headers = await _second_family_headers(db_session)
    resp = await client.put(
        f"/kids/{kid.id}/allowance",
        headers=other_headers,
        json={"amount": 5, "cadence": "weekly", "payday": 0, "is_active": True},
    )
    assert resp.status_code == 404


async def test_bulk_apply_sets_every_kid(client, auth_headers, family, db_session):
    k1 = await _kid(db_session, family, "A")
    k2 = await _kid(db_session, family, "B")

    resp = await client.post(
        "/family/allowances",
        headers=auth_headers,
        json={"amount": 15, "cadence": "monthly", "payday": 1, "is_active": True},
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["base_currency"] == "USD"
    assert {k["kid_id"] for k in body["kids"]} == {str(k1.id), str(k2.id)}
    assert all(Decimal(k["amount"]) == Decimal("15.00") for k in body["kids"])


async def test_bulk_apply_with_no_kids_is_a_400(client, auth_headers, family, db_session):
    resp = await client.post(
        "/family/allowances",
        headers=auth_headers,
        json={"amount": 15, "cadence": "monthly", "payday": 1, "is_active": True},
    )
    assert resp.status_code == 400


async def test_list_family_allowances_settles_due_payouts(client, auth_headers, family, db_session):
    kid = await _kid(db_session, family)
    await client.put(
        f"/kids/{kid.id}/allowance",
        headers=auth_headers,
        json={"amount": 10, "cadence": "weekly", "payday": 0, "is_active": True},
    )
    # Back-date the schedule so two payouts are due.
    allowance = await db_session.scalar(select(Allowance).where(Allowance.kid_id == kid.id))
    allowance.next_run_at = datetime.now(timezone.utc) - timedelta(days=8)
    await db_session.flush()

    listed = await client.get("/family/allowances", headers=auth_headers)
    assert listed.status_code == 200
    kid_view = listed.json()["kids"][0]
    assert kid_view["last_paid_at"] is not None
    assert len(kid_view["recent_payments"]) == 2

    hist = (await client.get(f"/kids/{kid.id}/debt", headers=auth_headers)).json()
    allowance_rows = [r for r in hist if r["is_allowance"]]
    assert len(allowance_rows) == 2
    assert all(r["note"] == "Weekly allowance" and r["type"] == "add" for r in allowance_rows)


async def test_settle_on_read_reflects_in_kid_balance(client, auth_headers, family, db_session):
    kid = await _kid(db_session, family)
    await client.put(
        f"/kids/{kid.id}/allowance",
        headers=auth_headers,
        json={"amount": 10, "cadence": "weekly", "payday": 0, "is_active": True},
    )
    allowance = await db_session.scalar(select(Allowance).where(Allowance.kid_id == kid.id))
    allowance.next_run_at = datetime.now(timezone.utc) - timedelta(days=1)
    await db_session.flush()

    # Kid opens their own allowance screen → payout settles.
    await client.get(f"/kids/{kid.public_id}/allowance", headers=_kid_headers(kid))

    portfolio = (await client.get(f"/kids/{kid.id}/portfolio", headers=auth_headers)).json()
    assert Decimal(portfolio["cash_available"]) == Decimal("10.00")
