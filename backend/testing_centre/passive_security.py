"""Stage 3 passive HTTPS security audit.

One authorized HTTPS target; no endpoint discovery, exploitation or redirects.
No response body, cookie values, credentials or full certificate data is stored.

The DNS-selected public IPv4 is pinned at TCP connection time and verified with
TLS SNI/hostname validation. Production still requires a real egress firewall,
rate limits, ownership verification and a separate worker. This is dev-only.
"""
import asyncio
import ipaddress
import re
import socket
import ssl
import time
import uuid
from datetime import datetime, timezone
from urllib.parse import quote, urlsplit

from .browser import resolve_public_ipv4

MAX_HEADERS = 24_576
READ_TIMEOUT = 9
MAX_FINDINGS = 25
ALLOWED_TLS = {"TLSv1.2", "TLSv1.3"}


def make_finding(code: str, severity: str, title: str, evidence: str,
                 recommendation: str, *, cwe: str, confidence: str = "high"):
    # OWASP Top 10:2025 is a related risk category, NOT an assertion
    # that this response proves the application is vulnerable.
    owasp = ("A04:2025 Cryptographic Failures"
             if code.startswith(("TLS_", "HSTS_", "COOKIE_SECURE_"))
             else "A02:2025 Security Misconfiguration")
    return {
        "id": str(uuid.uuid4()),
        "code": code,
        "category": "security_configuration",
        "severity": severity,
        "title": title,
        "detail": evidence[:240],
        "evidence": evidence[:240],
        "recommendation": recommendation,
        "cwe": cwe,
        "owasp_top_10_2025_related": owasp,
        "confidence": confidence,
        "verified_by": "tls_and_http_response_headers",
    }


