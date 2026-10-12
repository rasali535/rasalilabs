"""Security checkpoint: operator gate HTTP/WS and tenant separation.

No live target, models, legacy MongoDB or network access required.
"""
import os
import pathlib

import pytest
from fastapi import FastAPI, WebSocket
from fastapi.testclient import TestClient
from starlette.websockets import WebSocketDisconnect

from backend.testing_centre.legacy_gate import (
    LegacyOperatorGate, gate_enforced, operator_configured,
    request_guarded, validate_operator_token,
    ws_origin_allowed,
)

SECRET = "aB12_" * 12
ORIGIN = "https://rasalilabs.vercel.app"


def application():
    app = FastAPI()
    app.add_middleware(LegacyOperatorGate)

    @app.get("/api/health")
    async def health():
        return {"healthy": True}

    @app.get("/api/legacy-access/status")
    async def gate_status():
        return {"required": gate_enforced()}

    @app.get("/api/agents")
    async def agents():
        return {"secret": "operator-only"}

    @app.post("/api/cognee/forget")
    async def dangerous():
        return {"mutated": True}

    @app.get("/api/customer-testing/availability")
    async def customers():
        return {"enabled": True}

    @app.get("/api/testing/config")
    async def operator_testing():
        return {"independent": True}

    @app.websocket("/api/ws/project-a")
    async def socket(ws: WebSocket):
        await ws.accept()
        await ws.send_text("private-message")
        await ws.close()

    return app


def secure(monkeypatch):
    monkeypatch.setenv("LEGACY_OPERATOR_AUTH_ENFORCED", "true")
    monkeypatch.setenv("LEGACY_OPERATOR_TOKEN", SECRET)
    monkeypatch.setenv("LEGACY_OPERATOR_ALLOWED_WS_ORIGINS", ORIGIN)
    monkeypatch.delenv("TESTING_WORKSPACE_AUTH_ENABLED", raising=False)


def test_rollout_off_by_default_preserves_existing_agent_dashboard(monkeypatch):
    monkeypatch.delenv("LEGACY_OPERATOR_AUTH_ENFORCED", raising=False)
    monkeypatch.delenv("TESTING_WORKSPACE_AUTH_ENABLED", raising=False)
    assert gate_enforced() is False
    with TestClient(application()) as client:
        assert client.get("/api/agents").status_code == 200
        assert client.post("/api/cognee/forget").status_code == 200


def test_customer_mode_mandates_operator_gate_even_without_legacy_flag(monkeypatch):
    monkeypatch.delenv("LEGACY_OPERATOR_AUTH_ENFORCED", raising=False)
    monkeypatch.setenv("TESTING_WORKSPACE_AUTH_ENABLED", "true")
    monkeypatch.delenv("LEGACY_OPERATOR_TOKEN", raising=False)
    assert gate_enforced()
    with TestClient(application()) as client:
        assert client.get("/api/health").status_code == 200
        assert client.get("/api/agents").status_code == 503
        assert client.post("/api/cognee/forget").status_code == 503
        assert client.get("/api/customer-testing/availability").status_code == 200


def test_operator_gate_enforces_read_write_and_independent_customer_routes(monkeypatch):
    secure(monkeypatch)
    with TestClient(application()) as client:
        assert client.get("/api/agents").status_code == 401
        assert client.post("/api/cognee/forget").status_code == 401
        assert client.post("/api/cognee/forget",
                           headers={"X-Legacy-Operator-Token": "wrong"}).status_code == 401
        allowed = client.get("/api/agents", headers={
            "X-Legacy-Operator-Token": SECRET})
        assert allowed.status_code == 200
        assert allowed.json()["secret"] == "operator-only"
        assert client.post("/api/cognee/forget",
                           headers={"X-Legacy-Operator-Token": SECRET}).status_code == 200
        assert client.get("/api/customer-testing/availability").status_code == 200
        assert client.get("/api/testing/config").status_code == 200
        assert client.get("/api/legacy-access/status").json()["required"] is True


def test_ws_rejects_untrusted_origin_and_missing_operator_token(monkeypatch):
    secure(monkeypatch)
    with TestClient(application()) as client:
        with pytest.raises(WebSocketDisconnect):
            with client.websocket_connect("/api/ws/project-a",
                                          headers={"Origin": ORIGIN}):
                pass
        with pytest.raises(WebSocketDisconnect):
            with client.websocket_connect(
                "/api/ws/project-a",
                subprotocols=["rasali-operator." + SECRET],
                headers={"Origin": "https://attacker.vercel.app"},
            ):
                pass
        with client.websocket_connect(
            "/api/ws/project-a",
            subprotocols=["rasali-operator." + SECRET],
            headers={"Origin": ORIGIN},
        ) as ws:
            assert ws.receive_text() == "private-message"


def test_no_operator_secret_in_url_or_unconfigured_public_mode(monkeypatch):
    secure(monkeypatch)
    with TestClient(application()) as client:
        assert client.get("/api/agents?token=" + SECRET).status_code == 401
    monkeypatch.setenv("LEGACY_OPERATOR_TOKEN", "12345")
    assert not operator_configured()
    assert not validate_operator_token("12345")


def test_known_public_paths_and_strict_exemptions():
    assert not request_guarded("/api/customer-testing/jobs")
    assert not request_guarded("/api/testing/scans")
    assert request_guarded("/api/customer-testing-foreign")
    assert request_guarded("/api/testing-malicious")
    assert request_guarded("/api/models/config")
    assert request_guarded("/api/artifacts/render")
    assert request_guarded("/api/cognee/improve")
    assert request_guarded("/api/ws/project-42")


def test_no_hardcoded_cognee_fallback_in_current_source():
    root = pathlib.Path(__file__).parents[1]
    source = (root / "backend/server.py").read_text(encoding="utf-8")
    assert "COGNEE_API_KEY  = os.environ.get('COGNEE_API_KEY', '')" in source
    assert "app.add_middleware(LegacyOperatorGate)" in source
    assert "allow_origin_regex=None if gate_enforced()" in source
