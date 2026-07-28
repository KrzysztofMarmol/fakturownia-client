"""Typed exceptions raised by the Fakturownia clients."""

from __future__ import annotations

import httpx


class FakturowniaError(Exception):
    """Base error for all Fakturownia client failures.

    Messages never include the API token; the client sends it only in the
    ``Authorization`` header, so it cannot leak through URLs either.
    """

    def __init__(
        self,
        message: str,
        *,
        status_code: int | None = None,
        response: httpx.Response | None = None,
    ) -> None:
        super().__init__(message)
        self.status_code = status_code
        self.response = response


class AuthenticationError(FakturowniaError):
    """401/403 — invalid or missing API token."""


class NotFoundError(FakturowniaError):
    """404 — resource does not exist."""


class ValidationError(FakturowniaError):
    """422 — the API rejected the payload; message carries the API's reason."""


class BadRequestError(ValidationError):
    """400 — malformed request (missing wrapper key, bad params)."""


class RateLimitError(FakturowniaError):
    """429 — too many requests; ``retry_after`` holds the server hint in seconds."""

    def __init__(
        self,
        message: str,
        *,
        status_code: int | None = None,
        response: httpx.Response | None = None,
        retry_after: float | None = None,
    ) -> None:
        super().__init__(message, status_code=status_code, response=response)
        self.retry_after = retry_after


class ServerError(FakturowniaError):
    """5xx — Fakturownia-side failure."""


class TransportError(FakturowniaError):
    """Network-level failure (timeout, connection error, protocol error)."""


class ResponseParseError(FakturowniaError):
    """The server replied 2xx but the body could not be parsed as expected."""


def _retry_after_seconds(response: httpx.Response) -> float | None:
    value = response.headers.get("Retry-After")
    if value is None:
        return None
    try:
        return max(0.0, float(value))
    except ValueError:
        return None  # HTTP-date form — rare enough to ignore


def raise_for_status(response: httpx.Response) -> None:
    """Map an error response to a typed exception; no-op below 400."""
    status = response.status_code
    if status < 400:
        return
    try:
        message = str(response.json().get("message", response.text[:500]))
    except Exception:  # noqa: BLE001 - error bodies are not always JSON
        message = response.text[:500]
    detail = f"HTTP {status}: {message}"
    if status in (401, 403):
        raise AuthenticationError(detail, status_code=status, response=response)
    if status == 404:
        raise NotFoundError(detail, status_code=status, response=response)
    if status == 400:
        raise BadRequestError(detail, status_code=status, response=response)
    if status == 422:
        raise ValidationError(detail, status_code=status, response=response)
    if status == 429:
        raise RateLimitError(
            detail,
            status_code=status,
            response=response,
            retry_after=_retry_after_seconds(response),
        )
    if status >= 500:
        raise ServerError(detail, status_code=status, response=response)
    raise FakturowniaError(detail, status_code=status, response=response)
