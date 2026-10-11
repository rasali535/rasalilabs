"""Bounded browser QA for operator-approved HTTPS applications.

DEV/STAGING ONLY. Run this module behind restricted network egress, under an
unprivileged worker user. Browser route interception and DNS pinning are
defense-in-depth, not replacements for network-level isolation.
"""
import asyncio
import base64
import ipaddress
import re
import socket
import time
import uuid
from datetime import datetime, timezone
from urllib.parse import urlsplit

from .security import HOST_RE

VIEWPORTS = (
    {"name": "desktop", "width": 1366, "height": 768},
    {"name": "tablet", "width": 820, "height": 1180},
    {"name": "mobile", "width": 390, "height": 844},
)
MAX_REQUESTS = 120
MAX_FINDINGS = 60
MAX_SCREENSHOT_BYTES = 230_000
MAX_DIAGNOSTICS = 14
BROWSER_TIMEOUT_MS = 14_000
BROWSER_SEMAPHORE = asyncio.Semaphore(1)

DOM_PROBE = r"""() => {
  const nav = performance.getEntriesByType('navigation')[0];
  const paint = performance.getEntriesByType('paint')
    .find(entry => entry.name === 'first-contentful-paint');
  const links = Array.from(document.querySelectorAll('a[href]'));
  const images = Array.from(document.images);
  const wide = document.documentElement.scrollWidth > innerWidth + 3;
  const badImages = images.filter(el => !el.complete || el.naturalWidth === 0);
  const invalidAnchors = links.filter(el => {
    const href = (el.getAttribute('href') || '').trim();
    return href === '#' || href === '' || /^javascript:/i.test(href);
  });
  return {
    page_title: (document.title || '').slice(0, 140),
    headings: document.querySelectorAll('h1').length,
    body_text_length: (document.body?.innerText || '').trim().length,
    link_count: links.length,
    broken_images: badImages.length,
    invalid_anchors: invalidAnchors.length,
    horizontal_overflow: wide,
    document_width: document.documentElement.scrollWidth,
    viewport_width: innerWidth,
    navigation_ms: nav ? Math.round(nav.duration) : null,
    dom_content_loaded_ms: nav ? Math.round(nav.domContentLoadedEventEnd) : null,
    fcp_ms: paint ? Math.round(paint.startTime) : null
  };
}"""


def clean_diagnostic(text: str) -> str:
    """Redact URL query strings and truncate diagnostics; never record bodies."""
    text = str(text or "")
    text = re.sub(r'https?://[^\s\'"<>]+', lambda m: _redact_url(m.group(0)), text)
    return text[:260]


def _redact_url(url: str) -> str:
    try:
        parts = urlsplit(url)
        return f"{parts.scheme}://{parts.hostname or 'unknown'}{parts.path[:120]}"
    except ValueError:
        return "[invalid URL]"


def finding(category, severity, title, detail, recommendation, viewport=None):
    return {
        "id": str(uuid.uuid4()),
        "category": category,
        "severity": severity,
        "title": title,
        "detail": clean_diagnostic(detail),
        "recommendation": recommendation,
        "viewport": viewport,
        "verified_by": "browser_observation",
    }


def interpret_dom(probe: dict, viewport: str) -> list[dict]:
    findings = []
    if probe.get("body_text_length", 0) == 0:
        findings.append(finding("functional", "high", "Empty visible page",
            "No readable body text was rendered.", "Check client-side rendering and API errors.", viewport))
    if probe.get("broken_images", 0):
        findings.append(finding("functional", "medium", "Broken images",
            f"{probe['broken_images']} visible image element(s) did not load.",
            "Check image URLs, asset hosting, permissions and browser network errors.", viewport))
    if probe.get("invalid_anchors", 0):
        findings.append(finding("functional", "low", "Placeholder navigation links",
            f"{probe['invalid_anchors']} anchor(s) use empty, # or javascript: URLs.",
            "Replace placeholder links with valid destinations or buttons.", viewport))
    if probe.get("horizontal_overflow"):
        findings.append(finding("responsive", "medium", "Horizontal overflow",
            f"Document width {probe.get('document_width')}px exceeds the {probe.get('viewport_width')}px viewport.",
            "Inspect fixed widths, overflowing containers and responsive styles.", viewport))
    if not probe.get("page_title"):
        findings.append(finding("usability", "low", "Page title missing",
            "No page title was detected.", "Add a descriptive HTML title.", viewport))
    duration = probe.get("navigation_ms")
    if isinstance(duration, (int, float)) and duration > 5000:
        findings.append(finding("performance", "medium", "Slow navigation timing",
            f"Navigation timing: {round(duration)} ms.",
            "Profile resource loading, server response and frontend JavaScript.", viewport))
    return findings


