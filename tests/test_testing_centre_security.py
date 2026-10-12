"""Stage 3 passive-security regressions: no external network access."""
import asyncio
import ssl
from types import SimpleNamespace

import pytest

from backend.testing_centre.passive_security import (
    analyze_security_observation, parse_headers, passive_security_audit,
)
from tests.test_testing_centre import FakeDB, TOKEN, client_for, setup_config


def sample_observation(headers=None, **extra):
    data = {
        "path": "/", "status": 200,
        "tls": {"verified": True, "version": "TLSv1.3",
                "certificate_hostname_verified": True, "days_until_expiry": 90},
        "headers": list(headers or []),
    }
    data.update(extra)
    return data


def protected_headers():
    return [
        ("content-type", "text/html; charset=utf-8"),
        ("strict-transport-security", "max-age=31536000"),
        ("x-content-type-options", "nosniff"),
        ("content-security-policy", "default-src 'self'; frame-ancestors 'none'"),
        ("referrer-policy", "no-referrer"),
        ("permissions-policy", "camera=()"),
    ]


def test_strong_observations_do_not_invent_vulnerabilities():
    report = analyze_security_observation(sample_observation(protected_headers()))
    assert report["outcome"] == "pass"
    assert report["summary"]["findings"] == 0
    assert report["coverage"]["requests_sent"] == 1
    assert report["coverage"]["response_body_read"] is False


def test_missing_headers_and_tls_expiry_have_evidence_and_cwe():
    report = analyze_security_observation(sample_observation(
        [("content-type", "text/html")],
        tls={"version": "TLSv1.1", "days_until_expiry": 5, "verified": True},
    ))
    codes = {row["code"] for row in report["findings"]}
    assert {"TLS_LEGACY", "TLS_EXPIRING", "HSTS_MISSING",
            "NOSNIFF_MISSING", "CSP_MISSING", "FRAME_GUARD_MISSING"} <= codes
    assert all(row["evidence"] and row["recommendation"] and row["cwe"]
               for row in report["findings"])
    assert report["outcome"] == "warning"


def test_cookie_values_are_never_returned_and_cors_is_not_overstated():
    report = analyze_security_observation(sample_observation([
        ("content-type", "application/json"),
        ("strict-transport-security", "max-age=31536000"),
        ("x-content-type-options", "nosniff"),
        ("set-cookie", "my-secret-cookie-name=secret-value-123; Path=/"),
        ("access-control-allow-origin", "*"),
        ("access-control-allow-credentials", "true"),
    ], path="/api/status"))
    assert report["outcome"] == "warning"
    assert "COOKIE_SECURE_1" in {item["code"] for item in report["findings"]}
    assert "CORS_INVALID" in {item["code"] for item in report["findings"]}
    assert "credentialed CORS" in next(item["recommendation"] for item in report["findings"]
                                      if item["code"] == "CORS_INVALID")
    assert "secret-value" not in str(report)
    assert "my-secret-cookie-name" not in str(report)
    assert "set-cookie" not in str(report)


def test_status_errors_and_redirects_are_not_security_passes():
    rows = protected_headers()
    not_found = analyze_security_observation(sample_observation(rows, status=404))
    assert not_found["outcome"] == "warning"
    redirect = analyze_security_observation(sample_observation(rows, status=302))
    assert redirect["redirect_not_followed"] is True


def test_header_parsing_bounds_and_duplicate_set_cookies():
    data = (b"HTTP/1.1 200 OK\r\nContent-Type: text/html\r\n"
            b"Set-Cookie: first=abc; Secure\r\n"
            b"Set-Cookie: second=xyz; HttpOnly\r\n\r\n")
    status, headers = parse_headers(data)
    assert status == 200
    assert len([x for x in headers if x[0] == "set-cookie"]) == 2
    for bad in (b"garbage\r\n\r\n", b"HTTP/1.1 200 OK\r\n Illegal: x\r\n\r\n",
                b"HTTP/1.1 200 OK\r\n", b"HTTP/1.1 200 OK\r\nno-colon\r\n\r\n"):
        with pytest.raises(ValueError):
            parse_headers(bad)


class FakeStreamReader:
    def __init__(self, response):
        self.response = response
        self.delimiters = []

    async def readuntil(self, delimiter):
        self.delimiters.append(delimiter)
        return self.response


class FakeStreamWriter:
    def __init__(self):
        self.payload = None
        self.closed = False

    def get_extra_info(self, name):
        if name == "ssl_object":
            return SimpleNamespace(version=lambda: "TLSv1.3",
                                   getpeercert=lambda: {})
        if name == "peername":
            return ("93.184.215.14", 443)
        return None

    def write(self, data):
        self.payload = data

    async def drain(self):
        pass

    def close(self):
        self.closed = True

    async def wait_closed(self):
        pass


async def public_ipv4(host, port, **kwargs):
    return [(None, None, None, None, ("93.184.215.14", 443))]


