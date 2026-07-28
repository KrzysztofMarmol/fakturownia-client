"""InvoiceOcean API client — alias for :mod:`fakturownia_client`.

InvoiceOcean is the international brand of Fakturownia; both run the same
API. This package re-exports everything from ``fakturownia_client`` and adds
brand-matching class aliases. Pass your full domain, e.g.
``InvoiceOceanClient("mycompany.invoiceocean.com", api_token=...)``.
"""

from fakturownia_client import *  # noqa: F401,F403
from fakturownia_client import (  # noqa: F401
    AsyncFakturowniaClient,
    FakturowniaClient,
    __version__,
)

InvoiceOceanClient = FakturowniaClient
AsyncInvoiceOceanClient = AsyncFakturowniaClient
