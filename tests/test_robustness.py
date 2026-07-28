"""Tests for M0/M1 hardening: redirects, retries, parse errors, blank dates."""

import httpx
import pytest
import respx

from fakturownia_client import (
    AsyncFakturowniaClient,
    BadRequestError,
    FakturowniaClient,
    FakturowniaError,
    RateLimitError,
    ResponseParseError,
    RetryPolicy,
    TransportError,
    ValidationError,
)
from tests.conftest import TOKEN

FAST_RETRY = RetryPolicy(max_retries=2, backoff_base=0.0, backoff_max=0.0)


@pytest.fixture
def retry_client(api: respx.MockRouter) -> FakturowniaClient:
    with FakturowniaClient("testfirma", TOKEN, retry_policy=FAST_RETRY) as fk:
        yield fk


# -- PDF: redirects and signature ------------------------------------------------


def test_pdf_follows_redirect(api: respx.MockRouter, client: FakturowniaClient) -> None:
    api.get("/invoices/1.pdf").mock(
        return_value=httpx.Response(302, headers={"Location": "/storage/1.pdf"})
    )
    api.get("/storage/1.pdf").mock(return_value=httpx.Response(200, content=b"%PDF-1.7 real"))

    assert client.download_invoice_pdf(1).startswith(b"%PDF")


def test_pdf_html_body_raises_parse_error(api: respx.MockRouter, client: FakturowniaClient) -> None:
    api.get("/invoices/1.pdf").mock(
        return_value=httpx.Response(200, content=b"<html>login page</html>")
    )

    with pytest.raises(ResponseParseError, match="not a PDF"):
        client.download_invoice_pdf(1)


# -- retries ----------------------------------------------------------------------


def test_retry_on_429_then_success(api: respx.MockRouter, retry_client: FakturowniaClient) -> None:
    route = api.get("/invoices.json").mock(
        side_effect=[
            httpx.Response(429, headers={"Retry-After": "0"}),
            httpx.Response(200, json=[]),
        ]
    )

    assert retry_client.list_invoices() == []
    assert route.call_count == 2


def test_retry_on_500_then_success(api: respx.MockRouter, retry_client: FakturowniaClient) -> None:
    route = api.get("/products.json").mock(
        side_effect=[httpx.Response(500), httpx.Response(200, json=[])]
    )

    assert retry_client.list_products() == []
    assert route.call_count == 2


def test_retries_exhausted_raises_rate_limit_with_retry_after(
    api: respx.MockRouter, retry_client: FakturowniaClient
) -> None:
    api.get("/invoices.json").mock(
        return_value=httpx.Response(429, headers={"Retry-After": "7"}, json={"message": "slow"})
    )

    with pytest.raises(RateLimitError) as excinfo:
        retry_client.list_invoices()

    assert excinfo.value.retry_after == 7.0
    assert excinfo.value.response is not None


def test_no_retry_on_404(api: respx.MockRouter, retry_client: FakturowniaClient) -> None:
    route = api.get("/invoices/1.json").mock(return_value=httpx.Response(404))

    with pytest.raises(FakturowniaError):
        retry_client.get_invoice(1)

    assert route.call_count == 1


def test_transport_error_wrapped_and_retried(
    api: respx.MockRouter, retry_client: FakturowniaClient
) -> None:
    route = api.get("/clients.json").mock(
        side_effect=[httpx.ConnectError("boom"), httpx.Response(200, json=[])]
    )

    assert retry_client.list_clients() == []
    assert route.call_count == 2


def test_transport_error_exhausted_raises_typed(
    api: respx.MockRouter, client: FakturowniaClient
) -> None:
    api.get("/clients.json").mock(side_effect=httpx.ConnectError("boom"))

    with pytest.raises(TransportError, match="clients.json"):
        client.list_clients()


# -- error envelope & mapping -------------------------------------------------------


def test_change_status_error_envelope_raises(
    api: respx.MockRouter, client: FakturowniaClient
) -> None:
    api.post("/invoices/1/change_status.json").mock(
        return_value=httpx.Response(200, json={"code": "error", "message": "cannot change"})
    )

    with pytest.raises(FakturowniaError, match="cannot change"):
        client.change_invoice_status(1, "paid")


