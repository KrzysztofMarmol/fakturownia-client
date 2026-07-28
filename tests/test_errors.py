import httpx
import pytest
import respx

from fakturownia_client import (
    AuthenticationError,
    FakturowniaClient,
    FakturowniaError,
    NotFoundError,
    RateLimitError,
    ServerError,
    ValidationError,
    normalize_domain,
)
from tests.conftest import TOKEN


@pytest.mark.parametrize(
    ("status", "exc"),
    [
        (401, AuthenticationError),
        (403, AuthenticationError),
        (404, NotFoundError),
        (400, ValidationError),
        (422, ValidationError),
        (429, RateLimitError),
        (500, ServerError),
        (502, ServerError),
        (418, FakturowniaError),
    ],
)
def test_status_code_mapping(
    api: respx.MockRouter, client: FakturowniaClient, status: int, exc: type[FakturowniaError]
) -> None:
    api.get("/invoices/1.json").mock(
        return_value=httpx.Response(status, json={"code": "error", "message": "boom"})
    )

    with pytest.raises(exc) as excinfo:
        client.get_invoice(1)

    assert excinfo.value.status_code == status
    assert "boom" in str(excinfo.value)


def test_non_json_error_body_is_truncated_not_crashing(
    api: respx.MockRouter, client: FakturowniaClient
) -> None:
    api.get("/invoices/1.json").mock(return_value=httpx.Response(500, text="<html>oops</html>"))

    with pytest.raises(ServerError, match="oops"):
        client.get_invoice(1)


def test_error_message_never_contains_token(
    api: respx.MockRouter, client: FakturowniaClient
) -> None:
    api.get("/invoices/1.json").mock(
        return_value=httpx.Response(401, json={"code": "error", "message": "unauthorized"})
    )

    with pytest.raises(AuthenticationError) as excinfo:
        client.get_invoice(1)

    assert TOKEN not in str(excinfo.value)


@pytest.mark.parametrize(
    "raw",
    [
        "firma",
        "firma.fakturownia.pl",
        "https://firma.fakturownia.pl",
        "https://firma.fakturownia.pl/api",
    ],
)
def test_normalize_domain_variants(raw: str) -> None:
    assert normalize_domain(raw) == "firma.fakturownia.pl"


@pytest.mark.parametrize(
    "raw",
    [
        "mycompany.invoiceocean.com",
        "https://mycompany.invoiceocean.com",
        "mycompany.invoiceocean.com/api",
    ],
)
def test_normalize_domain_keeps_invoiceocean_hosts(raw: str) -> None:
    assert normalize_domain(raw) == "mycompany.invoiceocean.com"


def test_normalize_domain_rejects_empty() -> None:
    with pytest.raises(ValueError):
        normalize_domain("https://")


def test_client_rejects_empty_token() -> None:
    with pytest.raises(ValueError):
        FakturowniaClient("firma", "")
