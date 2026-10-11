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


def test_availability_probe_get_fallback_and_redirect_no_follow():
    calls = []
    statuses = [405, 200]
    def factory(**kwargs):
        return MockHttpClient(statuses, calls, **kwargs)
    result = asyncio.run(check_availability("https://example.com/", client_factory=factory))
    assert result["http_status"] == 200
    assert result["outcome"] == "pass"
    assert calls == [("HEAD", "https://example.com/"), ("GET", "https://example.com/")]

    calls = []
    statuses = [302]
    def redirect_factory(**kwargs):
        return MockHttpClient(statuses, calls, **kwargs)
    result = asyncio.run(check_availability("https://example.com/", client_factory=redirect_factory))
    assert result["redirect_not_followed"] is True
    assert len(calls) == 1


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
