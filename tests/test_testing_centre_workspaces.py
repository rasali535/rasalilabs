"""Stage 6A customer isolation tests; no DNS, GitHub or live scan traffic."""
import asyncio
import os
from copy import deepcopy

import bcrypt
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from pymongo.errors import DuplicateKeyError

from backend.testing_centre.tenant_auth import (
    Registration, Login, create_registration, log_in, issue_token, utcnow,
)
from backend.testing_centre.workspace_router import workspace_router


class Cursor:
    def __init__(self, docs):
        self.docs = docs

    def sort(self, key, direction=-1):
        self.docs.sort(key=lambda d: d.get(key, ""), reverse=(direction == -1))
        return self

    async def to_list(self, size):
        return deepcopy(self.docs[:size])


class Collection:
    def __init__(self):
        self.docs = []
        self.indices = []

    async def create_index(self, fields, unique=False):
        self.indices.append((fields, unique))

    @staticmethod
    def matches(d, q):
        for key, val in q.items():
            if key == "$or":
                if not any(Collection.matches(d, inner) for inner in val):
                    return False
            elif isinstance(val, dict):
                if "$in" in val:
                    if d.get(key) not in val["$in"]:
                        return False
                elif "$lt" in val:
                    if not d.get(key, 0) < val["$lt"]:
                        return False
                elif "$lte" in val:
                    if not d.get(key, 0) <= val["$lte"]:
                        return False
                elif "$gte" in val:
                    if not d.get(key, 0) >= val["$gte"]:
                        return False
                else:
                    raise AssertionError("Unsupported query " + str(val))
            elif d.get(key) != val:
                return False
        return True

    async def find_one(self, query, *_args):
        return deepcopy(next((d for d in self.docs if self.matches(d, query)), None))

    def find(self, query, *_args):
        return Cursor([deepcopy(d) for d in self.docs if self.matches(d, query)])

    async def count_documents(self, query):
        return sum(1 for d in self.docs if self.matches(d, query))

    async def insert_one(self, value):
        if "email" in value and any(x.get("email") == value["email"] for x in self.docs):
            raise DuplicateKeyError("unique email")
        if "hostname" in value and any(x.get("hostname") == value["hostname"] and
                                       x.get("workspace_id") == value.get("workspace_id")
                                       for x in self.docs):
            raise DuplicateKeyError("unique workspace hostname")
        self.docs.append(deepcopy(value))

    async def update_one(self, query, change):
        for doc in self.docs:
            if self.matches(doc, query):
                doc.update(deepcopy(change.get("$set", {})))
                return type("Result", (), {"modified_count": 1})()
        return type("Result", (), {"modified_count": 0})()


class FakeDatabase:
    _is_mock = False

    def __init__(self):
        self.testing_users = Collection()
        self.testing_workspaces = Collection()
        self.testing_memberships = Collection()
        self.testing_domains = Collection()
        self.testing_jobs = Collection()


INVITE = "i" * 44
JWT_SECRET = "v" * 64


def setup(monkeypatch, *, signup=True):
    monkeypatch.setenv("TESTING_WORKSPACE_AUTH_ENABLED", "true")
    monkeypatch.setenv("TESTING_WORKSPACE_JWT_SECRET", JWT_SECRET)
    monkeypatch.setenv("TESTING_WORKSPACE_SIGNUP_ENABLED", "true" if signup else "false")
    monkeypatch.setenv("TESTING_WORKSPACE_INVITE_SECRET", INVITE)


def create_client(db, dns=None):
    app = FastAPI()
    app.include_router(workspace_router(db, dns_lookup=dns))
    return TestClient(app)


def register(client, email, company):
    r = client.post("/customer-testing/auth/register", json={
        "email": email, "password": "VeryLongTestPass123!",
        "workspace_name": company, "invitation_code": INVITE,
    })
    assert r.status_code == 201, r.text
    return r.json()["workspace_id"]


def login(client, email):
    r = client.post("/customer-testing/auth/login", json={
        "email": email, "password": "VeryLongTestPass123!",
    })
    assert r.status_code == 200, r.text
    return {"Authorization": "Bearer " + r.json()["access_token"]}


def test_default_disabled_and_no_mock(monkeypatch):
    monkeypatch.delenv("TESTING_WORKSPACE_AUTH_ENABLED", raising=False)
    with create_client(FakeDatabase()) as client:
        assert client.get("/customer-testing/availability").status_code == 503
    setup(monkeypatch)
    db = FakeDatabase()
    db._is_mock = True
    with create_client(db) as client:
        assert client.get("/customer-testing/availability").status_code == 503


