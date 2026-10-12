"""Stage 6A tenant-scoped, invite-only Testing Centre API.

Intentionally separate from the operator-only /api/testing endpoints until
legacy auth, ownership verification, queueing and egress isolation are retired.
No unrestricted customer URL scanning is exposed.
"""
import os
import secrets
import uuid
from datetime import timedelta
from urllib.parse import urlsplit

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from pymongo.errors import DuplicateKeyError

from .security import HOST_RE, validate_target
from .tenant_auth import (
    Registration, Login, WorkspaceCreate, create_identity_dependencies,
    create_registration, enabled, ensure_config, ensure_indexes, log_in,
    utcnow,
)

DOMAIN_VALID_DAYS = 30
MAX_RECENT_JOBS = 100


class DomainRequest(BaseModel):
    hostname: str = Field(min_length=4, max_length=253)


class JobRequest(BaseModel):
    domain_id: str = Field(min_length=8, max_length=90)
    url: str = Field(min_length=10, max_length=2048)
    test_type: str = "availability"


async def lookup_txt(hostname):
    import dns.asyncresolver
    try:
        values = await dns.asyncresolver.resolve(hostname, "TXT", lifetime=4)
        return [b"".join(entry.strings).decode("utf-8") for entry in values]
    except Exception:
        return []


