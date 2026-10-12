"""Stage 5: bounded evidence-to-repair cases and honest regression comparison.

No finding is declared "fixed" from absence alone: scans are observations,
not deployment attestations. Baseline/retest must have comparable coverage.
"""
from datetime import datetime, timezone
import re
import uuid

OWNERS = {
    "runtime": "frontend",
    "functional": "frontend",
    "responsive": "frontend",
    "usability": "frontend",
    "network": "backend",
    "navigation": "backend",
    "performance": "developer",
    "security_configuration": "devops",
    "evidence": "devops",
}
VALID_TESTS = {"browser_smoke", "passive_security"}
SEVERITIES = {"high", "medium", "low", "info"}


def _text(value, limit=160):
    return re.sub(r"[\x00-\x1f\x7f]", " ", value).strip()[:limit] if isinstance(value, str) else ""


def _successful_scan(scan):
    result = scan.get("result") or {}
    return scan.get("status") == "completed" and result.get("outcome") in ("pass", "warning")


def _observation_key(item, test_type):
    """IDs are ephemeral UUIDs; stable code or category/title/viewport identifies issue."""
    if test_type == "passive_security":
        code = _text(item.get("code"), 60)
        return ("code", code) if code else None
    category = _text(item.get("category"), 50)
    title = _text(item.get("title"), 140)
    viewport = _text(item.get("viewport"), 40).lower()
    return ("browser", category, title, viewport) if category and title else None


def _viewport_coverage(scan):
    result = scan.get("result") or {}
    views = result.get("viewports")
    if not isinstance(views, list):
        return None
    return {
        item.get("name")
        for item in views
        if isinstance(item, dict)
        and item.get("name") in ("desktop", "tablet", "mobile")
        and isinstance(item.get("metrics"), dict)
        and item.get("metrics")
        and isinstance(item.get("http_status"), int)
        and 200 <= item["http_status"] < 400
    }


def comparable(scan, test_type, source_coverage):
    """Fail closed on incomplete browser frames, TLS failures and missing test scopes."""
    if not _successful_scan(scan) or scan.get("test_type") != test_type:
        return False
    result = scan["result"]
    if test_type == "browser_smoke":
        # Require all three usable viewport navigations, regardless of the issue
        # viewport. Block misleading 'not reproduced' after partial failures.
        required = {"desktop", "tablet", "mobile"}
        return _viewport_coverage(scan) == required and source_coverage == sorted(required) and (
            result.get("summary") or {}
        ).get("viewports_completed") == 3
    if test_type == "passive_security":
        coverage = result.get("coverage") or {}
        tls = result.get("tls") or {}
        return (
            bool(tls.get("verified"))
            and coverage.get("requests_sent") == 1
            and coverage.get("response_body_read") is False
            and coverage.get("method") == "pinned_public_ip_https_head"
            and result.get("http_status") == source_coverage.get("http_status")
            and isinstance(result.get("http_status"), int)
            and 200 <= result["http_status"] < 400
        )
    return False


