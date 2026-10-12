"""Bounded HTTPS availability observation for operator-approved Stage 1 hosts.

Uses the same pinned-public-IPv4 + TLS hostname verification + one HEAD
request as the passive observer; there is no fallback GET, body read, redirect
or unrestricted httpx DNS lookup. Real network egress still needs an
isolated worker. Keep the operator feature OFF on shared API deployments.
"""
import time
from typing import Any
from urllib.parse import urlsplit

from .passive_security import passive_security_audit


async def check_availability(url: str, probe=None) -> dict[str, Any]:
    """Return availability only from a verified, bounded HTTPS HEAD response."""
    started = time.monotonic()
    parts = urlsplit(url)
    if parts.scheme != "https" or not parts.hostname or parts.port not in (None, 443):
        raise ValueError("Availability checks require an approved HTTPS hostname.")
    if parts.query or parts.fragment or parts.username or parts.password:
        raise ValueError("URL query strings, fragments and credentials are not permitted.")

    run_probe = probe or passive_security_audit
    try:
        observation = await run_probe(url, parts.hostname)
    except Exception as exc:
        # No upstream URL, headers, tokens or error detail in persisted records.
        observation = {"reachable": False, "error": type(exc).__name__}

    verified = observation.get("tls", {}).get("verified") is True
    status = observation.get("http_status")
    completed = (
        observation.get("reachable") is True and verified and
        isinstance(status, int) and 100 <= status <= 599 and
        observation.get("coverage", {}).get("method") == "pinned_public_ip_https_head" and
        observation.get("coverage", {}).get("requests_sent") == 1 and
        observation.get("coverage", {}).get("response_body_read") is False
    )
    if not completed:
        return {
            "http_status": None,
            "latency_ms": round((time.monotonic() - started) * 1000),
            "reachable": False,
            "outcome": "fail",
            "error": str(observation.get("error") or "VerifiedHeadUnavailable")[:70],
            "checks": [],
            "coverage": {
                "method": "pinned_public_ip_https_head",
                "requests_sent": 0, "response_body_read": False,
                "redirects_followed": 0,
            },
            "limitations": [
                "No verified HTTP response confirmed", "No browser tests",
                "No vulnerability or penetration testing",
            ],
        }

    return {
        "http_status": status,
        "latency_ms": observation.get("latency_ms"),
        "reachable": True,
        "outcome": "pass" if 200 <= status < 300 else
                   "warning" if status < 500 else "fail",
        "redirect_not_followed": 300 <= status < 400,
        "tls_verified": True,
        "checks": ["IP-pinned TLS-verified HTTPS HEAD status", "Response latency"],
        "coverage": {
            "method": "pinned_public_ip_https_head",
            "requests_sent": 1, "response_body_read": False,
            "redirects_followed": 0,
        },
        "limitations": [
            "No HTTP GET or response body", "No redirect following",
            "No browser tests", "No vulnerability or penetration testing",
        ],
    }
