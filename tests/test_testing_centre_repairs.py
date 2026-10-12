"""Stage 5 repair cases, comparable retests and guarded API workflow."""
import copy
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

from fastapi import FastAPI
from fastapi.testclient import TestClient
import pytest

from backend.testing_centre.repairs import build_repair_case, assess_retest, repair_prompt
from backend.testing_centre.router import create_testing_router
from tests.test_testing_centre import FakeDB, MockCollection, TOKEN, setup_config


def scan(*, scan_id="s1", kind="browser_smoke", title="Uncaught JavaScript exception",
         include=True, completed=True, date="2026-10-12T08:00:00+00:00"):
    result = {
        "outcome": "warning" if include else "pass",
        "findings": ([{"id": "f1" if scan_id == "s1" else "NEW-DIFFERENT-ID",
                      "title": title, "category": "runtime" if kind == "browser_smoke" else "security_configuration",
                      "code": "HSTS_MISSING" if kind == "passive_security" else None,
                      "severity": "high", "viewport": "mobile" if kind == "browser_smoke" else None,
                      "detail": "Observed issue", "recommendation": "Review relevant code."}]
                     if include else []),
        "summary": {"viewports_completed": 3},
        "viewports": [{"name": name, "metrics": {"page_title": "Page"}, "http_status": 200}
                      for name in ("desktop", "tablet", "mobile")],
        "coverage": {"method": "pinned_public_ip_https_head", "requests_sent": 1,
                     "response_body_read": False},
        "tls": {"verified": True},
        "http_status": 200,
    }
    return {"id": scan_id, "url": "https://example.com/",
            "host": "example.com", "test_type": kind,
            "status": "completed" if completed else "failed",
            "created_at": date, "result": result}


class RepairCollection(MockCollection):
    async def update_one(self, query, update):
        for item in self.docs:
            if item.get("id") != query.get("id"):
                continue
            if "status" in query and item.get("status") != query["status"]:
                continue
            for key, value in update.get("$set", {}).items():
                item[key] = value
            for key, value in update.get("$push", {}).items():
                item.setdefault(key, []).append(value)
            return SimpleNamespace(modified_count=1)
        return SimpleNamespace(modified_count=0)


def api(db):
    app = FastAPI()
    app.include_router(create_testing_router(db), prefix="/api")
    return TestClient(app)


def test_create_case_copies_real_observation_and_suggests_not_assigns():
    baseline = scan()
    baseline_copy = copy.deepcopy(baseline)
    case = build_repair_case(baseline, "f1")
    assert baseline == baseline_copy
    assert case["source_finding_id"] == "f1"
    assert case["assigned_role"] == "frontend"
    assert case["handoff_state"] == "suggested_not_assigned"
    assert case["pr"] is None
    assert case["status"] == "proposed"
    assert "no code" not in repair_prompt(case).lower()
    assert "request review" in repair_prompt(case)


def test_forged_and_failed_source_rejected():
    baseline = scan()
    with pytest.raises(ValueError):
        build_repair_case(baseline, "invented-id")
    with pytest.raises(ValueError):
        build_repair_case(scan(completed=False), "f1")
    original = scan()
    original["test_type"] = "availability"
    with pytest.raises(ValueError):
        build_repair_case(original, "f1")


def test_retest_ids_change_but_signature_comparison_is_deterministic():
    original = scan()
    case = build_repair_case(original, "f1")
    later = scan(scan_id="s2", include=True, date="2026-10-12T09:00:00+00:00")
    still = assess_retest(case, original, later)
    assert still["result"] == "still_observed"
    assert still["fix_verified"] is False
    later["result"]["findings"] = []
    later["result"]["outcome"] = "pass"
    missing = assess_retest(case, original, later)
    assert missing["result"] == "not_observed_in_retest"
    assert missing["fix_verified"] is False
    assert missing["release_readiness"] == "not_verified"


def test_new_high_severity_observation_blocks_retest_green():
    original = scan()
    case = build_repair_case(original, "f1")
    later = scan(scan_id="s2", include=False, date="2026-10-12T09:00:00+00:00")
    later["result"]["findings"] = [{
        "id": "new-regression", "title": "New broken checkout",
        "category": "functional", "severity": "high", "viewport": "desktop",
    }]
    compared = assess_retest(case, original, later)
    assert compared["result"] == "regression_warning"
    assert compared["new_high_observations"] == 1
    assert compared["fix_verified"] is False


