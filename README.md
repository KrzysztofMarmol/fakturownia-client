# fakturownia-client

[![PyPI](https://img.shields.io/pypi/v/fakturownia-client)](https://pypi.org/project/fakturownia-client/)
[![CI](https://github.com/KrzysztofMarmol/fakturownia-client/actions/workflows/ci.yml/badge.svg)](https://github.com/KrzysztofMarmol/fakturownia-client/actions/workflows/ci.yml)
[![Python](https://img.shields.io/pypi/pyversions/fakturownia-client)](https://pypi.org/project/fakturownia-client/)
[![License: MIT](https://img.shields.io/badge/license-MIT-green.svg)](LICENSE)

Python client for the [Fakturownia](https://fakturownia.pl) (InvoiceOcean) REST API.
Covers invoices (list/search, create/update, status changes, PDF download),
clients (CRUD) and products.

## Security note: token in header, never in URL

The official Fakturownia docs mostly show `?api_token=...` in URLs, which leaks
tokens into server and proxy logs. This client sends the token **only** in the
`Authorization: Bearer` header. Header auth was verified against the live API
for every endpoint used here (see `scripts/verify_auth.py` — a no-side-effects
check you can run against your own account).

## Install

```bash
uv add fakturownia-client   # or: pip install fakturownia-client
```

## Usage

```python
from fakturownia_client import FakturowniaClient, InvoiceCreate, InvoicePositionCreate

with FakturowniaClient("mycompany", api_token="...") as fk:
    # list & search
    invoices = fk.list_invoices(period="this_month", include_positions=True)
    for inv in fk.iter_invoices(period="this_year"):  # auto-pagination
        print(inv.number, inv.price_gross)

    # create
    created = fk.create_invoice(
        InvoiceCreate(
            buyer_name="ACME Sp. z o.o.",
            buyer_tax_no="1234567890",
            positions=[InvoicePositionCreate(name="Usługa", total_price_gross=123.00, tax=23)],
        )
    )

    # status & PDF
    fk.change_invoice_status(created.id, "paid")
    pdf = fk.download_invoice_pdf(created.id)

    # clients / products
    clients = fk.list_clients(tax_no="1234567890")
    products = fk.list_products()
```

### Async

`AsyncFakturowniaClient` mirrors the sync API 1:1 on `httpx.AsyncClient`:

```python
from fakturownia_client import AsyncFakturowniaClient

async with AsyncFakturowniaClient("mycompany", api_token="...") as fk:
    invoices = await fk.list_invoices(period="this_month")
    async for inv in fk.iter_invoices(period="this_year"):
        print(inv.number)
```

`domain` accepts `"mycompany"`, `"mycompany.fakturownia.pl"` or a full URL.
Errors raise typed exceptions: `AuthenticationError`, `NotFoundError`,
`ValidationError`, `RateLimitError`, `ServerError` (all subclass `FakturowniaError`).

Caveat: `delete_product()` calls an endpoint absent from the official API docs —
it may not work on all accounts.

## Development

```bash
uv sync --extra dev
uv run ruff check . && uv run mypy && uv run pytest -m "not live"

# optional read-only smoke test against the real API:
FAKTUROWNIA_DOMAIN=mycompany FAKTUROWNIA_API_TOKEN=... uv run pytest -m live
```

## License

MIT
