"""Testing Centre API; disabled unless explicitly enabled by the operator.

Stage 1 is a single-operator development preview. Customer auth, ownership
verification and durable scan workers are required before public launch.
"""
import os
import uuid
import asyncio
import secrets
from datetime import datetime, timezone
from typing import Optional, Literal

from fastapi import APIRouter, Depends, HTTPException, Header
from pydantic import BaseModel, Field

from .agents import SPECIALISTS, build_review, enrich_review
from .repairs import build_repair_case, assess_retest, repair_prompt
from .github_drafts import (
    GitHubDraftPublisher, GitHubPublishError,
    publisher_configured, validate_publishing_input,
)

from .scanner import check_availability
from .browser import browser_audit
from .passive_security import passive_security_audit
from .security import TestingConfig, get_config, require_testing_access, validate_target


class RepairCreate(BaseModel):
    finding_id: str = Field(min_length=1, max_length=90)


class RepairCompare(BaseModel):
    retest_scan_id: str = Field(min_length=1, max_length=90)


class PublishRepair(BaseModel):
    repo: str = Field(min_length=3, max_length=150)
    file_path: str = Field(min_length=2, max_length=250)
    expected_blob_sha: str = Field(min_length=40, max_length=40)
    new_source: str = Field(min_length=1, max_length=48000)
    approval_phrase: str


class ReviewCreate(BaseModel):
    use_ai: bool = False


class ScanCreate(BaseModel):
    url: str = Field(min_length=10, max_length=2048)
    project_id: Optional[str] = Field(default=None, max_length=100)
    test_type: Literal["availability", "browser_smoke", "passive_security"] = "availability"


def timestamp() -> str:
    return datetime.now(timezone.utc).isoformat()


