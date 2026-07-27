import json

import httpx
import respx

from fakturownia_client import FakturowniaClient, Invoice, InvoiceCreate, InvoicePositionCreate
from tests.conftest import TOKEN

INVOICE_JSON = {
    "id": 111,
    "number": "2026/07/01",
    "kind": "vat",
    "status": "issued",
    "issue_date": "2026-07-15",
    "buyer_name": "ACME Sp. z o.o.",
    "price_net": "100.0",
    "price_gross": "123.0",
    "currency": "PLN",
    "some_unknown_field": "kept",
}


def test_list_invoices_builds_params_and_auth_header(
    api: respx.MockRouter, client: FakturowniaClient
) -> None:
    route = api.get("/invoices.json").mock(return_value=httpx.Response(200, json=[INVOICE_JSON]))

    invoices = client.list_invoices(period="this_month", client_id=7, include_positions=True)

    assert [inv.id for inv in invoices] == [111]
    request = route.calls.last.request
    assert request.headers["Authorization"] == f"Bearer {TOKEN}"
    assert "api_token" not in str(request.url)
    params = dict(httpx.URL(str(request.url)).params)
    assert params["period"] == "this_month"
    assert params["client_id"] == "7"
    assert params["include_positions"] == "true"
    assert "number" not in params  # None filters are dropped


def test_list_invoices_date_range_implies_period_more(
    api: respx.MockRouter, client: FakturowniaClient
) -> None:
    route = api.get("/invoices.json").mock(return_value=httpx.Response(200, json=[]))

    client.list_invoices(date_from="2026-01-01", date_to="2026-01-31")

    params = dict(httpx.URL(str(route.calls.last.request.url)).params)
    assert params["period"] == "more"


def test_get_invoice_parses_model_and_keeps_extra_fields(
    api: respx.MockRouter, client: FakturowniaClient
) -> None:
    api.get("/invoices/111.json").mock(return_value=httpx.Response(200, json=INVOICE_JSON))

    invoice = client.get_invoice(111)

    assert isinstance(invoice, Invoice)
    assert invoice.number == "2026/07/01"
    assert invoice.issue_date is not None and invoice.issue_date.year == 2026
    assert invoice.model_extra is not None
    assert invoice.model_extra["some_unknown_field"] == "kept"


def test_create_invoice_wraps_payload_and_keeps_token_out_of_body(
    api: respx.MockRouter, client: FakturowniaClient
) -> None:
    route = api.post("/invoices.json").mock(return_value=httpx.Response(201, json=INVOICE_JSON))

    invoice = InvoiceCreate(
        buyer_name="ACME Sp. z o.o.",
        positions=[InvoicePositionCreate(name="Usługa", total_price_gross=123.0, tax=23)],
    )
    created = client.create_invoice(invoice)

    assert created.id == 111
    body = json.loads(route.calls.last.request.content)
    assert set(body) == {"invoice"}
    assert body["invoice"]["buyer_name"] == "ACME Sp. z o.o."
    assert body["invoice"]["positions"][0]["name"] == "Usługa"
    assert "api_token" not in json.dumps(body)


def test_update_invoice_sends_partial_fields(
    api: respx.MockRouter, client: FakturowniaClient
) -> None:
    route = api.put("/invoices/111.json").mock(return_value=httpx.Response(200, json=INVOICE_JSON))

    client.update_invoice(111, {"buyer_email": "new@example.com"})

    body = json.loads(route.calls.last.request.content)
    assert body == {"invoice": {"buyer_email": "new@example.com"}}


def test_change_invoice_status_uses_query_param(
    api: respx.MockRouter, client: FakturowniaClient
) -> None:
    route = api.post("/invoices/111/change_status.json").mock(
        return_value=httpx.Response(200, json={"code": "success"})
    )

    client.change_invoice_status(111, "paid")

    params = dict(httpx.URL(str(route.calls.last.request.url)).params)
    assert params["status"] == "paid"


def test_download_invoice_pdf_returns_bytes(
    api: respx.MockRouter, client: FakturowniaClient
) -> None:
    pdf = b"%PDF-1.7 fake"
    api.get("/invoices/111.pdf").mock(return_value=httpx.Response(200, content=pdf))

    assert client.download_invoice_pdf(111) == pdf


def test_delete_invoice(api: respx.MockRouter, client: FakturowniaClient) -> None:
    route = api.delete("/invoices/111.json").mock(return_value=httpx.Response(200))

    client.delete_invoice(111)

    assert route.called
