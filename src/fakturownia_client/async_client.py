"""Asynchronous client for the Fakturownia (InvoiceOcean) REST API.

Same endpoints, models, exceptions and auth policy as
:class:`fakturownia_client.FakturowniaClient` (token only in the
``Authorization: Bearer`` header), built on ``httpx.AsyncClient``.
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from types import TracebackType
from typing import Any, TypeVar

import httpx

from . import _ops
from ._base import DEFAULT_TIMEOUT, auth_headers, base_url
from .exceptions import raise_for_status
from .models import Client, Invoice, InvoiceCreate, InvoiceStatus, Product
from .pagination import MAX_PER_PAGE

__all__ = ["AsyncFakturowniaClient"]

T = TypeVar("T")


class AsyncFakturowniaClient:
    """Async twin of :class:`fakturownia_client.FakturowniaClient`."""

    def __init__(
        self,
        domain: str,
        api_token: str,
        *,
        timeout: float = DEFAULT_TIMEOUT,
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        self.base_url = base_url(domain)
        self._http = httpx.AsyncClient(
            base_url=self.base_url,
            timeout=timeout,
            transport=transport,
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

    async def _execute(self, op: _ops.Op[T]) -> T:
        params = {k: v for k, v in op.params.items() if v is not None}
        response = await self._http.request(op.method, op.path, params=params, json=op.json_body)
        raise_for_status(response)
        if op.raw:
            return op.parse(response.content)
        return op.parse(response.json() if response.content else None)

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
        include_positions: bool = False,
        order: str | None = None,
        page: int = 1,
        per_page: int = 25,
    ) -> list[Invoice]:
        """``GET /invoices.json``; ``date_from``/``date_to`` imply ``period="more"``."""
        return await self._execute(
            _ops.list_invoices(
                period=period,
                date_from=date_from,
                date_to=date_to,
                client_id=client_id,
                number=number,
                kind=kind,
                include_positions=include_positions,
                order=order,
                page=page,
                per_page=per_page,
            )
        )

    async def iter_invoices(self, **filters: Any) -> AsyncIterator[Invoice]:
        filters.pop("page", None)
        filters.pop("per_page", None)
        page = 1
        while True:
            items = await self.list_invoices(page=page, per_page=MAX_PER_PAGE, **filters)
            for item in items:
                yield item
            if len(items) < MAX_PER_PAGE:
                return
            page += 1

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
        return await self._execute(_ops.change_invoice_status(invoice_id, status))

    async def download_invoice_pdf(self, invoice_id: int) -> bytes:
        return await self._execute(_ops.download_invoice_pdf(invoice_id))

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

    async def iter_clients(self, **filters: Any) -> AsyncIterator[Client]:
        filters.pop("page", None)
        filters.pop("per_page", None)
        page = 1
        while True:
            items = await self.list_clients(page=page, per_page=MAX_PER_PAGE, **filters)
            for item in items:
                yield item
            if len(items) < MAX_PER_PAGE:
                return
            page += 1

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

    async def iter_products(self) -> AsyncIterator[Product]:
        page = 1
        while True:
            items = await self.list_products(page=page, per_page=MAX_PER_PAGE)
            for item in items:
                yield item
            if len(items) < MAX_PER_PAGE:
                return
            page += 1

    async def get_product(self, product_id: int) -> Product:
        return await self._execute(_ops.get_product(product_id))

    async def create_product(self, product: dict[str, Any]) -> Product:
        return await self._execute(_ops.create_product(product))

    async def update_product(self, product_id: int, fields: dict[str, Any]) -> Product:
        return await self._execute(_ops.update_product(product_id, fields))

    async def delete_product(self, product_id: int) -> None:
        """Undocumented endpoint — the official API README lists no product DELETE."""
        await self._execute(_ops.delete_product(product_id))
