"""Synchronous client for the Fakturownia (InvoiceOcean) REST API.

Authentication: the API token is sent exclusively in the ``Authorization:
Bearer`` header (verified against the live API for every endpoint used here).
It is never placed in URLs or request bodies, so it cannot leak via server or
proxy logs — including the DEBUG logs emitted by this module.

Endpoint definitions live in :mod:`fakturownia_client._ops` and are shared
with :class:`fakturownia_client.AsyncFakturowniaClient`.
"""

from __future__ import annotations

import logging
import time
from collections.abc import Iterator
from types import TracebackType
from typing import Any, TypeVar

import httpx
import pydantic

from . import _ops
from ._base import DEFAULT_TIMEOUT, Timeout, auth_headers, base_url, normalize_domain
from ._retry import RetryPolicy
from .exceptions import (
    FakturowniaError,
    ResponseParseError,
    TransportError,
    _retry_after_seconds,
    raise_for_status,
)
from .models import Client, Invoice, InvoiceCreate, InvoiceStatus, Product
from .pagination import MAX_PER_PAGE, iter_pages

__all__ = ["FakturowniaClient", "normalize_domain"]

logger = logging.getLogger(__name__)

T = TypeVar("T")


class FakturowniaClient:
    """Thin, typed wrapper over the Fakturownia REST API."""

    def __init__(
        self,
        domain: str,
        api_token: str,
        *,
        timeout: Timeout = DEFAULT_TIMEOUT,
        max_retries: int = 3,
        retry_policy: RetryPolicy | None = None,
        verify: bool = True,
        limits: httpx.Limits | None = None,
        transport: httpx.BaseTransport | None = None,
    ) -> None:
        self.base_url = base_url(domain)
        self._retry = retry_policy or RetryPolicy(max_retries=max_retries)
        self._http = httpx.Client(
            base_url=self.base_url,
            timeout=timeout,
            transport=transport,
            verify=verify,
            limits=limits or httpx.Limits(),
            follow_redirects=True,
            headers=auth_headers(api_token),
        )

    # -- lifecycle -----------------------------------------------------------

    def close(self) -> None:
        self._http.close()

    def __enter__(self) -> FakturowniaClient:
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: TracebackType | None,
    ) -> None:
        self.close()

    # -- transport -----------------------------------------------------------

    def _send(self, op: _ops.Op[T], params: dict[str, Any]) -> httpx.Response:
        """Issue the request with retries on 429/5xx and transport errors."""
        attempt = 0
        while True:
            try:
                response = self._http.request(op.method, op.path, params=params, json=op.json_body)
            except httpx.HTTPError as exc:
                if not self._retry.should_retry(attempt, None):
                    raise TransportError(f"{op.method} {op.path}: {exc}") from exc
                delay = self._retry.delay(attempt)
                logger.info(
                    "%s %s transport error, retry in %.1fs: %s", op.method, op.path, delay, exc
                )
            else:
                if not self._retry.should_retry(attempt, response.status_code):
                    return response
                retry_after = (
                    _retry_after_seconds(response) if response.status_code == 429 else None
                )
                delay = self._retry.delay(attempt, retry_after=retry_after)
                logger.info(
                    "%s %s -> %s, retry in %.1fs", op.method, op.path, response.status_code, delay
                )
            time.sleep(delay)
            attempt += 1

    def _execute(self, op: _ops.Op[T]) -> T:
        params = {k: v for k, v in op.params.items() if v is not None}
        start = time.monotonic()
        response = self._send(op, params)
        logger.debug(
            "%s %s -> %s (%.0f ms)",
            op.method,
            op.path,
            response.status_code,
            (time.monotonic() - start) * 1000,
        )
        raise_for_status(response)
        return _parse(op, response)

    # -- invoices --------------------------------------------------------------

    def list_invoices(
        self,
        *,
        period: str | None = None,
        date_from: str | None = None,
        date_to: str | None = None,
        client_id: int | None = None,
        number: str | None = None,
        kind: str | None = None,
        income: bool | None = None,
        include_positions: bool = False,
        order: str | None = None,
        page: int = 1,
        per_page: int = 25,
    ) -> list[Invoice]:
        """``GET /invoices.json``; ``date_from``/``date_to`` imply ``period="more"``.

        ``income``: None (default) lists sales invoices, ``False`` lists
        cost/expense invoices (``income=no``), ``True`` forces sales explicitly.
        """
        return self._execute(
            _ops.list_invoices(
                period=period,
                date_from=date_from,
                date_to=date_to,
                client_id=client_id,
                number=number,
                kind=kind,
                income=income,
                include_positions=include_positions,
                order=order,
                page=page,
                per_page=per_page,
            )
        )

    def iter_invoices(self, **filters: Any) -> Iterator[Invoice]:
        filters.pop("page", None)
        filters.pop("per_page", None)
        return iter_pages(
            lambda page: self.list_invoices(page=page, per_page=MAX_PER_PAGE, **filters)
        )

    def get_invoice(self, invoice_id: int) -> Invoice:
        return self._execute(_ops.get_invoice(invoice_id))

    def create_invoice(self, invoice: InvoiceCreate | dict[str, Any]) -> Invoice:
        return self._execute(_ops.create_invoice(invoice))

    def update_invoice(self, invoice_id: int, fields: dict[str, Any]) -> Invoice:
        return self._execute(_ops.update_invoice(invoice_id, fields))

    def delete_invoice(self, invoice_id: int) -> None:
        """Permanently delete an invoice — destructive, prefer status changes."""
        self._execute(_ops.delete_invoice(invoice_id))

    def change_invoice_status(self, invoice_id: int, status: InvoiceStatus) -> Any:
        """Raises :class:`FakturowniaError` when the API answers 200 with an error envelope."""
        return self._execute(_ops.change_invoice_status(invoice_id, status))

    def download_invoice_pdf(self, invoice_id: int) -> bytes:
        content: bytes = self._execute(_ops.download_invoice_pdf(invoice_id))
        _check_pdf(content)
        return content

    # -- clients ---------------------------------------------------------------

    def list_clients(
        self,
        *,
        name: str | None = None,
        tax_no: str | None = None,
        email: str | None = None,
        external_id: str | None = None,
        page: int = 1,
        per_page: int = 25,
    ) -> list[Client]:
        return self._execute(
            _ops.list_clients(
                name=name,
                tax_no=tax_no,
                email=email,
                external_id=external_id,
                page=page,
                per_page=per_page,
            )
        )

    def iter_clients(self, **filters: Any) -> Iterator[Client]:
        filters.pop("page", None)
        filters.pop("per_page", None)
        return iter_pages(
            lambda page: self.list_clients(page=page, per_page=MAX_PER_PAGE, **filters)
        )

    def get_client(self, client_id: int) -> Client:
        return self._execute(_ops.get_client(client_id))

    def create_client(self, client: dict[str, Any]) -> Client:
        return self._execute(_ops.create_client(client))

    def update_client(self, client_id: int, fields: dict[str, Any]) -> Client:
        return self._execute(_ops.update_client(client_id, fields))

    def delete_client(self, client_id: int) -> None:
        self._execute(_ops.delete_client(client_id))

    # -- products ----------------------------------------------------------------

    def list_products(self, *, page: int = 1, per_page: int = 25) -> list[Product]:
        return self._execute(_ops.list_products(page=page, per_page=per_page))

    def iter_products(self, **filters: Any) -> Iterator[Product]:
        filters.pop("page", None)
        filters.pop("per_page", None)
        return iter_pages(
            lambda page: self.list_products(page=page, per_page=MAX_PER_PAGE, **filters)
        )

    def get_product(self, product_id: int) -> Product:
        return self._execute(_ops.get_product(product_id))

    def create_product(self, product: dict[str, Any]) -> Product:
        return self._execute(_ops.create_product(product))

    def update_product(self, product_id: int, fields: dict[str, Any]) -> Product:
        return self._execute(_ops.update_product(product_id, fields))

    def delete_product(self, product_id: int) -> None:
        """Undocumented endpoint — the official API README lists no product DELETE."""
        self._execute(_ops.delete_product(product_id))


def _parse(op: _ops.Op[T], response: httpx.Response) -> T:
    """Parse a 2xx response body; wrap decode/validation failures."""
    if op.raw:
        return op.parse(response.content)
    try:
        data = response.json() if response.content else None
        return op.parse(data)
    except FakturowniaError:
        raise
    except (ValueError, TypeError, pydantic.ValidationError) as exc:
        raise ResponseParseError(
            f"{op.method} {op.path}: cannot parse API response ({exc})", response=response
        ) from exc


def _check_pdf(content: bytes) -> None:
    if not content.startswith(b"%PDF"):
        raise ResponseParseError(
            "Response is not a PDF document (missing %PDF signature) — "
            "the API may have redirected to an HTML page."
        )