async def private_ipv4(host, port, **kwargs):
    return [(None, None, None, None, ("127.0.0.1", 443))]


def test_pinned_tls_head_no_body_no_redirect():
    writer = FakeStreamWriter()
    reader = FakeStreamReader(
        b"HTTP/1.1 301 Moved Permanently\r\n"
        b"Location: https://elsewhere.example/login\r\n"
        b"Strict-Transport-Security: max-age=31536000\r\n\r\n"
    )
    calls = []

    async def fake_connector(**kwargs):
        calls.append(kwargs)
        return reader, writer

    result = asyncio.run(passive_security_audit(
        "https://example.com/", "example.com",
        resolver=public_ipv4, connector=fake_connector
    ))
    assert result["http_status"] == 301
    assert result["redirect_not_followed"] is True
    assert result["coverage"]["requests_sent"] == 1
    assert result["coverage"]["response_body_read"] is False
    assert reader.delimiters == [b"\r\n\r\n"]
    assert writer.payload.startswith(b"HEAD / HTTP/1.1\r\nHost: example.com\r\n")
    assert b"GET" not in writer.payload
    assert writer.closed
    assert len(calls) == 1
    assert calls[0]["host"] == "93.184.215.14"
    assert calls[0]["server_hostname"] == "example.com"
    assert isinstance(calls[0]["ssl"], ssl.SSLContext)


def test_private_network_and_http_are_rejected_before_connecting():
    connected = []
    async def fake_connector(**kwargs):
        connected.append(kwargs)
        raise AssertionError("Must not connect")

    async def run_private():
        with pytest.raises(ValueError):
            await passive_security_audit(
                "https://example.com/", "example.com",
                resolver=private_ipv4, connector=fake_connector
            )

    asyncio.run(run_private())
    with pytest.raises(ValueError):
        asyncio.run(passive_security_audit(
            "http://example.com/", "example.com",
            resolver=public_ipv4, connector=fake_connector
        ))
    assert not connected


def test_passive_route_off_by_default_and_requires_network_isolation(monkeypatch):
    setup_config(monkeypatch)
    monkeypatch.setenv("TESTING_PASSIVE_SECURITY_ENABLED", "true")
    monkeypatch.delenv("TESTING_SECURITY_NETWORK_ISOLATED", raising=False)
    db = FakeDB()

    async def valid(url, hosts):
        return url, "example.com"

    monkeypatch.setattr("backend.testing_centre.router.validate_target", valid)
    client = client_for(db)
    auth = {"X-Testing-Token": TOKEN}
    response = client.get("/api/testing/config", headers=auth)
    assert response.status_code == 200
    assert response.json()["stage"] >= 3  # Stage 4 adds agents without removing Stage 3
    assert response.json()["passive_security_enabled"] is False
    blocked = client.post("/api/testing/scans", headers=auth,
        json={"url": "https://example.com/", "test_type": "passive_security"})
    assert blocked.status_code == 503
    assert client.post("/api/testing/scans", json={
        "url": "https://example.com/", "test_type": "passive_security"
    }).status_code == 403
    assert not db.testing_scans.docs


def test_security_report_saved_with_no_secret_headers(monkeypatch):
    setup_config(monkeypatch)
    monkeypatch.setenv("TESTING_PASSIVE_SECURITY_ENABLED", "true")
    monkeypatch.setenv("TESTING_SECURITY_NETWORK_ISOLATED", "true")

    async def valid(url, hosts):
        return url, "example.com"

    async def passive(url, host):
        assert (url, host) == ("https://example.com/", "example.com")
        return analyze_security_observation(sample_observation([
            ("content-type", "text/html"),
            ("set-cookie", "private-name=DO-NOT-STORE; Path=/"),
        ]))

    monkeypatch.setattr("backend.testing_centre.router.validate_target", valid)
    monkeypatch.setattr("backend.testing_centre.router.passive_security_audit", passive)
    db = FakeDB()
    client = client_for(db)
    auth = {"X-Testing-Token": TOKEN}
    response = client.post("/api/testing/scans", headers=auth, json={
        "url": "https://example.com/", "test_type": "passive_security",
    })
    assert response.status_code == 201, response.text
    scan = response.json()
    assert scan["status"] == "completed"
    assert scan["test_type"] == "passive_security"
    assert scan["result"]["summary"]["findings"] >= 1
    assert "DO-NOT-STORE" not in str(scan)
    assert "DO-NOT-STORE" not in str(db.testing_scans.docs)
    fetched = client.get("/api/testing/scans/" + scan["id"], headers=auth)
    assert fetched.status_code == 200
    assert fetched.json()["test_type"] == "passive_security"

    invalid = client.post("/api/testing/scans", headers=auth, json={
        "url": "http://example.com/", "test_type": "passive_security"
    })
    assert invalid.status_code == 422
