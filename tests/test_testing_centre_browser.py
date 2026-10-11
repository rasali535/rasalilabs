"""Stage 2 checks without contacting external websites.

Live Playwright launch is separately exercised by CI with an offline HTML page;
authorized staging URL smoke tests remain a manual deployment acceptance gate.
"""
import asyncio
from types import SimpleNamespace

import pytest

from backend.testing_centre.browser import clean_diagnostic, interpret_dom, interpret_link_checks, resolve_public_ipv4
from tests.test_testing_centre import FakeDB, MockCollection, TOKEN, client_for, setup_config


async def public_dns(host, port, **kwargs):
    return [(None, None, None, None, ("93.184.215.14", port))]


async def private_dns(host, port, **kwargs):
    return [(None, None, None, None, ("127.0.0.1", port))]


def test_browser_resolver_denies_internal_addresses():
    assert asyncio.run(resolve_public_ipv4("example.com", resolver=public_dns)) == "93.184.215.14"
    with pytest.raises(ValueError, match="private or non-public"):
        asyncio.run(resolve_public_ipv4("example.com", resolver=private_dns))
    with pytest.raises(ValueError):
        asyncio.run(resolve_public_ipv4("localhost", resolver=public_dns))


def test_dom_finding_classification_and_url_redaction():
    report = interpret_dom({
        "body_text_length": 0,
        "broken_images": 2,
        "invalid_anchors": 1,
        "horizontal_overflow": True,
        "document_width": 600,
        "viewport_width": 390,
        "page_title": "",
        "navigation_ms": 6200,
    }, "mobile")
    names = {finding["title"] for finding in report}
    assert "Empty visible page" in names
    assert "Broken images" in names
    assert "Horizontal overflow" in names
    assert "Slow navigation timing" in names
    assert all(finding["verified_by"] == "browser_observation" for finding in report)
    assert "secret" not in clean_diagnostic("Request https://example.com/?token=secret failed")


def test_link_head_checks_only_flag_confirmed_missing_destinations():
    items = interpret_link_checks([
        {"path": "/missing", "status": 404},
        {"path": "/gone", "status": 410},
        {"path": "/head-unsupported", "status": 405},
        {"path": "/healthy", "status": 200},
    ])
    assert len(items) == 2
    assert all(item["title"] == "Broken same-origin link" for item in items)
    assert all(item["verified_by"] == "browser_observation" for item in items)


def test_browser_disabled_without_isolation_config(monkeypatch):
    setup_config(monkeypatch)
    monkeypatch.setenv("TESTING_BROWSER_ENABLED", "true")
    monkeypatch.delenv("TESTING_BROWSER_NETWORK_ISOLATED", raising=False)

    async def validated(url, hosts):
        return url, "example.com"

    monkeypatch.setattr("backend.testing_centre.router.validate_target", validated)
    client = client_for(FakeDB())
    auth = {"X-Testing-Token": TOKEN}
    config = client.get("/api/testing/config", headers=auth)
    assert config.status_code == 200
    assert config.json()["browser_enabled"] is False
    result = client.post("/api/testing/scans", headers=auth,
                         json={"url": "https://example.com/", "test_type": "browser_smoke"})
    assert result.status_code == 503


def test_browser_result_persistence_and_evidence_download(monkeypatch):
    setup_config(monkeypatch)
    monkeypatch.setenv("TESTING_BROWSER_ENABLED", "true")
    monkeypatch.setenv("TESTING_BROWSER_NETWORK_ISOLATED", "true")

    async def validated(url, hosts):
        return url, "example.com"

    async def mocked_audit(url, host):
        assert url == "https://example.com/"
        assert host == "example.com"
        return {
            "outcome": "warning", "findings": [{
                "id": "issue-1", "title": "Broken images", "detail": "Image failed",
                "category": "functional", "severity": "medium",
                "viewport": "mobile", "recommendation": "Repair image URL",
                "verified_by": "browser_observation",
            }],
            "viewports": [{
                "name": "mobile", "width": 390, "height": 844, "http_status": 200,
                "metrics": {"fcp_ms": 900}, "evidence_id": "evidence-1",
            }],
            "summary": {"high": 0, "medium": 1, "low": 0, "viewports_completed": 1},
            "screenshots": [{"id": "evidence-1", "viewport": "mobile",
                             "media_type": "image/jpeg", "content_b64": "YWJj"}],
        }

    monkeypatch.setattr("backend.testing_centre.router.validate_target", validated)
    monkeypatch.setattr("backend.testing_centre.router.browser_audit", mocked_audit)
    db = FakeDB()
    db.testing_evidence = MockCollection()
    app = client_for(db)
    auth = {"X-Testing-Token": TOKEN}
    result = app.post("/api/testing/scans", headers=auth,
                      json={"url": "https://example.com/", "test_type": "browser_smoke"})
    assert result.status_code == 201, result.text
    data = result.json()
    assert data["status"] == "completed"
    assert data["result"]["screenshots"] == [{"id": "evidence-1",
        "viewport": "mobile", "media_type": "image/jpeg"}]
    assert "content_b64" not in str(data)
    assert len(db.testing_evidence.docs) == 1

    evidence = app.get("/api/testing/evidence/evidence-1", headers=auth)
    assert evidence.status_code == 200
    assert evidence.json()["data_uri"] == "data:image/jpeg;base64,YWJj"
    assert app.get("/api/testing/evidence/missing", headers=auth).status_code == 404
    assert app.get("/api/testing/evidence/evidence-1").status_code == 403


def test_browser_failure_saved_as_failed_scan(monkeypatch):
    setup_config(monkeypatch)
    monkeypatch.setenv("TESTING_BROWSER_ENABLED", "true")
    monkeypatch.setenv("TESTING_BROWSER_NETWORK_ISOLATED", "true")

    async def validated(url, hosts):
        return url, "example.com"

    async def crashed(url, host):
        raise RuntimeError("Browser dependency missing")

    monkeypatch.setattr("backend.testing_centre.router.validate_target", validated)
    monkeypatch.setattr("backend.testing_centre.router.browser_audit", crashed)
    db = FakeDB()
    app = client_for(db)
    response = app.post("/api/testing/scans",
                        headers={"X-Testing-Token": TOKEN},
                        json={"url": "https://example.com/", "test_type": "browser_smoke"})
    assert response.status_code == 201
    assert response.json()["status"] == "failed"
    assert response.json()["result"]["outcome"] == "fail"
