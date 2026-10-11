# Ras Ali Labs — Stage 2: Live Browser Diagnostics

This adds an **opt-in browser QA mode** to the Stage 1 Testing Centre. It keeps
the existing AI-agent boardroom, project system and availability scans intact.

## What is actually measured

- Real Chromium navigation (document status), uncaught JavaScript exceptions,
  console errors, failed requests and HTTP 4xx/5xx resource responses
- DOM smoke signals: empty visible content, broken image elements, placeholder
  navigation anchors, missing title and horizontal overflow
- Three preset viewports: desktop 1366×768, tablet 820×1180, mobile 390×844
- Navigation timing, DOMContentLoaded timing, first contentful paint when available
- Bounded JPEG screenshot per viewport, stored in MongoDB in a separate evidence
  collection (not embedded in scan history), retrieved with the testing token
- Severity, evidence-oriented diagnostics and actionable recommendations

All measurements report **observed facts** or explicit limitations. No made-up
security scores, compliance certifications or AI-generated test outcomes.

## What it DOES NOT do

- No penetration testing, vulnerability exploitation, OWASP ZAP, authentication,
  payment testing, account flows, or write operations
- No clicks or form submissions; no arbitrary user-journey automation
- No Lighthouse score or full performance audit (only browser timing signals)
- No exhaustive link crawling. Placeholder anchors and broken image elements
  are checked; full internal destination validation is a separate enhancement
- Does not prove a site is safe, fully functional or free of vulnerabilities
- No multitenant production access, verified customer ownership, queued workers
  or long-term scheduled checks

A site can pass these limited checks and still contain security or logic defects.
Third-party resources are blocked. This can produce incomplete layouts, missing
assets and misleading performance measurements; the report calls out blocked
requests. Review findings in context and reproduce in the customer's own environment.

## SECURITY GATE: do not deploy as a public scanner

Stage 1 operator controls remain mandatory:
- TESTING_CENTRE_ENABLED=true
- TESTING_ACCESS_TOKEN=<random 32+ character value>
- TESTING_ALLOWED_HOSTS=an-exact-hostname-you-own-or-have-permission-to-test

**New** controls required for browser mode:
- TESTING_BROWSER_ENABLED=true
- TESTING_BROWSER_NETWORK_ISOLATED=true

The second flag **must only be set once the browser worker actually runs inside
an unprivileged isolated container/VM with network egress restricted to the
explicitly authorized public target addresses**. The flag does not implement
the firewall or container. This is a serious outstanding deploy requirement.
Do not set it to bypass the gate on an ordinary production web/API server.

The code blocks cross-host requests, unsafe methods and traffic beyond a
per-viewport request cap; disables service workers, forbids TLS bypass, maps
the approved hostname to a validated public IPv4 address, limits browser
navigation time and serialized evidence size, and uses a singleton semaphore.
These are defense-in-depth, NOT a complete sandbox. Browser network side
channels and DNS rebinding risks require network-level egress enforcement.

**Never run the browser against arbitrary public URLs from a shared or
serverless production API deployment.** The current scan operation is bounded
but synchronous in the API request. Stage 3/future infrastructure should move
it to a queue-backed worker with authentication, per-user ownership checks,
rate limiting, egress controls, retention policy and cancellation.

Page JavaScript may initiate state-changing requests; we reject non-GET/HEAD
requests from the browser network route, but GETs can still have side effects
on broken applications. Only operator-controlled applications are in scope.

Screenshots may contain private customer information if testing real user pages.
Use unauthenticated/staging test pages, set retention limits in MongoDB, and
never store credentials or PII in test fixtures.

## API changes

POST /api/testing/scans accepts:
  {"url":"https://approved.example/","test_type":"browser_smoke"}

(With omitted test_type, the original availability check remains the default.)
The response includes status, findings, viewport metrics and screenshot IDs.

GET /api/testing/evidence/{evidence_id} returns an image data URI for an
authorized operator. The existing GET /api/testing/scans endpoints retain
full history without large embedded screenshots.

GET /api/testing/config returns stage=2, browser_enabled and capability notes.

## Validation / review gates

The GitHub Action **Testing Centre Stages 1 and 2** runs:
1. Python syntax validation
2. Stage 1 and Stage 2 API/logic regression tests with mocked network
3. Real headless Chromium startup and screenshot of offline HTML
4. Full existing React production build

These tests do NOT contact arbitrary websites. Before merge or staged use,
perform an authorized live smoke check in a real egress-isolated browser worker,
verify screenshot retrieval, and retest the agent boardroom and other original
project screens. Only the owner can approve merging the PR.

Security hardening of the pre-existing exposed Cognee credential remains a
separate, urgent task.
