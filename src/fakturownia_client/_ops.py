"""Endpoint definitions shared by the sync and async clients.

Each function builds an :class:`Op` describing the HTTP request and how to
parse its response, so request construction and parsing live in exactly one
place regardless of transport.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any, Generic, TypeVar

from .models import Client, Invoice, InvoiceCreate, InvoiceStatus, Product

T = TypeVar("T")


@dataclass(frozen=True)
class Op(Generic[T]):
    method: str
    path: str
    parse: Callable[[Any], T]
    params: dict[str, Any] = field(default_factory=dict)
    json_body: dict[str, Any] | None = None
    raw: bool = False


def _invoice(data: Any) -> Invoice:
    return Invoice.model_validate(data)


def _invoices(data: Any) -> list[Invoice]:
    return [Invoice.model_validate(item) for item in data]


def _client(data: Any) -> Client:
    return Client.model_validate(data)


def _clients(data: Any) -> list[Client]:
    return [Client.model_validate(item) for item in data]


def _product(data: Any) -> Product:
    return Product.model_validate(data)


def _products(data: Any) -> list[Product]:
    return [Product.model_validate(item) for item in data]


def _none(data: Any) -> None:
    return None


def _passthrough(data: Any) -> Any:
    return data


def _bytes(data: Any) -> bytes:
    return bytes(data)


# -- invoices ------------------------------------------------------------------


def list_invoices(
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
) -> Op[list[Invoice]]:
    if (date_from or date_to) and period is None:
        period = "more"
    return Op(
        "GET",
        "/invoices.json",
        _invoices,
        params={
            "period": period,
            "date_from": date_from,
            "date_to": date_to,
            "client_id": client_id,
            "number": number,
            "kind": kind,
            "income": None if income is None else ("yes" if income else "no"),
            "include_positions": "true" if include_positions else None,
            "order": order,
            "page": page,
            "per_page": per_page,
        },
    )


def get_invoice(invoice_id: int) -> Op[Invoice]:
    return Op("GET", f"/invoices/{invoice_id}.json", _invoice)


def create_invoice(invoice: InvoiceCreate | dict[str, Any]) -> Op[Invoice]:
    payload = (
        invoice.model_dump(mode="json", exclude_none=True)
        if isinstance(invoice, InvoiceCreate)
        else invoice
    )
    return Op("POST", "/invoices.json", _invoice, json_body={"invoice": payload})


def update_invoice(invoice_id: int, fields: dict[str, Any]) -> Op[Invoice]:
    return Op("PUT", f"/invoices/{invoice_id}.json", _invoice, json_body={"invoice": fields})


def delete_invoice(invoice_id: int) -> Op[None]:
    return Op("DELETE", f"/invoices/{invoice_id}.json", _none)


def change_invoice_status(invoice_id: int, status: InvoiceStatus) -> Op[Any]:
    return Op(
        "POST",
        f"/invoices/{invoice_id}/change_status.json",
        _passthrough,
        params={"status": status},
    )


def download_invoice_pdf(invoice_id: int) -> Op[bytes]:
    return Op("GET", f"/invoices/{invoice_id}.pdf", _bytes, raw=True)


# -- clients -------------------------------------------------------------------


def list_clients(
    *,
    name: str | None = None,
    tax_no: str | None = None,
    email: str | None = None,
    external_id: str | None = None,
    page: int = 1,
    per_page: int = 25,
) -> Op[list[Client]]:
    return Op(
        "GET",
        "/clients.json",
        _clients,
        params={
            "name": name,
            "tax_no": tax_no,
            "email": email,
            "external_id": external_id,
            "page": page,
            "per_page": per_page,
        },
    )


def get_client(client_id: int) -> Op[Client]:
    return Op("GET", f"/clients/{client_id}.json", _client)


def create_client(client: dict[str, Any]) -> Op[Client]:
    return Op("POST", "/clients.json", _client, json_body={"client": client})


def update_client(client_id: int, fields: dict[str, Any]) -> Op[Client]:
    return Op("PUT", f"/clients/{client_id}.json", _client, json_body={"client": fields})


def delete_client(client_id: int) -> Op[None]:
    return Op("DELETE", f"/clients/{client_id}.json", _none)


# -- products ------------------------------------------------------------------


def list_products(*, page: int = 1, per_page: int = 25) -> Op[list[Product]]:
    return Op("GET", "/products.json", _products, params={"page": page, "per_page": per_page})


def get_product(product_id: int) -> Op[Product]:
    return Op("GET", f"/products/{product_id}.json", _product)


def create_product(product: dict[str, Any]) -> Op[Product]:
    return Op("POST", "/products.json", _product, json_body={"product": product})


def update_product(product_id: int, fields: dict[str, Any]) -> Op[Product]:
    return Op("PUT", f"/products/{product_id}.json", _product, json_body={"product": fields})


def delete_product(product_id: int) -> Op[None]:
    return Op("DELETE", f"/products/{product_id}.json", _none)
