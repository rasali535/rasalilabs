"""Stage 1 Testing Centre regression checks: no external web requests."""
import asyncio
from types import SimpleNamespace

import httpx
from fastapi import FastAPI
from fastapi.testclient import TestClient

from backend.testing_centre.router import create_testing_router
from backend.testing_centre.scanner import check_availability
from backend.testing_centre.security import validate_target


TOKEN = "a" * 40


async def public_dns(host, port):
    return [(None, None, None, None, ("93.184.215.14", port))]


async def private_dns(host, port):
    return [(None, None, None, None, ("127.0.0.1", port))]


def test_target_blocks_unapproved_private_and_unsafe_urls():
    allow = frozenset({"example.com"})
    invalid = [
        "http://127.0.0.1/",
        "http://localhost/",
        "http://169.254.169.254/",
        "http://example.com:9000/",
        "http://example.com/?token=secret",
        "https://user:pass@example.com/",
        "ftp://example.com/",
        "https://other-example.com/",
        "https://example.com/#secret",
        "https://example.com%2F.evil/",
    ]
    for url in invalid:
        try:
            asyncio.run(validate_target(url, allow, resolver=public_dns))
            assert False, "Expected validation to reject " + url
        except ValueError:
            pass
    try:
        asyncio.run(validate_target("https://example.com/", allow, resolver=private_dns))
        assert False, "Expected private DNS rejection"
    except ValueError:
        pass


def test_target_accepts_approved_public_dns():
    url, host = asyncio.run(validate_target("https://example.com/check", frozenset({"example.com"}), resolver=public_dns))
    assert url == "https://example.com/check"
    assert host == "example.com"


class Stream:
    def __init__(self, response):
        self.response = response

    async def __aenter__(self):
        return SimpleNamespace(status_code=self.response)

    async def __aexit__(self, *_args):
        pass


class MockHttpClient:
    def __init__(self, statuses, calls, **_kwargs):
        self.statuses = statuses
        self.calls = calls

    async def __aenter__(self):
        return self

    async def __aexit__(self, *_args):
        pass

    def stream(self, method, url):
        self.calls.append((method, url))
        return Stream(self.statuses.pop(0))


def test_availability_uses_only_pinned_tls_verified_head():
    async def completed(url, host):
        assert url == "https://example.com/"
        assert host == "example.com"
        return {
            "reachable": True, "outcome": "warning",
            "tls": {"verified": True}, "http_status": 302, "latency_ms": 23,
            "coverage": {
                "method": "pinned_public_ip_https_head",
                "requests_sent": 1,
                "response_body_read": False,
                "redirects_followed": 0,
            },
        }

    result = asyncio.run(check_availability("https://example.com/", probe=completed))
    assert result["http_status"] == 302
    assert result["redirect_not_followed"] is True
    assert result["outcome"] == "warning"
    assert result["coverage"]["requests_sent"] == 1
    assert result["coverage"]["response_body_read"] is False
    assert result["tls_verified"] is True
    assert not any("GET" in x for x in result["checks"])


def test_availability_refuses_unverified_and_unsafe_observations():
    async def missing_tls(url, host):
        return {
            "reachable": True, "http_status": 200,
            "tls": {"verified": False}, "coverage": {
                "method": "pinned_public_ip_https_head",
                "requests_sent": 1, "response_body_read": False,
            },
        }

    async def unpinned(url, host):
        return {
            "reachable": True, "http_status": 200,
            "tls": {"verified": True}, "coverage": {
                "method": "generic_http", "requests_sent": 1,
                "response_body_read": False,
            },
        }

    async def body_read(url, host):
        return {
            "reachable": True, "http_status": 200,
            "tls": {"verified": True}, "coverage": {
                "method": "pinned_public_ip_https_head",
                "requests_sent": 1, "response_body_read": True,
            },
        }

    for probe in (missing_tls, unpinned, body_read):
        result = asyncio.run(check_availability("https://example.com/", probe=probe))
        assert result["outcome"] == "fail"
        assert result["http_status"] is None
        assert result["coverage"]["requests_sent"] == 0

    for url in ("http://example.com/", "https://user:pass@example.com/",
                "https://example.com/?secret=1", "https://example.com:8443/"):
        try:
            asyncio.run(check_availability(url, probe=missing_tls))
            assert False, "Expected invalid URL to fail: " + url
        except ValueError:
            pass


def test_readiness_public_but_token_and_scans_are_protected(monkeypatch):
    monkeypatch.delenv("TESTING_CENTRE_ENABLED", raising=False)
    monkeypatch.delenv("TESTING_ACCESS_TOKEN", raising=False)
    monkeypatch.delenv("TESTING_ALLOWED_HOSTS", raising=False)
    db = FakeDB()
    client = client_for(db)
    status = client.get("/api/testing/status")
    assert status.status_code == 200
    assert status.json()["mode"] == "disabled"
    assert "allowed_hosts" not in status.text
    assert "token" not in status.text.lower().replace("testing_token", "")
    assert client.get("/api/testing/config").status_code == 503
    setup_config(monkeypatch)
    status = client.get("/api/testing/status")
    assert status.json()["mode"] == "operator_configured"
    assert status.json()["availability_method"] == "tls_pinned_https_head"
    assert client.get("/api/testing/scans").status_code == 403
    db._is_mock = True
    assert client.get("/api/testing/status").json()["mode"] == "storage_unavailable"