def test_change_status_success_envelope_returned(
    api: respx.MockRouter, client: FakturowniaClient
) -> None:
    api.post("/invoices/1/change_status.json").mock(
        return_value=httpx.Response(200, json={"code": "success"})
    )

    assert client.change_invoice_status(1, "paid") == {"code": "success"}


def test_400_is_bad_request_and_validation_subclass(
    api: respx.MockRouter, client: FakturowniaClient
) -> None:
    api.post("/invoices.json").mock(
        return_value=httpx.Response(400, json={"code": "error", "message": "missing invoice data"})
    )

    with pytest.raises(BadRequestError) as excinfo:
        client.create_invoice({})

    assert isinstance(excinfo.value, ValidationError)


# -- parse errors -------------------------------------------------------------------


def test_non_json_200_raises_parse_error(api: respx.MockRouter, client: FakturowniaClient) -> None:
    api.get("/invoices.json").mock(return_value=httpx.Response(200, content=b"<html>oops</html>"))

    with pytest.raises(ResponseParseError):
        client.list_invoices()


def test_empty_200_body_on_list_raises_parse_error(
    api: respx.MockRouter, client: FakturowniaClient
) -> None:
    api.get("/invoices.json").mock(return_value=httpx.Response(200, content=b""))

    with pytest.raises(ResponseParseError):
        client.list_invoices()


# -- model robustness ------------------------------------------------------------------


def test_blank_date_strings_parse_as_none(api: respx.MockRouter, client: FakturowniaClient) -> None:
    api.get("/invoices.json").mock(
        return_value=httpx.Response(
            200,
            json=[{"id": 1, "issue_date": "", "payment_to": "", "paid_date": "", "sell_date": ""}],
        )
    )

    (invoice,) = client.list_invoices()

    assert invoice.issue_date is None
    assert invoice.payment_to is None


# -- pagination -------------------------------------------------------------------------


def test_iter_clients_paginates(api: respx.MockRouter, client: FakturowniaClient) -> None:
    route = api.get("/clients.json").mock(
        side_effect=[
            httpx.Response(200, json=[{"id": i} for i in range(100)]),
            httpx.Response(200, json=[{"id": 100}]),
        ]
    )

    assert len(list(client.iter_clients())) == 101
    assert route.call_count == 2


def test_iter_products_paginates(api: respx.MockRouter, client: FakturowniaClient) -> None:
    api.get("/products.json").mock(return_value=httpx.Response(200, json=[{"id": 9}]))

    assert len(list(client.iter_products())) == 1


def test_pagination_guard_detects_non_advancing_pages(
    api: respx.MockRouter, client: FakturowniaClient
) -> None:
    same_page = [{"id": i} for i in range(100)]
    api.get("/invoices.json").mock(return_value=httpx.Response(200, json=same_page))

    with pytest.raises(FakturowniaError, match="not advancing"):
        list(client.iter_invoices())


async def test_async_iter_clients_and_guard(api: respx.MockRouter) -> None:
    async with AsyncFakturowniaClient("testfirma", TOKEN, max_retries=0) as fk:
        api.get("/clients.json").mock(
            side_effect=[
                httpx.Response(200, json=[{"id": i} for i in range(100)]),
                httpx.Response(200, json=[{"id": 100}]),
            ]
        )
        assert len([c async for c in fk.iter_clients()]) == 101

        api.get("/products.json").mock(return_value=httpx.Response(200, json=[{"id": 9}]))
        assert len([p async for p in fk.iter_products()]) == 1


async def test_async_retry_on_429(api: respx.MockRouter) -> None:
    async with AsyncFakturowniaClient("testfirma", TOKEN, retry_policy=FAST_RETRY) as fk:
        route = api.get("/invoices.json").mock(
            side_effect=[
                httpx.Response(429, headers={"Retry-After": "0"}),
                httpx.Response(200, json=[]),
            ]
        )

        assert await fk.list_invoices() == []
        assert route.call_count == 2


def test_user_agent_header_sent(api: respx.MockRouter, client: FakturowniaClient) -> None:
    route = api.get("/invoices.json").mock(return_value=httpx.Response(200, json=[]))

    client.list_invoices()

    assert route.calls.last.request.headers["User-Agent"].startswith("fakturownia-client/")
