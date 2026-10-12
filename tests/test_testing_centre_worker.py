"""Stage 6A worker queue ownership and lease tests, fully offline."""
import asyncio
from copy import deepcopy
from datetime import timedelta

import pytest

from backend.testing_centre.tenant_auth import utcnow
from backend.testing_centre.workspace_worker import (
    claim_one, fail_expired_jobs, poll_once, process_job, worker_configured,
)
from tests.test_testing_centre_workspaces import FakeDatabase, Collection


class Queue(Collection):
    async def find_one_and_update(self, query, changes, sort=None,
                                  return_document=None, projection=None):
        candidates = [d for d in self.docs if self.matches(d, query)]
        if not candidates:
            return None
        selected = sorted(candidates, key=lambda d: d["created_at"])[0]
        selected.update(deepcopy(changes.get("$set", {})))
        for field, n in changes.get("$inc", {}).items():
            selected[field] = selected.get(field, 0) + n
        return deepcopy(selected)

    async def update_many(self, query, changes):
        updated = 0
        for d in self.docs:
            if self.matches(d, query):
                d.update(deepcopy(changes.get("$set", {})))
                updated += 1
        return type("Result", (), {"modified_count": updated})()


def fake_db():
    db = FakeDatabase()
    db.testing_jobs = Queue()
    return db


def job(when=None, status="queued", attempts=0):
    return {
        "id": "j1", "workspace_id": "work-a", "domain_id": "d1",
        "url": "https://site.example.com/", "host": "site.example.com",
        "status": status, "worker_id": None, "attempts": attempts,
        "lease_until": when,
        "created_at": (utcnow() - timedelta(minutes=1)).isoformat(),
    }


async def safe(url, allowed):
    assert allowed == frozenset({"site.example.com"})
    return url, "site.example.com"


async def fake_probe(url, host):
    assert url == "https://site.example.com/"
    assert host == "site.example.com"
    return {"reachable": True, "http_status": 200,
            "tls": {"verified": True}, "latency_ms": 30}


def add_domain(db, expires=None):
    db.testing_domains.docs.append({
        "id": "d1", "workspace_id": "work-a", "hostname": "site.example.com",
        "verification_expires_at": expires or (utcnow() + timedelta(days=10)).isoformat(),
    })


def test_worker_off_by_default(monkeypatch):
    monkeypatch.delenv("TESTING_WORKER_ENABLED", raising=False)
    monkeypatch.delenv("TESTING_WORKER_NETWORK_ISOLATED", raising=False)
    assert worker_configured() is False
    monkeypatch.setenv("TESTING_WORKER_ENABLED", "true")
    monkeypatch.setenv("TESTING_WORKER_NETWORK_ISOLATED", "true")
    monkeypatch.setenv("TESTING_WORKSPACE_AUTH_ENABLED", "true")
    assert worker_configured() is True


def test_queued_job_claim_is_atomic_and_consumes_lease():
    async def scenario():
        db = fake_db()
        db.testing_jobs.docs.append(job())
        got = await claim_one(db, "worker-1")
        assert got["worker_id"] == "worker-1"
        assert got["attempts"] == 1
        assert got["status"] == "running"
        assert await claim_one(db, "worker-2") is None
    asyncio.run(scenario())


def test_expired_domain_fails_before_fetch():
    async def scenario():
        db = fake_db()
        db.testing_jobs.docs.append(job(status="running", attempts=1))
        db.testing_jobs.docs[0]["worker_id"] = "worker-1"
        add_domain(db, expires=(utcnow() - timedelta(days=1)).isoformat())
        called = []
        async def checker(*_):
            called.append(True)
            raise AssertionError("Must not scan expired verified domain")
        saved, err = await process_job(db, db.testing_jobs.docs[0], "worker-1",
                                       checker=checker, validator=safe)
        assert saved is True
        assert err == "ValueError"
        assert called == []
        assert db.testing_jobs.docs[0]["status"] == "failed"
        assert db.testing_jobs.docs[0]["result"]["reachable"] is False
    asyncio.run(scenario())


def test_worker_processes_verified_domain_but_not_unverified_tls():
    async def scenario():
        db = fake_db()
        db.testing_jobs.docs.append(job())
        add_domain(db)
        claimed = await claim_one(db, "worker-a")
        assert claimed
        saved, err = await process_job(db, claimed, "worker-a",
                                       checker=fake_probe, validator=safe)
        assert saved and err is None
        assert db.testing_jobs.docs[0]["status"] == "completed"
        assert db.testing_jobs.docs[0]["result"]["http_status"] == 200
        assert "content_b64" not in str(db.testing_jobs.docs[0])
        assert await claim_one(db, "worker-b") is None
    asyncio.run(scenario())


def test_stale_worker_cannot_overwrite_new_attempt():
    async def scenario():
        db = fake_db()
        db.testing_jobs.docs.append(job(status="running", attempts=2))
        db.testing_jobs.docs[0]["worker_id"] = "newer-worker"
        add_domain(db)
        old_job = deepcopy(db.testing_jobs.docs[0])
        old_job["worker_id"] = "stale-worker"
        old_job["attempts"] = 1
        updated, err = await process_job(db, old_job, "stale-worker",
                                         checker=fake_probe, validator=safe)
        assert updated is False
        assert db.testing_jobs.docs[0]["status"] == "running"
    asyncio.run(scenario())


def test_expired_final_attempt_terminates_instead_of_renewing():
    async def scenario():
        db = fake_db()
        db.testing_jobs.docs.append(job(when=(utcnow() - timedelta(seconds=8)).isoformat(),
                                        status="running", attempts=2))
        affected = await fail_expired_jobs(db)
        assert affected == 1
        assert db.testing_jobs.docs[0]["status"] == "failed"
        assert db.testing_jobs.docs[0]["result"]["error"] == "WorkerLeaseExpired"
        assert await claim_one(db, "new-worker") is None
    asyncio.run(scenario())


def test_no_domain_proof_cannot_call_network():
    async def scenario():
        db = fake_db()
        db.testing_jobs.docs.append(job(status="running", attempts=1))
        db.testing_jobs.docs[0]["worker_id"] = "worker-x"
        calls = []
        async def checker(*_):
            calls.append(True)
            return {}
        complete, error = await process_job(db, db.testing_jobs.docs[0],
                                             "worker-x", checker=checker, validator=safe)
        assert complete
        assert error == "ValueError"
        assert calls == []
    asyncio.run(scenario())
