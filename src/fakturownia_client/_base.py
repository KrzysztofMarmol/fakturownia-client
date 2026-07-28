"""Shared configuration helpers for the sync and async clients."""

from __future__ import annotations

import httpx

from ._version import __version__

_SUFFIX = ".fakturownia.pl"

DEFAULT_TIMEOUT = 30.0

USER_AGENT = f"fakturownia-client/{__version__}"


def normalize_domain(domain: str) -> str:
    """Return the API host for an account name, full domain or URL.

    A bare account name (``"firma"``) gets the default ``.fakturownia.pl``
    suffix. Anything containing a dot is treated as a complete host, so
    InvoiceOcean and other regional domains work as-is
    (``"mycompany.invoiceocean.com"``, ``"firma.fakturownia.pl"``, full URLs).
    """
    host = domain.strip().removeprefix("https://").removeprefix("http://").split("/")[0]
    if not host:
        raise ValueError("Fakturownia domain must not be empty")
    if "." not in host:
        host += _SUFFIX
    return host


def base_url(domain: str) -> str:
    return f"https://{normalize_domain(domain)}"


def auth_headers(api_token: str) -> dict[str, str]:
    """The token travels only in the Authorization header — never in URLs or bodies."""
    if not api_token:
        raise ValueError("api_token must not be empty")
    return {
        "Authorization": f"Bearer {api_token}",
        "Accept": "application/json",
        "User-Agent": USER_AGENT,
    }


Timeout = float | httpx.Timeout