def test_timezone_offsets_cannot_make_older_retest_look_newer():
    original = scan()
    case = build_repair_case(original, "f1")
    later = scan(scan_id="s2", include=False, date="2026-10-12T09:00:00+02:00")
    with pytest.raises(ValueError):
        assess_retest(case, original, later)


def test_broken_mobile_or_changed_test_type_does_not_pass():
    original = scan()
    case = build_repair_case(original, "f1")
    changed = scan(scan_id="s2", include=False, date="2026-10-12T09:00:00+00:00")
    changed["result"]["viewports"][2]["metrics"] = {}
    assert assess_retest(case, original, changed)["result"] == "inconclusive"
    changed["result"]["viewports"][2]["metrics"] = {"page_title": "Page"}
    changed["result"]["summary"]["viewports_completed"] = 1
    assert assess_retest(case, original, changed)["result"] == "inconclusive"
    changed["result"]["summary"]["viewports_completed"] = 3
    changed["url"] = "https://other.com/"
    with pytest.raises(ValueError):
        assess_retest(case, original, changed)


def test_passive_security_requires_verified_tls_and_identical_status():
    original = scan(kind="passive_security")
    case = build_repair_case(original, "f1")
    later = scan(scan_id="s2", kind="passive_security", include=False,
                 date="2026-10-12T09:00:00+00:00")
    assert assess_retest(case, original, later)["result"] == "not_observed_in_retest"
    later["result"]["tls"]["verified"] = False
    assert assess_retest(case, original, later)["result"] == "inconclusive"
    later["result"]["tls"]["verified"] = True
    later["result"]["http_status"] = 302
    assert assess_retest(case, original, later)["result"] == "inconclusive"


def test_finding_cap_is_not_mistaken_for_a_clean_retest():
    original = scan()
    case = build_repair_case(original, "f1")
    later = scan(scan_id="s2", include=False, date="2026-10-12T09:00:00+00:00")
    later["result"]["findings"] = [
        {"id": "other-" + str(i), "category": "runtime",
         "title": "Other issue " + str(i), "viewport": "desktop"}
        for i in range(60)
    ]
    assert assess_retest(case, original, later)["result"] == "inconclusive"
    passive = scan(kind="passive_security")
    p_case = build_repair_case(passive, "f1")
    retry = scan(scan_id="s3", kind="passive_security", include=False,
                 date="2026-10-12T09:00:00+00:00")
    retry["result"]["findings"] = [
        {"id": "other-" + str(i), "code": "OTHER_" + str(i)}
        for i in range(25)
    ]
    assert assess_retest(p_case, passive, retry)["result"] == "inconclusive"


def test_route_persists_proposed_case_and_evidence_only_verification(monkeypatch):
    setup_config(monkeypatch)
    db = FakeDB()
    db.testing_repairs = RepairCollection()
    db.testing_scans.docs.extend([scan(), scan(scan_id="s2", include=False,
                date="2026-10-12T09:00:00+00:00")])
    client = api(db)
    auth = {"X-Testing-Token": TOKEN}
    assert client.get("/api/testing/repairs").status_code == 403
    resp = client.post("/api/testing/scans/s1/repairs",
                       headers=auth, json={"finding_id": "f1"})
    assert resp.status_code == 201, resp.text
    case = resp.json()
    assert case["status"] == "proposed"
    assert "coding_agent_prompt" in case
    listing = client.get("/api/testing/repairs", headers=auth).json()
    assert listing[0]["id"] == case["id"]
    compare = client.post("/api/testing/repairs/" + case["id"] + "/verify",
                          headers=auth, json={"retest_scan_id": "s2"})
    assert compare.status_code == 200, compare.text
    assert compare.json()["result"] == "not_observed_in_retest"
    stored = client.get("/api/testing/repairs/" + case["id"], headers=auth).json()
    assert len(stored["verification_history"]) == 1
    assert stored["release_readiness"] == "not_verified"
    assert stored["status"] == "proposed"
    assert client.post("/api/testing/scans/s1/repairs",
                       headers=auth, json={"finding_id": "faked"}).status_code == 409
    assert client.post("/api/testing/repairs/" + case["id"] + "/verify",
                       headers=auth, json={"retest_scan_id": "s1"}).status_code == 409
    assert client.get("/api/testing/repairs/does-not-exist", headers=auth).status_code == 404
    db._is_mock = True
    assert client.get("/api/testing/repairs", headers=auth).status_code == 503
