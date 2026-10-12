"""Testing Centre API; disabled unless explicitly enabled by the operator.

Stage 1 is a single-operator development preview. Customer auth, ownership
verification and durable scan workers are required before public launch.
"""
import os
import uuid
import asyncio
from datetime import datetime, timezone
from typing import Optional, Literal

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from .scanner import check_availability
from .browser import browser_audit
from .passive_security import passive_security_audit
from .security import TestingConfig, require_testing_access, validate_target


class ScanCreate(BaseModel):
    url: str = Field(min_length=10, max_length=2048)
    project_id: Optional[str] = Field(default=None, max_length=100)
    test_type: Literal["availability", "browser_smoke", "passive_security"] = "availability"


def timestamp() -> str:
    return datetime.now(timezone.utc).isoformat()


def create_testing_router(db) -> APIRouter:
    router = APIRouter(prefix="/testing", tags=["Testing Centre"])

    def require_persistent_db() -> None:
        if getattr(db, "_is_mock", False):
            raise HTTPException(status_code=503, detail="Persistent scan storage is unavailable.")

    def browser_enabled() -> bool:
        return (os.getenv("TESTING_BROWSER_ENABLED", "false").lower() == "true"
                and os.getenv("TESTING_BROWSER_NETWORK_ISOLATED", "false").lower() == "true")

    def passive_security_enabled() -> bool:
        return (os.getenv("TESTING_PASSIVE_SECURITY_ENABLED", "false").lower() == "true"
                and os.getenv("TESTING_SECURITY_NETWORK_ISOLATED", "false").lower() == "true")

    @router.get("/config")
    async def testing_config(config: TestingConfig = Depends(require_testing_access)):
        return {
            "stage": 3,
            "passive_security_enabled": passive_security_enabled(),
            "browser_enabled": browser_enabled(),
            "enabled": True,
            "allowed_hosts": sorted(config.allowed_hosts),
            "capabilities": ["HTTP availability", "response latency", "scan history"]
            + (["Browser functional smoke", "Desktop/tablet/mobile checks", "Screenshots", "Navigation timing"] if browser_enabled() else [])
            + (["Passive TLS, HTTP security headers, cookie and API response diagnostics"] if passive_security_enabled() else []),
            "not_included": ["penetration testing", "active vulnerability scanning", "Authenticated user journeys", "Full Lighthouse score"],
        }

    @router.get("/scans")
    async def list_scans(config: TestingConfig = Depends(require_testing_access)):
        require_persistent_db()
        try:
            docs = await db.testing_scans.find({}, {"_id": 0}).sort("created_at", -1).to_list(50)
            return docs
        except Exception as exc:
            raise HTTPException(status_code=503, detail="Unable to load scan history.") from exc

    @router.get("/scans/{scan_id}")
    async def get_scan(scan_id: str, config: TestingConfig = Depends(require_testing_access)):
        require_persistent_db()
        try:
            doc = await db.testing_scans.find_one({"id": scan_id}, {"_id": 0})
        except Exception as exc:
            raise HTTPException(status_code=503, detail="Unable to load scan.") from exc
        if not doc:
            raise HTTPException(status_code=404, detail="Scan not found.")
        return doc

    @router.get("/evidence/{evidence_id}")
    async def get_evidence(evidence_id: str, config: TestingConfig = Depends(require_testing_access)):
        require_persistent_db()
        try:
            doc = await db.testing_evidence.find_one({"id": evidence_id}, {"_id": 0})
        except Exception as exc:
            raise HTTPException(status_code=503, detail="Unable to load evidence.") from exc
        if not doc:
            raise HTTPException(status_code=404, detail="Evidence not found.")
        return {"id": evidence_id, "viewport": doc["viewport"],
                "data_uri": "data:" + doc["media_type"] + ";base64," + doc["content_b64"]}

    @router.post("/scans", status_code=201)
    async def create_scan(
        payload: ScanCreate, config: TestingConfig = Depends(require_testing_access)
    ):
        require_persistent_db()
        try:
            clean_url, host = await validate_target(payload.url.strip(), config.allowed_hosts)
        except ValueError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc

        if payload.test_type == "passive_security":
            if not passive_security_enabled():
                raise HTTPException(status_code=503,
                    detail="Passive security checks require an enabled, network-isolated development worker.")
            if not clean_url.startswith("https://"):
                raise HTTPException(status_code=422, detail="Passive security audits require HTTPS.")

        if payload.test_type == "browser_smoke":
            if not browser_enabled():
                raise HTTPException(status_code=503,
                    detail="Browser scans require an enabled, network-isolated development worker.")
            if not clean_url.startswith("https://"):
                raise HTTPException(status_code=422, detail="Browser scans require HTTPS.")

        if payload.project_id:
            try:
                project = await db.projects.find_one({"id": payload.project_id}, {"_id": 1})
            except Exception as exc:
                raise HTTPException(status_code=503, detail="Unable to validate project.") from exc
            if not project:
                raise HTTPException(status_code=404, detail="Project not found.")

        now = timestamp()
        doc = {
            "id": str(uuid.uuid4()),
            "project_id": payload.project_id,
            "url": clean_url,
            "host": host,
            "status": "running",
            "test_type": payload.test_type,
            "result": None,
            "created_at": now,
            "updated_at": now,
            "finished_at": None,
        }
        try:
            await db.testing_scans.insert_one(dict(doc))
        except Exception as exc:
            raise HTTPException(status_code=503, detail="Unable to persist scan.") from exc

        # Stage 2 preview still uses a bounded in-request scan. Do not deploy
        # as a public service or serverless runtime; use a dedicated isolated
        # development worker with restricted network egress.
        try:
            if payload.test_type == "browser_smoke":
                result = await asyncio.wait_for(browser_audit(clean_url, host), timeout=65)
                evidence = result.pop("screenshots", [])
                if evidence:
                    for item in evidence:
                        await db.testing_evidence.insert_one({**item, "scan_id": doc["id"]})
                # Never duplicate base64 bytes in the scan history document.
                result["screenshots"] = [
                    {"id": item["id"], "viewport": item["viewport"], "media_type": item["media_type"]}
                    for item in evidence
                ]
            elif payload.test_type == "passive_security":
                result = await asyncio.wait_for(passive_security_audit(clean_url, host), timeout=15)
            else:
                result = await check_availability(clean_url)
        except Exception as exc:
            result = {
                "outcome": "fail", "reachable": False,
                "error": type(exc).__name__,
                "checks": [], "limitations": ["Scan execution failed; no test coverage confirmed."],
            }
        doc.update({
            "status": "failed" if result["outcome"] == "fail" else "completed",
            "result": result,
            "updated_at": timestamp(),
            "finished_at": timestamp(),
        })
        try:
            await db.testing_scans.update_one(
                {"id": doc["id"]},
                {"$set": {
                    "status": doc["status"],
                    "result": result,
                    "updated_at": doc["updated_at"],
                    "finished_at": doc["finished_at"],
                }},
            )
        except Exception as exc:
            raise HTTPException(status_code=503, detail="Scan ran but results could not be saved.") from exc
        return doc

    return router
