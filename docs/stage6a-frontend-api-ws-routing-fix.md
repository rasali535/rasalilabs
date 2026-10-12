# Ras Ali Labs — Frontend API routing / WebSocket / Testing Centre 503 repair

## Observed problem (12 Oct 2026)

Browser console:
- `wss://rasalilabs.onrender.com/api/ws/{project_id}` disconnect/failure
- `rasalilabs.onrender.com/api/testing/config` returns 503
- `rasalilabs.onrender.com/api/testing/scans` returns 503

The Vercel `rasalilabs` project's production build was built from `main`
(commit `bac1898`) and did **not** have any REACT_APP_BACKEND_URL env
variable. The old `frontend/src/lib/api.js` default for Vercel sites
hardcoded `https://rasalilabs.onrender.com`, hosted in a *different* Render
profile.

The new secured API is
`https://rasalilabs-api-staging.onrender.com`.
It runs from the hardened Stage 6A feature branch on the connected Render
profile, has MongoDB Atlas connectivity, and uses a separate private operator
unlock. The staging API is **not public-customer-ready**.

## Fix delivered

- The frontend uses an explicit build-time `REACT_APP_BACKEND_URL`, otherwise
  the known **secured staging API**, never the outdated Render hostname.
  The REST and WebSocket URL are based on this same backend.
- The private Models screen and agent ChatDrawer mount ONLY after operator
  unlock, so locked sessions cannot accidentally fetch protected content.
- ChatDrawer uses the shared Axios client, including operator authentication,
  rather than making uncredentialed axios requests.
- Testing Centre checks `/testing/config` *before* fetching scans. If disabled,
  it displays an actionable explanation rather than sending two 503 requests.
- Tests and CI reject a compiled JavaScript bundle referencing the old host.

The new Render staging API's **explicit** HTTP CORS and WebSocket origins were
extended to include the actual official `https://rasalilabs.vercel.app`.
The existing rasalilabs.com/www entries remain intact; no wildcard preview
origins were permitted.

## Important boundaries

- `TESTING_CENTRE_ENABLED` remains **false**. The Testing Centre API returning
  503 is the correct fail-closed behavior until a scoped token, allowed hosts,
  DNS ownership controls and isolated execution worker are verified. No
  security scanning was enabled in this fix.
- The `X-Legacy-Operator-Token` is **different** from `X-Testing-Token`.
  Private AI-agent models/boardroom require the former; operator testing
  requires both proper opt-in and the latter.
- Vercel builds with `REACT_APP_BACKEND_URL` baked into the React JS bundle.
  Changing environment variables after build requires a new deployment.
- To use a different backend for production in the future, set the
  `REACT_APP_BACKEND_URL` Vercel environment variable to the intended
  secure HTTPS API origin and deploy after review. Never place credentials
  in frontend env vars.
- Branch deployment previews use distinct `*.vercel.app` origins. Each preview
  origin must be explicitly approved on staging for CORS/WS testing; do not
  open CORS to wildcard `*.vercel.app`.
- The existing `vercel.json` has a same-origin FastAPI route; this patch
  routes the React client explicitly to the secured Render API instead,
  preventing accidental use of the unconfigured Vercel serverless backend.

## Manual rollout acceptance (pending)

1. Review and merge this PR only after owner approval and green CI.
2. Vercel should build the new `main`. Refresh the browser so the old cached
   `main.19cdb0bd.js` is replaced.
3. Confirm Network endpoints use
   `rasalilabs-api-staging.onrender.com` for `/api/legacy-access/status`,
   private model/boardroom requests, and `wss://` Boardroom.
4. Confirm old backend is never contacted by the React app.
5. Unlock the original eight-agent UI with the actual Render operator token
   (configured securely in the connected Render account). Do not paste it
   into code, chats, or PR comments.
6. Confirm CORS origin allowed, HTTP 401 when logged out, and protected WS
   refuses unauthenticated/foreign origins, and succeeds after unlocking.
7. Verify Mongo persistence, current project/meeting IDs, and confirm whether
   old and new backends use the intended same Atlas database name.
8. Operator Testing Centre may still respond 503; show the disabled notice
   rather than enabling scanners prematurely.

**Do not enable customer signups, unisolated browser scans, public GitHub
repair publishing or security testing as part of this fix.**
