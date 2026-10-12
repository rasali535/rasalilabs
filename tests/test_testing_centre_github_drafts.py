"""Draft PR safety gates and real mocked GitHub request sequence (no network)."""
import asyncio
import base64
from types import SimpleNamespace

import httpx
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from backend.testing_centre.github_drafts import (
    GitHubDraftPublisher, GitHubPublishError,
    publisher_configured, validate_publishing_input,
)
from backend.testing_centre.router import create_testing_router
from tests.test_testing_centre import FakeDB, TOKEN, setup_config
from tests.test_testing_centre_repairs import RepairCollection, build_repair_case, scan


BLOB = "a" * 40
HEAD = "b" * 40
APPROVAL = "r" * 40


def setup_git(monkeypatch):
    monkeypatch.setenv("TESTING_REPAIR_GITHUB_ENABLED", "true")
    monkeypatch.setenv("TESTING_REPAIR_SCOPE_ACK", "true")
    monkeypatch.setenv("TESTING_REPAIR_REPO", "rasali535/rasalilabs")
    monkeypatch.setenv("TESTING_REPAIR_APPROVAL_TOKEN", APPROVAL)
    monkeypatch.setenv("TESTING_GITHUB_TOKEN", "integration-test-token")


def test_git_publishing_disabled_by_default_and_input_is_strict(monkeypatch):
    monkeypatch.delenv("TESTING_REPAIR_GITHUB_ENABLED", raising=False)
    assert publisher_configured() is False
    setup_git(monkeypatch)
    assert publisher_configured() is True
    validate_publishing_input("rasali535/rasalilabs",
        "frontend/src/App.jsx", BLOB, "export default function App() {}")
    bad_paths = [
        ".github/workflows/deploy.yml", "src/../../.env", "/src/App.jsx",
        "backend/server.py", "backend/auth.py", "src/config.py",
        "src/node_modules/index.js", "frontend/src/.env", "src/file.txt",
        "src//bad.js", "docs/readme.md",
    ]
    for path in bad_paths:
        with pytest.raises(ValueError):
            validate_publishing_input("rasali535/rasalilabs", path, BLOB, "valid")
    with pytest.raises(ValueError):
        validate_publishing_input("someone-else/ralion", "src/a.js", BLOB, "valid")
    with pytest.raises(ValueError):
        validate_publishing_input("rasali535/rasalilabs", "src/app.js", "broken", "valid")
    with pytest.raises(ValueError):
        validate_publishing_input("rasali535/rasalilabs", "src/app.js", BLOB, "x" * 48001)


def test_publisher_creates_only_draft_from_unchanged_main_and_approved_source(monkeypatch):
    setup_git(monkeypatch)
    case = build_repair_case(scan(), "f1")
    case["status"] = "publishing"
    calls = []
    replacement = "export default function Fixed(){return null}\n"

    def handler(req):
        calls.append((req.method, str(req.url), req.content))
        if req.method == "GET" and req.url.path.endswith("/git/ref/heads/main"):
            return httpx.Response(200, json={"object": {"sha": HEAD}})
        if req.method == "GET" and "/contents/" in req.url.path:
            assert req.url.params["ref"] == "main"
            return httpx.Response(200, json={"sha": BLOB, "type": "file"})
        if req.method == "POST" and req.url.path.endswith("/git/refs"):
            return httpx.Response(201, json={"ref": "refs/heads/repair"})
        if req.method == "PUT" and "/contents/" in req.url.path:
            data = __import__("json").loads(req.content)
            assert data["sha"] == BLOB
            assert base64.b64decode(data["content"]).decode() == replacement
            assert data["branch"].startswith("repair/")
            return httpx.Response(200, json={"content": {"sha": "c" * 40}})
        if req.method == "POST" and req.url.path.endswith("/pulls"):
            data = __import__("json").loads(req.content)
            assert data["draft"] is True
            assert data["base"] == "main"
            assert data["head"].startswith("repair/")
            return httpx.Response(201, json={"number": 27, "draft": True,
                "html_url": "https://github.com/rasali535/rasalilabs/pull/27"})
        raise AssertionError("Unexpected GitHub action: " + str(req.url))

    transport = httpx.MockTransport(handler)
    factory = lambda **kw: httpx.AsyncClient(transport=transport, **kw)
    publisher = GitHubDraftPublisher("fake-token", client_factory=factory)
    pr = asyncio.run(publisher.publish(
        case, "rasali535/rasalilabs", "frontend/src/App.jsx", BLOB, replacement))
    assert pr["draft"] is True
    assert pr["url"].endswith("/pull/27")
    assert [row[0] for row in calls] == ["GET", "GET", "POST", "PUT", "POST"]
    assert all("github.com" in url for _, url, _ in calls)
    assert all("/merges" not in url and "/deployments" not in url for _, url, _ in calls)


