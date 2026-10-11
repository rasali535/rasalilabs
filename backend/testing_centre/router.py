"""Testing Centre API; disabled unless explicitly enabled by the operator.

Stage 1 is a single-operator development preview. Customer auth, ownership
verification and durable scan workers are required before public launch.
"""
import uuid
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from .scanner import check_availability
from .security import TestingConfig, require_testing_access, validate_target


class ScanCreate(BaseModel):
    url: str = Field(min_length=10, max_length=2048)
    project_id: Optional[str] = Field(default=None, max_length=100)


def timestamp() -> str:
    return datetime.now(timezone.utc).isoformat()


def create_testing_router(db) -> APIRouter:
    router = APIRouter(prefix="/testing", tags=["Testing Centre"])

    def require_persistent_db() -> None:
        if getattr(db, "_is_mock", False):
            raise HTTPException(status_code=503, detail="Persistent scan storage is unavailable.")

    @router.get("/config")
    async def testing_config(config: TestingConfig = Depends(require_testing_access)):
        return {
            "stage": 1,
            "enabled": True,
            "allowed_hosts": sorted(config.allowed_hosts),
            "capabilities": ["HTTP availability", "response latency", "scan history"],
            "not_included": ["penetration testing", "vulnerability scan", "browser functional tests"],
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

    @router.post("/scans", status_code=201)
    async def create_scan(
        payload: ScanCreate, config: TestingConfig = Depends(require_testing_access)
    ):
        require_persistent_db()
        try:
            clean_url, host = await validate_target(payload.url.strip(), config.allowed_hosts)
        except ValueError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc

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
            "test_type": "availability",
            "result": None,
            "created_at": now,
            "updated_at": now,
            "finished_at": None,
        }
        try:
            await db.testing_scans.insert_one(dict(doc))
        except Exception as exc:
            raise HTTPException(status_code=503, detail="Unable to persist scan.") from exc

        # Bounded synchronous probe (not a background job). Stage 2 will
        # introduce an isolated durable worker with strict egress controls.
        result = await check_availability(clean_url)
        doc.update({
            "status": "completed" if result["reachable"] else "failed",
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
