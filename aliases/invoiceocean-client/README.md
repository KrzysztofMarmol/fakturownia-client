# invoiceocean-client

Python client for the [InvoiceOcean](https://invoiceocean.com) REST API.

This is an **official alias** for
[`fakturownia-client`](https://pypi.org/project/fakturownia-client/) —
InvoiceOcean is the international brand of Fakturownia and both run the same
API. The alias pins the exact matching release and re-exports the full API
with brand-matching class names:

```python
from invoiceocean_client import InvoiceOceanClient

with InvoiceOceanClient("mycompany.invoiceocean.com", api_token="...") as io:
    invoices = io.list_invoices(period="this_month")
```

`AsyncInvoiceOceanClient` mirrors the sync API on `httpx.AsyncClient`.
The API token is sent only in the `Authorization: Bearer` header — never in
URLs. Full documentation lives in the
[fakturownia-client repository](https://github.com/KrzysztofMarmol/fakturownia-client).

## License

MIT
