"""Savings plan management (parent) + deposit/withdraw (kid) over the
HTTP surface, plus the tenant-isolation guard architecture 5.5 asks for
on every family-scoped resource."""

from decimal import Decimal

from app.core.security import issue_session_token
from app.models.family import Family
from app.models.kid import Kid
from app.models.user import User
from app.services import debts_db_service
from app.services.debts_db_service import DebtTransactionType


async def _kid(db_session, family, name="Kid") -> Kid:
    kid = Kid(family_id=family.id, name=name, avatar_color="amber")
    db_session.add(kid)
    await db_session.flush()
    return kid


async def _second_family_headers(db_session) -> dict[str, str]:
    other = Family(base_currency="EUR", onboarding_completed=True)
    db_session.add(other)
    await db_session.flush()
    user = User(family_id=other.id, email="other@example.com", google_sub="other-sub")
    db_session.add(user)
    await db_session.flush()
    return {"Authorization": f"Bearer {issue_session_token(user.id, other.id, user.email)}"}


async def test_create_list_and_delete_a_plan(client, auth_headers, family, db_session):
    create = await client.post(
        "/family/savings-plans",
        headers=auth_headers,
        json={"name": "Rainy day", "monthly_rate": 1.5, "lock_months": 0},
    )
    assert create.status_code == 201
    body = create.json()
    assert body["lock_months"] == 0
    assert Decimal(body["annual_rate"]) > Decimal("1.5")  # compounded > monthly
    plan_id = body["id"]

    listed = await client.get("/family/savings-plans", headers=auth_headers)
    assert [p["id"] for p in listed.json()] == [plan_id]

    deleted = await client.delete(f"/family/savings-plans/{plan_id}", headers=auth_headers)
    assert deleted.status_code == 204
    assert await client.get("/family/savings-plans", headers=auth_headers) is not None
    assert (await client.get("/family/savings-plans", headers=auth_headers)).json() == []


async def test_editing_a_plan_does_not_touch_existing_deposits(client, auth_headers, family, db_session):
    kid = await _kid(db_session, family)
    await debts_db_service.record_transaction(db_session, kid.id, DebtTransactionType.ADD, Decimal("100"))
    await db_session.commit()

    plan_id = (
        await client.post(
            "/family/savings-plans",
            headers=auth_headers,
            json={"name": "Flex", "monthly_rate": 1.0, "lock_months": 0},
        )
    ).json()["id"]

    dep = await client.post(
        f"/kids/{kid.id}/savings/deposit", headers=auth_headers, json={"plan_id": plan_id, "amount": 50}
    )
    assert dep.status_code == 201
    assert Decimal(dep.json()["monthly_rate"]) == Decimal("1.000")

    await client.patch(
        f"/family/savings-plans/{plan_id}",
        headers=auth_headers,
        json={"monthly_rate": 8.0, "lock_months": 12},
    )

    overview = await client.get(f"/kids/{kid.id}/savings", headers=auth_headers)
    deposit = overview.json()["deposits"][0]
    assert Decimal(deposit["monthly_rate"]) == Decimal("1.000")
    assert deposit["lock_months"] == 0


async def test_delete_reports_open_deposit_count_for_the_warning(client, auth_headers, family, db_session):
    kid = await _kid(db_session, family)
    await debts_db_service.record_transaction(db_session, kid.id, DebtTransactionType.ADD, Decimal("100"))
    await db_session.commit()
    plan_id = (
        await client.post(
            "/family/savings-plans",
            headers=auth_headers,
            json={"name": "Flex", "monthly_rate": 1.0, "lock_months": 0},
        )
    ).json()["id"]
    await client.post(
        f"/kids/{kid.id}/savings/deposit", headers=auth_headers, json={"plan_id": plan_id, "amount": 20}
    )

    plans = (await client.get("/family/savings-plans", headers=auth_headers)).json()
    assert plans[0]["open_deposit_count"] == 1

    # Deleting still works — the deposit is left untouched, just unlinked.
    assert (await client.delete(f"/family/savings-plans/{plan_id}", headers=auth_headers)).status_code == 204
    overview = await client.get(f"/kids/{kid.id}/savings", headers=auth_headers)
    assert len(overview.json()["deposits"]) == 1


