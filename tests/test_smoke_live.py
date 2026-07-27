"""Read-only smoke tests against the real API. Run manually:

FAKTUROWNIA_DOMAIN=... FAKTUROWNIA_API_TOKEN=... uv run pytest -m live -v
"""

import os

import pytest

from fakturownia_client import FakturowniaClient

DOMAIN = os.environ.get("FAKTUROWNIA_DOMAIN")
TOKEN = os.environ.get("FAKTUROWNIA_API_TOKEN")

pytestmark = [
    pytest.mark.live,
    pytest.mark.skipif(
        not (DOMAIN and TOKEN),
        reason="FAKTUROWNIA_DOMAIN and FAKTUROWNIA_API_TOKEN not set",
    ),
]


@pytest.fixture(scope="module")
def fk() -> FakturowniaClient:
    assert DOMAIN is not None and TOKEN is not None
    return FakturowniaClient(DOMAIN, TOKEN)


def test_list_invoices(fk: FakturowniaClient) -> None:
    invoices = fk.list_invoices(per_page=1)
    assert isinstance(invoices, list)


def test_list_clients(fk: FakturowniaClient) -> None:
    assert isinstance(fk.list_clients(per_page=1), list)


def test_list_products(fk: FakturowniaClient) -> None:
    assert isinstance(fk.list_products(per_page=1), list)
