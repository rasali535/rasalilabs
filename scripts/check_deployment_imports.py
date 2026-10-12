"""Import smoke in a CLEAN Python environment with only root requirements.

Catches serverless/Render crashes caused by a missing top-level dependency.
Do not run real scans, migrations, external network requests or startup hooks.
"""
import importlib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
source = (ROOT / "requirements.txt").read_text(encoding="utf-8")
pins = {
    line.split("==", 1)[0].strip().lower()
    for line in source.splitlines()
    if "==" in line and not line.startswith("#")
}
required = {
    "fastapi", "uvicorn", "python-dotenv", "motor", "pymongo",
    "httpx", "pydantic", "openai", "fpdf2",
    "bcrypt", "pyjwt", "dnspython",
}
missing = sorted(required - pins)
if missing:
    raise SystemExit("Missing pinned runtime dependencies: " + ", ".join(missing))

for mod in ("bcrypt", "jwt", "dns.asyncresolver", "motor.motor_asyncio",
            "pymongo", "httpx", "fastapi", "pydantic"):
    importlib.import_module(mod)

api = importlib.import_module("api.index")
app = api.app
paths = {getattr(route, "path", "") for route in app.routes}
for path in (
    "/api/health",
    "/api/agents",
    "/api/testing/config",
    "/api/customer-testing/auth/login",
    "/api/customer-testing/workspaces",
    "/api/customer-testing/jobs",
):
    if path not in paths:
        raise SystemExit("Backend route missing from deployment entrypoint: " + path)

print("Deployment entrypoint imports with root requirements: PASS")
print("Stage 6A customer and legacy API routes registered: PASS")
print("Real Render/Vercel deployment or network validation: NOT TESTED")