def analyze_security_observation(data: dict) -> dict:
    """Evaluate only directly observed TLS and response-header signals."""
    tls = data.get("tls", {})
    pairs = data.get("headers", [])
    headers = {}
    for key, value in pairs:
        headers.setdefault(key.lower(), []).append(value.strip())
    first = lambda name: (headers.get(name, [""])[0]).strip()
    has = lambda name: bool(first(name))
    content_type = first("content-type").lower()
    html = "text/html" in content_type
    api = ("application/json" in content_type or
           data.get("path", "/").lower().startswith("/api/"))
    findings = []

    def add(code, severity, title, evidence, recommendation, cwe, confidence="high"):
        findings.append(make_finding(code, severity, title, evidence,
                                     recommendation, cwe=cwe, confidence=confidence))

    version = tls.get("version")
    if version and version not in ALLOWED_TLS:
        add("TLS_LEGACY", "high", "Legacy TLS protocol negotiated",
            f"Negotiated protocol: {version}.",
            "Require TLS 1.2 or TLS 1.3 on this endpoint.", "CWE-326")

    days = tls.get("days_until_expiry")
    if isinstance(days, int):
        if days < 0:
            add("TLS_EXPIRED", "high", "TLS certificate has expired",
                f"Certificate expired {-days} day(s) ago.",
                "Renew and deploy a trusted TLS certificate.", "CWE-295")
        elif days < 15:
            add("TLS_EXPIRING", "medium", "TLS certificate expires soon",
                f"Certificate expires in {days} day(s).",
                "Renew the certificate and confirm automated renewal.", "CWE-295")

    if not has("strict-transport-security"):
        add("HSTS_MISSING", "medium", "HSTS header not observed",
            "No Strict-Transport-Security header in the sampled HTTPS response.",
            "Configure an appropriate HSTS max-age after confirming HTTPS works on the entire host.",
            "CWE-319")
    else:
        match = re.search(r"(?:^|;)\s*max-age\s*=\s*(\d+)", first("strict-transport-security"), re.I)
        if not match or int(match.group(1)) < 86400:
            add("HSTS_WEAK", "low", "HSTS max-age absent or short",
                "HSTS max-age is absent or under one day.",
                "Use an appropriate HSTS max-age after validating HTTPS coverage.", "CWE-319")

    if first("x-content-type-options").lower() != "nosniff":
        add("NOSNIFF_MISSING", "low", "MIME sniffing protection not observed",
            "X-Content-Type-Options: nosniff was not seen.",
            "Set X-Content-Type-Options: nosniff on browser-delivered responses.", "CWE-693")

    if html:
        if not has("content-security-policy"):
            add("CSP_MISSING", "medium", "Content Security Policy not observed",
                "No enforcing Content-Security-Policy header on an HTML response.",
                "Define a restrictive policy based on actual script/style origins; deploy in report-only mode first.",
                "CWE-693", "medium")
        csp = first("content-security-policy").lower()
        frame = first("x-frame-options").lower()
        if "frame-ancestors" not in csp and frame not in ("deny", "sameorigin"):
            add("FRAME_GUARD_MISSING", "medium", "Frame embedding protection not observed",
                "Neither CSP frame-ancestors nor X-Frame-Options: DENY/SAMEORIGIN was observed.",
                "Protect relevant HTML pages with CSP frame-ancestors or a supported X-Frame-Options policy.",
                "CWE-1021", "medium")
        if not has("referrer-policy"):
            add("REFERRER_MISSING", "low", "Referrer policy not observed",
                "No Referrer-Policy header on sampled HTML response.",
                "Define an appropriate Referrer-Policy, e.g. strict-origin-when-cross-origin.",
                "CWE-200", "medium")
        if not has("permissions-policy"):
            add("PERMISSIONS_POLICY_MISSING", "info", "Permissions Policy not observed",
                "No Permissions-Policy header was seen on sampled HTML response.",
                "Consider limiting unnecessary browser capabilities with Permissions-Policy.",
                "CWE-693", "medium")

    for idx, cookie in enumerate(headers.get("set-cookie", [])[:12], start=1):
        # Do not include cookie names or values in findings or metadata.
        attrs = [part.strip().lower() for part in cookie.split(";")[1:]]
        flag = lambda name: any(x == name for x in attrs)
        if not flag("secure"):
            add(f"COOKIE_SECURE_{idx}", "medium", "Cookie missing Secure attribute",
                f"Set-Cookie entry #{idx} lacks Secure (cookie name/value withheld).",
                "Mark cookies issued on HTTPS as Secure.", "CWE-614", "high")
        if not flag("httponly"):
            add(f"COOKIE_HTTPONLY_{idx}", "low", "Cookie missing HttpOnly attribute",
                f"Set-Cookie entry #{idx} lacks HttpOnly (may be intentional for JavaScript-readable cookies).",
                "Use HttpOnly for session/authentication cookies that should not be read by scripts.",
                "CWE-1004", "medium")
        if not any(x.startswith("samesite=") for x in attrs):
            add(f"COOKIE_SAMESITE_{idx}", "low", "Cookie lacks explicit SameSite",
                f"Set-Cookie entry #{idx} has no SameSite attribute.",
                "Consider SameSite=Lax or Strict for applicable cookies; evaluate cross-site workflows.",
                "CWE-1275", "medium")

    # Wildcard CORS alone is valid for public resources; invalid combo is a
    # configuration signal, not proof of cross-origin credential access.
    if first("access-control-allow-origin") == "*" and first("access-control-allow-credentials").lower() == "true":
        add("CORS_INVALID", "low", "Inconsistent CORS response",
            "Access-Control-Allow-Origin: * with Access-Control-Allow-Credentials: true.",
            "Use explicit trusted origins if credentialed CORS is required; browsers reject this combination.",
            "CWE-942", "high")

    if api and not has("content-type"):
        add("API_CONTENT_TYPE_MISSING", "low", "API response lacks a content type",
            "No Content-Type header was seen for an /api/ path.",
            "Return an accurate Content-Type and use nosniff for browser clients.",
            "CWE-16", "medium")

    if api and has("cache-control"):
        policy = first("cache-control").lower()
        if "public" in policy and "no-store" not in policy:
            add("API_PUBLIC_CACHE", "low", "API response permits shared caching",
                "Cache-Control includes public on an API/JSON response; sensitivity is unknown.",
                "Check whether this response contains user-specific data; use private/no-store if appropriate.",
                "CWE-525", "low")

    if first("server") and re.search(r"/\d", first("server")):
        add("SERVER_VERSION_EXPOSED", "info", "Server software version advertised",
            "Server header includes an observable version token; exact value withheld.",
            "Consider suppressing precise server version details if operationally practical.",
            "CWE-200", "medium")

    findings = findings[:MAX_FINDINGS]
    high = sum(f["severity"] == "high" for f in findings)
    medium = sum(f["severity"] == "medium" for f in findings)
    low = sum(f["severity"] == "low" for f in findings)
    informational = sum(f["severity"] == "info" for f in findings)
    return {
        "outcome": "warning" if high or medium or low or data.get("status", 200) >= 400 else "pass",
        "reachable": True,
        "audit_type": "passive_security",
        "http_status": data.get("status"),
        "redirect_not_followed": 300 <= data.get("status", 0) < 400,
        "tls": tls,
        "findings": findings,
        "summary": {"findings": len(findings), "high": high, "medium": medium,
                    "low": low, "info": informational},
        "checks": ["Validated HTTPS/TLS handshake and certificate expiry",
                   "Observed response security headers", "Observed Set-Cookie attributes",
                   "Observed CORS and API cache headers"],
        "limitations": [
            "No penetration test or vulnerability exploitation",
            "One HEAD response only; no body content and no redirect following",
            "Absence of headers on HEAD may differ from GET",
            "No authenticated tests, authorization or API business-logic tests",
            "Unobserved protections are not proof of exploitable vulnerabilities",
        ],
        "coverage": {"method": "pinned_public_ip_https_head", "requests_sent": 1,
                     "path_checked": data.get("path", "/"), "response_body_read": False,
                     "redirects_followed": 0, "cookies_values_stored": False},
    }


