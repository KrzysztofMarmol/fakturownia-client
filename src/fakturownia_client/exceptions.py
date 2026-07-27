"""Typed exceptions raised by the Fakturownia clients."""

from __future__ import annotations

import httpx


class FakturowniaError(Exception):
    """Base error for all Fakturownia API failures.

    Messages never include the API token; the client sends it only in the
    ``Authorization`` header, so it cannot leak through URLs either.
    """

    def __init__(self, message: str, *, status_code: int | None = None) -> None:
        super().__init__(message)
        self.status_code = status_code


class AuthenticationError(FakturowniaError):
    """401/403 — invalid or missing API token."""


class NotFoundError(FakturowniaError):
    """404 — resource does not exist."""


class ValidationError(FakturowniaError):
    """400/422 — the API rejected the payload; message carries the API's reason."""


class RateLimitError(FakturowniaError):
    """429 — too many requests."""


class ServerError(FakturowniaError):
    """5xx — Fakturownia-side failure."""


def raise_for_status(response: httpx.Response) -> None:
    """Map an error response to a typed exception; no-op below 400."""
    status = response.status_code
    if status < 400:
        return
    try:
        message = str(response.json().get("message", response.text))
    except Exception:  # noqa: BLE001 - error bodies are not always JSON
        message = response.text[:500]
    detail = f"HTTP {status}: {message}"
    if status in (401, 403):
        raise AuthenticationError(detail, status_code=status)
    if status == 404:
        raise NotFoundError(detail, status_code=status)
    if status in (400, 422):
        raise ValidationError(detail, status_code=status)
    if status == 429:
        raise RateLimitError(detail, status_code=status)
    if status >= 500:
        raise ServerError(detail, status_code=status)
    raise FakturowniaError(detail, status_code=status)
