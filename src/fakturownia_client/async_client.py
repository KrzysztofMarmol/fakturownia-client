"""Asynchronous client for the Fakturownia (InvoiceOcean) REST API.

Same endpoints, models, exceptions, retry policy and auth rules as
:class:`fakturownia_client.FakturowniaClient` (token only in the
``Authorization: Bearer`` header), built on ``httpx.AsyncClient``.
"""

from __future__ import annotations

import asyncio
import logging
import time
from collections.abc import AsyncIterator
from types import TracebackType
from typing import Any, TypeVar

import httpx

from . import _ops
from ._base import DEFAULT_TIMEOUT, Timeout, auth_headers, base_url
from ._retry import RetryPolicy
from .client import _check_pdf, _parse
from .exceptions import TransportError, _retry_after_seconds, raise_for_status
from .models import Client, Invoice, InvoiceCreate, InvoiceStatus, Product
from .pagination import MAX_PER_PAGE, aiter_pages

__all__ = ["AsyncFakturowniaClient"]

logger = logging.getLogger(__name__)

T = TypeVar("T")


class AsyncFakturowniaClient:
    """Async twin of :class:`fakturownia_client.FakturowniaClient`."""

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
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        self.base_url = base_url(domain)
        self._retry = retry_policy or RetryPolicy(max_retries=max_retries)
        self._http = httpx.AsyncClient(
            base_url=self.base_url,
            timeout=timeout,
            transport=transport,
            verify=verify,
            limits=limits or httpx.Limits(),
            follow_redirects=True,
            headers=auth_headers(api_token),
        )

    # -- lifecycle -----------------------------------------------------------

    async def close(self) -> None:
        await self._http.aclose()

    async def __aenter__(self) -> AsyncFakturowniaClient:
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: TracebackType | None,
    ) -> None:
        await self.close()

    # -- transport -----------------------------------------------------------

    async def _send(self, op: _ops.Op[T], params: dict[str, Any]) -> httpx.Response:
        attempt = 0
        while True:
            try:
                response = await self._http.request(
                    op.method, op.path, params=params, json=op.json_body
                )
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
            await asyncio.sleep(delay)
            attempt += 1

    async def _execute(self, op: _ops.Op[T]) -> T:
        params = {k: v for k, v in op.params.items() if v is not None}
        start = time.monotonic()
        response = await self._send(op, params)
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

    async def list_invoices(
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
        return await self._execute(
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

    def iter_invoices(self, **filters: Any) -> AsyncIterator[Invoice]:
        filters.pop("page", None)
        filters.pop("per_page", None)

        async def fetch(page: int) -> list[Invoice]:
            return await self.list_invoices(page=page, per_page=MAX_PER_PAGE, **filters)

        return aiter_pages(fetch)

    async def get_invoice(self, invoice_id: int) -> Invoice:
        return await self._execute(_ops.get_invoice(invoice_id))

    async def create_invoice(self, invoice: InvoiceCreate | dict[str, Any]) -> Invoice:
        return await self._execute(_ops.create_invoice(invoice))

    async def update_invoice(self, invoice_id: int, fields: dict[str, Any]) -> Invoice:
        return await self._execute(_ops.update_invoice(invoice_id, fields))

    async def delete_invoice(self, invoice_id: int) -> None:
        """Permanently delete an invoice — destructive, prefer status changes."""
        await self._execute(_ops.delete_invoice(invoice_id))

    async def change_invoice_status(self, invoice_id: int, status: InvoiceStatus) -> Any:
        """Raises :class:`FakturowniaError` when the API answers 200 with an error envelope."""
        return await self._execute(_ops.change_invoice_status(invoice_id, status))

    async def download_invoice_pdf(self, invoice_id: int) -> bytes:
        content: bytes = await self._execute(_ops.download_invoice_pdf(invoice_id))
        _check_pdf(content)
        return content

    # -- clients ---------------------------------------------------------------

    async def list_clients(
        self,
        *,
        name: str | None = None,
        tax_no: str | None = None,
        email: str | None = None,
        external_id: str | None = None,
        page: int = 1,
        per_page: int = 25,
    ) -> list[Client]:
        return await self._execute(
            _ops.list_clients(
                name=name,
                tax_no=tax_no,
                email=email,
                external_id=external_id,
                page=page,
                per_page=per_page,
            )
        )

    def iter_clients(self, **filters: Any) -> AsyncIterator[Client]:
        filters.pop("page", None)
        filters.pop("per_page", None)

        async def fetch(page: int) -> list[Client]:
            return await self.list_clients(page=page, per_page=MAX_PER_PAGE, **filters)

        return aiter_pages(fetch)

    async def get_client(self, client_id: int) -> Client:
        return await self._execute(_ops.get_client(client_id))

    async def create_client(self, client: dict[str, Any]) -> Client:
        return await self._execute(_ops.create_client(client))

    async def update_client(self, client_id: int, fields: dict[str, Any]) -> Client:
        return await self._execute(_ops.update_client(client_id, fields))

    async def delete_client(self, client_id: int) -> None:
        await self._execute(_ops.delete_client(client_id))

    # -- products ----------------------------------------------------------------

    async def list_products(self, *, page: int = 1, per_page: int = 25) -> list[Product]:
        return await self._execute(_ops.list_products(page=page, per_page=per_page))

    def iter_products(self, **filters: Any) -> AsyncIterator[Product]:
        filters.pop("page", None)
        filters.pop("per_page", None)

        async def fetch(page: int) -> list[Product]:
            return await self.list_products(page=page, per_page=MAX_PER_PAGE, **filters)

        return aiter_pages(fetch)

    async def get_product(self, product_id: int) -> Product:
        return await self._execute(_ops.get_product(product_id))

    async def create_product(self, product: dict[str, Any]) -> Product:
        return await self._execute(_ops.create_product(product))

    async def update_product(self, product_id: int, fields: dict[str, Any]) -> Product:
        return await self._execute(_ops.update_product(product_id, fields))

    async def delete_product(self, product_id: int) -> None:
        """Undocumented endpoint — the official API README lists no product DELETE."""
        await self._execute(_ops.delete_product(product_id))
