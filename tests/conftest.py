from collections.abc import Iterator

import pytest
import respx

from fakturownia_client import FakturowniaClient

BASE = "https://testfirma.fakturownia.pl"
TOKEN = "secret-token-123"


@pytest.fixture
def api() -> Iterator[respx.MockRouter]:
    with respx.mock(base_url=BASE, assert_all_called=False) as router:
        yield router


@pytest.fixture
def client(api: respx.MockRouter) -> Iterator[FakturowniaClient]:
    with FakturowniaClient("testfirma", TOKEN) as fk:
        yield fk
