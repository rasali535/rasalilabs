# Stage 6A — Customer identity, workspace isolation and queued scan foundation

**Status: code foundation, NOT production-ready or externally validated.**

This is a deliberately separate customer-facing API and React screen.
The original eight-agent "company" and the Stages 1–5 operator Testing Centre
remain unchanged. The new path is /workspace-testing in the React app;
the API is /api/customer-testing.

## Implemented

- New invite-only customer account (email + bcrypt password), with unique
  MongoDB email index. No generic signup by default. Passwords are never
  returned to the frontend.
- Thirty-minute signed bearer JWT with issuer, audience, not-before,
  expiration and account token_version checks. Token is held in browser
  component memory only (no persistent localStorage).
- Per-workspace membership lookup on EVERY domains/jobs read or write.
  Disallowed workspace IDs return 404 and disclose no documents.
- Workspace ownership of domain registration; exact hostname DNS TXT challenge
  with cryptographically random token. Ownership is reverified every 30 days.
  Subdomain and parent are distinct assets.
- Queue-only customer HTTPS availability. Submitted targets must match a
  verified exact hostname; DNS addresses must resolve to public IPs.
  Jobs are stored with workspace_id and user ID. At most three outstanding
  jobs per workspace (application-level check, not robust distributed quota).
  Browser, API exploit, login and penetration testing remain DISABLED for
  customers.
- Separate worker process connects to a dedicated MongoDB credential,
  atomically leases jobs and validates verified domain ownership again.
  It calls the existing TLS-verified, **IP-pinned HEAD** passive probe,
  never follows redirects and does not fetch response bodies. Worker writes
  only bounded HTTP observations, not cookie/header details.
- Lease expiry and two-attempt limit prevent most stuck jobs. Expired final
  attempts are terminally failed. Old worker results cannot overwrite later
  retries thanks to conditional update.
- Unique MongoDB indexes for accounts, workspace membership, domain ownership
  records and scan queue IDs. Failure to initialize indexes disables the API.
- CI regression tests cover two separate accounts, cross-tenant access denial,
  invalid sessions, missing DNS proof, atomic job leases and unsafe destinations.

## Required configuration: OFF by default

Customer API:
- TESTING_WORKSPACE_AUTH_ENABLED=true
- TESTING_WORKSPACE_JWT_SECRET=<generated unpredictable 48+ byte secret>
- TESTING_WORKSPACE_SIGNUP_ENABLED=true (pilot invite-only signup only)
- TESTING_WORKSPACE_INVITE_SECRET=<random 32+ character secret>

Do not use the same secret for these separate purposes. Configure both in
a secret manager. Never check values into the repository.

Customer scan submission is separately disabled until worker/network deployment
is actually complete:
- TESTING_CUSTOMER_JOB_SUBMISSION_ENABLED=true

Worker process (run separately as an unprivileged user in a constrained VM or
container, NOT in the web app):
- TESTING_WORKER_ENABLED=true
- TESTING_WORKSPACE_AUTH_ENABLED=true
- TESTING_WORKER_NETWORK_ISOLATED=true
- TESTING_WORKER_MONGO_URI=<separate limited MongoDB worker credential>
- DB_NAME=rasalilabs (or production database name)

Execute via:
    python -m backend.testing_centre.workspace_worker

The NETWORK_ISOLATED environment flag is merely a declaration. It is **NOT**
a firewall. Deploy with actual OS/container/network-policy egress enforcement:
deny RFC1918, loopback, link-local, cloud metadata, Kubernetes service CIDRs
and sensitive internal ranges; allow public HTTPS only to explicitly verified
target IPs and necessary DNS and MongoDB services. Use a separate VPC/namespace
with locked-down worker privileges, no mounted app secrets, and audit logging.
The default code validates public DNS then TLS-pins the resolved public IPv4,
but genuine network isolation requires infrastructure implementation.

**Never turn on customer job submission until the network layer is verified.**

## Customer API routes

POST /api/customer-testing/auth/register
  {email, password, workspace_name, invitation_code}
POST /api/customer-testing/auth/login
  {email, password} -> 30-min bearer token
GET /api/customer-testing/auth/me
GET /api/customer-testing/workspaces
POST /api/customer-testing/workspaces {name}

All remaining routes require:
- Authorization: Bearer <customer-session-token>
- X-Workspace-ID: <workspace id that the user belongs to>

