"""Dedicated Stage 6A queue worker for verified customer HTTPS availability.

This process MUST run in an unprivileged, externally egress-restricted runtime,
not the shared API container. Environment flags are declarations, not isolation.
No browser, exploit traffic, redirects, GETs, or response bodies.
"""
import asyncio
import os
import signal
import uuid
from datetime import timedelta

from pymongo import ReturnDocument

from .passive_security import passive_security_audit
from .security import validate_target
from .tenant_auth import utcnow

LEASE_SECONDS = 90
MAX_ATTEMPTS = 2


def worker_configured():
    return (
        os.getenv("TESTING_WORKER_ENABLED", "").lower() == "true"
        and os.getenv("TESTING_WORKER_NETWORK_ISOLATED", "").lower() == "true"
        and os.getenv("TESTING_WORKSPACE_AUTH_ENABLED", "").lower() == "true"
    )


async def claim_one(db, worker_id):
    """Atomically lease one queued job (or a timed-out first attempt)."""
    now = utcnow().isoformat()
    lease = (utcnow() + timedelta(seconds=LEASE_SECONDS)).isoformat()
    return await db.testing_jobs.find_one_and_update(
        {
            "$or": [
                {"status": "queued", "attempts": {"$lt": MAX_ATTEMPTS}},
                {"status": "running", "lease_until": {"$lte": now},
                 "attempts": {"$lt": MAX_ATTEMPTS}},
            ],
        },
        {"$set": {
            "status": "running", "lease_until": lease, "worker_id": worker_id,
            "updated_at": now,
        }, "$inc": {"attempts": 1}},
        sort=[("created_at", 1)],
        return_document=ReturnDocument.AFTER,
        projection={"_id": 0},
    )


async def process_job(db, job, worker_id, checker=None, validator=None):
    """Validate ownership again at execution; store results in scoped document."""
    checker = checker or passive_security_audit
    validator = validator or validate_target
    failure = None
    report = None
    try:
        domain = await db.testing_domains.find_one({
            "id": job["domain_id"], "workspace_id": job["workspace_id"],
            "hostname": job["host"],
        }, {"_id": 0})
        if not domain or not domain.get("verification_expires_at") or (
            domain["verification_expires_at"] <= utcnow().isoformat()
        ):
            raise ValueError("Verified domain scope is absent or expired.")
        clean_url, host = await validator(job["url"], frozenset({domain["hostname"]}))
        if clean_url != job["url"] or host != job["host"] or not clean_url.startswith("https://"):
            raise ValueError("Queued target differs from verified HTTPS scope.")
        audit = await asyncio.wait_for(checker(clean_url, host), timeout=18)
        if not audit.get("reachable") or not audit.get("tls", {}).get("verified"):
            raise ValueError("TLS-verified HEAD observation was not completed.")
        status_code = audit.get("http_status")
        if not isinstance(status_code, int) or not 100 <= status_code <= 599:
            raise ValueError("HTTP response status was not confirmed.")
        result_state = (
            "pass" if 200 <= status_code < 300
            else "warning" if 300 <= status_code < 500 else "fail"
        )
        report = {
            "outcome": result_state, "reachable": True,
            "http_status": status_code, "latency_ms": audit.get("latency_ms"),
            "tls_verified": True, "redirect_not_followed": 300 <= status_code < 400,
            "checks": ["TLS-verified HTTPS HEAD response status",
                       "Observed request latency"],
            "limitations": ["No browser checks", "No penetration test",
                            "No website security certification", "No redirect following"],
        }
    except Exception as exc:
        failure = type(exc).__name__
        report = {
            "outcome": "fail", "reachable": False,
            "http_status": None, "error": failure,
            "checks": [],
            "limitations": ["No successful verified HTTP response was measured."],
        }
    finish = utcnow().isoformat()
    # Compare-and-set ensures an expired worker cannot overwrite a later retry.
    result = await db.testing_jobs.update_one(
        {"id": job["id"], "workspace_id": job["workspace_id"],
         "status": "running", "worker_id": worker_id,
         "attempts": job["attempts"]},
        {"$set": {
            "status": "completed" if report["reachable"] else "failed",
            "result": report, "updated_at": finish,
            "completed_at": finish, "lease_until": None,
        }},
    )
    return bool(getattr(result, "modified_count", 0)), failure


async def fail_expired_jobs(db):
    """Terminalize expired final attempts rather than leaving stuck jobs."""
    now = utcnow().isoformat()
    result = await db.testing_jobs.update_many(
        {"status": "running", "attempts": {"$gte": MAX_ATTEMPTS},
         "lease_until": {"$lte": now}},
        {"$set": {"status": "failed", "updated_at": now,
                  "completed_at": now, "lease_until": None,
                  "result": {"outcome": "fail", "reachable": False,
                             "error": "WorkerLeaseExpired",
                             "checks": [], "limitations": [
                                 "Worker attempts expired; a valid scan was not completed."
                             ]}}},
    )
    return getattr(result, "modified_count", 0)


async def poll_once(db, worker_id, checker=None, validator=None):
    await fail_expired_jobs(db)
    job = await claim_one(db, worker_id)
    if not job:
        return False
    await process_job(db, job, worker_id, checker=checker, validator=validator)
    return True


async def main():
    if not worker_configured():
        raise SystemExit(
            "Worker disabled: require TESTING_WORKER_ENABLED, "
            "TESTING_WORKSPACE_AUTH_ENABLED and real TESTING_WORKER_NETWORK_ISOLATED."
        )
    mongo = os.getenv("TESTING_WORKER_MONGO_URI")
    if not mongo:
        raise SystemExit("Use a scoped TESTING_WORKER_MONGO_URI credential.")
    from motor.motor_asyncio import AsyncIOMotorClient
    client = AsyncIOMotorClient(mongo, serverSelectionTimeoutMS=3000)
    db = client[os.getenv("DB_NAME", "rasalilabs")]
    await client.admin.command("ping")
    worker_id = str(uuid.uuid4())
    stop = asyncio.Event()
    loop = asyncio.get_running_loop()
    for signame in (signal.SIGINT, signal.SIGTERM):
        try:
            loop.add_signal_handler(signame, stop.set)
        except NotImplementedError:
            pass
    try:
        while not stop.is_set():
            did_work = await poll_once(db, worker_id)
            if not did_work:
                try:
                    await asyncio.wait_for(stop.wait(), timeout=2)
                except asyncio.TimeoutError:
                    pass
    finally:
        client.close()


if __name__ == "__main__":
    asyncio.run(main())
