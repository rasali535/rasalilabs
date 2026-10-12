# Ras Ali Labs — Stage 5: Fix & Verify

**Development-only feature.** This adds an evidence-to-repair workflow to
Testing Centre while retaining the original eight company agents and the
Stage 1–4 scanners/reviewers.

## What actually works

1. Choose a **completed Stage 2 browser or Stage 3 passive security scan**.
2. Open a repair case tied to one *recorded finding ID*. The immutable
   fingerprint contains the issue's observed title/category/viewport, or
   the stable passive-security rule code. Scanner-generated UUIDs are not
   used for equality between different scans.
3. The case contains evidence, the recorded recommendation, a *suggested*
   engineering owner (Pixel/frontend, Forge/backend, Cipher/developer,
   Sentinel/DevOps), plus a copyable coding-agent investigation prompt.
   It does **not** invent code changes or assign tasks automatically.
4. Developers review the relevant authorized repository and prepare
   a replacement source file. A separate, opt-in GitHub bridge (below)
   can publish a **single reviewed file** on a new feature branch as a
   **draft pull request**. It is never automatically merged or deployed.
5. After a human deploys a change to the authorized staging target, click
   **Run live retest**. The app reuses the existing Stage 2/3 scanner,
   respecting its approved-host, worker-isolation and operator-token gates.
6. A new scan is persisted and compared with the baseline:
   - still_observed — same issue signature still appears;
   - not_observed_in_retest — issue signature was not seen, but the result
     **does not prove the code was fixed or certify the application**;
   - inconclusive — equivalent test coverage was not established.

For browsers, all three viewport navigations and document metrics must
be complete in both scans. For passive security, validated TLS, one pinned
HTTPS HEAD response, and a matching response status are required. All
comparison attempts are recorded in the repair's verification history.
No comparison changes release_readiness from not_verified. A human must
confirm deployment SHA and run appropriate test coverage before claiming
a release is ready.

## Routes (operator X-Testing-Token always required)

- GET /api/testing/repairs — recent repair cases
- GET /api/testing/repairs/{case_id} — evidence, PR and comparison history
- POST /api/testing/scans/{scan_id}/repairs {"finding_id": "<measured id>"}
- POST /api/testing/repairs/{case_id}/verify
  {"retest_scan_id": "<new persisted scan id>"}
- POST /api/testing/repairs/{case_id}/publish-pr — optional, explicitly
  approved single-file draft GitHub PR; requires an **additional** header
  X-Repair-Approval-Token.

## GitHub PR bridge: OFF by default

Requires a human-controlled, narrowly scoped GitHub App token or fine-grained
token. Do not use a personal unrestricted PAT. Grant Contents RW and Pull
requests RW ONLY on the explicitly selected repository. Do not enable this
on the existing public shared API, which lacks tenant isolation.

Environment variables, all needed to enable:

- TESTING_REPAIR_GITHUB_ENABLED=true
- TESTING_REPAIR_SCOPE_ACK=true
- TESTING_REPAIR_REPO=owner/exact-authorized-repository
- TESTING_GITHUB_TOKEN=<repository-scoped-secret-token>
- TESTING_REPAIR_APPROVAL_TOKEN=<separate-random-secret-32-plus-characters>

A draft PR requires:
- Operator Testing Centre token and separate repair approval token.
- Exact repo match to TESTING_REPAIR_REPO.
- Exact file path within allowed application source roots, with safe
  extension and no hidden/secret/workflow/credentials/auth/config files.
- Original main branch blob SHA of this file, as independently reviewed.
- Complete reviewed replacement source (max 48KB). Source is sent only
  to the configured GitHub repository and never stored in MongoDB.
- Exact explicit confirmation phrase: CREATE DRAFT PR.

The bridge reads main and file metadata from api.github.com, checks the
reviewed file SHA, creates an independent repair branch, commits the one
file, then creates a draft PR to main. It cannot merge, approve or deploy.
If an error occurs after branch creation, publishing becomes
publish_failed_reconcile: an operator must inspect GitHub manually, not
blindly retry and duplicate writes. Current repair cases are restricted
to ONE drafted PR; there is no automated PR revision workflow.

**This is NOT autonomous code generation.** The supplied patch must come
from a developer or a coding agent operating within an authorized repo
and reviewed by an operator. AI model notes from Stage 4 never become
code changes. The UI deliberately asks the human for a complete reviewed
file and its current blob SHA.

The backend currently performs GitHub operations from the API process.
Before commercial release migrate publishing to an isolated auditable
job worker, enforce org/tenant authorization and rate limits, add
deployment SHA attestation, status reconciliation, human approval
records tied to authenticated user identities, abuse protection and
strong secret management.

## Real staging validation (not yet completed)

Stage 1–4 live staging checks were previously outstanding. The script
scripts/stage5_staging_smoke.py performs a **real** non-destructive
operator-confirmed scan/review smoke ONLY when manually run with all:

- TESTING_STAGING_BASE_URL=https://your-staging-api.example
- TESTING_STAGING_AUTHORIZED_URL=https://the-owner-approved-app.example
- TESTING_STAGING_TOKEN=<operator-testing-token>
- TESTING_STAGING_SCOPE_CONFIRMED=I_HAVE_AUTHORIZATION_AND_NETWORK_ISOLATION

The target must also be on the backend TESTING_ALLOWED_HOSTS list. This
script does not run in CI, create repair PRs or contact arbitrary URLs.
It checks HTTP, optionally browser and passive security if those are
enabled in the truly network-isolated staging environment; persists
scans and creates evidence-grounded reviews. Review results and validate
both failed-path and success-path behavior manually. A staging run does
not certify production safety or replace an independent pen test.

### CI gates

GitHub Actions performs:
- Syntax validation and Stages 1–5 offline mocked Python tests.
- HTTP mock tests of the exact GitHub GET/GET/POST/PUT/POST draft PR
  sequence, stale SHA rejection, operator approval and one-time locking.
- Real offline Chromium screenshot smoke.
- Full existing React production build.

These verify implementation behavior; they do NOT prove that your live
target was scanned, a repository was modified, a draft PR was remotely
created, a change was deployed or a vulnerability was fixed.

### Unresolved production blockers

- Customer authentication/tenant isolation in the legacy backend.
- Real worker/egress isolation, scan quotas, ownership verification.
- Strong security token management and secret rotation (the legacy
  hardcoded Cognee key remains exposed until separately rotated).
- GitHub App installation flow and repository-specific user consent.
- Safe per-project code context and automated patch generation.
- Authentic PR merge/deploy monitoring and regression-test provenance.
- Live staging acceptance on a site the operator is authorized to test.

Keep this Stage 5 PR in draft until the owner approves its changes.
