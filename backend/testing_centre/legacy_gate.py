"""Opt-in legacy agent operator API boundary for Stage 6A.

Existing agent routes have no tenant isolation. This is a single-operator
lock, NOT a multi-tenant user authentication system. Customer endpoints
remain separate and do not gain access to boardroom data.
"""
import os
import re
import secrets
from urllib.parse import urlsplit

from starlette.responses import JSONResponse

TOKEN_HEADER = b"x-legacy-operator-token"
WS_PROTOCOL = "rasali-operator."
EXEMPT = frozenset({
    "/api", "/api/", "/api/health", "/api/logo", "/api/legacy-access/status",
    "/api/legacy-access/check",
})
EXEMPT_PREFIXES = ("/api/customer-testing/", "/api/testing/")


def gate_enforced():
    # A customer-facing deployment MUST NOT expose unguarded legacy agents.
    return (
        os.getenv("LEGACY_OPERATOR_AUTH_ENFORCED", "false").lower() == "true"
        or os.getenv("TESTING_WORKSPACE_AUTH_ENABLED", "false").lower() == "true"
    )


def operator_configured():
    secret = os.getenv("LEGACY_OPERATOR_TOKEN", "")
    # Avoid known development strings; this must be an independent secret.
    return (bool(re.fullmatch(r"[A-Za-z0-9_-]{48,128}", secret)) and
            secret.lower() not in ("changeme", "change-me", "development") and
            secret != os.getenv("TESTING_ACCESS_TOKEN", "\x00") and
            secret != os.getenv("TESTING_WORKSPACE_JWT_SECRET", "\x00"))


def validate_operator_token(token):
    if not gate_enforced():
        return True
    expected = os.getenv("LEGACY_OPERATOR_TOKEN", "")
    return operator_configured() and isinstance(token, str) and secrets.compare_digest(token, expected)


def request_guarded(path):
    if not path.startswith("/api/"):
        return False
    if path in EXEMPT:
        return False
    return not any(path.startswith(prefix) for prefix in EXEMPT_PREFIXES)


def ws_origin_allowed(scope):
    allowed = {x.strip() for x in os.getenv(
        "LEGACY_OPERATOR_ALLOWED_WS_ORIGINS", ""
    ).split(",") if x.strip()}
    # For enforced mode WebSocket origin must be explicitly configured.
    if not allowed:
        return False
    headers = dict(scope.get("headers") or [])
    raw = headers.get(b"origin", b"")
    try:
        origin = raw.decode("ascii")
        p = urlsplit(origin)
        if p.scheme not in ("https", "http") or p.username or p.password or p.path not in ("", "/"):
            return False
    except (UnicodeDecodeError, ValueError):
        return False
    return origin in allowed


class LegacyOperatorGate:
    """ASGI middleware protecting *all* legacy HTTP and WebSocket endpoints.

    Starlette/HTTP middleware alone would not guard WebSocket endpoints.
    No token is accepted in a query string or logged to the response.
    """

    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if not gate_enforced() or scope["type"] not in ("http", "websocket"):
            return await self.app(scope, receive, send)
        path = scope.get("path", "")
        if not request_guarded(path):
            return await self.app(scope, receive, send)
        headers = dict(scope.get("headers") or [])
        if scope["type"] == "http":
            if scope.get("method") == "OPTIONS":
                # CORS preflight does not execute the actual protected route.
                return await self.app(scope, receive, send)
            raw = headers.get(TOKEN_HEADER, b"")
            try:
                provided = raw.decode("ascii")
            except UnicodeDecodeError:
                provided = ""
            if not operator_configured():
                return await JSONResponse({"detail": "Legacy operator API is unavailable."}, status_code=503)(
                    scope, receive, send,
                )
            if not validate_operator_token(provided):
                return await JSONResponse({"detail": "Legacy operator access required."}, status_code=401)(
                    scope, receive, send,
                )
            return await self.app(scope, receive, send)

        # Browser WebSockets cannot set custom HTTP headers. Use a WebSocket
        # subprotocol value instead of a URL query; verify Origin as well.
        protocols = []
        for k, v in scope.get("headers") or []:
            if k == b"sec-websocket-protocol":
                try:
                    protocols.extend(x.strip() for x in v.decode("ascii").split(","))
                except UnicodeDecodeError:
                    pass
        offered = [x[len(WS_PROTOCOL):] for x in protocols if x.startswith(WS_PROTOCOL)]
        allowed = (
            operator_configured() and ws_origin_allowed(scope) and
            len(offered) == 1 and validate_operator_token(offered[0])
        )
        if not allowed:
            # Close before websocket.accept: no resource streams escape.
            return await send({"type": "websocket.close", "code": 4403})
        return await self.app(scope, receive, send)