def workspace_router(db, dns_lookup=None):
    router = APIRouter(prefix="/customer-testing", tags=["Customer Testing (Stage 6A)"])
    current_user, require_workspace = create_identity_dependencies(db)
    dns_lookup = dns_lookup or lookup_txt
    state = {"ready": False}

    @router.on_event("startup")
    async def initialize():
        state["ready"] = False
        if not enabled() or getattr(db, "_is_mock", False):
            return
        try:
            ensure_config(db)
            await ensure_indexes(db)
            state["ready"] = True
        except Exception:
            # Fail closed if indexes/migrations cannot be created.
            state["ready"] = False

    def ready():
        ensure_config(db)
        if not state["ready"]:
            raise HTTPException(503, "Workspace database initialization is incomplete.")

    @router.get("/availability")
    async def available():
        ready()
        return {"enabled": True, "registration_invite_only": True,
                "scanning": "queued_https_availability_only",
                "customer_browser_scan_enabled": False,
                "customer_penetration_testing_enabled": False}

    @router.post("/auth/register", status_code=201)
    async def register(data: Registration):
        ready()
        return await create_registration(db, data)

    @router.post("/auth/login")
    async def login(data: Login):
        ready()
        return await log_in(db, data)

    @router.get("/auth/me")
    async def whoami(user=Depends(current_user)):
        ready()
        return user

    @router.get("/workspaces")
    async def list_workspaces(user=Depends(current_user)):
        ready()
        try:
            memberships = await db.testing_memberships.find(
                {"user_id": user["id"], "status": "active"}, {"_id": 0}
            ).to_list(20)
            results = []
            for membership in memberships:
                ws = await db.testing_workspaces.find_one({
                    "id": membership["workspace_id"], "status": "active",
                }, {"_id": 0})
                if ws:
                    results.append({"id": ws["id"], "name": ws["name"],
                                    "role": membership["role"]})
            return results
        except Exception as exc:
            raise HTTPException(503, "Workspace listing unavailable.") from exc

    @router.post("/workspaces", status_code=201)
    async def new_workspace(data: WorkspaceCreate, user=Depends(current_user)):
        ready()
        try:
            current = await db.testing_memberships.count_documents({
                "user_id": user["id"], "status": "active",
            })
            if current >= 3:
                raise HTTPException(429, "Workspace limit reached.")
            wid = str(uuid.uuid4())
            now = utcnow().isoformat()
            ws = {"id": wid, "name": data.name.strip(), "owner_id": user["id"],
                  "status": "active", "created_at": now}
            await db.testing_workspaces.insert_one(ws)
            await db.testing_memberships.insert_one({
                "id": str(uuid.uuid4()), "user_id": user["id"],
                "workspace_id": wid, "role": "owner", "status": "active",
            })
            return {"id": wid, "name": ws["name"], "role": "owner"}
        except HTTPException:
            raise
        except Exception as exc:
            raise HTTPException(503, "Workspace creation unavailable.") from exc

    @router.get("/domains")
    async def domains(scope=Depends(require_workspace)):
        ready()
        try:
            docs = await db.testing_domains.find({
                "workspace_id": scope["workspace_id"],
            }, {"_id": 0}).to_list(50)
            return [{k: v for k, v in row.items() if k != "verification_token"}
                    | {"challenge_record": "_rasalilabs-verify." + row["hostname"],
                       "challenge_value": "rasalilabs-verification=" + row["verification_token"]}
                    for row in docs]
        except Exception as exc:
            raise HTTPException(503, "Domain listing unavailable.") from exc

    @router.post("/domains", status_code=201)
    async def create_domain(data: DomainRequest, scope=Depends(require_workspace)):
        ready()
        if scope["role"] != "owner":
            raise HTTPException(403, "Workspace owner permission required.")
        host = data.hostname.strip().lower().rstrip(".")
        if not HOST_RE.fullmatch(host):
            raise HTTPException(422, "A fully qualified public hostname is required.")
        now = utcnow().isoformat()
        doc = {
            "id": str(uuid.uuid4()), "workspace_id": scope["workspace_id"],
            "hostname": host, "verification_token": secrets.token_urlsafe(32),
            "verified_at": None, "verification_expires_at": None,
            "created_by": scope["user"]["id"], "created_at": now,
        }
        try:
            await db.testing_domains.insert_one(doc)
        except DuplicateKeyError as exc:
            raise HTTPException(409, "Host already registered in this workspace.") from exc
        except Exception as exc:
            raise HTTPException(503, "Domain registration unavailable.") from exc
        return {
            "id": doc["id"], "hostname": host, "verified": False,
            "challenge_record": "_rasalilabs-verify." + host,
            "challenge_value": "rasalilabs-verification=" + doc["verification_token"],
        }

    @router.post("/domains/{domain_id}/verify")
    async def verify_domain(domain_id: str, scope=Depends(require_workspace)):
        ready()
        if scope["role"] != "owner":
            raise HTTPException(403, "Workspace owner permission required.")
        try:
            doc = await db.testing_domains.find_one({
                "id": domain_id, "workspace_id": scope["workspace_id"],
            }, {"_id": 0})
        except Exception as exc:
            raise HTTPException(503, "Domain lookup unavailable.") from exc
        if doc is None:
            raise HTTPException(404, "Domain not found.")
        required = "rasalilabs-verification=" + doc["verification_token"]
        observed = await dns_lookup("_rasalilabs-verify." + doc["hostname"])
        if required not in observed:
            raise HTTPException(409, "Matching DNS TXT ownership record not found.")
        until = utcnow() + timedelta(days=DOMAIN_VALID_DAYS)
        try:
            await db.testing_domains.update_one({
                "id": domain_id, "workspace_id": scope["workspace_id"],
                "verification_token": doc["verification_token"],
            }, {"$set": {
                "verified_at": utcnow().isoformat(),
                "verification_expires_at": until.isoformat(),
            }})
        except Exception as exc:
            raise HTTPException(503, "Unable to record domain verification.") from exc
        return {"id": domain_id, "verified": True,
                "verification_expires_at": until.isoformat()}

    @router.get("/jobs")
    async def list_jobs(scope=Depends(require_workspace)):
        ready()
        try:
            return await db.testing_jobs.find({
                "workspace_id": scope["workspace_id"],
            }, {"_id": 0}).sort("created_at", -1).to_list(MAX_RECENT_JOBS)
        except Exception as exc:
            raise HTTPException(503, "Scan history unavailable.") from exc

    @router.get("/jobs/{job_id}")
    async def get_job(job_id: str, scope=Depends(require_workspace)):
        ready()
        try:
            doc = await db.testing_jobs.find_one({
                "id": job_id, "workspace_id": scope["workspace_id"],
            }, {"_id": 0})
        except Exception as exc:
            raise HTTPException(503, "Scan lookup unavailable.") from exc
        if not doc:
            raise HTTPException(404, "Scan not found.")
        return doc

    @router.post("/jobs", status_code=202)
    async def enqueue_job(data: JobRequest, scope=Depends(require_workspace)):
        ready()
        if data.test_type != "availability":
            raise HTTPException(422,
                "Customer jobs currently support HTTPS availability only. "
                "Browser and security modes require worker validation.")
        if not data.url.lower().startswith("https://"):
            raise HTTPException(422, "HTTPS is required.")
        try:
            domain = await db.testing_domains.find_one({
                "id": data.domain_id, "workspace_id": scope["workspace_id"],
            }, {"_id": 0})
        except Exception as exc:
            raise HTTPException(503, "Domain lookup unavailable.") from exc
        if not domain:
            raise HTTPException(404, "Domain not found.")
        expiry = domain.get("verification_expires_at")
        if not expiry or expiry <= utcnow().isoformat():
            raise HTTPException(403, "Domain ownership verification is required or has expired.")
        try:
            clean_url, host = await validate_target(data.url.strip(), frozenset({domain["hostname"]}))
        except ValueError as exc:
            raise HTTPException(422, str(exc)) from exc
        if host != domain["hostname"]:
            raise HTTPException(422, "Host must match the verified domain exactly.")
        try:
            recent = await db.testing_jobs.count_documents({
                "workspace_id": scope["workspace_id"], "status": {"$in": ["queued", "running"]},
            })
            if recent >= 3:
                raise HTTPException(429, "At most three outstanding jobs per workspace.")
            now = utcnow().isoformat()
            job = {
                "id": str(uuid.uuid4()), "workspace_id": scope["workspace_id"],
                "requested_by": scope["user"]["id"], "domain_id": domain["id"],
                "url": clean_url, "host": host, "test_type": "availability",
                "status": "queued", "created_at": now, "updated_at": now,
                "lease_until": None, "worker_id": None, "attempts": 0,
                "completed_at": None, "result": None,
            }
            await db.testing_jobs.insert_one(dict(job))
            return job
        except HTTPException:
            raise
        except Exception as exc:
            raise HTTPException(503, "Unable to enqueue scan.") from exc

    return router
