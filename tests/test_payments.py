import json

import httpx
import pytest
import respx

from fakturownia_client import FakturowniaClient, FakturowniaError, Payment

PAYMENT_JSON = {
    "id": 77,
    "name": "Payment 001",
    "price": "100.05",
    "currency": "PLN",
    "paid": True,
    "kind": "api",
    "invoice_id": 555,
    "paid_date": "",
}


def test_list_payments(api: respx.MockRouter, client: FakturowniaClient) -> None:
    route = api.get("/banking/payments.json").mock(
        return_value=httpx.Response(200, json=[PAYMENT_JSON])
    )

    payments = client.list_payments(per_page=10)

    assert isinstance(payments[0], Payment)
    assert payments[0].price == "100.05"
    assert payments[0].paid_date is None  # blank string coerced
    params = dict(httpx.URL(str(route.calls.last.request.url)).params)
    assert params["per_page"] == "10"
    assert "include" not in params


def test_list_payments_include_invoices(api: respx.MockRouter, client: FakturowniaClient) -> None:
    embedded = dict(PAYMENT_JSON, invoices=[{"id": 555, "number": "2026/07/01"}])
    route = api.get("/banking/payments.json").mock(
        return_value=httpx.Response(200, json=[embedded])
    )

    (payment,) = client.list_payments(include_invoices=True)

    assert dict(httpx.URL(str(route.calls.last.request.url)).params)["include"] == "invoices"
    assert payment.invoices is not None
    assert payment.invoices[0].number == "2026/07/01"


def test_get_payment_uses_plural_path_docs_are_wrong(
    api: respx.MockRouter, client: FakturowniaClient
) -> None:
    # Official docs show /banking/payment/{id}.json (singular) but the live API
    # 404s on it; only the plural path works — do not "fix" this back.
    api.get("/banking/payments/77.json").mock(return_value=httpx.Response(200, json=PAYMENT_JSON))

    assert client.get_payment(77).id == 77


def test_payment_paid_date_accepts_full_timestamp(
    api: respx.MockRouter, client: FakturowniaClient
) -> None:
    record = dict(PAYMENT_JSON, paid_date="2026-07-31T15:55:57.000+02:00")
    api.get("/banking/payments.json").mock(return_value=httpx.Response(200, json=[record]))

    (payment,) = client.list_payments()

    assert payment.paid_date is not None
    assert payment.paid_date.year == 2026


def test_create_payment_wraps_banking_payment_and_keeps_token_out_of_body(
    api: respx.MockRouter, client: FakturowniaClient
) -> None:
    create = api.post("/banking/payments.json").mock(
        return_value=httpx.Response(201, json=PAYMENT_JSON)
    )

    payment = client.create_payment(
        {"name": "Payment 001", "price": 100.05, "invoice_ids": [555, 666], "kind": "api"}
    )

    assert payment.id == 77
    body = json.loads(create.calls.last.request.content)
    assert body == {
        "banking_payment": {
            "name": "Payment 001",
            "price": 100.05,
            "invoice_ids": [555, 666],
            "kind": "api",
        }
    }
    assert "secret-token" not in create.calls.last.request.content.decode()
    assert "api_token" not in str(create.calls.last.request.url)


def test_update_payment_uses_patch(api: respx.MockRouter, client: FakturowniaClient) -> None:
    update = api.patch("/banking/payments/77.json").mock(
        return_value=httpx.Response(200, json=PAYMENT_JSON)
    )

    client.update_payment(77, {"name": "New name"})

    assert json.loads(update.calls.last.request.content) == {
        "banking_payment": {"name": "New name"}
    }


def test_delete_payment(api: respx.MockRouter, client: FakturowniaClient) -> None:
    delete = api.delete("/banking/payments/77.json").mock(return_value=httpx.Response(200))

    client.delete_payment(77)

    assert delete.called


def test_iter_payments_paginates(api: respx.MockRouter, client: FakturowniaClient) -> None:
    pages = {
        "1": [dict(PAYMENT_JSON, id=i) for i in range(1, 101)],
        "2": [dict(PAYMENT_JSON, id=101)],
    }
    api.get("/banking/payments.json").mock(
        side_effect=lambda request: httpx.Response(
            200, json=pages[dict(request.url.params)["page"]]
        )
    )

    assert len(list(client.iter_payments())) == 101


def test_send_invoice_by_email_params(api: respx.MockRouter, client: FakturowniaClient) -> None:
    route = api.post("/invoices/1/send_by_email.json").mock(
        return_value=httpx.Response(200, json={"code": "success"})
    )

    client.send_invoice_by_email(
        1,
        email_to=["a@acme.pl", "b@acme.pl"],
        email_cc="c@acme.pl",
        email_pdf=True,
        print_option="duplicate",
    )

    params = dict(httpx.URL(str(route.calls.last.request.url)).params)
    assert params["email_to"] == "a@acme.pl,b@acme.pl"  # list joined into the comma format
    assert params["email_cc"] == "c@acme.pl"
    assert params["email_pdf"] == "true"
    assert params["print_option"] == "duplicate"
    assert "update_buyer_email" not in params
    assert "api_token" not in params


def test_send_invoice_by_email_defaults_to_buyer(
    api: respx.MockRouter, client: FakturowniaClient
) -> None:
    route = api.post("/invoices/1/send_by_email.json").mock(
        return_value=httpx.Response(200, json={"code": "success"})
    )

    client.send_invoice_by_email(1)

    assert dict(httpx.URL(str(route.calls.last.request.url)).params) == {}


def test_send_invoice_by_email_rejects_error_envelope(
    api: respx.MockRouter, client: FakturowniaClient
) -> None:
    api.post("/invoices/1/send_by_email.json").mock(
        return_value=httpx.Response(200, json={"code": "error", "message": "no buyer email"})
    )

    with pytest.raises(FakturowniaError, match="no buyer email"):
        client.send_invoice_by_email(1)
