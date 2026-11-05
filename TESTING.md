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

Use only development DATABASE_URL. 67 tests currently pass. They cover private API auth,
URL/SSRF validation, canonical and near-duplicates, transcript gating, research schema,
mocked local-model integration, score/approval/audit flow, stale writes, safe official feeds,
metadata failures, body caps, Telegram authorization and command handling, Tehran timing,
durable polling offsets, uncertain delivery handling and rate-limit retries. The full mocked
manual-link → transcript → research → Telegram report → approval path executes. Migration tests
upgrade populated revision 0001 to 0003, repeat the upgrade and check schema consistency.

A separate real loopback server smoke test used a fresh migrated temporary database and a
generated ephemeral token: health, persisted link, missing-transcript rejection and invalid-token
rejection passed. No secrets were printed; the temporary server was stopped afterward.

Live development validation on 2026-11-05: Telegram getMe succeeded, a founder-submitted
YouTube URL was persisted and its private bot reply was confirmed. A current-day report
outbox record is sent. This verifies delivery during a test session, not an unattended 05:00
run or continuous uptime. No live inline approval callback has been exercised.
The YouTube metadata attempt failed at the proxy with 403; no source analysis is claimed.
No paid service, live model inference or production connection was used. PostgreSQL, research
quality, official discovery quotas and unattended scheduling remain unverified. One upstream Starlette TestClient/httpx deprecation warning remains.
The full media/script/render/export workflow is not implemented or tested.
