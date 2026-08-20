"""End-to-end at the API layer: sign-in -> onboarding -> add balance ->
buy -> sell -> change currency, exactly the path a real user takes,
exercised through the real FastAPI app (not by calling service functions
directly). This is the practical substitute for a browser-driven E2E
test here — Google OAuth can't be scripted safely/reliably in an
automated test (see test_api_auth.py's docstring), so this suite proves
the whole backend, wired together exactly as the frontend calls it,
still works — everything after Google's own login screen.
"""


def _fake_verify(claims: dict):
    def _verify(raw_id_token: str) -> dict:
        return claims

    return _verify


async def test_full_parent_journey(client, monkeypatch):
    monkeypatch.setattr(
        "app.api.routes_auth.verify_google_id_token",
        _fake_verify({"email": "journey@example.com", "sub": "journey-sub"}),
    )

    # 1. Sign in
    sync = await client.post("/auth/sync", json={"id_token": "whatever"})
    assert sync.status_code == 200
    token = sync.json()["session_token"]
    headers = {"Authorization": f"Bearer {token}"}

    # 2. Fresh family needs onboarding
    settings = await client.get("/family/settings", headers=headers)
    assert settings.json()["onboarding_completed"] is False

    # 3. Onboarding: pick currency + first kid
    onboarding = await client.post(
        "/family/onboarding", headers=headers, json={"base_currency": "ILS", "kid_names": ["Maya"]}
    )
    assert onboarding.status_code == 200
    assert onboarding.json() == {"base_currency": "ILS", "onboarding_completed": True}

    # 4. Home shows the onboarded kid with a zero balance
    home = await client.get("/home", headers=headers)
    kids = home.json()["kids"]
    assert len(kids) == 1
    kid_id = kids[0]["id"]
    assert kids[0]["cash_balance"] == "0.00"

    # 5. Parent adds allowance
    add = await client.post(f"/kids/{kid_id}/debt", headers=headers, json={"type": "add", "amount": 100, "note": "allowance"})
    assert add.status_code == 201
    assert add.json()["new_balance"] == "100.00"

    # 6. Add a second kid from Settings
    second_kid = await client.post("/kids", headers=headers, json={"name": "Noam"})
    assert second_kid.status_code == 201

    home2 = await client.get("/home", headers=headers)
    assert {k["name"] for k in home2.json()["kids"]} == {"Maya", "Noam"}

    # 7. Deduct some balance
    deduct = await client.post(f"/kids/{kid_id}/debt", headers=headers, json={"type": "deduct", "amount": 30})
    assert deduct.json()["new_balance"] == "70.00"

    # 8. Change currency mid-flow
    changed = await client.patch("/family/settings", headers=headers, json={"base_currency": "USD"})
    assert changed.json()["base_currency"] == "USD"

    # 9. Remove the second kid
    removed = await client.delete(f"/kids/{second_kid.json()['id']}", headers=headers)
    assert removed.status_code == 204
    home3 = await client.get("/home", headers=headers)
    assert [k["name"] for k in home3.json()["kids"]] == ["Maya"]


async def test_buy_and_sell_journey(client, monkeypatch, seeded_asset):
    monkeypatch.setattr(
        "app.api.routes_auth.verify_google_id_token",
        _fake_verify({"email": "investor@example.com", "sub": "investor-sub"}),
    )
    sync = await client.post("/auth/sync", json={"id_token": "whatever"})
    headers = {"Authorization": f"Bearer {sync.json()['session_token']}"}

    await client.post("/family/onboarding", headers=headers, json={"base_currency": "USD", "kid_names": ["Offir"]})
    kid_id = (await client.get("/home", headers=headers)).json()["kids"][0]["id"]
    await client.post(f"/kids/{kid_id}/debt", headers=headers, json={"type": "add", "amount": 500})

    # Buy screen: catalog listing shows the seeded asset with a price
    catalog = await client.get("/catalog", headers=headers)
    test_asset = next(a for a in catalog.json() if a["symbol"] == "TEST")
    assert test_asset["price"] == "100.0000"

    # Live quote preview
    quote = await client.post(f"/kids/{kid_id}/quote", headers=headers, json={"symbol": "TEST", "units": 2})
    assert quote.json()["cost"] == "200.00"

    # Buy
    buy = await client.post(f"/kids/{kid_id}/buy", headers=headers, json={"symbol": "TEST", "units": 2})
    assert buy.status_code == 201

    portfolio = await client.get(f"/kids/{kid_id}/portfolio", headers=headers)
    assert portfolio.json()["cash_available"] == "300.00"
    assert portfolio.json()["holdings"][0]["units"] == "2.00000000"

    # Sell half
    sell = await client.post(f"/kids/{kid_id}/sell", headers=headers, json={"symbol": "TEST", "units": 1})
    assert sell.status_code == 201

    portfolio2 = await client.get(f"/kids/{kid_id}/portfolio", headers=headers)
    assert portfolio2.json()["cash_available"] == "400.00"
    assert portfolio2.json()["holdings"][0]["units"] == "1.00000000"

    # Investment-only history shows both — separate from the general
    # debt ledger (which also has the allowance add). Ordering itself is
    # covered by test_investing_service.py's dedicated ordering test —
    # Postgres's now() is fixed for the whole transaction, and this
    # fixture's savepoint-per-test isolation means buy/sell here share
    # one transaction, so their timestamps can tie (never happens across
    # separate real HTTP requests, which is how this actually runs).
    inv_history = await client.get(f"/kids/{kid_id}/investment-transactions", headers=headers)
    assert {t["type"] for t in inv_history.json()} == {"buy", "sell"}

    debt_history = await client.get(f"/kids/{kid_id}/debt", headers=headers)
    debt_types = [t["type"] for t in debt_history.json()]
    assert debt_types.count("add") == 2  # original allowance + sell proceeds
    assert debt_types.count("deduct") == 1  # the buy


async def test_cannot_buy_more_than_can_afford(client, monkeypatch, seeded_asset):
    monkeypatch.setattr(
        "app.api.routes_auth.verify_google_id_token",
        _fake_verify({"email": "poor@example.com", "sub": "poor-sub"}),
    )
    sync = await client.post("/auth/sync", json={"id_token": "whatever"})
    headers = {"Authorization": f"Bearer {sync.json()['session_token']}"}
    await client.post("/family/onboarding", headers=headers, json={"base_currency": "USD", "kid_names": ["Tamar"]})
    kid_id = (await client.get("/home", headers=headers)).json()["kids"][0]["id"]

    # No allowance added — cash available is 0.
    resp = await client.post(f"/kids/{kid_id}/buy", headers=headers, json={"symbol": "TEST", "units": 1})
    assert resp.status_code == 400
    assert "Insufficient" in resp.json()["detail"]
