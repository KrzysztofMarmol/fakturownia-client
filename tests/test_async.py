import json

import httpx
import pytest
import respx

from fakturownia_client import (
    AsyncFakturowniaClient,
    Invoice,
    NotFoundError,
)
from tests.conftest import TOKEN


@pytest.fixture
async def aclient(api: respx.MockRouter) -> AsyncFakturowniaClient:
    async with AsyncFakturowniaClient("testfirma", TOKEN, max_retries=0) as fk:
        yield fk


async def test_async_list_invoices_uses_bearer_header(
    api: respx.MockRouter, aclient: AsyncFakturowniaClient
) -> None:
    route = api.get("/invoices.json").mock(
        return_value=httpx.Response(200, json=[{"id": 1, "number": "A/1"}])
    )

    invoices = await aclient.list_invoices(period="this_month")

    assert isinstance(invoices[0], Invoice)
    request = route.calls.last.request
    assert request.headers["Authorization"] == f"Bearer {TOKEN}"
    assert "api_token" not in str(request.url)


async def test_async_create_invoice_wraps_payload(
    api: respx.MockRouter, aclient: AsyncFakturowniaClient
) -> None:
    route = api.post("/invoices.json").mock(return_value=httpx.Response(201, json={"id": 2}))

    created = await aclient.create_invoice({"buyer_name": "ACME"})

    assert created.id == 2
    assert json.loads(route.calls.last.request.content) == {"invoice": {"buyer_name": "ACME"}}


async def test_async_iter_invoices_paginates(
    api: respx.MockRouter, aclient: AsyncFakturowniaClient
) -> None:
    route = api.get("/invoices.json").mock(
        side_effect=[
            httpx.Response(200, json=[{"id": i} for i in range(100)]),
            httpx.Response(200, json=[{"id": 100}]),
        ]
    )

    invoices = [inv async for inv in aclient.iter_invoices()]

    assert len(invoices) == 101
    assert route.call_count == 2


async def test_async_error_mapping(api: respx.MockRouter, aclient: AsyncFakturowniaClient) -> None:
    api.get("/invoices/1.json").mock(
        return_value=httpx.Response(404, json={"code": "error", "message": "nope"})
    )

    with pytest.raises(NotFoundError):
        await aclient.get_invoice(1)


async def test_async_pdf_bytes(api: respx.MockRouter, aclient: AsyncFakturowniaClient) -> None:
    api.get("/invoices/1.pdf").mock(return_value=httpx.Response(200, content=b"%PDF"))

    assert await aclient.download_invoice_pdf(1) == b"%PDF"
