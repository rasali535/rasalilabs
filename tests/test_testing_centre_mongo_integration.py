"""Stage 6A real MongoDB isolation smoke in CI service (not live customer sites)."""
import asyncio
import os
import uuid

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from motor.motor_asyncio import AsyncIOMotorClient
from pymongo import MongoClient

from backend.testing_centre.workspace_router import workspace_router
from backend.testing_centre.workspace_worker import claim_one, process_job
from tests.test_testing_centre_workspaces import INVITE, JWT_SECRET


URI = os.getenv("TESTING_INTEGRATION_MONGO_URI")
pytestmark = pytest.mark.skipif(not URI, reason="No disposable CI MongoDB configured")


def test_real_mongo_indexes_isolation_and_worker(monkeypatch):
    dbname = "ral6a_test_" + uuid.uuid4().hex[:12]
    monkeypatch.setenv("TESTING_WORKSPACE_AUTH_ENABLED", "true")
    monkeypatch.setenv("TESTING_WORKSPACE_JWT_SECRET", JWT_SECRET)
    monkeypatch.setenv("TESTING_WORKSPACE_SIGNUP_ENABLED", "true")
    monkeypatch.setenv("TESTING_WORKSPACE_INVITE_SECRET", INVITE)
    monkeypatch.setenv("TESTING_CUSTOMER_JOB_SUBMISSION_ENABLED", "true")
    motor_client = AsyncIOMotorClient(URI, serverSelectionTimeoutMS=3000)
    db = motor_client[dbname]
    challenge = {"value": ""}

    async def txt_record(_host):
        return [challenge["value"]] if challenge["value"] else []

    app = FastAPI()
    app.include_router(workspace_router(db, dns_lookup=txt_record))

    def create_account(api, email, workspace_name):
        response = api.post("/customer-testing/auth/register", json={
            "email": email, "password": "StrongPilotPass123!",
            "workspace_name": workspace_name, "invitation_code": INVITE,
        })
        assert response.status_code == 201, response.text
        auth = api.post("/customer-testing/auth/login", json={
            "email": email, "password": "StrongPilotPass123!",
        })
        assert auth.status_code == 200, auth.text
        return response.json()["workspace_id"], {
            "Authorization": "Bearer " + auth.json()["access_token"],
        }

    # This integration test uses actual Motor, Mongo indexes/queries,
    # and only stubbed DNS/HTTPS. It does not contact public endpoints.
    try:
        with TestClient(app) as api:
            wa, a = create_account(api, "ci-alpha@example.com", "Alpha")
            wb, b = create_account(api, "ci-beta@example.com", "Beta")
            scoped_a = {**a, "X-Workspace-ID": wa}
            scoped_b = {**b, "X-Workspace-ID": wb}
            foreign = {**b, "X-Workspace-ID": wa}
            assert api.get("/customer-testing/domains", headers=foreign).status_code == 404
            assert api.get("/customer-testing/jobs", headers=foreign).status_code == 404
            target = api.post("/customer-testing/domains", headers=scoped_a,
                              json={"hostname": "ci.example.com"})
            assert target.status_code == 201, target.text
            domain = target.json()
            challenge["value"] = domain["challenge_value"]
            verified = api.post("/customer-testing/domains/" + domain["id"] + "/verify",
                                headers=scoped_a)
            assert verified.status_code == 200
            assert api.post("/customer-testing/domains/" + domain["id"] + "/verify",
                            headers=scoped_b).status_code == 404

            from backend.testing_centre import workspace_router as workspace_mod
            original = workspace_mod.validate_target

            async def allow_ci(url, hosts):
                assert hosts == frozenset({"ci.example.com"})
                return url, "ci.example.com"

            workspace_mod.validate_target = allow_ci
            try:
                job = api.post("/customer-testing/jobs", headers=scoped_a,
                               json={"domain_id": domain["id"],
                                     "url": "https://ci.example.com/"})
                assert job.status_code == 202, job.text
                jid = job.json()["id"]
                assert api.get("/customer-testing/jobs/" + jid, headers=foreign).status_code == 404
                assert api.get("/customer-testing/jobs/" + jid, headers=scoped_b).status_code == 404
            finally:
                workspace_mod.validate_target = original

        # New Motor client per asyncio.run prevents crossing test-server event loop.
        async def execute():
            worker_mongo = AsyncIOMotorClient(URI, serverSelectionTimeoutMS=3000)
            worker_db = worker_mongo[dbname]
            claimed = await claim_one(worker_db, "ci-test-worker")
            assert claimed["id"] == jid
            assert claimed["workspace_id"] == wa
            assert await claim_one(worker_db, "other-worker") is None
            async def checked(url, host):
                return {"reachable": True, "tls": {"verified": True},
                        "http_status": 200, "latency_ms": 17}
            done, reason = await process_job(
                worker_db, claimed, "ci-test-worker",
                checker=checked, validator=allow_ci,
            )
            assert done and reason is None
            row = await worker_db.testing_jobs.find_one({"id": jid}, {"_id": 0})
            assert row["status"] == "completed"
            assert row["result"]["tls_verified"] is True
            worker_mongo.close()

        asyncio.run(execute())
    finally:
        motor_client.close()
        MongoClient(URI, serverSelectionTimeoutMS=3000).drop_database(dbname)
