import httpx
import respx

from fakturownia_client import FakturowniaClient
from fakturownia_client.pagination import iter_pages


def test_iter_pages_stops_on_short_page() -> None:
    pages = {1: list(range(100)), 2: list(range(100, 140))}
    calls: list[int] = []

    def fetch(page: int) -> list[int]:
        calls.append(page)
        return pages.get(page, [])

    items = list(iter_pages(fetch))

    assert len(items) == 140
    assert calls == [1, 2]  # short page 2 ends iteration without a third request


def test_iter_pages_empty_first_page() -> None:
    assert list(iter_pages(lambda page: [])) == []


def test_iter_invoices_paginates_with_max_per_page(
    api: respx.MockRouter, client: FakturowniaClient
) -> None:
    full_page = [{"id": i} for i in range(100)]
    short_page = [{"id": 100}]
    route = api.get("/invoices.json").mock(
        side_effect=[
            httpx.Response(200, json=full_page),
            httpx.Response(200, json=short_page),
        ]
    )

    invoices = list(client.iter_invoices(period="this_year"))

    assert len(invoices) == 101
    assert route.call_count == 2
    first_params = dict(httpx.URL(str(route.calls[0].request.url)).params)
    assert first_params["per_page"] == "100"
    assert first_params["page"] == "1"
    assert dict(httpx.URL(str(route.calls[1].request.url)).params)["page"] == "2"