async def test_deposit_then_withdraw_round_trips_cash(client, auth_headers, family, db_session):
    kid = await _kid(db_session, family)
    await debts_db_service.record_transaction(db_session, kid.id, DebtTransactionType.ADD, Decimal("100"))
    await db_session.commit()
    plan_id = (
        await client.post(
            "/family/savings-plans",
            headers=auth_headers,
            json={"name": "Flex", "monthly_rate": 1.0, "lock_months": 0},
        )
    ).json()["id"]

    dep = await client.post(
        f"/kids/{kid.id}/savings/deposit", headers=auth_headers, json={"plan_id": plan_id, "amount": 60}
    )
    deposit_id = dep.json()["deposit_id"]
    portfolio = await client.get(f"/kids/{kid.id}/portfolio", headers=auth_headers)
    assert Decimal(portfolio.json()["cash_available"]) == Decimal("40.00")

    wd = await client.post(
        f"/kids/{kid.id}/savings/{deposit_id}/withdraw", headers=auth_headers
    )
    assert wd.status_code == 200
    assert wd.json()["is_open"] is False
    portfolio = await client.get(f"/kids/{kid.id}/portfolio", headers=auth_headers)
    assert Decimal(portfolio.json()["cash_available"]) >= Decimal("100.00")


async def test_locked_deposit_withdrawal_is_rejected_over_http(client, auth_headers, family, db_session):
    kid = await _kid(db_session, family)
    await debts_db_service.record_transaction(db_session, kid.id, DebtTransactionType.ADD, Decimal("100"))
    await db_session.commit()
    plan_id = (
        await client.post(
            "/family/savings-plans",
            headers=auth_headers,
            json={"name": "Locked", "monthly_rate": 2.0, "lock_months": 6},
        )
    ).json()["id"]
    deposit_id = (
        await client.post(
            f"/kids/{kid.id}/savings/deposit", headers=auth_headers, json={"plan_id": plan_id, "amount": 50}
        )
    ).json()["deposit_id"]

    wd = await client.post(f"/kids/{kid.id}/savings/{deposit_id}/withdraw", headers=auth_headers)
    assert wd.status_code == 400


async def test_presets_catalog_has_one_flexible_and_several_locked(client, auth_headers, family):
    presets = (await client.get("/family/savings-presets", headers=auth_headers)).json()
    kinds = [p["kind"] for p in presets]
    assert kinds.count("flexible") == 1
    assert kinds.count("locked") >= 3
    # annual rate is compounded, always above the monthly figure
    for p in presets:
        assert Decimal(p["annual_rate"]) > Decimal(p["monthly_rate"])


async def test_toggling_a_preset_on_then_off_creates_then_removes_the_plan(client, auth_headers, family):
    on = await client.post(
        "/family/savings-presets", headers=auth_headers, json={"key": "locked-6m", "active": True}
    )
    assert on.status_code == 204
    plans = (await client.get("/family/savings-plans", headers=auth_headers)).json()
    assert [p["preset_key"] for p in plans] == ["locked-6m"]
    assert plans[0]["is_active"] is True

    off = await client.post(
        "/family/savings-presets", headers=auth_headers, json={"key": "locked-6m", "active": False}
    )
    assert off.status_code == 204
    assert (await client.get("/family/savings-plans", headers=auth_headers)).json() == []


