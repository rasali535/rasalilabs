#!/usr/bin/env python3
"""Operator-run two-account Stage 6A staging acceptance smoke.

Requires user-controlled HTTPS staging API, two existing authorized pilot
accounts, and an already DNS-verified test domain. Never runs in PR CI.
Does not provision, merge, attack, fetch raw web pages or disclose credentials.
"""
import asyncio
import os
from urllib.parse import urlsplit

import httpx


def env(name):
    value = os.getenv(name, "").strip()
    if not value:
        raise SystemExit("Missing required staging configuration: " + name)
    return value


async def run():
    if env("RAL6A_SCOPE_ACK") != "I_HAVE_AUTHORIZED_THE_STAGING_SITE_AND_ISOLATED_WORKER":
        raise SystemExit("Explicit owner/worker authorization confirmation required.")
    api = env("RAL6A_STAGING_API").rstrip("/")
    target = env("RAL6A_AUTHORIZED_URL")
    if not (api.startswith("https://") and target.startswith("https://")):
        raise SystemExit("Only HTTPS staging endpoints may be exercised.")
    if (urlsplit(api).username or urlsplit(api).password or
        urlsplit(target).username or urlsplit(target).password or
        urlsplit(target).query or urlsplit(target).fragment):
        raise SystemExit("Do not embed credentials, URL query or fragments.")
    workspace_a = env("RAL6A_WORKSPACE_A")
    workspace_b = env("RAL6A_WORKSPACE_B")
    if workspace_a == workspace_b:
        raise SystemExit("Use two DIFFERENT customer workspaces.")
    domain_id = env("RAL6A_VERIFIED_DOMAIN_ID_A")
    async with httpx.AsyncClient(
        timeout=25, follow_redirects=False, trust_env=False,
    ) as client:
        async def login(email, password):
            response = await client.post(api + "/api/customer-testing/auth/login", json={
                "email": email, "password": password,
            })
            response.raise_for_status()
            return response.json()["access_token"]

        ta = await login(env("RAL6A_USER_A_EMAIL"), env("RAL6A_USER_A_PASSWORD"))
        tb = await login(env("RAL6A_USER_B_EMAIL"), env("RAL6A_USER_B_PASSWORD"))
        a = {"Authorization": "Bearer " + ta, "X-Workspace-ID": workspace_a}
        b = {"Authorization": "Bearer " + tb, "X-Workspace-ID": workspace_b}
        cross = {"Authorization": "Bearer " + tb, "X-Workspace-ID": workspace_a}

        async def get(path, headers):
            return await client.get(api + "/api/customer-testing" + path, headers=headers)

        own_a = await get("/domains", a)
        own_a.raise_for_status()
        own_b = await get("/domains", b)
        own_b.raise_for_status()
        if (await get("/domains", cross)).status_code != 404:
            raise RuntimeError("Cross-tenant domain isolation FAILED")
        if (await get("/jobs", cross)).status_code != 404:
            raise RuntimeError("Cross-tenant job history isolation FAILED")
        domain = next((d for d in own_a.json() if d["id"] == domain_id), None)
        if not domain or domain["hostname"] != urlsplit(target).hostname:
            raise RuntimeError("Stage 6A target is not in workspace A domain inventory")
        if not domain.get("verification_expires_at"):
            raise RuntimeError("Domain is not DNS verified")

        check = await client.post(api + "/api/customer-testing/jobs", headers=a, json={
            "domain_id": domain_id, "url": target, "test_type": "availability",
        })
        check.raise_for_status()
        job = check.json()
        if job["workspace_id"] != workspace_a or job["status"] != "queued":
            raise RuntimeError("Job not persisted as a tenant-scoped queue item")
        if (await get("/jobs/" + job["id"], cross)).status_code != 404:
            raise RuntimeError("Cross-tenant job detail isolation FAILED")

        # Poll a bounded number of times. No claim of success while queued.
        for _ in range(12):
            current = await get("/jobs/" + job["id"], a)
            current.raise_for_status()
            state = current.json()
            if state["status"] in ("completed", "failed"):
                outcome = (state.get("result") or {}).get("outcome")
                print("Stage 6A staging check recorded:", state["status"], outcome)
                if state["status"] != "completed" or not state.get("result", {}).get("tls_verified"):
                    raise RuntimeError("No successful TLS-verified worker observation")
                print("Two-account workspace isolation: PASS")
                print("Verified DNS target and worker HTTPS HEAD: PASS")
                print("Overall security certification: NOT PERFORMED")
                return
            await asyncio.sleep(5)
        raise RuntimeError("Scan is still queued/running; worker deploy or queue needs investigation")


if __name__ == "__main__":
    asyncio.run(run())