def build_repair_case(scan, finding_id):
    """Create a proposal tied to a REAL finding in a complete Stage 2/3 scan."""
    if not _successful_scan(scan) or scan.get("test_type") not in VALID_TESTS:
        raise ValueError("A completed browser or passive-security scan is required.")
    result = scan["result"]
    items = result.get("findings") or []
    if not isinstance(items, list):
        raise ValueError("Scan has no usable finding list.")
    matches = [x for x in items[:60] if isinstance(x, dict) and x.get("id") == finding_id]
    if len(matches) != 1:
        raise ValueError("Select one unique measured finding from this scan.")
    item = matches[0]
    key = _observation_key(item, scan["test_type"])
    if not key or item.get("severity") not in SEVERITIES:
        raise ValueError("Finding lacks a stable comparison key or severity.")
    test_type = scan["test_type"]
    if test_type == "browser_smoke":
        base_coverage = sorted(_viewport_coverage(scan) or [])
    else:
        base_coverage = {"http_status": result.get("http_status")}
    owner = OWNERS.get(item.get("category"), "developer")
    return {
        "id": str(uuid.uuid4()),
        "source_scan_id": scan["id"],
        "source_finding_id": finding_id,
        "url": scan["url"],
        "host": scan["host"],
        "test_type": test_type,
        "issue_key": list(key),
        "finding": {
            "title": _text(item.get("title"), 140),
            "category": _text(item.get("category"), 50),
            "severity": item["severity"],
            "viewport": _text(item.get("viewport"), 40),
            "observed": _text(item.get("evidence") or item.get("detail"), 240),
            "code": _text(item.get("code"), 60),
        },
        "proposed_action": _text(item.get("recommendation"), 300) or "Investigate and reproduce the recorded observation.",
        "assigned_role": owner,   # suggested, not dispatched
        "handoff_state": "suggested_not_assigned",
        "status": "proposed",
        "pr": None,
        "latest_verification": None,
        "verification_history": [],
        "baseline_coverage": base_coverage,
        "release_readiness": "not_verified",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "updated_at": datetime.now(timezone.utc).isoformat(),
    }


def assess_retest(case, original, latest):
    """Compare a new actually-executed scan, NOT an LLM assertion."""
    if latest.get("id") in (case.get("source_scan_id"), None):
        raise ValueError("Retest must be a different scan record.")
    if latest.get("url") != case.get("url") or latest.get("test_type") != case.get("test_type"):
        raise ValueError("Retest URL and scan profile must exactly match the original.")
    if original.get("id") != case.get("source_scan_id"):
        raise ValueError("Original scan does not match repair evidence.")
    if latest.get("created_at", "") <= original.get("created_at", ""):
        raise ValueError("Retest must be newer than the original scan.")
    origin_key = tuple(case["issue_key"])
    source_coverage = case.get("baseline_coverage")
    source_ok = comparable(original, case["test_type"], source_coverage)
    latest_ok = comparable(latest, case["test_type"], source_coverage)
    observation = {
        "id": str(uuid.uuid4()),
        "source_scan_id": original["id"],
        "retest_scan_id": latest["id"],
        "created_at": datetime.now(timezone.utc).isoformat(),
        "result": "inconclusive",
        "reason": "Comparable scan coverage was not confirmed.",
        "release_readiness": "not_verified",
        "fix_verified": False,
    }
    if not source_ok or not latest_ok:
        return observation
    findings = (latest.get("result") or {}).get("findings")
    if not isinstance(findings, list) or len(findings) > 60:
        observation["reason"] = "Retest finding inventory is missing or truncated."
        return observation
    if any(_observation_key(x, case["test_type"]) == origin_key for x in findings if isinstance(x, dict)):
        observation.update(result="still_observed",
                           reason="The original finding signature is present in the comparable retest.")
        return observation
    observation.update(result="not_observed_in_retest",
                       reason="This finding signature was not seen in a comparable retest. "
                              "That does not prove code was repaired or certify the app.")
    return observation


def repair_prompt(case):
    """Copyable prompt for a human-controlled coding agent; no access to credentials."""
    return (
        f"Investigate the following OBSERVED {case['test_type']} finding. "
        f"Finding reference {case['source_scan_id']}/{case['source_finding_id']}. "
        f"Category: {case['finding']['category']}; title: {case['finding']['title']}; "
        f"viewport: {case['finding']['viewport'] or 'n/a'}. "
        f"Observed: {case['finding']['observed']}. "
        f"Suggested investigation: {case['proposed_action']}. "
        "Locate the relevant code in the explicitly authorized repository. "
        "Propose a minimal patch and regression test on a feature branch. "
        "Do not touch secrets or deploy/merge; request review before changing code. "
        "Do not claim a fix until a comparable live scan verifies the observation."
    )
