# Testing Centre — readiness and safe HTTPS availability (operator preview)

This checkpoint fixes the recurring disabled \`/api/testing/config\` and
\`/api/testing/scans\` 503 confusion without silently enabling any scanner.

## What changed

- **GET /api/testing/status** is non-sensitive and requires no token. It does
  not access the network, enumerate host allowlists or read credentials.
  The mode is: \`disabled\`, \`configuration_required\`,
  \`storage_unavailable\`, or \`operator_configured\`.
- The React Testing Centre displays the live status before the operator
  enters a testing token. If disabled, it does NOT send protected
  \`/config\` or \`/scans\` calls merely to determine why.
- The actual **operator token remains separate** from the AI-agent operator
  token. The scan config, history, screenshots, reviews and repair cases
  still require \`X-Testing-Token\`.
- Availability checks now use the existing strict passive observer's
  **public IPv4 pinning, verified TLS, HTTPS-only one HEAD response**, with
  no GET fallback, redirects, cookies, credentials or response-body reads.
  HTTP-only URLs are rejected before a scan record is created.
- Unit/regression tests exercise no real websites and reject simulated
  unverified TLS, unpinned network requests, HTML body reads, wrong tokens,
  and unavailable storage.

## Why we are not enabling scans yet

The existing \`backend/testing_centre/router.py\` still runs operator
availability, Playwright browser and passive security checks **inside the
FastAPI request handler**. Even an IP-pinned HEAD call is not a
substitute for a separate runtime with enforced egress controls.

For this reason, leave the following disabled on the shared API:
- \`TESTING_CENTRE_ENABLED=false\`
- \`TESTING_BROWSER_ENABLED=false\`
- \`TESTING_PASSIVE_SECURITY_ENABLED=false\`
- \`TESTING_REPAIR_GITHUB_ENABLED=false\`
- \`TESTING_AGENT_AI_ENABLED=false\`

The existing customer worker in
\`backend/testing_centre/workspace_worker.py\` is **availability-only**,
not a general browser/penetration testing runner. Its declared
\`TESTING_WORKER_NETWORK_ISOLATED\` flag is NOT proof of a firewall.

## Deployment acceptance

1. Review and merge this PR to \`rasali535/rasalilabs\` after green CI.
2. Render staging currently uses the
   \`feature/stage-6a-security-staging-hardening\` branch and has automatic
   deploys OFF. This code will NOT reach Render until the owner separately
   approves changing the service branch/deploy.
3. Call the new status endpoint on the intended Render backend:
   \`https://rasalilabs-api-staging.onrender.com/api/testing/status\`.
   Expect \`mode: disabled\` and HTTP 200; a 503 from \`/config\` while
   disabled is intentional and does NOT mean API health is failing.
4. Verify original agent APIs and MongoDB health are unaffected, and
   no customer scans or GitHub repairs have become enabled.
5. Provision and independently verify a real restricted worker, required
   domain ownership/allowed hosts, per-operator quotas, safe job limits and
   auditable scan histories BEFORE activating real operator scan execution.
6. After that infrastructure passes negative egress tests, select exact
   approved hosts (for example the owner's \`rasalilabs.com\`),
   a new 48+ character random \`TESTING_ACCESS_TOKEN\` with least privilege,
   and enable the preview only in a controlled staging environment.
   NEVER reuse \`LEGACY_OPERATOR_TOKEN\`, put secrets in frontend code,
   or expose sensitive credentials in tickets/chats.
7. Validate HTTP 403 for missing/wrong Testing Centre token, 422 for
   invalid/non-HTTPS targets, 503 for missing storage, and real
   pinned HTTPS HEAD behavior only after worker isolation is verified.

## Important distinctions

- Stage 6A customer workspaces and their DNS TXT ownership workflow are
  separate from this legacy single-operator Testing Centre.
- The previous HTTP availability probe issued GET on a 405/501 HEAD result.
  That has been removed. A HEAD response of 405/501 is now a measured
  result; it is not a reason to fetch website body content.
- \`operator_configured\` means the secret, host allowlist and persistent
  database are present. It is NOT a firewall attestation, a passing
  penetration test or permission to offer public scanning.
- All old scan results retain their old documented methodology. New scan
  records contain a clear \`coverage.method\` value so comparisons do not
  confuse new and old observations.
- UI and API readiness do not prove a target has been scanned. Use a
  real, operator-authorized job receipt and results after deployment.

**PR branch only. No merge, customer activation, or Render deploy included.**
