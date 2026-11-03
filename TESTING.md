# Validation
From this checkout run:

```sh
uv sync --frozen
uv run pytest -q
uv run ruff check src tests migrations
uv run alembic upgrade head
uv run alembic upgrade head
uv run alembic check
```

Use only development DATABASE_URL. 63 tests currently pass. They cover private API auth,
URL/SSRF validation, canonical and near-duplicates, transcript gating, research schema,
mocked local-model integration, score/approval/audit flow, stale writes, safe official feeds,
metadata failures, body caps, Telegram authorization and command handling, Tehran timing,
durable polling offsets, uncertain delivery handling and rate-limit retries. The full mocked
manual-link → transcript → research → Telegram report → approval path executes. Migration tests
upgrade populated revision 0001 to 0003, repeat the upgrade and check schema consistency.

A separate real loopback server smoke test used a fresh migrated temporary database and a
generated ephemeral token: health, persisted link, missing-transcript rejection and invalid-token
rejection passed. No secrets were printed; the temporary server was stopped afterward.

No actual paid service, Telegram message, YouTube retrieval, live model inference or production
connection was used. PostgreSQL, research quality, official discovery quotas and real scheduled
delivery remain unverified. One upstream Starlette TestClient/httpx deprecation warning remains.
The full media/script/render/export workflow is not implemented or tested.