def test_readiness_configuration_required(monkeypatch):
    monkeypatch.setenv("TESTING_CENTRE_ENABLED", "true")
    monkeypatch.delenv("TESTING_ACCESS_TOKEN", raising=False)
    monkeypatch.delenv("TESTING_ALLOWED_HOSTS", raising=False)
    client = client_for(FakeDB())
    assert client.get("/api/testing/status").json()["mode"] == "configuration_required"



class MockCursor:
    def __init__(self, docs):
        self.docs = docs

    def sort(self, *_args):
        return self

    async def to_list(self, _limit):
        return [dict(doc) for doc in self.docs]


class MockCollection:
    def __init__(self):
        self.docs = []

    def find(self, *_args):
        return MockCursor(self.docs)

    async def find_one(self, query, *_args):
        for doc in self.docs:
            if doc.get("id") == query.get("id"):
                return dict(doc)
        return None

    async def insert_one(self, doc):
        self.docs.append(dict(doc))

    async def update_one(self, query, update):
        for doc in self.docs:
            if doc.get("id") == query.get("id"):
                doc.update(update["$set"])


class FakeDB:
    def __init__(self):
        self._is_mock = False
        self.testing_scans = MockCollection()
        self.projects = MockCollection()


def client_for(db):
    app = FastAPI()
    app.include_router(create_testing_router(db), prefix="/api")
    return TestClient(app)


def setup_config(monkeypatch):
    monkeypatch.setenv("TESTING_CENTRE_ENABLED", "true")
    monkeypatch.setenv("TESTING_ALLOWED_HOSTS", "example.com")
    monkeypatch.setenv("TESTING_ACCESS_TOKEN", TOKEN)
    monkeypatch.setenv("TESTING_SCAN_EXECUTION_ENABLED", "true")  # offline mocked execution only


def test_access_denied_by_default_and_on_wrong_token(monkeypatch):
    monkeypatch.delenv("TESTING_CENTRE_ENABLED", raising=False)
    monkeypatch.delenv("TESTING_ACCESS_TOKEN", raising=False)
    monkeypatch.delenv("TESTING_ALLOWED_HOSTS", raising=False)
    client = client_for(FakeDB())
    assert client.get("/api/testing/scans").status_code == 503
    setup_config(monkeypatch)
    assert client.get("/api/testing/scans").status_code == 403
    assert client.get("/api/testing/scans", headers={"X-Testing-Token": "incorrect"}).status_code == 403
    assert client.get("/api/testing/config", headers={"X-Testing-Token": TOKEN}).status_code == 200


def test_operator_read_only_mode_blocks_scans_without_dns_or_network(monkeypatch):
    setup_config(monkeypatch)
    monkeypatch.delenv("TESTING_SCAN_EXECUTION_ENABLED", raising=False)
    db = FakeDB()
    client = client_for(db)
    auth = {"X-Testing-Token": TOKEN}

    status = client.get("/api/testing/status").json()
    assert status["mode"] == "operator_configured"
    assert status["scan_execution_enabled"] is False

    config = client.get("/api/testing/config", headers=auth)
    assert config.status_code == 200
    assert config.json()["read_only_mode"] is True
    assert config.json()["scan_execution_enabled"] is False
    assert client.get("/api/testing/scans", headers=auth).status_code == 200
    assert client.post("/api/testing/scans", headers=auth, json={
        "url": "https://example.com/", "test_type": "availability",
    }).status_code == 503
    assert client.post("/api/testing/scans", headers=auth, json={
        "url": "https://example.com/", "test_type": "browser_smoke",
    }).status_code == 503
    assert client.post("/api/testing/scans", headers=auth, json={
        "url": "https://example.com/", "test_type": "passive_security",
    }).status_code == 503
    assert db.testing_scans.docs == []


def test_scan_create_persist_history_and_failure_reporting(monkeypatch):
    setup_config(monkeypatch)

    async def valid(url, hosts):
        assert "example.com" in hosts
        return url, "example.com"

    async def failed(url):
        return {
            "reachable": False, "outcome": "fail", "http_status": 503, "latency_ms": 4,
            "checks": ["HTTP response status"], "limitations": ["No penetration test"],
        }

    monkeypatch.setattr("backend.testing_centre.router.validate_target", valid)
    monkeypatch.setattr("backend.testing_centre.router.check_availability", failed)
    db = FakeDB()
    client = client_for(db)
    auth = {"X-Testing-Token": TOKEN}
    response = client.post("/api/testing/scans", headers=auth, json={"url": "https://example.com/"})
    assert response.status_code == 201, response.text
    scan = response.json()
    assert scan["status"] == "failed"
    assert scan["result"]["http_status"] == 503
    assert len(db.testing_scans.docs) == 1
    listing = client.get("/api/testing/scans", headers=auth)
    assert listing.status_code == 200
    assert listing.json()[0]["id"] == scan["id"]
    assert client.get("/api/testing/scans/" + scan["id"], headers=auth).status_code == 200
    assert client.get("/api/testing/scans/missing", headers=auth).status_code == 404

    db._is_mock = True
    assert client.post("/api/testing/scans", headers=auth, json={"url": "https://example.com/"}).status_code == 503
    assert client.get("/api/testing/scans", headers=auth).status_code == 503
