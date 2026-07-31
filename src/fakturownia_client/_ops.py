"""Endpoint definitions shared by the sync and async clients.

Each function builds an :class:`Op` describing the HTTP request and how to
parse its response, so request construction and parsing live in exactly one
place regardless of transport.
"""

from __future__ import annotations

from collections.abc import Callable, Sequence
from dataclasses import dataclass, field
from typing import Any, Generic, TypeVar

from .exceptions import FakturowniaError
from .models import Client, Invoice, InvoiceCreate, InvoiceStatus, Payment, Product

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


def _payment(data: Any) -> Payment:
    return Payment.model_validate(data)


def _payments(data: Any) -> list[Payment]:
    return [Payment.model_validate(item) for item in data]


def _none(data: Any) -> None:
    return None


def _passthrough(data: Any) -> Any:
    return data


def _checked_envelope(data: Any) -> Any:
    """Some endpoints answer 200 with {"code": "error", ...} — surface that."""
    if isinstance(data, dict) and data.get("code") not in (None, "success"):
        raise FakturowniaError(
            f"API returned an error envelope: {data.get('message', data)}", status_code=200
        )
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
        _checked_envelope,
        params={"status": status},
    )


def download_invoice_pdf(invoice_id: int) -> Op[bytes]:
    return Op("GET", f"/invoices/{invoice_id}.pdf", _bytes, raw=True)


def _emails(value: str | Sequence[str] | None) -> str | None:
    if value is None or isinstance(value, str):
        return value
    return ",".join(value)


def send_invoice_by_email(
    invoice_id: int,
    *,
    email_to: str | Sequence[str] | None = None,
    email_cc: str | Sequence[str] | None = None,
    email_pdf: bool | None = None,
    print_option: str | None = None,
    update_buyer_email: bool | None = None,
) -> Op[Any]:
    """POST /invoices/{id}/send_by_email.json — the API caps ``email_to`` at 5 addresses."""
    return Op(
        "POST",
        f"/invoices/{invoice_id}/send_by_email.json",
        _checked_envelope,
        params={
            "email_to": _emails(email_to),
            "email_cc": _emails(email_cc),
            "email_pdf": email_pdf,
            "print_option": print_option,
            "update_buyer_email": update_buyer_email,
        },
    )


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


# -- payments (banking) ----------------------------------------------------------


def list_payments(
    *, page: int = 1, per_page: int = 25, include_invoices: bool = False
) -> Op[list[Payment]]:
    return Op(
        "GET",
        "/banking/payments.json",
        _payments,
        params={
            "page": page,
            "per_page": per_page,
            "include": "invoices" if include_invoices else None,
        },
    )


def get_payment(payment_id: int) -> Op[Payment]:
    # Official docs show a singular path (/banking/payment/{id}.json) but that
    # 404s on the live API; only the plural form works (verified 2026-07-31).
    return Op("GET", f"/banking/payments/{payment_id}.json", _payment)


def create_payment(payment: dict[str, Any]) -> Op[Payment]:
    return Op("POST", "/banking/payments.json", _payment, json_body={"banking_payment": payment})


def update_payment(payment_id: int, fields: dict[str, Any]) -> Op[Payment]:
    return Op(
        "PATCH",
        f"/banking/payments/{payment_id}.json",
        _payment,
        json_body={"banking_payment": fields},
    )


def delete_payment(payment_id: int) -> Op[None]:
    return Op("DELETE", f"/banking/payments/{payment_id}.json", _none)


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
