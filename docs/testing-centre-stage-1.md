# Ras Ali Labs · Testing Centre, Stage 1

This is a **development-only foundation** added beside the existing AI agent
system. It provides a responsive Testing Centre page, guarded scan endpoints,
persistent scan history and a bounded HTTP availability/latency check.

## Explicit non-goals

- **No penetration testing or active vulnerability scanning.**
- No browser automation, JavaScript evaluation or automated repairs.
- No public/customer signups, multitenancy or domain ownership verification.
- No automatic redirects or third-party crawling.
- No live application testing in the unit test suite.

These capabilities will need new implementations and authorization controls.

## Enable for a trusted development environment ONLY

Disabled by default. Do not set these values in public production until a
proper account system, proven domain ownership/permission and isolated egress
worker are in place.

1. Set backend environment variables (never commit actual secrets):

       TESTING_CENTRE_ENABLED=true
       TESTING_ACCESS_TOKEN=<random secret of at least 32 characters>
       TESTING_ALLOWED_HOSTS=your-authorized-public-domain.example

   Comma-separated exact hostnames are supported. No wildcard or private hosts.
   Use an operator-controlled target; you must have permission to check it.

2. Run the existing backend, MongoDB and React frontend normally.
3. Navigate to **Testing Centre**. Enter the development access token in
   the password field. The token is held in component memory, not persistent
   browser storage. Click **Open Testing Centre**.
4. Supply an approved HTTP(S) URL with no credentials, query or fragment and
   use **Run check**.
5. Inspect the result/history. A 5xx or network failure is recorded as failed;
   a client error or redirect produces a warning/pass as reported in the result
   (redirects are *not followed*).

API (all routes require header X-Testing-Token):
- GET /api/testing/config
- GET /api/testing/scans
- GET /api/testing/scans/{id}
- POST /api/testing/scans {"url": "https://approved.example/"}

Scan documents include id, URL/host, project reference (optional), running/
completed/failed status, HTTP result, creation and finish time. Scans refuse to
run when the database has switched to the legacy in-memory fallback.

## Architecture and safety limitations

Only explicitly operator-allowlisted FQDNs are accepted. DNS answers are
checked for globally routable IP addresses before a request; nonstandard ports,
embedded credentials, queries/fragments and IP-literal hosts are rejected.
The HTTP client does not follow redirects or trust proxy environment variables,
and uses an eight-second timeout.

**Stage 1 DNS checks are not a complete defense against DNS rebinding.**
Deploy in an isolated development environment with restricted outbound
network access. A future worker must pin/validate actual network destinations,
implement complete egress filtering and enforce per-tenant scope & quotas.
Do not expose a public scanner until those protections are implemented.

The HTTP HEAD probe falls back to a streaming GET only if HEAD isn't supported.
It does not download the response body. Results include explicit untested
capabilities, not a fabricated security score.

Project validation is available through the optional project_id API field;
the UI only exposes standalone scans in this stage. The existing project
engine and eight agents are intentionally unchanged.

## Validation

    python -m pip install fastapi==0.110.1 starlette==0.37.2 httpx==0.28.1 pydantic==2.12.5 pytest==9.0.3
    python -m pytest -q tests/test_testing_centre.py
    cd frontend && npm ci --legacy-peer-deps && CI=false npm run build

The focused tests use stubbed HTTP/DNS and a fake database; real authorized
website checks still need manual staging validation. This PR must not be
merged until reviewed and approved.
