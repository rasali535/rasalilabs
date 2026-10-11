"""Bounded, non-invasive HTTP availability probe for approved Stage 1 hosts.

No redirects followed, no active attacks, no JavaScript and no crawling.
"""
import time
from typing import Any

import httpx


async def check_availability(url: str, client_factory=None) -> dict[str, Any]:
    factory = client_factory or httpx.AsyncClient
    started = time.monotonic()
    try:
        async with factory(timeout=httpx.Timeout(8.0), follow_redirects=False, trust_env=False) as client:
            async with client.stream("HEAD", url) as response:
                status_code = response.status_code
            if status_code in (405, 501):
                async with client.stream("GET", url) as response:
                    status_code = response.status_code
        latency_ms = round((time.monotonic() - started) * 1000)
        # Redirects are reported instead of followed; destinations require new approval.
        return {
            "http_status": status_code,
            "latency_ms": latency_ms,
            "reachable": status_code < 500,
            "outcome": "pass" if 200 <= status_code < 400 else "warning" if status_code < 500 else "fail",
            "redirect_not_followed": 300 <= status_code < 400,
            "checks": ["HTTP response status", "response latency"],
            "limitations": ["No browser tests", "No vulnerability scans", "No penetration test"],
        }
    except (httpx.HTTPError, OSError, TimeoutError) as exc:
        return {
            "http_status": None,
            "latency_ms": round((time.monotonic() - started) * 1000),
            "reachable": False,
            "outcome": "fail",
            "error": type(exc).__name__,
            "checks": ["HTTP response status"],
            "limitations": ["No browser tests", "No vulnerability scans", "No penetration test"],
        }
