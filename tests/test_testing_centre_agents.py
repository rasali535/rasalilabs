"""Stage 4: specialist agents never fabricate scan evidence or execute fixes."""
import asyncio
import copy
import json

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from backend.testing_centre.agents import (
    SPECIALISTS, _parse_ai_notes, build_review, enrich_review,
)
from backend.testing_centre.router import create_testing_router
from tests.test_testing_centre import FakeDB, MockCollection, TOKEN, setup_config


def source_scan():
    return {
        "id": "scan-123",
        "test_type": "browser_smoke",
        "status": "completed",
        "result": {
            "outcome": "warning",
            "findings": [
                {"id": "js-1", "title": "Uncaught JavaScript exception",
                 "category": "runtime", "severity": "high",
                 "detail": "ReferenceError: widget is not defined",
                 "recommendation": "Import the missing component.", "viewport": "mobile"},
                {"id": "sec-1", "title": "HSTS header not observed",
                 "category": "security_configuration", "severity": "medium",
                 "evidence": "No HSTS header on HTTPS HEAD",
                 "recommendation": "Review HTTPS coverage then configure HSTS."},
                {"id": "bad-input", "title": "Not actually measured",
                 "category": "unknown_category", "severity": "high"},
                {"id": "js-1", "title": "duplicate", "category": "runtime", "severity": "high"},
            ],
            "not_tested": ["Authenticated journeys were not exercised."],
        },
    }


def test_specialists_preserve_existing_evidence_and_no_auto_approval():
    scan = source_scan()
    before = copy.deepcopy(scan)
    review = build_review(scan)
    assert scan == before
    assert [a["role"] for a in SPECIALISTS] == [
        "qa_engineer", "security_engineer", "test_architect"]
    assert {r["role"] for r in review["roles"]} == {
        "qa_engineer", "security_engineer", "test_architect"}
    assert review["summary"]["observations"] == 2
    assert review["summary"]["qa_findings"] == 1
    assert review["summary"]["security_findings"] == 1
    assert review["summary"]["handoffs"] == 2
    assert review["release_readiness"] == "not_verified"
    assert review["ai"]["status"] == "not_requested"
    ids = {h["source_finding_id"] for h in review["handoffs"]}
    assert ids == {"js-1", "sec-1"}
    assert all(h["state"] == "suggested_not_executed" for h in review["handoffs"])
    assert all(g["status"] == "not_tested" for g in review["coverage_gaps"])


def test_failed_or_incomplete_scans_cannot_be_reviewed():
    scan = source_scan()
    scan["status"] = "failed"
    with pytest.raises(ValueError):
        build_review(scan)
    scan["status"] = "completed"
    scan["result"]["outcome"] = "fail"
    with pytest.raises(ValueError):
        build_review(scan)


def test_zero_findings_does_not_imply_launch_ready():
    scan = source_scan()
    scan["result"] = {"outcome": "pass", "findings": [], "checks": ["HTTP availability"]}
    review = build_review(scan)
    assert review["summary"]["observations"] == 0
    assert review["release_readiness"] == "not_verified"
    assert review["summary"]["gaps"] > 0
    assert review["roles"][1]["findings"] == []


def test_ai_notes_only_accept_known_issue_ids_not_new_vulnerabilities():
    valid = _parse_ai_notes(json.dumps({"notes": [
        {"id": "js-1", "note": "Investigate component mounting with a browser trace."},
        {"id": "invented-xss", "note": "Critical exploit that does not exist"},
        {"id": "sec-1", "note": "This is fixed and fully secure"},
        {"id": "js-1", "note": "Duplicate"},
    ]}), {"js-1", "sec-1"})
    assert len(valid) == 1
    assert valid[0]["id"] == "js-1"
    assert valid[0]["state"] == "unverified_ai_suggestion"
    assert _parse_ai_notes("Here is a finding", {"js-1"}) == []