async def test_turning_a_preset_off_keeps_the_plan_if_a_kid_has_money_in_it(
    client, auth_headers, family, db_session
):
    kid = await _kid(db_session, family)
    await debts_db_service.record_transaction(db_session, kid.id, DebtTransactionType.ADD, Decimal("100"))
    await db_session.commit()
    await client.post("/family/savings-presets", headers=auth_headers, json={"key": "flex", "active": True})
    plan_id = (await client.get("/family/savings-plans", headers=auth_headers)).json()[0]["id"]
    await client.post(
        f"/kids/{kid.id}/savings/deposit", headers=auth_headers, json={"plan_id": plan_id, "amount": 30}
    )

    await client.post("/family/savings-presets", headers=auth_headers, json={"key": "flex", "active": False})

    plans = (await client.get("/family/savings-plans", headers=auth_headers)).json()
    assert len(plans) == 1 and plans[0]["is_active"] is False
    # the deposit is still there and still growing
    overview = await client.get(f"/kids/{kid.id}/savings", headers=auth_headers)
    assert len(overview.json()["deposits"]) == 1
    # a switched-off preset isn't offered for new deposits
    assert overview.json()["plans"] == []


async def test_reactivating_a_preset_that_still_has_deposits_reuses_the_same_row(
    client, auth_headers, family, db_session
):
    kid = await _kid(db_session, family)
    await debts_db_service.record_transaction(db_session, kid.id, DebtTransactionType.ADD, Decimal("100"))
    await db_session.commit()
    await client.post("/family/savings-presets", headers=auth_headers, json={"key": "flex", "active": True})
    first_id = (await client.get("/family/savings-plans", headers=auth_headers)).json()[0]["id"]
    await client.post(
        f"/kids/{kid.id}/savings/deposit", headers=auth_headers, json={"plan_id": first_id, "amount": 20}
    )

    # off keeps the row (deposit present), on flips it back to the same row
    await client.post("/family/savings-presets", headers=auth_headers, json={"key": "flex", "active": False})
    await client.post("/family/savings-presets", headers=auth_headers, json={"key": "flex", "active": True})

    plans = (await client.get("/family/savings-plans", headers=auth_headers)).json()
    assert len(plans) == 1 and plans[0]["id"] == first_id and plans[0]["is_active"] is True


async def test_plan_deposits_breakdown_lists_each_kid(client, auth_headers, family, db_session):
    a = await _kid(db_session, family, "A")
    b = await _kid(db_session, family, "B")
    for kid in (a, b):
        await debts_db_service.record_transaction(db_session, kid.id, DebtTransactionType.ADD, Decimal("200"))
    await db_session.commit()
    plan_id = (
        await client.post(
            "/family/savings-plans", headers=auth_headers, json={"name": "F", "monthly_rate": 1.0, "lock_months": 0}
        )
    ).json()["id"]
    for kid in (a, b):
        await client.post(
            f"/kids/{kid.id}/savings/deposit", headers=auth_headers, json={"plan_id": plan_id, "amount": 50}
        )

    rows = (await client.get(f"/family/savings-plans/{plan_id}/deposits", headers=auth_headers)).json()
    assert sorted(r["kid_name"] for r in rows) == ["A", "B"]
    assert all(Decimal(r["current_value"]) >= Decimal("50") for r in rows)