def test_changed_blob_prevents_branch_and_pr(monkeypatch):
    setup_git(monkeypatch)
    case = build_repair_case(scan(), "f1")
    case["status"] = "publishing"
    paths = []

    def handler(req):
        paths.append(req.url.path)
        if req.url.path.endswith("/git/ref/heads/main"):
            return httpx.Response(200, json={"object": {"sha": HEAD}})
        if "/contents/" in req.url.path:
            return httpx.Response(200, json={"sha": "d" * 40, "type": "file"})
        raise AssertionError("No writes permitted on stale base")

    factory = lambda **kw: httpx.AsyncClient(transport=httpx.MockTransport(handler), **kw)
    publisher = GitHubDraftPublisher("fake-token", client_factory=factory)
    with pytest.raises(GitHubPublishError, match="Refresh and reapprove"):
        asyncio.run(publisher.publish(
            case, "rasali535/rasalilabs", "frontend/src/App.jsx", BLOB, "valid"))
    assert len(paths) == 2


def test_separate_approval_token_and_atomic_one_time_route(monkeypatch):
    setup_config(monkeypatch)
    setup_git(monkeypatch)
    db = FakeDB()
    db.testing_repairs = RepairCollection()
    case = build_repair_case(scan(), "f1")
    db.testing_repairs.docs.append(case)
    db.testing_scans.docs.append(scan())

    called = []
    class FakePublisher:
        def __init__(self, _token):
            pass

        async def publish(self, case_arg, repo, path, blob, source):
            called.append((case_arg["status"], repo, path, blob, source))
            return {"draft": True, "url": "https://github.com/rasali535/rasalilabs/pull/99",
                    "number": 99, "repo": repo, "branch": "repair/test", "base": "main"}

    monkeypatch.setattr("backend.testing_centre.router.GitHubDraftPublisher", FakePublisher)
    app = FastAPI()
    app.include_router(create_testing_router(db), prefix="/api")
    client = TestClient(app)
    payload = {
        "repo": "rasali535/rasalilabs", "file_path": "frontend/src/App.jsx",
        "expected_blob_sha": BLOB, "new_source": "export default function App(){}",
        "approval_phrase": "CREATE DRAFT PR",
    }
    auth = {"X-Testing-Token": TOKEN}
    assert client.post("/api/testing/repairs/" + case["id"] + "/publish-pr",
                       headers=auth, json=payload).status_code == 403
    wrong_approval = {**auth, "X-Repair-Approval-Token": "wrong"}
    assert client.post("/api/testing/repairs/" + case["id"] + "/publish-pr",
                       headers=wrong_approval, json=payload).status_code == 403
    approved = {**auth, "X-Repair-Approval-Token": APPROVAL}
    no_phrase = {**payload, "approval_phrase": "merge it"}
    assert client.post("/api/testing/repairs/" + case["id"] + "/publish-pr",
                       headers=approved, json=no_phrase).status_code == 422
    successful = client.post("/api/testing/repairs/" + case["id"] + "/publish-pr",
                             headers=approved, json=payload)
    assert successful.status_code == 201, successful.text
    assert db.testing_repairs.docs[0]["status"] == "draft_pr_opened"
    assert len(called) == 1 and called[0][0] == "publishing"
    assert db.testing_repairs.docs[0]["pr"]["draft"]
    assert "new_source" not in str(db.testing_repairs.docs)
    assert client.post("/api/testing/repairs/" + case["id"] + "/publish-pr",
                       headers=approved, json=payload).status_code == 409