def test_invite_registration_password_and_revocable_token(monkeypatch):
    setup(monkeypatch)
    db = FakeDatabase()
    with create_client(db) as client:
        response = client.post("/customer-testing/auth/register", json={
            "email": "a@example.com", "password": "VeryLongTestPass123!",
            "workspace_name": "Agency One", "invitation_code": "wrong",
        })
        assert response.status_code == 403
        wid = register(client, "A@Example.com", "Agency One")
        assert client.post("/customer-testing/auth/register", json={
            "email": "A@Example.com", "password": "VeryLongTestPass123!",
            "workspace_name": "Other", "invitation_code": INVITE,
        }).status_code == 409
        account = db.testing_users.docs[0]
        assert account["email"] == "a@example.com"
        assert "VeryLongTestPass123!" not in str(account)
        assert bcrypt.checkpw(b"VeryLongTestPass123!", account["password_hash"].encode())
        bad = client.post("/customer-testing/auth/login", json={
            "email": "a@example.com", "password": "wrong",
        })
        assert bad.status_code == 401
        headers = login(client, "a@example.com")
        assert client.get("/customer-testing/auth/me", headers=headers).status_code == 200
        items = client.get("/customer-testing/workspaces", headers=headers).json()
        assert len(items) == 1 and items[0]["id"] == wid
        db.testing_users.docs[0]["token_version"] = 2
        assert client.get("/customer-testing/workspaces", headers=headers).status_code == 401


def test_separate_workspaces_and_cross_tenant_denial(monkeypatch):
    setup(monkeypatch)
    db = FakeDatabase()
    with create_client(db) as client:
        wa = register(client, "a@example.com", "Alpha")
        wb = register(client, "b@example.com", "Beta")
        ha, hb = login(client, "a@example.com"), login(client, "b@example.com")
        a = {**ha, "X-Workspace-ID": wa}
        b = {**hb, "X-Workspace-ID": wb}
        cross = {**ha, "X-Workspace-ID": wb}
        d = client.post("/customer-testing/domains", headers=a, json={"hostname": "owned.example.com"})
        assert d.status_code == 201, d.text
        did = d.json()["id"]
        assert client.get("/customer-testing/domains", headers=cross).status_code == 404
        assert client.get("/customer-testing/jobs", headers=cross).status_code == 404
        assert client.get("/customer-testing/jobs", headers=b).json() == []
        assert client.post("/customer-testing/domains/" + did + "/verify",
                           headers=b).status_code == 404
        assert client.post("/customer-testing/jobs", headers=cross, json={
            "domain_id": did, "url": "https://owned.example.com/",
        }).status_code == 404
        assert client.get("/customer-testing/domains", headers=b).json() == []


def test_dns_txt_owner_scope_required_before_job(monkeypatch):
    setup(monkeypatch)
    db = FakeDatabase()
    async def dns(name):
        assert name == "_rasalilabs-verify.site.example.com"
        return ["rasalilabs-verification=" + db.testing_domains.docs[0]["verification_token"]]

    with create_client(db, dns=dns) as client:
        wid = register(client, "owner@example.com", "Owner")
        headers = {**login(client, "owner@example.com"), "X-Workspace-ID": wid}
        data = client.post("/customer-testing/domains", headers=headers,
                           json={"hostname": "site.example.com"}).json()
        denied = client.post("/customer-testing/jobs", headers=headers, json={
            "domain_id": data["id"], "url": "https://site.example.com/",
        })
        assert denied.status_code == 403
        verified = client.post("/customer-testing/domains/" + data["id"] + "/verify",
                               headers=headers)
        assert verified.status_code == 200
        doc = client.get("/customer-testing/domains", headers=headers).json()[0]
        assert doc["challenge_value"] == "rasalilabs-verification=" + db.testing_domains.docs[0]["verification_token"]
        # Replace resolver for deterministic DNS allowlist validation.
        from backend.testing_centre import workspace_router as workspace_module
        original = workspace_module.validate_target
        async def safe(url, hosts):
            assert hosts == frozenset({"site.example.com"})
            if "other" in url:
                raise ValueError("Forbidden")
            return url, "site.example.com"
        workspace_module.validate_target = safe
        try:
            queued = client.post("/customer-testing/jobs", headers=headers, json={
                "domain_id": data["id"], "url": "https://site.example.com/",
            })
            assert queued.status_code == 202, queued.text
            assert queued.json()["status"] == "queued"
            assert queued.json()["result"] is None
            got = client.get("/customer-testing/jobs/" + queued.json()["id"], headers=headers)
            assert got.status_code == 200
            assert got.json()["workspace_id"] == wid
            invalid = client.post("/customer-testing/jobs", headers=headers, json={
                "domain_id": data["id"], "url": "https://other.example.com/",
            })
            assert invalid.status_code == 422
            unsupported = client.post("/customer-testing/jobs", headers=headers, json={
                "domain_id": data["id"], "url": "https://site.example.com/",
                "test_type": "browser_smoke",
            })
            assert unsupported.status_code == 422
        finally:
            workspace_module.validate_target = original


def test_worker_queue_gate_rejects_mock_mode_and_uninitialized_indexes(monkeypatch):
    setup(monkeypatch)
    db = FakeDatabase()
    with create_client(db) as client:
        assert client.get("/customer-testing/availability").status_code == 200
        assert len(db.testing_users.indices) > 0
    monkeypatch.delenv("TESTING_WORKSPACE_JWT_SECRET", raising=False)
    with create_client(FakeDatabase()) as client:
        assert client.get("/customer-testing/availability").status_code == 503
