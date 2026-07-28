# Contributing / Development

```bash
git clone https://github.com/KrzysztofMarmol/fakturownia-client
cd fakturownia-client
uv sync --extra dev
```

Checks (CI runs the same set on pushes, PRs and release tags):

```bash
uv run ruff check . && uv run ruff format --check .
uv run mypy
uv run pytest -m "not live" --cov=fakturownia_client --cov-fail-under=90
```

Optional read-only smoke test against a real account:

```bash
FAKTUROWNIA_DOMAIN=... FAKTUROWNIA_API_TOKEN=... uv run pytest -m live -v
```

## Releasing

1. Bump `__version__` in `src/fakturownia_client/_version.py`
   (pyproject reads it dynamically) and update `CHANGELOG.md`.
2. Commit, then `git tag vX.Y.Z && git push origin vX.Y.Z`.
3. `publish.yml` tests, builds and uploads to PyPI.

Release this package **before** `fakturownia-mcp` when the server depends
on new client features.