def test_opt_in_model_receives_only_finding_metadata():
    review = build_review(source_scan())
    messages_seen = []

    async def model(messages):
        messages_seen.extend(messages)
        return json.dumps({"notes": [
            {"id": "js-1", "note": "Reproduce with a minimal component test."},
            {"id": "invented", "note": "Made up result"},
        ]})

    result = asyncio.run(enrich_review(review, provider=model, model_name="test-local-model"))
    assert result["ai"]["status"] == "generated_unverified"
    assert result["ai"]["accepted_notes"] == 1
    assert len(result["ai_notes"]) == 1
    data = str(messages_seen)
    assert "widget is not defined" not in data
    assert "No HSTS header on HTTPS HEAD" not in data
    assert "scan-123" not in data
    assert "js-1" in data


def test_model_errors_are_disclosed_not_simulated():
    review = build_review(source_scan())
    async def model(_):
        raise TimeoutError("Provider unavailable")
    updated = asyncio.run(enrich_review(review, provider=model, model_name="configured"))
    assert updated["ai"]["status"] == "unavailable"
    assert updated["ai"]["accepted_notes"] == 0
    assert updated["ai"]["model"] is None
    assert "ai_notes" not in updated


def test_review_routes_protected_and_persist(monkeypatch):
    setup_config(monkeypatch)
    monkeypatch.delenv("TESTING_AGENT_AI_ENABLED", raising=False)
    monkeypatch.delenv("TESTING_AGENT_AI_DISCLOSURE_ACK", raising=False)
    db = FakeDB()
    db.testing_reviews = MockCollection()
    db.testing_scans.docs.append(source_scan())
    app = FastAPI()
    app.include_router(create_testing_router(db), prefix="/api")
    client = TestClient(app)
    auth = {"X-Testing-Token": TOKEN}
    assert client.get("/api/testing/agents").status_code == 403
    profiles = client.get("/api/testing/agents", headers=auth)
    assert profiles.status_code == 200
    assert len(profiles.json()) == 3
    assert client.get("/api/testing/config", headers=auth).json()["agent_ai_enabled"] is False
    forbidden = client.post("/api/testing/scans/scan-123/reviews", json={})
    assert forbidden.status_code == 403
    model_disabled = client.post("/api/testing/scans/scan-123/reviews",
        json={"use_ai": True}, headers=auth)
    assert model_disabled.status_code == 503

    saved = client.post("/api/testing/scans/scan-123/reviews",
        json={"use_ai": False}, headers=auth)
    assert saved.status_code == 201, saved.text
    assert saved.json()["scan_id"] == "scan-123"
    assert saved.json()["release_readiness"] == "not_verified"
    assert db.testing_reviews.docs[0]["id"] == saved.json()["id"]
    history = client.get("/api/testing/scans/scan-123/reviews", headers=auth)
    assert history.status_code == 200
    assert history.json()[0]["id"] == saved.json()["id"]
    missing = client.post("/api/testing/scans/unknown/reviews", json={}, headers=auth)
    assert missing.status_code == 404
    db._is_mock = True
    assert client.post("/api/testing/scans/scan-123/reviews", json={},
                       headers=auth).status_code == 503


def test_ai_route_requires_two_flags_and_injected_provider(monkeypatch):
    setup_config(monkeypatch)
    monkeypatch.setenv("TESTING_AGENT_AI_ENABLED", "true")
    monkeypatch.setenv("TESTING_AGENT_AI_DISCLOSURE_ACK", "true")
    db = FakeDB()
    db.testing_reviews = MockCollection()
    db.testing_scans.docs.append(source_scan())
    called = []
    async def model(messages):
        called.append(messages)
        return json.dumps({"notes": [{"id": "js-1", "note": "Investigate the component."}]})
    app = FastAPI()
    app.include_router(create_testing_router(db, agent_provider=model, agent_model_name="test"), prefix="/api")
    client = TestClient(app)
    auth = {"X-Testing-Token": TOKEN}
    assert client.get("/api/testing/config", headers=auth).json()["agent_ai_enabled"] is True
    r = client.post("/api/testing/scans/scan-123/reviews", json={"use_ai": True}, headers=auth)
    assert r.status_code == 201
    assert len(called) == 1
    assert r.json()["ai"]["status"] == "generated_unverified"
