#!/usr/bin/env python3
"""Explicit opt-in real staging smoke for Stages 1–5.

Requires operator permission and an actually isolated worker deployment.
Never runs from CI; never tests an arbitrary target without explicit confirmation.
No GitHub writes, fixes or PR creation.
"""
import asyncio
import os
from urllib.parse import urlsplit

import httpx


async def main():
    base = os.getenv("TESTING_STAGING_BASE_URL", "").rstrip("/")
    target = os.getenv("TESTING_STAGING_AUTHORIZED_URL", "")
    token = os.getenv("TESTING_STAGING_TOKEN", "")
    acknowledgment = os.getenv("TESTING_STAGING_SCOPE_CONFIRMED", "")
    if acknowledgment != "I_HAVE_AUTHORIZATION_AND_NETWORK_ISOLATION":
        raise SystemExit("Explicit site owner permission and network isolation acknowledgment required.")
    if not token or not base.startswith("https://") or not target.startswith("https://"):
        raise SystemExit("Staging HTTPS backend, authorized HTTPS site and token are required.")
    site = urlsplit(target)
    backend = urlsplit(base)
    if any((not site.hostname, not backend.hostname, site.query, site.fragment,
            site.username, backend.username, site.password, backend.password)):
        raise SystemExit("Rejecting ambiguous/unapproved URLs or embedded credentials.")
    hdr = {"X-Testing-Token": token}
    async with httpx.AsyncClient(timeout=90, follow_redirects=False, trust_env=False) as client:
        async def checked(method, endpoint, **kwargs):
            res = await client.request(method, base + "/api/testing" + endpoint,
                                       headers=hdr, **kwargs)
            if res.status_code >= 400:
                raise RuntimeError(f"Staging {endpoint} returned HTTP {res.status_code}")
            return res.json()

        cfg = await checked("GET", "/config")
        if site.hostname not in cfg.get("allowed_hosts", []):
            raise SystemExit("Staging operator did not approve the target hostname.")
        kinds = ["availability"]
        if cfg.get("browser_enabled"):
            kinds.append("browser_smoke")
        if cfg.get("passive_security_enabled"):
            kinds.append("passive_security")
        results = []
        for kind in kinds:
            scan = await checked("POST", "/scans", json={"url": target, "test_type": kind})
            persisted = await checked("GET", "/scans/" + scan["id"])
            if persisted.get("id") != scan.get("id"):
                raise RuntimeError("Persisted scan identifier did not match.")
            report = persisted.get("result") or {}
            print("SCAN", kind, persisted.get("status"), report.get("outcome"),
                  "recorded:", bool(report))
            results.append(persisted)
            if persisted.get("status") == "completed":
                review = await checked("POST", "/scans/" + scan["id"] + "/reviews",
                                       json={"use_ai": False})
                assert review["scan_id"] == scan["id"]
                assert review["release_readiness"] == "not_verified"
                print("REVIEW", kind, review["analysis_engine"], "gaps:",
                      review["summary"].get("gaps"))
        print("STAGING CHECK COMPLETED, NOT A PRODUCTION OR SECURITY CERTIFICATION")
        print("Profiles checked:", ", ".join(kinds))
        print("Real automated repair, protected GitHub publishing and third-party testing: NOT EXERCISED")


if __name__ == "__main__":
    asyncio.run(main())