async def test_cash_out_plan_closes_every_deposit_in_it_across_kids(client, auth_headers, family, db_session):
    a = await _kid(db_session, family, "A")
    b = await _kid(db_session, family, "B")
    for kid in (a, b):
        await debts_db_service.record_transaction(db_session, kid.id, DebtTransactionType.ADD, Decimal("200"))
    await db_session.commit()
    flex = (
        await client.post(
            "/family/savings-plans", headers=auth_headers, json={"name": "F", "monthly_rate": 1.0, "lock_months": 0}
        )
    ).json()["id"]
    other = (
        await client.post(
            "/family/savings-plans", headers=auth_headers, json={"name": "O", "monthly_rate": 1.0, "lock_months": 0}
        )
    ).json()["id"]
    for kid in (a, b):
        await client.post(
            f"/kids/{kid.id}/savings/deposit", headers=auth_headers, json={"plan_id": flex, "amount": 50}
        )
    await client.post(
        f"/kids/{a.id}/savings/deposit", headers=auth_headers, json={"plan_id": other, "amount": 20}
    )

    resp = await client.post(f"/family/savings-plans/{flex}/cash-out", headers=auth_headers)
    assert resp.status_code == 200 and resp.json()["closed_count"] == 2

    # only the "flex" plan's deposits were closed; the "other" one survives
    for kid in (a, b):
        deposits = (await client.get(f"/kids/{kid.id}/savings", headers=auth_headers)).json()["deposits"]
        assert all(d["plan_name"] != "F" for d in deposits)
    a_deposits = (await client.get(f"/kids/{a.id}/savings", headers=auth_headers)).json()["deposits"]
    assert [d["plan_name"] for d in a_deposits] == ["O"]


async def test_cash_out_plan_overrides_the_maturity_lock(client, auth_headers, family, db_session):
    kid = await _kid(db_session, family)
    await debts_db_service.record_transaction(db_session, kid.id, DebtTransactionType.ADD, Decimal("100"))
    await db_session.commit()
    locked = (
        await client.post(
            "/family/savings-plans", headers=auth_headers, json={"name": "L", "monthly_rate": 2.0, "lock_months": 12}
        )
    ).json()["id"]
    await client.post(
        f"/kids/{kid.id}/savings/deposit", headers=auth_headers, json={"plan_id": locked, "amount": 80}
    )

    resp = await client.post(f"/family/savings-plans/{locked}/cash-out", headers=auth_headers)
    assert resp.status_code == 200 and resp.json()["closed_count"] == 1
    assert (await client.get(f"/kids/{kid.id}/savings", headers=auth_headers)).json()["deposits"] == []


async def test_custom_plan_can_be_deactivated_and_reactivated(client, auth_headers, family):
    plan_id = (
        await client.post(
            "/family/savings-plans", headers=auth_headers, json={"name": "Mine", "monthly_rate": 1.0, "lock_months": 0}
        )
    ).json()["id"]

    off = await client.patch(f"/family/savings-plans/{plan_id}", headers=auth_headers, json={"is_active": False})
    assert off.json()["is_active"] is False
    # a deactivated plan isn't offered to kids
    kid_view = (await client.get("/family/savings-plans", headers=auth_headers)).json()
    assert kid_view[0]["is_active"] is False

    on = await client.patch(f"/family/savings-plans/{plan_id}", headers=auth_headers, json={"is_active": True})
    assert on.json()["is_active"] is True


async def test_cannot_touch_another_familys_plans_or_deposit_for_their_kid(
    client, auth_headers, family, db_session
):
    kid = await _kid(db_session, family)
    await debts_db_service.record_transaction(db_session, kid.id, DebtTransactionType.ADD, Decimal("100"))
    await db_session.commit()
    plan_id = (
        await client.post(
            "/family/savings-plans",
            headers=auth_headers,
            json={"name": "Mine", "monthly_rate": 1.0, "lock_months": 0},
        )
    ).json()["id"]

    other = await _second_family_headers(db_session)
    assert (await client.patch(f"/family/savings-plans/{plan_id}", headers=other, json={"name": "x"})).status_code == 404
    assert (await client.delete(f"/family/savings-plans/{plan_id}", headers=other)).status_code == 404
    assert (await client.get(f"/family/savings-plans/{plan_id}/deposits", headers=other)).status_code == 404
    assert (await client.post(f"/family/savings-plans/{plan_id}/cash-out", headers=other)).status_code == 404
    assert (
        await client.post(
            f"/kids/{kid.id}/savings/deposit", headers=other, json={"plan_id": plan_id, "amount": 10}
        )
    ).status_code == 404
