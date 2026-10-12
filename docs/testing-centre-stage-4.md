# Stage 4: Evidence-grounded testing specialists

The Testing Centre adds **Trace (QA Engineer)**, **Aegis (Security Engineer)**
and **Vector (Test Architect)** as specialist reviewers of stored scan evidence.
They operate alongside, not inside, the original eight-agent boardroom.

## Truthful operation

- Trace classifies measured runtime, functional, mobile and network findings.
- Aegis classifies passive security configuration observations and does NOT
  claim exploitability from missing headers.
- Vector documents untested workflows, scan limitations and coverage gaps.
- Reports reference actual source finding IDs and persist separately in the
  MongoDB testing_reviews collection; source scan records remain unchanged.
- Handoffs to developer, frontend, backend and DevOps are SUGGESTIONS only.
  No tasks, code edits, branches, PRs, automatic fixes or retests are executed.
- Release readiness always remains NOT VERIFIED, even if zero findings appear.
- Failed or incomplete scans cannot be used as successful evidence.

## API

All endpoints require the original Testing Centre X-Testing-Token header and
persistent database, and the feature remains unavailable unless the existing
operator gate is enabled.

- GET /api/testing/agents — metadata for three specialist personas.
- GET /api/testing/scans/{scan_id}/reviews — review history, newest first.
- POST /api/testing/scans/{scan_id}/reviews — creates review.
  JSON body with use_ai false produces deterministic evidence-based triage.
  JSON body with use_ai true requests optional LLM commentary.

Unauthorized users receive HTTP 403, disabled or unavailable features HTTP
503, unknown scans HTTP 404, and unusable scans HTTP 409.

## Generative AI is opt-in only

The baseline review does NOT use an LLM; it is honest, deterministic
evidence analysis. Optional, real model-generated notes on EXISTING issue
IDs require all of:

- Existing operator testing access.
- AIML_API_KEY configured in the backend (never committed).
- TESTING_AGENT_AI_ENABLED=true.
- TESTING_AGENT_AI_DISCLOSURE_ACK=true: operator accepts that limited
  third-party data will be sent to the configured external provider.
- A user intentionally selects the AI commentary option for that review.

Only bounded IDs, finding titles, categories and severity are sent.
Neither raw evidence, screenshot bytes, URL, cookie values nor credentials
are sent. Nevertheless, finding titles are untrusted website-derived text,
and the provider receives third-party application metadata. Do not enable
this without authorization and a clear customer disclosure.

AI output must parse as JSON and reference only existing issue/gap IDs.
Unknown references are discarded. Accepted notes are explicitly marked
UNVERIFIED; model output cannot mutate findings, status or release approval.
No Cognee memory writes or simulated legacy agent fallbacks. If the model
is unavailable, the report records that instead of claiming AI success.

Current provider calls have a bounded wait, but background Python threads
cannot be forcibly stopped when the provider hangs. Implement queue-based
worker scheduling, quotas and cancellation before production rollout.

## Known scope limits

No exploitation, penetration testing, autonomous patching, customer signup,
tenant separation, source analysis, full user journeys or release certification.
A good review does not prove the underlying site is secure.

Stage 1–3 live staging verification on an operator-approved application remains
outstanding. A real egress-isolated worker and customer authorization must
precede any public scanner deployment. Stage 4 cannot remedy this.

The existing exposed legacy Cognee credential has not been changed in this
stage and still needs urgent revocation and rotation.

## Acceptance / CI

- All Stages 1–4 offline Python regression tests pass.
- Real Chromium offline screenshot smoke passes.
- Existing React production build passes.
- Original eight-agent routes and project flows remain intact.
- Manually verify a review built from a real authorized staging scan.
- Explicit owner merge approval is required.
