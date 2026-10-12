"""Stage 6A: isolated customer identity for Testing Centre (not legacy agents).

Invite-only registration, bcrypt passwords, short-lived signed bearer sessions.
Authorization checks membership on every workspace request. Disabled by default.
"""
import os
import re
import secrets
import uuid
from datetime import datetime, timedelta, timezone
from typing import Optional

import bcrypt
import jwt
from fastapi import Depends, Header, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import BaseModel, Field
from pymongo.errors import DuplicateKeyError

EMAIL_RE = re.compile(r"^[^\s@]{1,64}@[^\s@]{1,190}\.[^\s@]{2,63}$")
JWT_ALGORITHM = "HS256"
ISSUER = "rasalilabs-workspace-testing"
AUDIENCE = "rasalilabs-testing-api"
bearer = HTTPBearer(auto_error=False)


def utcnow():
    return datetime.now(timezone.utc)


def enabled():
    return os.getenv("TESTING_WORKSPACE_AUTH_ENABLED", "false").lower() == "true"


def ensure_config(db):
    if not enabled():
        raise HTTPException(503, "Customer Testing Centre is disabled.")
    if getattr(db, "_is_mock", False):
        raise HTTPException(503, "Persistent database is required.")
    secret = os.getenv("TESTING_WORKSPACE_JWT_SECRET", "")
    if len(secret.encode("utf-8")) < 48 or secret.lower() in ("change-me", "changeme"):
        raise HTTPException(503, "Workspace signing configuration is unavailable.")
    return secret


class Registration(BaseModel):
    email: str = Field(min_length=6, max_length=255)
    password: str = Field(min_length=12, max_length=72)
    workspace_name: str = Field(min_length=2, max_length=80)
    invitation_code: str = Field(min_length=1, max_length=150)


class Login(BaseModel):
    email: str = Field(min_length=6, max_length=255)
    password: str = Field(min_length=1, max_length=150)


class WorkspaceCreate(BaseModel):
    name: str = Field(min_length=2, max_length=80)


def normalize_email(value):
    email = value.strip().lower()
    if not EMAIL_RE.fullmatch(email):
        raise HTTPException(422, "Invalid email address.")
    return email


def password_bytes(password):
    raw = password.encode("utf-8")
    if len(raw) > 72:
        raise HTTPException(422, "Password must be no more than 72 UTF-8 bytes.")
    return raw


async def create_registration(db, data):
    ensure_config(db)
    if os.getenv("TESTING_WORKSPACE_SIGNUP_ENABLED", "false").lower() != "true":
        raise HTTPException(503, "Customer registration is not enabled.")
    invite = os.getenv("TESTING_WORKSPACE_INVITE_SECRET", "")
    if len(invite) < 32 or not secrets.compare_digest(data.invitation_code, invite):
        raise HTTPException(403, "Invitation not valid.")
    email = normalize_email(data.email)
    password = password_bytes(data.password)
    uid = str(uuid.uuid4())
    wid = str(uuid.uuid4())
    now = utcnow().isoformat()
    account = {
        "id": uid, "email": email,
        "password_hash": bcrypt.hashpw(password, bcrypt.gensalt(rounds=12)).decode(),
        "token_version": 1, "disabled": False, "created_at": now,
    }
    workspace = {
        "id": wid, "name": data.workspace_name.strip(), "owner_id": uid,
        "created_at": now, "status": "active",
    }
    membership = {"id": str(uuid.uuid4()), "user_id": uid,
                  "workspace_id": wid, "role": "owner", "status": "active"}
    try:
        await db.testing_users.insert_one(account)
    except DuplicateKeyError as exc:
        raise HTTPException(409, "Account already registered.") from exc
    except Exception as exc:
        raise HTTPException(503, "Registration persistence unavailable.") from exc
    # These writes are not multi-document atomic on standalone Mongo deployments:
    # on partial failure, deny access and require manual reconciliation.
    try:
        await db.testing_workspaces.insert_one(workspace)
        await db.testing_memberships.insert_one(membership)
    except Exception as exc:
        raise HTTPException(503, "Account initialization incomplete. Contact support.") from exc
    return {"registered": True, "workspace_id": wid}


