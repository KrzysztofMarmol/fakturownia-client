# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Commands

```bash
uv sync --extra dev                 # install (uv-managed venv)
uv run ruff check . && uv run ruff format --check .
uv run mypy                         # strict, src/ only
uv run pytest -m "not live"         # full offline suite (respx mocks)
uv run pytest tests/test_invoices.py::test_create_invoice_wraps_payload_and_keeps_token_out_of_body
FAKTUROWNIA_DOMAIN=... FAKTUROWNIA_API_TOKEN=... uv run pytest -m live   # read-only, real API
uv build && uv build aliases/invoiceocean-client -o dist                 # both wheels
```

CI (`ci.yml`, push/PR) runs the same set with `--cov-fail-under=90` on Python 3.10/3.12/3.13.

## Architecture

Single source of truth for endpoints is `src/fakturownia_client/_ops.py`: each
function builds an `Op` (method, path, params, json_body, `parse` callback).
`client.py` (sync, `httpx.Client`) and `async_client.py` (async) are thin
transports over the same Ops — **any endpoint change happens once in `_ops.py`**;
the two clients only mirror method signatures.

Request flow: `_execute` → `_send` (retry loop driven by `_retry.RetryPolicy`:
429/5xx/transport errors, honours `Retry-After`, exponential backoff + jitter)
→ `exceptions.raise_for_status` (typed hierarchy; 400 `BadRequestError` is a
subclass of 422 `ValidationError`) → `_parse` (wraps JSON/pydantic failures in
`ResponseParseError`; note the deliberate distinction from pydantic's own
`ValidationError`, which this library never lets escape).

Other load-bearing pieces:
- `_base.py` — `normalize_domain`: bare name gets `.fakturownia.pl`; anything
  containing a dot passes through unchanged (this is how InvoiceOcean /
  VosFactures / BitFactura regional domains work — do not "fix" it).
- `models.py` — pydantic v2, `extra="allow"` (API returns ~80 fields; only the
  important ones are typed). Money stays `str` on purpose (no float rounding).
  Blank-string dates (`""`) are coerced to `None` by validators.
- `pagination.py` — `iter_pages`/`aiter_pages`; stop condition is a short page;
  a repeated identical page raises (guards against APIs ignoring `page`).
- `download_invoice_pdf` validates the `%PDF` signature (redirects are
  followed; an HTML body raises `ResponseParseError`).
- `delete_product` calls an endpoint absent from official API docs — keep the
  caveat in its docstring; it has no MCP exposure.

## Hard invariants (tests enforce these)

- The API token travels **only** in the `Authorization: Bearer` header — never
  in URLs, request bodies, logs or exception messages.
- `change_invoice_status` must reject the API's `200 + {"code": "error"}`
  envelope (`_checked_envelope` in `_ops.py`).

## Releasing

Version is single-sourced from `src/fakturownia_client/_version.py`. The alias
metapackage `aliases/invoiceocean-client/pyproject.toml` must carry the **same
version** and an exact `fakturownia-client==<version>` pin — `publish.yml` has
a check step that fails the release otherwise. Flow: bump both + `CHANGELOG.md`
→ commit → wait for green CI → `git tag vX.Y.Z && git push origin vX.Y.Z`
(publishes main package and alias together). Release this repo **before**
`fakturownia-mcp` (sibling repo) when the server needs new client features.

## Conventions

- Do not add `Co-Authored-By` trailers to commits.
- `gh run view --json conclusion` exits 0 even for failed runs — never use it
  as a `&&` gate; read the conclusion value instead.
- This is an unofficial project: keep the trademark disclaimer wording in
  README/descriptions intact; InvoiceOcean-facing examples use English and
  `mycompany`, not `firma`.
