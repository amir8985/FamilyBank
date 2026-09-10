from app.main import app


async def test_health_reports_running_api_version(client):
    resp = await client.get("/health")
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "ok"
    # Mirrors the FastAPI app version — the Settings screen shows this so a
    # parent can tell which API build is live.
    assert isinstance(body["version"], str) and body["version"]
    assert body["version"] == app.version
