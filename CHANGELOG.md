# Changelog

All notable changes to this project are documented here.
Format: [Keep a Changelog](https://keepachangelog.com/), versioning: SemVer.

## [0.1.0] - 2026-07-28

### Added
- Automatic retries with exponential backoff and jitter on 429/5xx and
  transport errors; `Retry-After` is honoured. Configurable via
  `max_retries` or a custom `RetryPolicy`.
- New exceptions: `BadRequestError` (400, subclass of `ValidationError`),
  `TransportError` (network failures), `ResponseParseError` (unparseable
  2xx bodies). All exceptions now carry the `httpx.Response`;
  `RateLimitError` exposes `retry_after`.
- DEBUG/INFO logging (`logging.getLogger("fakturownia_client.*")`) — never
  includes the API token.
- `User-Agent: fakturownia-client/<version>` header.
- `timeout` accepts `httpx.Timeout`; new `verify` and `limits` passthroughs.
- Async pagination helper `aiter_pages`; `iter_products` accepts filters.

### Fixed
- PDF downloads now follow redirects and validate the `%PDF` signature —
  previously a 302 response body could be silently saved as a "PDF".
- `change_invoice_status` raises on the API's `200 + {"code": "error"}`
  envelope instead of reporting success.
- Blank date strings (`""`) in API responses parse as `None` instead of
  failing the whole page.
- Pagination aborts with a clear error if the API ignores the `page`
  parameter (previously an infinite loop).

### Changed
- Version is single-sourced from `fakturownia_client.__version__`.
- License metadata migrated to PEP 639.

## [0.0.1] - 2026-07-28

### Added
- Initial release: sync (`FakturowniaClient`) and async
  (`AsyncFakturowniaClient`) clients for invoices, clients and products;
  Bearer-header-only authentication; pydantic v2 models; typed exceptions;
  auto-pagination.
