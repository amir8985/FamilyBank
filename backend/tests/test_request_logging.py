"""app/core/request_logging.py: request timing/logging middleware + the
POST /internal/client-metrics endpoint. DB persistence is disabled for the
whole suite (see conftest.py's autouse `_no_request_log_persistence`), so
these tests check the parts that don't depend on it: JWT decoding, the
structured stdout log line, and that the RequestLog model itself is
writable through the normal test db_session.
"""

import json
import logging
import uuid

from app.core.request_logging import _decode_bearer
from app.core.security import issue_session_token
from app.models.request_log import RequestLog


def test_decode_bearer_extracts_user_and_family(user):
    token = issue_session_token(user.id, user.family_id, user.email)
    decoded_user_id, decoded_family_id = _decode_bearer(f"Bearer {token}")
    assert decoded_user_id == user.id
    assert decoded_family_id == user.family_id


def test_decode_bearer_returns_none_for_missing_or_malformed():
    assert _decode_bearer(None) == (None, None)
    assert _decode_bearer("not-a-bearer-header") == (None, None)
    assert _decode_bearer("Bearer not-a-real-jwt") == (None, None)


async def test_middleware_logs_a_structured_line_per_request(client, auth_headers, caplog):
    with caplog.at_level(logging.INFO, logger="app.requests"):
        resp = await client.get("/family/settings", headers=auth_headers)
    assert resp.status_code == 200

    records = [r for r in caplog.records if r.name == "app.requests"]
    assert records, "expected the middleware to emit a structured log line"
    payload = json.loads(records[-1].getMessage())
    assert payload["path"] == "/family/settings"
    assert payload["status_code"] == 200
    assert payload["source"] == "server"
    assert payload["duration_ms"] >= 0


async def test_middleware_attributes_the_request_to_its_family(client, auth_headers, user, caplog):
    with caplog.at_level(logging.INFO, logger="app.requests"):
        await client.get("/family/settings", headers=auth_headers)

    records = [r for r in caplog.records if r.name == "app.requests"]
    payload = json.loads(records[-1].getMessage())
    assert payload["family_id"] == str(user.family_id)
    assert payload["user_id"] == str(user.id)


async def test_middleware_logs_unauthenticated_requests_without_attribution(client, caplog):
    with caplog.at_level(logging.INFO, logger="app.requests"):
        resp = await client.get("/health")
    assert resp.status_code == 200

    records = [r for r in caplog.records if r.name == "app.requests"]
    payload = json.loads(records[-1].getMessage())
    assert payload["family_id"] is None
    assert payload["user_id"] is None


async def test_client_metrics_endpoint_accepts_and_logs_a_report(client, auth_headers, user, caplog):
    with caplog.at_level(logging.INFO, logger="app.requests"):
        resp = await client.post(
            "/internal/client-metrics",
            headers=auth_headers,
            json={"path": "/home", "duration_ms": 842.5},
        )
    assert resp.status_code == 200

    # Two lines get logged for this call: the client-reported one from the
    # route itself, and the middleware's own server-side timing of the
    # POST /internal/client-metrics request — find the former specifically.
    payloads = [json.loads(r.getMessage()) for r in caplog.records if r.name == "app.requests"]
    payload = next(p for p in payloads if p["source"] == "client")
    assert payload["path"] == "/home"
    assert payload["method"] == "GET"  # defaulted — not sent above
    assert payload["duration_ms"] == 842.5
    assert payload["family_id"] == str(user.family_id)


async def test_client_metrics_endpoint_records_the_real_http_method(client, auth_headers, caplog):
    with caplog.at_level(logging.INFO, logger="app.requests"):
        resp = await client.post(
            "/internal/client-metrics",
            headers=auth_headers,
            json={"path": "/kids/abc/debt", "method": "POST", "duration_ms": 50.0},
        )
    assert resp.status_code == 200

    payloads = [json.loads(r.getMessage()) for r in caplog.records if r.name == "app.requests"]
    payload = next(p for p in payloads if p["source"] == "client")
    assert payload["method"] == "POST"


async def test_client_metrics_endpoint_works_without_auth(client):
    resp = await client.post(
        "/internal/client-metrics", json={"path": "/sign-in", "duration_ms": 120.0}
    )
    assert resp.status_code == 200


async def test_request_log_row_is_writable(db_session, family):
    row = RequestLog(
        request_id=uuid.uuid4(),
        source="server",
        method="GET",
        path="/health",
        status_code=200,
        duration_ms=12.3,
        family_id=family.id,
        user_id=None,
    )
    db_session.add(row)
    await db_session.flush()
    assert row.id is not None
    assert row.created_at is not None
