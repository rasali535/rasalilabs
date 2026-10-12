#!/usr/bin/env python3
"""Read-only + unauthorized-request negative test for legacy-agent staging.

Does NOT test a public production site without operator-controlled staging.
No writes are authenticated. Uses operator token only to check a harmless GET.
"""
import asyncio
import os
from urllib.parse import urlsplit

import httpx


def required(name):
    value = os.getenv(name, "").strip()
    if not value:
        raise SystemExit("Missing staging environment: " + name)
    return value


async def smoke():
    if required("LEGACY_STAGING_SCOPE_ACK") != "I_CONTROL_THIS_STAGING_DEPLOYMENT":
        raise SystemExit("Explicit staging ownership acknowledgment required.")
    base = required("LEGACY_STAGING_API_BASE").rstrip("/")
    operator = required("LEGACY_STAGING_OPERATOR_TOKEN")
    parsed = urlsplit(base)
    if (parsed.scheme != "https" or not parsed.hostname or
        parsed.username or parsed.password or parsed.query or parsed.fragment):
        raise SystemExit("Must provide a clean HTTPS staging API origin.")
    async with httpx.AsyncClient(
        trust_env=False, timeout=12, follow_redirects=False,
    ) as client:
        async def request(method, endpoint, *, token=None, body=None):
            headers = {"X-Legacy-Operator-Token": token} if token is not None else {}
            return await client.request(method, base + endpoint, headers=headers, json=body)

        health = await request("GET", "/api/health")
        if health.status_code != 200:
            raise RuntimeError("Staging health endpoint unavailable.")

        status = await request("GET", "/api/legacy-access/status")
        status.raise_for_status()
        state = status.json()
        if not state.get("required") or not state.get("configured"):
            raise RuntimeError("Legacy gate is not actively protecting this staging deployment.")

        # This sequence deliberately does not send any authorized mutations.
        for endpoint in ("/api/projects", "/api/models", "/api/chat/history"):
            denied = await request("GET", endpoint)
            if denied.status_code != 401:
                raise RuntimeError(f"Private route {endpoint} failed without-token check.")
        for endpoint in ("/api/cognee/forget", "/api/models/config"):
            denied = await request("POST", endpoint, body={})
            if denied.status_code != 401:
                raise RuntimeError(f"Sensitive mutation {endpoint} failed without-token check.")

        invalid = await request("GET", "/api/agents", token="invalid-operator-token")
        if invalid.status_code != 401:
            raise RuntimeError("Invalid operator token was not rejected.")

        valid = await request("GET", "/api/agents", token=operator)
        if valid.status_code != 200:
            raise RuntimeError("Operator token did not authorize private agent reads.")
        if not isinstance(valid.json(), list):
            raise RuntimeError("Unexpected agent collection after authorization.")

        customer = await request("GET", "/api/customer-testing/availability")
        if customer.status_code not in (200, 503):
            raise RuntimeError("Customer API is unexpectedly affected by legacy gate.")

        print("Legacy operator protection: PASS")
        print("Unauthorized private reads and writes: DENIED")
        print("Authorized agent read: PASS")
        print("Customer auth route remains independent: PASS")
        print("Live WebSocket origin/auth, worker egress and full user journeys: NOT TESTED")
        print("Security certification / provider secret rotation: NOT PERFORMED")


if __name__ == "__main__":
    asyncio.run(smoke())
