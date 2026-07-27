"""Shared configuration helpers for the sync and async clients."""

from __future__ import annotations

_SUFFIX = ".fakturownia.pl"

DEFAULT_TIMEOUT = 30.0


def normalize_domain(domain: str) -> str:
    """Accept ``"firma"``, ``"firma.fakturownia.pl"`` or a full URL; return the host."""
    host = domain.strip().removeprefix("https://").removeprefix("http://").split("/")[0]
    if not host:
        raise ValueError("Fakturownia domain must not be empty")
    if not host.endswith(_SUFFIX):
        host += _SUFFIX
    return host


def base_url(domain: str) -> str:
    return f"https://{normalize_domain(domain)}"


def auth_headers(api_token: str) -> dict[str, str]:
    """The token travels only in the Authorization header — never in URLs or bodies."""
    if not api_token:
        raise ValueError("api_token must not be empty")
    return {"Authorization": f"Bearer {api_token}", "Accept": "application/json"}
