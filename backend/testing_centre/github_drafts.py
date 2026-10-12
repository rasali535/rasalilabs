"""An explicitly approved one-file *draft* GitHub PR publisher.

A staging-only bridge, disabled without operator and approval credentials.
NO model chooses file contents; a human/coding workflow supplies and reviews
the exact replacement source and base blob SHA. This module cannot merge PRs.
"""
import base64
import os
import re
import uuid
from urllib.parse import quote

import httpx

GITHUB = "https://api.github.com"
SHA_RE = re.compile(r"^[a-f0-9]{40}$")
REPO_RE = re.compile(r"^[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+$")
SAFE_FILE_RE = re.compile(r"^[a-zA-Z0-9_./-]{2,250}$")
SAFE_PREFIXES = ("src/", "app/", "pages/", "frontend/src/", "backend/")
SAFE_EXTENSIONS = (".js", ".jsx", ".ts", ".tsx", ".py", ".css", ".html")
BLOCKED_PARTS = {
    ".env", ".git", ".github", "__pycache__", "node_modules", "secrets",
    "credentials", "settings", "keys", "migrations",
}


class GitHubPublishError(RuntimeError):
    pass


def publisher_configured():
    return (
        os.getenv("TESTING_REPAIR_GITHUB_ENABLED", "").lower() == "true"
        and os.getenv("TESTING_REPAIR_SCOPE_ACK", "").lower() == "true"
        and len(os.getenv("TESTING_REPAIR_APPROVAL_TOKEN", "")) >= 32
        and bool(os.getenv("TESTING_GITHUB_TOKEN", "").strip())
        and bool(os.getenv("TESTING_REPAIR_REPO", "").strip())
    )


def validate_publishing_input(repo, path, expected_sha, new_source):
    if not isinstance(repo, str) or not REPO_RE.fullmatch(repo) or repo.lower() in ("", "undefined/undefined"):
        raise ValueError("Invalid GitHub repository.")
    allowed = os.getenv("TESTING_REPAIR_REPO", "").strip()
    if not allowed or repo != allowed:
        raise ValueError("Repository is not explicitly operator-approved for writes.")
    if not isinstance(path, str) or not SAFE_FILE_RE.fullmatch(path) or path.startswith("/"):
        raise ValueError("Unsafe file path.")
    parts = path.split("/")
    if any(segment in ("", ".", "..") or segment.lower() in BLOCKED_PARTS or
           segment.startswith(".") for segment in parts):
        raise ValueError("Protected or ambiguous file path.")
    if not path.startswith(SAFE_PREFIXES) or not path.lower().endswith(SAFE_EXTENSIONS):
        raise ValueError("Only approved source files may be edited.")
    if path.lower().endswith(("server.py", "config.py", "auth.py", "security.py")):
        raise ValueError("Sensitive infrastructure and authorization files cannot be patched here.")
    if not isinstance(expected_sha, str) or not SHA_RE.fullmatch(expected_sha):
        raise ValueError("A valid reviewed base blob SHA is required.")
    if not isinstance(new_source, str) or not new_source.strip() or len(new_source.encode("utf-8")) > 48_000:
        raise ValueError("Replacement source must be nonempty and at most 48KB.")
    if "\x00" in new_source:
        raise ValueError("Binary content is not allowed.")
    return repo, path


class GitHubDraftPublisher:
    def __init__(self, token: str, client_factory=None):
        self.token = token
        self.client_factory = client_factory or httpx.AsyncClient

    async def publish(self, case, repo, file_path, base_blob_sha, source):
        """Create an isolated branch and draft PR. Never merges or deploys."""
        validate_publishing_input(repo, file_path, base_blob_sha, source)
        if case.get("status") != "publishing":
            raise GitHubPublishError("Case is not in explicitly approved publishing state.")
        owner, project = repo.split("/")
        urlbase = f"/repos/{quote(owner, safe='')}/{quote(project, safe='')}"
        headers = {
            "Authorization": f"Bearer {self.token}",
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
        }
        branch_name = f"repair/{case['id'][:8]}-{uuid.uuid4().hex[:8]}"
        async with self.client_factory(
            base_url=GITHUB, headers=headers, trust_env=False,
            timeout=httpx.Timeout(12.0), follow_redirects=False,
        ) as client:
            async def request(method, url, **kwargs):
                try:
                    response = await client.request(method, url, **kwargs)
                    if not 200 <= response.status_code < 300:
                        raise GitHubPublishError(
                            f"GitHub operation returned HTTP {response.status_code}. "
                            "Manual reconciliation may be required if a branch was created."
                        )
                    return response.json()
                except (httpx.HTTPError, ValueError) as exc:
                    raise GitHubPublishError(
                        f"GitHub operation failed ({type(exc).__name__}); inspect provider logs."
                    ) from exc

            main = await request("GET", urlbase + "/git/ref/heads/main")
            base_sha = (main.get("object") or {}).get("sha")
            if not isinstance(base_sha, str) or not SHA_RE.fullmatch(base_sha):
                raise GitHubPublishError("Could not verify the GitHub main commit.")
            item = await request(
                "GET", urlbase + "/contents/" + quote(file_path, safe="/"),
                params={"ref": "main"},
            )
            if item.get("type") != "file" or item.get("sha") != base_blob_sha:
                raise GitHubPublishError(
                    "Reviewed base file SHA differs from current main. Refresh and reapprove."
                )
            await request("POST", urlbase + "/git/refs",
                          json={"ref": "refs/heads/" + branch_name, "sha": base_sha})
            await request(
                "PUT", urlbase + "/contents/" + quote(file_path, safe="/"),
                json={
                    "message": "fix(testing): proposed repair for recorded finding",
                    "content": base64.b64encode(source.encode("utf-8")).decode("ascii"),
                    "sha": base_blob_sha,
                    "branch": branch_name,
                },
            )
            pr = await request("POST", urlbase + "/pulls", json={
                "title": "Review repair: " + case["finding"]["title"][:80],
                "head": branch_name, "base": "main", "draft": True,
                "body": (
                    "Proposed repair for observed Testing Centre finding.\n\n"
                    f"Case: {case['id']}\n"
                    f"Source scan: {case['source_scan_id']}\n"
                    f"Finding: {case['source_finding_id']}\n"
                    "Changes are NOT verified; review source, run CI, "
                    "deploy to authorized staging and retest before merging."
                ),
            })
            pr_number = pr.get("number")
            if not isinstance(pr_number, int) or pr_number < 1 or not pr.get("draft"):
                raise GitHubPublishError("GitHub did not confirm a draft PR.")
            result_url = f"https://github.com/{repo}/pull/{pr_number}"
            if pr.get("html_url") != result_url:
                raise GitHubPublishError("GitHub draft PR URL did not match the allowed repository.")
            return {
                "repo": repo, "number": pr_number,
                "url": result_url, "branch": branch_name,
                "base": "main", "draft": True,
                "verification": "not_tested",
                "base_sha": base_sha,
                "file_path": file_path,
            }