async def resolve_public_ipv4(host: str, resolver=None) -> str:
    """Resolve + choose globally routed IPv4 for Chromium DNS pinning."""
    if not HOST_RE.fullmatch(host):
        raise ValueError("Invalid browser target hostname.")
    getter = resolver or asyncio.get_running_loop().getaddrinfo
    infos = await getter(host, 443, family=socket.AF_INET, type=socket.SOCK_STREAM)
    ips = [ipaddress.ip_address(row[4][0]) for row in infos]
    if not ips or not all(ip.is_global for ip in ips):
        raise ValueError("Browser target DNS contains a private or non-public IPv4 address.")
    return str(ips[0])


async def browser_audit(url: str, host: str, *, resolver=None, playwright_factory=None):
    """Scan a single approved origin in 3 viewports; no clicking or login."""
    parsed = urlsplit(url)
    if parsed.scheme != "https" or parsed.hostname != host or parsed.port not in (None, 443):
        raise ValueError("Browser audit requires an approved HTTPS origin.")
    ip = await resolve_public_ipv4(host, resolver=resolver)
    if playwright_factory is None:
        try:
            from playwright.async_api import async_playwright
        except ImportError as exc:
            raise RuntimeError("Playwright must be installed in the isolated browser worker.") from exc
        playwright_factory = async_playwright

    report = {
        "audit_type": "browser_smoke",
        "outcome": "pass",
        "findings": [],
        "viewports": [],
        "tested_checks": [
            "Page navigation and HTML response",
            "JavaScript runtime errors and browser console errors",
            "Failed same-origin network requests",
            "Image and navigation element checks",
            "Responsive horizontal overflow",
            "Navigation and first-contentful-paint timing",
            "Desktop, tablet and mobile screenshots",
        ],
        "not_tested": [
            "Penetration testing", "Authentication and payments",
            "Full user workflows", "Third-party service availability",
            "Lighthouse lab score", "All application pages",
        ],
        "screenshots": [],
        "third_party_requests_blocked": 0,
        "elapsed_ms": None,
        "completed_at": None,
    }
    start = time.monotonic()

    async with BROWSER_SEMAPHORE:
        async with playwright_factory() as pw:
            browser = await pw.chromium.launch(
                headless=True,
                args=["--no-proxy-server", f"--host-resolver-rules=MAP {host} {ip}"],
            )
            try:
                for viewport in VIEWPORTS:
                    context = await browser.new_context(
                        viewport={"width": viewport["width"], "height": viewport["height"]},
                        device_scale_factor=1,
                        service_workers="block",
                        accept_downloads=False,
                        ignore_https_errors=False,
                    )
                    page = await context.new_page()
                    issues = []
                    request_count = 0
                    seen_errors = 0

                    async def guard(route):
                        nonlocal request_count, seen_errors
                        request_count += 1
                        req = route.request
                        try:
                            target = urlsplit(req.url)
                            permitted = (target.scheme == "https" and target.hostname == host
                                         and target.port in (None, 443) and request_count <= MAX_REQUESTS)
                        except ValueError:
                            permitted = False
                        if not permitted:
                            report["third_party_requests_blocked"] += 1
                            await route.abort()
                        else:
                            await route.continue_()

                    await context.route("**/*", guard)

                    def page_error(exc):
                        nonlocal seen_errors
                        if seen_errors < MAX_DIAGNOSTICS:
                            issues.append(finding("runtime", "high", "Uncaught JavaScript exception",
                                clean_diagnostic(str(exc)),
                                "Inspect the browser stack trace and failing component.", viewport["name"]))
                        seen_errors += 1

                    def console_message(message):
                        nonlocal seen_errors
                        if message.type == "error" and seen_errors < MAX_DIAGNOSTICS:
                            issues.append(finding("runtime", "medium", "Browser console error",
                                clean_diagnostic(message.text),
                                "Review browser console diagnostics and the originating asset.", viewport["name"]))
                            seen_errors += 1

                    def request_failed(request):
                        nonlocal seen_errors
                        if seen_errors < MAX_DIAGNOSTICS and urlsplit(request.url).hostname == host:
                            issues.append(finding("network", "medium", "Failed same-origin request",
                                clean_diagnostic(request.url),
                                "Inspect the failing request in developer tools.", viewport["name"]))
                            seen_errors += 1

                    def response_error(response):
                        nonlocal seen_errors
                        if response.status >= 400 and seen_errors < MAX_DIAGNOSTICS:
                            issues.append(finding("network", "medium" if response.status < 500 else "high",
                                "HTTP error response",
                                f"HTTP {response.status}: {clean_diagnostic(response.url)}",
                                "Check the failing resource and server logs.", viewport["name"]))
                            seen_errors += 1

                    page.on("pageerror", page_error)
                    page.on("console", console_message)
                    page.on("requestfailed", request_failed)
                    page.on("response", response_error)

                    result = {
                        "name": viewport["name"],
                        "width": viewport["width"],
                        "height": viewport["height"],
                        "http_status": None,
                        "metrics": {},
                        "evidence_id": None,
                    }
                    try:
                        response = await page.goto(url, wait_until="domcontentloaded",
                                                   timeout=BROWSER_TIMEOUT_MS)
                        result["http_status"] = response.status if response else None
                        try:
                            await page.wait_for_load_state("load", timeout=3500)
                        except Exception:
                            pass
                        await page.wait_for_timeout(400)
                        if page.url and urlsplit(page.url).hostname != host:
                            issues.append(finding("navigation", "high", "Unexpected navigation",
                                "Navigation left the approved hostname and was blocked.",
                                "Review redirects and application navigation.", viewport["name"]))
                        probe = await page.evaluate(DOM_PROBE)
                        result["metrics"] = probe
                        issues.extend(interpret_dom(probe, viewport["name"]))
                        if result["http_status"] and result["http_status"] >= 400:
                            issues.append(finding("navigation", "high", "Page returned HTTP error",
                                f"HTTP {result['http_status']}", "Review page routing and server logs.", viewport["name"]))
                        screenshot = await page.screenshot(type="jpeg", quality=42,
                                                           animations="disabled", full_page=False,
                                                           timeout=3500)
                        if len(screenshot) <= MAX_SCREENSHOT_BYTES:
                            evidence_id = str(uuid.uuid4())
                            report["screenshots"].append({
                                "id": evidence_id, "viewport": viewport["name"],
                                "media_type": "image/jpeg",
                                "content_b64": base64.b64encode(screenshot).decode("ascii"),
                                "created_at": datetime.now(timezone.utc).isoformat(),
                            })
                            result["evidence_id"] = evidence_id
                        else:
                            issues.append(finding("evidence", "low", "Screenshot exceeded size limit",
                                f"{len(screenshot)} bytes exceeded the evidence cap.",
                                "Collect a smaller viewport screenshot in a dedicated worker.", viewport["name"]))
                    except Exception as exc:
                        issues.append(finding("navigation", "high", "Browser navigation failed",
                            f"{type(exc).__name__}: {clean_diagnostic(str(exc))}",
                            "Verify the target is reachable from the isolated browser worker.", viewport["name"]))
                    finally:
                        report["viewports"].append(result)
                        report["findings"].extend(issues[:MAX_DIAGNOSTICS])
                        await context.close()
            finally:
                await browser.close()

    report["findings"] = report["findings"][:MAX_FINDINGS]
    report["elapsed_ms"] = round((time.monotonic() - start) * 1000)
    report["completed_at"] = datetime.now(timezone.utc).isoformat()
    report["summary"] = {
        "findings": len(report["findings"]),
        "high": sum(item["severity"] == "high" for item in report["findings"]),
        "medium": sum(item["severity"] == "medium" for item in report["findings"]),
        "low": sum(item["severity"] == "low" for item in report["findings"]),
        "viewports_completed": sum(bool(item["metrics"]) for item in report["viewports"]),
    }
    if report["summary"]["viewports_completed"] == 0:
        report["outcome"] = "fail"
    elif report["summary"]["high"] or report["summary"]["medium"]:
        report["outcome"] = "warning"
    return report