def issue_token(user, secret):
    now = utcnow()
    return jwt.encode({
        "iss": ISSUER, "aud": AUDIENCE, "sub": user["id"],
        "ver": user["token_version"], "iat": now,
        "nbf": now, "exp": now + timedelta(minutes=30),
        "jti": str(uuid.uuid4()),
    }, secret, algorithm=JWT_ALGORITHM)


async def log_in(db, data):
    secret = ensure_config(db)
    email = normalize_email(data.email)
    try:
        account = await db.testing_users.find_one({"email": email}, {"_id": 0})
    except Exception as exc:
        raise HTTPException(503, "Account lookup unavailable.") from exc
    stored = (account or {}).get("password_hash")
    # Run bcrypt even for unknown accounts to limit user enumeration by timing.
    dummy = "$2b$12$N9qo8uLOickgx2ZMRZoMye7HbuYQv.RGAF.P6l8YxZdWv4J4wzW3G"
    digest = stored or dummy
    try:
        good = bcrypt.checkpw(password_bytes(data.password), digest.encode())
    except (ValueError, TypeError):
        good = False
    if not account or account.get("disabled") or not good:
        raise HTTPException(401, "Invalid credentials.")
    return {"access_token": issue_token(account, secret),
            "token_type": "bearer", "expires_in": 1800}


def create_identity_dependencies(db):
    async def current_user(credentials: Optional[HTTPAuthorizationCredentials] = Depends(bearer)):
        secret = ensure_config(db)
        if credentials is None or credentials.scheme.lower() != "bearer":
            raise HTTPException(401, "Customer sign-in required.")
        try:
            payload = jwt.decode(
                credentials.credentials, secret,
                algorithms=[JWT_ALGORITHM], audience=AUDIENCE, issuer=ISSUER,
                options={"require": ["sub", "iss", "aud", "exp", "iat", "nbf", "jti", "ver"]},
                leeway=5,
            )
            uid = payload["sub"]
            if not isinstance(uid, str) or len(uid) > 90:
                raise ValueError("Invalid subject.")
            account = await db.testing_users.find_one({"id": uid}, {"_id": 0})
        except (jwt.InvalidTokenError, ValueError, TypeError) as exc:
            raise HTTPException(401, "Session invalid or expired.") from exc
        except Exception as exc:
            raise HTTPException(503, "Session validation unavailable.") from exc
        if not account or account.get("disabled") or account.get("token_version") != payload.get("ver"):
            raise HTTPException(401, "Session revoked or expired.")
        return {"id": uid, "email": account["email"]}

    async def workspace_access(
        user=Depends(current_user),
        x_workspace_id: str = Header(default="", alias="X-Workspace-ID"),
    ):
        if not x_workspace_id or len(x_workspace_id) > 90:
            raise HTTPException(400, "Select a workspace.")
        try:
            member = await db.testing_memberships.find_one({
                "user_id": user["id"], "workspace_id": x_workspace_id,
                "status": "active",
            }, {"_id": 0})
            workspace = await db.testing_workspaces.find_one({
                "id": x_workspace_id, "status": "active",
            }, {"_id": 0})
        except Exception as exc:
            raise HTTPException(503, "Workspace authorization unavailable.") from exc
        if not member or not workspace:
            # No disclosure of whether a foreign workspace exists.
            raise HTTPException(404, "Workspace not found.")
        return {"user": user, "workspace_id": x_workspace_id, "role": member["role"]}

    return current_user, workspace_access


async def ensure_indexes(db):
    """Must succeed before accepting signups/jobs; invoke on startup."""
    await db.testing_users.create_index("email", unique=True)
    await db.testing_users.create_index("id", unique=True)
    await db.testing_workspaces.create_index("id", unique=True)
    await db.testing_memberships.create_index(
        [("workspace_id", 1), ("user_id", 1)], unique=True)
    await db.testing_domains.create_index(
        [("workspace_id", 1), ("hostname", 1)], unique=True)
    await db.testing_jobs.create_index("id", unique=True)
    await db.testing_jobs.create_index(
        [("workspace_id", 1), ("created_at", -1)])
    await db.testing_jobs.create_index(
        [("status", 1), ("lease_until", 1), ("created_at", 1)])
