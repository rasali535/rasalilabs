"""Guardrails for Stage 1 URL availability checks.

Stage 1 is opt-in, operator allowlisted and token gated. It is not a
general-purpose URL fetcher, domain-ownership verifier, or pentest tool.
"""
import asyncio
import ipaddress
import os
import re
import secrets
from dataclasses import dataclass
from urllib.parse import urlsplit, urlunsplit

from fastapi import Header, HTTPException

HOST_RE = re.compile(r"^(?=.{1,253}$)(?:[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?\.)+[a-z]{2,63}$")


@dataclass(frozen=True)
class TestingConfig:
    enabled: bool
    token: str
    allowed_hosts: frozenset[str]

    @property
    def configured(self) -> bool:
        return self.enabled and len(self.token) >= 32 and bool(self.allowed_hosts)


def get_config() -> TestingConfig:
    hosts = frozenset(
        value.strip().lower().rstrip(".")
        for value in os.getenv("TESTING_ALLOWED_HOSTS", "").split(",")
        if value.strip()
    )
    return TestingConfig(
        enabled=os.getenv("TESTING_CENTRE_ENABLED", "false").lower() == "true",
        token=os.getenv("TESTING_ACCESS_TOKEN", ""),
        allowed_hosts=hosts,
    )


def require_testing_access(x_testing_token: str = Header(default="")) -> TestingConfig:
    config = get_config()
    if not config.configured:
        raise HTTPException(status_code=503, detail="Testing Centre is disabled or not configured.")
    if not secrets.compare_digest(x_testing_token, config.token):
        raise HTTPException(status_code=403, detail="Testing access denied.")
    return config


async def validate_target(raw_url: str, allowed_hosts: frozenset[str], resolver=None) -> tuple[str, str]:
    """Accept only explicit, public, exact-match operator-approved destinations."""
    if len(raw_url) > 2048 or any(c.isspace() or ord(c) < 32 for c in raw_url):
        raise ValueError("Enter a valid URL without whitespace.")
    try:
        parsed = urlsplit(raw_url)
        host = (parsed.hostname or "").lower().rstrip(".")
        port = parsed.port
    except ValueError as exc:
        raise ValueError("Invalid target URL.") from exc

    if parsed.scheme not in ("http", "https") or not host or parsed.username or parsed.password:
        raise ValueError("Only HTTP(S) URLs without credentials are accepted.")
    if parsed.query or parsed.fragment:
        raise ValueError("Remove query parameters and fragments before scanning.")
    if port is not None and port != (443 if parsed.scheme == "https" else 80):
        raise ValueError("Nonstandard ports are not permitted.")
    if not HOST_RE.fullmatch(host) or host not in allowed_hosts:
        raise ValueError("Domain is not on the operator-approved allowlist.")
    if "%" in raw_url or "\\" in raw_url:
        raise ValueError("Encoded hosts and backslash URLs are not permitted.")

    try:
        results = await (resolver(host, port or (443 if parsed.scheme == "https" else 80))
                         if resolver else asyncio.get_running_loop().getaddrinfo(
                             host, port or (443 if parsed.scheme == "https" else 80),
                             type=__import__("socket").SOCK_STREAM))
    except (OSError, ValueError) as exc:
        raise ValueError("Unable to resolve the approved domain.") from exc
    addresses = [ipaddress.ip_address(info[4][0]) for info in results]
    if not addresses or not all(address.is_global for address in addresses):
        raise ValueError("Private, reserved or non-public network destinations are blocked.")

    path = parsed.path or "/"
    # Do not preserve URL userinfo, ports, query, or fragment.
    clean_url = urlunsplit((parsed.scheme, host, path, "", ""))
    return clean_url, host