def parse_headers(data: bytes) -> tuple[int, list[tuple[str, str]]]:
    """Strict bounded response-header parsing; no body processing."""
    top, sep, _ = data.partition(b"\r\n\r\n")
    if not sep:
        raise ValueError("Complete HTTP headers were not received within the bound.")
    try:
        lines = top.decode("iso-8859-1").split("\r\n")
        match = re.fullmatch(r"HTTP/1\.[01]\s+(\d{3})(?:\s+.*)?", lines[0])
        if not match:
            raise ValueError("Unsupported HTTP status line.")
        status = int(match.group(1))
        headers = []
        for line in lines[1:]:
            if not line or line[0] in " \t" or ":" not in line:
                raise ValueError("Invalid response header line.")
            name, value = line.split(":", 1)
            if not re.fullmatch(r"[A-Za-z0-9!#$%&'*+.^_\x60|~-]+", name):
                raise ValueError("Malformed HTTP response header.")
            headers.append((name.lower(), value.strip()))
        return status, headers
    except (UnicodeDecodeError, IndexError) as exc:
        raise ValueError("Invalid HTTP response headers.") from exc


async def passive_security_audit(url: str, host: str, resolver=None, connector=None):
    """Perform one same-host, no-redirect, no-body HEAD over verified TLS."""
    parts = urlsplit(url)
    if parts.scheme != "https" or parts.hostname != host or parts.port not in (None, 443):
        raise ValueError("Passive audit requires an operator-approved HTTPS host.")
    if parts.query or parts.fragment or parts.username or parts.password:
        raise ValueError("Queries, fragments and credentials are not permitted.")
    if any(ord(c) < 32 for c in url):
        raise ValueError("Invalid URL.")
    target_ip = await resolve_public_ipv4(host, resolver=resolver)
    if not ipaddress.ip_address(target_ip).is_global:
        raise ValueError("Public target resolution required.")
    route = quote(parts.path or "/", safe="/:@!$&'()*+,;=-._~")
    if len(route) > 1500:
        raise ValueError("Request path is too long.")
    ctx = ssl.create_default_context()
    ctx.set_alpn_protocols(["http/1.1"])
    started = time.monotonic()
    connect = connector or asyncio.open_connection

    async def run():
        reader, writer = await connect(
            host=target_ip, port=443, ssl=ctx, server_hostname=host,
            limit=MAX_HEADERS)
        try:
            ssl_obj = writer.get_extra_info("ssl_object")
            if ssl_obj is None:
                raise ValueError("TLS handshake missing.")
            cert = ssl_obj.getpeercert() or {}
            peer = writer.get_extra_info("peername")
            if peer and peer[0] != target_ip:
                raise ValueError("Connected peer differs from validated public IP.")
            days = None
            if cert.get("notAfter"):
                expiry = ssl.cert_time_to_seconds(cert["notAfter"])
                days = int((expiry - time.time()) // 86400)
            tls = {
                "verified": True, "version": ssl_obj.version(),
                "days_until_expiry": days,
                "certificate_hostname_verified": True,
            }
            message = (f"HEAD {route} HTTP/1.1\r\n"
                       f"Host: {host}\r\n"
                       "User-Agent: RasAliLabs-PassiveAudit/1.0\r\n"
                       "Accept: */*\r\n"
                       "Connection: close\r\n\r\n")
            writer.write(message.encode("ascii"))
            await writer.drain()
            # readuntil consumes exactly the header terminator, not body bytes.
            # The asyncio stream reader enforces a bounded buffer limit.
            buffer = await reader.readuntil(b"\r\n\r\n")
            if len(buffer) > MAX_HEADERS:
                raise ValueError("Response headers exceeded safety limit.")
            status, pairs = parse_headers(buffer)
            return {"status": status, "headers": pairs,
                    "tls": tls, "path": parts.path or "/"}
        finally:
            writer.close()
            await writer.wait_closed()

    try:
        observation = await asyncio.wait_for(run(), timeout=READ_TIMEOUT)
        report = analyze_security_observation(observation)
        report["latency_ms"] = round((time.monotonic() - started) * 1000)
        report["completed_at"] = datetime.now(timezone.utc).isoformat()
        return report
    except (OSError, ValueError, ssl.SSLError, asyncio.TimeoutError,
            asyncio.LimitOverrunError, asyncio.IncompleteReadError) as exc:
        # A TLS verification failure is not a validated handshake; do not
        # declare any header checks passed, and do not expose full exception.
        return {
            "outcome": "fail", "reachable": False, "audit_type": "passive_security",
            "error": type(exc).__name__,
            "findings": [],
            "summary": {"findings": 0, "high": 0, "medium": 0, "low": 0, "info": 0},
            "checks": [], "limitations": [
                "Audit failed before a verified HTTP observation.",
                "No claims about target security can be made.",
            ],
            "coverage": {"requests_sent": 0, "response_body_read": False,
                         "redirects_followed": 0},
        }
