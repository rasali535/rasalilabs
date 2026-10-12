# Stage 6A deployment triage — root runtime dependencies

## Verified facts, 2026-10-12

- GitHub Stages 1–6A CI passed, including frontend React production build.
- Vercel **production deployment for Stage 6A merge fff6313 is READY**.
  Inspector: https://vercel.com/alis-projects-635e952f/rasalilabs/2MMvC7WHaYTgJP1N2RMpwhZooF3C
- The newest security-checkpoint **preview** is ERROR with `git_info_fail`,
  meaning Vercel failed to resolve Git/deployment metadata; it does not
  demonstrate a React compilation error.
- Previous security-checkpoint preview deployment was READY.
- **Root requirements.txt** was missing bcrypt, PyJWT and dnspython,
  despite imports from backend/testing_centre/tenant_auth.py and
  workspace_router.py. Vercel's api/index.py imports backend.server, which
  includes the Stage 6A workspace router. If the host uses root
  requirements.txt, runtime imports could crash with ModuleNotFoundError.
- No Render workspace was selected and no Render deployment logs were
  inspected. **The Render root cause remains UNCONFIRMED.**

## Fix in this PR

- Pins all dependencies required to import the Stage 6A backend in root
  requirements.txt, aligned to the backend runtime manifest.
- Adds clean-environment CI installing ONLY root requirements and importing
  api.index (Vercel entrypoint), checking customer and operator route wiring.
- Does NOT add Chromium to serverless: Playwright remains a separately
  gated isolated-worker concern.

## Render configuration to inspect

In the correct Render service, check:
- Git repo `rasali535/rasalilabs`, branch `main`, and Stage 6A SHA
  `fff6313690b03edd256adb410b26e4592d061696`.
- Correct root directory and build command. If building from the repo root,
  install `pip install -r requirements.txt`. If using backend as root,
  use `backend/requirements.txt` with a compatible Python runtime.
  Don't guess or change current commands without checking actual logs.
- Start command should point at `backend.server:app` when run from the
  repository root with a suitable Uvicorn runtime.
- Look for `ModuleNotFoundError`, dependency resolver conflict, Python
  version mismatch, startup timeout, missing MongoDB access, or application
  error in Render deploy + build logs.
- Do not turn on customer auth, scan submissions or security workers just
  to fix import errors.

## Vercel configuration to inspect

- The product is configured as Create React App on Vercel, with
  `api/index.py` importing FastAPI and root `vercel.json` API rewrites.
- For `git_info_fail`, check the Vercel Git integration and repository
  installation permissions, and retry deployment only after verifying
  the intended team/project/commit. This issue is not fixed by Python
  package changes. Preview build logs may be unavailable for this failure.
- Check the selected frontend root directory and build/output settings
  if the deployed React app is blank even though the deployment is READY.
- A READY build is not the same as a tested functioning HTTP API.

## Non-actions and outstanding checks

No deploy, merge, Render config mutation, Vercel environment change,
credential transfer or production endpoint request was performed here.
The Stage 6A live staging acceptance test and restricted network worker
deployment remain pending. Preserve independent testing/workspace auth
and original agent boardroom while evaluating this hotfix.

Owner must approve merging. If Render logs reveal a different problem,
fix it on a follow-up reviewable PR, not by unreviewed production changes.
