# Ras Ali Labs · Testing Centre Stage 3 — Passive Security

**Implementation status:** development preview on an opt-in, operator-approved
HTTPS target. This is NOT penetration testing, vulnerability exploitation,
security certification, or permission to test third-party websites.

The existing eight-agent AI system and Stage 1/2 availability/browser modes are
unchanged. Stage 3 adds a third testing profile: **Passive Security**.

## Implemented checks

One TLS-verified connection and **one HEAD request** to the selected,
explicitly allowlisted, HTTPS target path. It does not fetch a response body,
follow redirects, crawl for endpoints, enumerate resources, submit forms, or
attempt logins. It does not perform request tampering, fuzzing or exploitation.

- TLS handshake with hostname verification and default trust validation;
  negotiated TLS version; certificate expiry if provided by peer metadata
- Observed HSTS policy and minimum-max-age signal
- X-Content-Type-Options: nosniff
- HTML-only: Content-Security-Policy presence, CSP frame-ancestors or
  X-Frame-Options protection, Referrer-Policy and Permissions-Policy
- Up to 12 observed Set-Cookie entries: Secure, HttpOnly, SameSite
  (findings refer to entry numbers, **never cookie names or values**)
- Non-exploitative API/JSON response signals: content type, conditional
  public cache policy and inconsistent wildcard credentialed CORS headers
- Server version advertised as a version **signal**, without logging it
- CWE identifiers and **related** OWASP Top 10:2025 risk categories:
  A02:2025 Security Misconfiguration / A04:2025 Cryptographic Failures.
  These are informational mappings, **not proof of a corresponding weakness**.
- Evidence, finding severity, confidence, rationale and recommendation;
  status, scan history and a dedicated dashboard report.

An absent header on a HEAD response can be a false positive when GET responses
differ. Missing CSP isn't proof of XSS, missing frame restrictions aren't proof
of exploitable clickjacking, missing HttpOnly can be intentional, and CORS
headers alone do not prove unauthorized access. Review with context.

## Operator-only configuration

Keep the existing Stage 1 gate:
- TESTING_CENTRE_ENABLED=true
- TESTING_ACCESS_TOKEN=<random uncommitted token with 32+ characters>
- TESTING_ALLOWED_HOSTS=<exact public hostname explicitly authorized by owner>

To additionally enable passive security checks:
- TESTING_PASSIVE_SECURITY_ENABLED=true
- TESTING_SECURITY_NETWORK_ISOLATED=true

**Critical:** The isolation variable is a **declaration**, not a firewall.
Set it ONLY after placing execution in an unprivileged restricted network
environment with egress allowlisting to the approved public IPs and no access
to internal/cloud metadata services. The backend currently performs scans
**synchronously in the API process**; public or production deployment requires
a separate queue-backed worker, hardened OS/container isolation, rate limits,
domain ownership verification, customer/tenant separation, bounded concurrency
and scan lifecycle/cancellation controls. Never set the flag simply to make the
UI option clickable.

Stage 3 mitigates one form of DNS rebinding by resolving a public IPv4 and
**connecting directly to that validated IP with TLS SNI for the allowlisted
host**. Proxy environment variables are not used for this direct TLS socket.
It limits header bytes and total read time, and refuses redirects. No real
network activity is executed in unit tests.

The audit is unavailable by default and the API returns 503 without the
operator/isolation gates, 403 for invalid tokens, 422 for non-HTTPS targets,
and failure rather than success if transport verification fails.

## API and results

- Existing POST /api/testing/scans with body:
  {"url": "https://approved.example/path", "test_type": "passive_security"}
- GET /api/testing/config advertises passive_security_enabled and Stage 3.
- Existing GET /api/testing/scans and GET /api/testing/scans/{id} include
  scan type, report, findings, coverage and summary.

Results do not contain raw response headers, body bytes, cookie secrets,
certificate subjects or raw TLS exception messages. They include check
limitations: no active penetration testing, no authenticated flow verification,
no guarantee against flaws in hidden routes and no comprehensive API testing.

## Validation and merge gates

CI runs the original Stages 1–2 regression suite plus Stage 3 tests for:
- Strong / weak HTTPS headers and TLS-expiry signals
- Absence of cookie secret values in reports and persisted scan documents
- Bounded header parsing and no-redirect/HEAD-only request behavior
- Pinned public IPv4 with TLS SNI and rejection of private destinations
- Disabled-by-default controls, invalid access token and non-HTTPS rejection
- Security finding serialization, API records and unchanged other profiles
- Offline real Chromium launch and screenshot plus full existing React build

Before approval of any production exposure, a separate, genuinely
network-isolated staging deployment must perform a supervised check on a
website the operator controls. Verify that HEAD headers match expected GET
policies, test failure and negative cases, confirm data retention rules,
and manually smoke-test the original agent dashboard.

**Known carry-over debt:** Stages 1/2 were merged before a real staging
scan was completed. The old public hard-coded Cognee credential remains
unrotated at the owner's request and requires urgent separate remediation.

See [OWASP Top 10:2025](https://top10.owasp.org/2025/) for the related risk
taxonomy (OWASP does not certify these scan findings).
