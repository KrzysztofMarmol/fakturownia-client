"""Python client for the Fakturownia (InvoiceOcean) REST API."""

from .async_client import AsyncFakturowniaClient
from .client import FakturowniaClient, normalize_domain
from .exceptions import (
    AuthenticationError,
    FakturowniaError,
    NotFoundError,
    RateLimitError,
    ServerError,
    ValidationError,
)
from .models import (
    Client,
    Invoice,
    InvoiceCreate,
    InvoiceKind,
    InvoicePosition,
    InvoicePositionCreate,
    InvoiceStatus,
    Product,
)

__version__ = "0.0.1"

__all__ = [
    "AsyncFakturowniaClient",
    "AuthenticationError",
    "Client",
    "FakturowniaClient",
    "FakturowniaError",
    "Invoice",
    "InvoiceCreate",
    "InvoiceKind",
    "InvoicePosition",
    "InvoicePositionCreate",
    "InvoiceStatus",
    "NotFoundError",
    "Product",
    "RateLimitError",
    "ServerError",
    "ValidationError",
    "__version__",
    "normalize_domain",
]