def create_testing_router(db, agent_provider=None, agent_model_name=None) -> APIRouter:
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

    def agent_llm_available() -> bool:
        return (os.getenv("TESTING_AGENT_AI_ENABLED", "false").lower() == "true"
                and os.getenv("TESTING_AGENT_AI_DISCLOSURE_ACK", "false").lower() == "true"
                and agent_provider is not None)

    def repair_publisher_enabled() -> bool:
        return publisher_configured()

    @router.get("/status")
    async def testing_status():
        """No token needed: honest setup state, never credentials or hostnames.

        This does not perform scanning, DNS lookups or external API calls.
        Browser/security execution and per-host scopes remain private to
        the operator-authorized /config endpoint.
        """
        cfg = get_config()
        if not cfg.enabled:
            mode = "disabled"
        elif not cfg.configured:
            mode = "configuration_required"
        elif getattr(db, "_is_mock", False):
            mode = "storage_unavailable"
        else:
            mode = "operator_configured"
        return {
            "mode": mode,
            "scan_execution_enabled": mode == "operator_configured",
            "authentication": "separate_testing_token",
            "availability_method": "tls_pinned_https_head",
            "public_signup_enabled": False,
            "worker_isolation_verified": False,
            "notice": (
                "An enabled operator preview is not a production-isolated "
                "worker or security certification."
            ),
        }

    @router.get("/config")
    async def testing_config(config: TestingConfig = Depends(require_testing_access)):
        return {
            "stage": 5,
            "repair_pr_publisher_enabled": repair_publisher_enabled(),
            "repair_allowlisted_repo": os.getenv("TESTING_REPAIR_REPO", "") if repair_publisher_enabled() else None,
            "review_agents": [agent["role"] for agent in SPECIALISTS],
            "agent_ai_enabled": agent_llm_available(),
            "passive_security_enabled": passive_security_enabled(),
            "browser_enabled": browser_enabled(),
            "enabled": True,
            "allowed_hosts": sorted(config.allowed_hosts),
            "capabilities": ["HTTP availability", "response latency", "scan history"]
            + (["Browser functional smoke", "Desktop/tablet/mobile checks", "Screenshots", "Navigation timing"] if browser_enabled() else [])
            + (["Passive TLS, HTTP security headers, cookie and API response diagnostics"] if passive_security_enabled() else []),
            "not_included": ["penetration testing", "active vulnerability scanning", "Authenticated user journeys", "Full Lighthouse score"],
        }

    @router.get("/agents")
    async def get_testing_agents(config: TestingConfig = Depends(require_testing_access)):
        return list(SPECIALISTS)

    @router.get("/repairs")
    async def list_repairs(config: TestingConfig = Depends(require_testing_access)):
        require_persistent_db()
        try:
            return await db.testing_repairs.find({}, {"_id": 0}).sort("created_at", -1).to_list(50)
        except Exception as exc:
            raise HTTPException(status_code=503, detail="Unable to list repair cases.") from exc

    @router.get("/repairs/{repair_id}")
    async def get_repair(repair_id: str, config: TestingConfig = Depends(require_testing_access)):
        require_persistent_db()
        try:
            case = await db.testing_repairs.find_one({"id": repair_id}, {"_id": 0})
        except Exception as exc:
            raise HTTPException(status_code=503, detail="Unable to retrieve repair case.") from exc
        if case is None:
            raise HTTPException(status_code=404, detail="Repair case not found.")
        return case

    @router.post("/scans/{scan_id}/repairs", status_code=201)
    async def create_repair(scan_id: str, payload: RepairCreate,
                            config: TestingConfig = Depends(require_testing_access)):
        require_persistent_db()
        try:
            scan = await db.testing_scans.find_one({"id": scan_id}, {"_id": 0})
        except Exception as exc:
            raise HTTPException(status_code=503, detail="Unable to retrieve source scan.") from exc
        if scan is None:
            raise HTTPException(status_code=404, detail="Source scan not found.")
        try:
            case = build_repair_case(scan, payload.finding_id)
        except ValueError as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc
        case["coding_agent_prompt"] = repair_prompt(case)
        try:
            await db.testing_repairs.insert_one(dict(case))
        except Exception as exc:
            raise HTTPException(status_code=503, detail="Unable to save repair case.") from exc
        return case

    @router.post("/repairs/{repair_id}/verify")
    async def verify_repair(repair_id: str, payload: RepairCompare,
                            config: TestingConfig = Depends(require_testing_access)):
        require_persistent_db()
        try:
            case = await db.testing_repairs.find_one({"id": repair_id}, {"_id": 0})
            if case is None:
                raise HTTPException(status_code=404, detail="Repair case not found.")
            original = await db.testing_scans.find_one({"id": case["source_scan_id"]}, {"_id": 0})
            latest = await db.testing_scans.find_one({"id": payload.retest_scan_id}, {"_id": 0})
        except HTTPException:
            raise
        except Exception as exc:
            raise HTTPException(status_code=503, detail="Unable to load comparison scans.") from exc
        if not original or not latest:
            raise HTTPException(status_code=404, detail="A comparison scan was not found.")
        try:
            check = assess_retest(case, original, latest)
        except ValueError as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc
        # Append-only attempt evidence. This does NOT mark a patch as fixed.
        try:
            await db.testing_repairs.update_one(
                {"id": repair_id},
                {"$push": {"verification_history": check},
                 "$set": {"latest_verification": check, "updated_at": timestamp()}},
            )
        except Exception as exc:
            raise HTTPException(status_code=503, detail="Unable to persist comparison.") from exc
        return check

    @router.post("/repairs/{repair_id}/publish-pr", status_code=201)
    async def publish_repair_pr(repair_id: str, payload: PublishRepair,
                                x_repair_approval_token: str = Header(default=""),
                                config: TestingConfig = Depends(require_testing_access)):
        require_persistent_db()
        if not repair_publisher_enabled():
            raise HTTPException(status_code=503, detail="GitHub repair publishing is disabled.")
        if not secrets.compare_digest(
            x_repair_approval_token,
            os.getenv("TESTING_REPAIR_APPROVAL_TOKEN", ""),
        ):
            raise HTTPException(status_code=403, detail="Separate repair approval required.")
        if payload.approval_phrase != "CREATE DRAFT PR":
            raise HTTPException(status_code=422, detail="Explicit approval phrase required.")
        try:
            validate_publishing_input(payload.repo, payload.file_path,
                                      payload.expected_blob_sha, payload.new_source)
        except ValueError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc
        try:
            case = await db.testing_repairs.find_one({"id": repair_id}, {"_id": 0})
        except Exception as exc:
            raise HTTPException(status_code=503, detail="Unable to load repair case.") from exc
        if not case:
            raise HTTPException(status_code=404, detail="Repair case not found.")
        if case["status"] != "proposed":
            raise HTTPException(status_code=409, detail="Repair is not awaiting first publication.")
        # Atomic single-use transition; stop parallel PR submissions.
        try:
            updated = await db.testing_repairs.update_one(
                {"id": repair_id, "status": "proposed"},
                {"$set": {"status": "publishing", "updated_at": timestamp()}},
            )
        except Exception as exc:
            raise HTTPException(status_code=503, detail="Unable to reserve publication.") from exc
        if getattr(updated, "modified_count", 0) != 1:
            raise HTTPException(status_code=409, detail="Repair publication already started.")
        case["status"] = "publishing"
        publisher = GitHubDraftPublisher(os.getenv("TESTING_GITHUB_TOKEN", ""))
        try:
            pr = await publisher.publish(case, payload.repo, payload.file_path,
                                         payload.expected_blob_sha, payload.new_source)
        except Exception as exc:
            # Once a branch might exist, never retry automatically or hide it.
            try:
                await db.testing_repairs.update_one(
                    {"id": repair_id, "status": "publishing"},
                    {"$set": {"status": "publish_failed_reconcile",
                              "publish_error": type(exc).__name__,
                              "updated_at": timestamp()}},
                )
            except Exception:
                pass
            raise HTTPException(status_code=502,
                                detail="Draft PR publication failed. Reconcile GitHub state manually before retry.") from exc
        try:
            await db.testing_repairs.update_one(
                {"id": repair_id, "status": "publishing"},
                {"$set": {"status": "draft_pr_opened", "pr": pr,
                          "updated_at": timestamp()}},
            )
        except Exception as exc:
            raise HTTPException(status_code=503,
                                detail="GitHub draft may exist but local state was not saved; manually reconcile.") from exc
        return {"repair_id": repair_id, "pr": pr, "status": "draft_pr_opened"}

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

    @router.get("/scans/{scan_id}/reviews")
    async def scan_reviews(scan_id: str, config: TestingConfig = Depends(require_testing_access)):
        require_persistent_db()
        try:
            scan = await db.testing_scans.find_one({"id": scan_id}, {"_id": 0})
            if not scan:
                raise HTTPException(status_code=404, detail="Scan not found.")
            docs = await db.testing_reviews.find({"scan_id": scan_id}, {"_id": 0}).sort("created_at", -1).to_list(10)
            return docs
        except HTTPException:
            raise
        except Exception as exc:
            raise HTTPException(status_code=503, detail="Unable to load specialist reviews.") from exc

    @router.post("/scans/{scan_id}/reviews", status_code=201)
    async def create_scan_review(scan_id: str, payload: ReviewCreate,
                                 config: TestingConfig = Depends(require_testing_access)):
        require_persistent_db()
        if payload.use_ai and not agent_llm_available():
            raise HTTPException(status_code=503,
                                detail="Opt-in AI analysis is disabled or not configured.")
        try:
            scan = await db.testing_scans.find_one({"id": scan_id}, {"_id": 0})
        except Exception as exc:
            raise HTTPException(status_code=503, detail="Unable to load source scan.") from exc
        if not scan:
            raise HTTPException(status_code=404, detail="Scan not found.")
        try:
            review = build_review(scan)
        except ValueError as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc

        if payload.use_ai:
            review = await enrich_review(review, provider=agent_provider,
                                         model_name=agent_model_name or "configured model")
        try:
            # Reports are derived only from existing scans; no HTTP requests or
            # agent execution in this route, unless explicitly opted into AI.
            await db.testing_reviews.insert_one(dict(review))
        except Exception as exc:
            raise HTTPException(status_code=503, detail="Unable to save specialist review.") from exc
        return review

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

        if payload.test_type == "availability" and not clean_url.startswith("https://"):
            raise HTTPException(status_code=422, detail="Availability checks require HTTPS.")

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