GET /api/customer-testing/domains
POST /api/customer-testing/domains {hostname}
POST /api/customer-testing/domains/{domain_id}/verify
GET /api/customer-testing/jobs
GET /api/customer-testing/jobs/{id}
POST /api/customer-testing/jobs
  {domain_id, url: "https://verified.example/path", test_type:"availability"}

Register domain first, add the TXT value at
_rasalilabs-verify.<hostname>, then verify ownership.
The worker does not accept unrestricted arbitrary URLs. DNS TXT proves control
of the exact host, not authorization to attack other services or IP ranges.

## Deployment and security blockers — NOT solved in 6A

- **Legacy agent API routes remain unauthenticated and remain completely
  outside this customer authentication system.** The old operator Testing
  Centre uses a separate global token. Do not treat the entire existing app
  as tenant secure; disable legacy operator testing on customer infrastructure.
- Separate egress-restricted worker runtime and database security policies
  have **not** been provisioned by this PR.
- Invite creation/revocation, email verification, password reset, MFA,
  per-IP login rate limiting, abuse detection, account deletion, billing,
  paid entitlements, secure retention and audit events are not implemented.
- The MongoDB registration procedure uses several writes; a mid-flight
  database failure can leave an incomplete onboarding. Production should
  require a replica-set transaction and reconciliation workflow.
- Current queue quota is not atomic under concurrent requests; production
  requires a distributed per-user limit, usage metering and cancellation.
- Worker leases lack heartbeats; operations longer than the fixed lease may
  be retried, which is acceptable only for idempotent bounded HEAD checks.
- JWTs are short-lived and can be invalidated by changing token_version or
  disabling the account, but there is no end-user session management UI.
- The exposed legacy hardcoded Cognee key is **still a critical security debt**,
  unchanged here per prior instruction. Rotate/revoke before real launch.
- External authorized end-to-end staging, migration/backfill, privacy/legal
  review, incident response, and an independent penetration test are pending.

This is a staged, fail-closed foundation for a small invite-only pilot, not
an approval to onboard public customers.

## Validation

Offline CI runs original Stages 1–5 regressions, isolated Stage 6A
customer/domain/worker tests, offline real Chromium smoke, React production
build and all relevant Python syntax checks.

Live staged acceptance (not yet executed):
1. Provision restricted MongoDB indexes/replica set and strong unique secrets.
2. Deploy app and verified, tightly egress-controlled worker separately.
3. Create TWO pilot accounts/workspaces, register and DNS-verify one hostname.
4. Confirm an unauthorized workspace cannot access domains or jobs, even by
   guessing IDs and switching X-Workspace-ID.
5. Submit a safe HTTPS check, inspect claimed and completed record and
   redirect/error behavior with a genuine approved URL.
6. Test missing/expired TXT verification, expired sessions, tampered tokens,
   disabled account, invalid targets and worker absent.
7. Confirm original eight-agent UI still works and old operator Testing Centre
   is disabled for customer access.
8. Run supervised security review before expanding beyond the pilot.


## Operator-run Stage 6A staging smoke

Once BOTH separate pilot accounts, two workspaces, verified domain and
actual isolated worker have been provisioned, run the following ONLY in the
authorized staging network (never in PR CI). Export the environment
variables below, preferably through a local secret manager or ephemeral
shell session; do not paste real credentials into GitHub, ChatGPT or logs.

- RAL6A_SCOPE_ACK=I_HAVE_AUTHORIZED_THE_STAGING_SITE_AND_ISOLATED_WORKER
- RAL6A_STAGING_API=https://your-staging-api
- RAL6A_AUTHORIZED_URL=https://your-authorized-staging-host/
- RAL6A_WORKSPACE_A=<owner workspace identifier>
- RAL6A_WORKSPACE_B=<second customer's distinct workspace identifier>
- RAL6A_VERIFIED_DOMAIN_ID_A=<the verified domain id in workspace A>
- RAL6A_USER_A_EMAIL and RAL6A_USER_A_PASSWORD
- RAL6A_USER_B_EMAIL and RAL6A_USER_B_PASSWORD

Then execute: python scripts/stage6a_staging_smoke.py

It verifies that the second account gets 404 for the first customer's
domains and scan history even with a guessed workspace ID; queues one
owner-authorized HTTPS check; waits up to roughly a minute for the actual
worker's TLS-verified response. This test must be run after deploy; it
**has not been executed** in this PR. The script never runs exploit scans,
deployments, penetration tests or any GitHub code writes.

**DO NOT MERGE UNTIL OWNER APPROVAL AND DO NOT ENABLE PUBLIC CUSTOMER TESTING.**
