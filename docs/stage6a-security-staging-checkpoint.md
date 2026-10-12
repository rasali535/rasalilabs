# Stage 6A Security & Staging Checkpoint — Release Hold

**Status: REVIEW-ONLY. Do not merge or turn on production onboarding
until operator access, staging and worker isolation acceptance are complete.**

Repository: rasali535/rasalilabs. Keep the original eight agent roles and
the separately preserved blueprint unchanged. Stage 6B billing is NOT in scope.

## 1. Why this work is needed

The old /api agent system was built as a private single-operator workspace,
not as a tenant-isolated multi-customer product. Before this change it
exposed projects, meetings, decisions, budget, model config, chat, Cognee
and WebSocket activity without separate authentication.

Stage 6A customer accounts are isolated under /api/customer-testing, but
**must not** be allowed to use the old agent API as a backdoor into a shared
operator project database. The new legacy gate is deliberately a
**single-operator lock**, not customer organization-level authorization.
Do NOT market the eight-agent dashboard as tenant-isolated.

## 2. Safe staged authorization rollout

Legacy HTTP/WS is protected by a new ASGI middleware that handles BOTH
request types. It explicitly exempts only:
- GET /api/health, /api/logo, root /api, and the limited gate-status/check routes.
- /api/customer-testing/*: requires the separate Stage 6A customer JWT.
- /api/testing/*: retains separate Stage 1–5 operator X-Testing-Token.

All other /api/* endpoints (read and write) require a separate
X-Legacy-Operator-Token. The WebSocket /api/ws/{project_id} requires:
- a protocol field "rasali-operator." + the approved operator token,
  **not URL query parameters**, and
- an Origin in the explicit LEGACY_OPERATOR_ALLOWED_WS_ORIGINS list.

If enforcement is enabled but the token is missing/invalid, protected
HTTP endpoints fail closed with 503 (unconfigured) or 401 (unauthorized),
and WebSockets are refused *before accept*. CORS wildcard Vercel preview
patterns are also disabled while the gate is enforced. Only explicit
ALLOWED_ORIGINS are allowed then.

The React app now asks for a private operator unlock code before rendering
legacy agent routes. The token remains in React memory only and is attached
to legacy API requests; it is not stored in localStorage or URLs. Unlock is
only a convenience layer: backend middleware does the real authorization.

### Deployment environment

Set **before** activating the customer preview:

- LEGACY_OPERATOR_TOKEN=<independent cryptographically random 48–128 char
  URL-safe token; use a secret manager, e.g. 64 random alphanumeric/URL-safe
  characters, and never commit the value>
- LEGACY_OPERATOR_ALLOWED_WS_ORIGINS=https://your-real-frontend-domain
- ALLOWED_ORIGINS=https://your-real-frontend-domain
- LEGACY_OPERATOR_AUTH_ENFORCED=true

Enforcement defaults **OFF** for a reversible rollout of existing private
agent deployments. However, once TESTING_WORKSPACE_AUTH_ENABLED=true,
the legacy agent gate is **FORCED ON** even if
LEGACY_OPERATOR_AUTH_ENFORCED=false. Do not enable customer accounts before
the operator secret and exact frontend origins are deployed. Customer
registration and queued scan submission remain OFF by default.

This is NOT SSO, per-customer authorization of agent models or multi-tenant
projects. Do not distribute the operator code to customers. Its owner must
rotate it if compromised; an access code is not MFA. Use HTTPS only.

### Smoke test (staging only)

Run:
  python scripts/stage6a_legacy_security_smoke.py

With environment variables (set locally, never in committed files):
- LEGACY_STAGING_SCOPE_ACK=I_CONTROL_THIS_STAGING_DEPLOYMENT
- LEGACY_STAGING_API_BASE=https://your-STAGING-api
- LEGACY_STAGING_OPERATOR_TOKEN=<operator token configured in staging>

It checks public health, gate enabled/configured, rejects unauthenticated
projects/models/chat-history and critical write endpoints, rejects a bogus
operator token, accepts an authorized read-only agent GET, and leaves
customer auth separate. Never makes authorized mutations or attacks.

This staging script has NOT been run as part of this PR.
Do not substitute a production URL without your own explicit authorization.

## 3. Exposed provider credential

The old server.py contained an embedded fallback Cognee API credential.
The fallback is removed, and Cognee requests now fail closed if a secret
is not configured.

**URGENT OPERATOR ACTION:** The original credential is still present in
historical commits, backups and possibly deployed images; deleting it from
the latest source DOES NOT revoke it.

- Revoke the exposed credential in Cognee's provider/account console.
- Issue a NEW credential; store it ONLY in the deployment secret manager
  as COGNEE_API_KEY, with correct least-privilege scope.
- Audit recent usage of the old key and review any dataset exposure.
- Remove inherited credentials from old deployed service images and logs,
  rotate any other secrets if compromise is plausible.
- Do not paste either key into GitHub source, PR comments or this chat.

Credential revocation is an external action and has not been performed
by this PR. Do not claim this risk is fully resolved until the provider
confirms revocation.

## 4. Real worker network isolation (external deployment blocker)

The Stage 6A worker source lives at
backend/testing_centre/workspace_worker.py and is explicitly not executed
inside the API. It already limits jobs to previously DNS-verified, exact
HTTPS hosts and performs an IP-pinned, SNI-verified, one-request HEAD probe.
These checks are defense in depth, NOT a full network sandbox.

A restricted environment must be provisioned at the actual provider
before enabling TESTING_CUSTOMER_JOB_SUBMISSION_ENABLED:

1. Separate private worker VM/container/pod; NON-root UID, no Docker
   socket, no host networking, no privilege escalation, read-only filesystem
   and minimal CPU/memory/process limits.
2. Strict ENFORCED outbound network policy (provider firewall, Kubernetes
   egress policy under a supporting CNI, or equivalent) that blocks cloud
   metadata/link-local, loopback, RFC1918/VPC/Kubernetes/private, IPv6
   unless controlled, and all unapproved ports/targets.
3. Allow verified target IPv4 on TCP 443 only. Use a controlled DNS service
   and a narrowly scoped TLS-encrypted MongoDB endpoint/credential.
   Never allow general arbitrary HTTP(S) to private services.
4. Run an external network-policy acceptance suite from INSIDE the worker
   runtime, verifying denied internal/metadata addresses and allowed
   known-good owner-authorized destination. Failure means NO rollout.
5. Confirm worker leases, renewals, retries, failed jobs, attempt caps
   and field-level DB permissions in an actual staging deployment.
6. Verify that a separate tenant cannot see/retrieve another tenant's
   scan IDs or evidence, including negative cases.
7. Enable customer job submission **only after** this evidence is collected.

A boolean TESTING_WORKER_NETWORK_ISOLATED flag is **NOT** a network
firewall or deployment attestation. This PR does NOT provision that
environment or enable worker execution. The connected Render account
requires an explicitly selected workspace before any infrastructure
changes, and no workspace was selected. No hosting changes were made.

## 5. Staging and migration acceptance — pending

Scripts already included from Stage 6A:
  python scripts/stage6a_staging_smoke.py

This requires TWO separate invited pilot accounts, two workspaces, a
DNS-TXT-verified owner-authorized hostname, separate scoped DB credentials,
a deployed worker and explicit user-controlled staging configuration.
It verifies cross-tenant domain/job denial, worker queue and TLS HEAD result.

Additional manual acceptance checks:
- Run the private operator negative-request smoke above.
- Confirm all eight legacy agents, boardroom, model config, chat and
  authorized WebSocket behave for the operator (no customer login bypass).
- Confirm unauthenticated WebSocket and foreign Origin are denied.
- Verify customer account logout/session expiry, invalid JWT, suspended
  user, expired domain and unapproved HTTP/redirect targets fail closed.
- Audit database indexes, TTL/retention, onboarding transactions, rate
  limiting, provider secret inventory and separation of roles.
- Confirm zero shared credentials in frontend bundles, environment dumps,
  logs and generated artifacts; document incident response.
- Run external independent penetration test and production deployment
  security review BEFORE unrestricted onboarding.

## 6. CI versus reality

CI runs all prior Stages 1–6A regression suites, real disposable MongoDB
cross-tenant tests with network stubs, real offline Chromium and React
production build, plus new legacy HTTP/WS operator-auth tests.

CI does NOT prove production/staging deployment, true egress restrictions,
secrets revocation, external account onboarding, or provider-side
permissions. Keep customer job submission OFF and do not enable public
registration until these pass.

**Branch → CI → draft PR → explicit owner approval before merge.**
