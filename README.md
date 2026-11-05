# 3EO Content Studio

Private, approval-driven Persian SEO research and production system. This branch implements
the manual-link Scout workflow and private Telegram worker; live integrations require setup.
See [status](DEVELOPMENT_STATUS.md), [architecture](ARCHITECTURE.md) and [brief](REQUIREMENTS.md).
Video production and the dashboard are not implemented. No production deployment is authorized.

## Local development
Python 3.12+ and uv required. From this repository:

```sh
export UV_CACHE_DIR=/workspace/.cache/uv
export UV_PROJECT_ENVIRONMENT="$PWD/.venv"
uv sync --frozen
uv run alembic upgrade head
uv run alembic check
uv run pytest -q
uv run uvicorn studio.api:create_app --factory --host 127.0.0.1 --port 8000
```

Use only a development database. Default is ignored `studio.db`; `DATABASE_URL` can select
another database. PostgreSQL driver support is present but integration testing is pending.
Set `STUDIO_ADMIN_TOKEN` securely before starting authenticated operations; unset means denied.
Never commit or print tokens. The API and worker must share the same development database.
`GET /health` verifies migrated storage, not external integration readiness. All content routes
require `Authorization: Bearer <token>`. No public docs, preview or media exposure is enabled.

## Manual workflow
1. `POST /items`: `{"url":"https://youtu.be/abcdefghijk"}`. Variants share an ID.
2. Optional `POST /items/{id}/metadata`: public YouTube oEmbed only; no automatic transcript.
3. `PUT /items/{id}/transcript`: `text`, `provenance`, optional `author`/`published_at`.
4. `POST /items/{id}/research`: submit reviewed research matching `studio.research.Research`,
   or omit the body to use the configured local provider. Missing provider returns 503.
5. `GET /items` lists the latest 100. `GET /items/{id}/duplicates` suggests similar items.
6. `POST /items/{id}/transition`: `status` IDEA_APPROVED, REJECTED, SAVED or MORE_RESEARCH.
7. `POST /reports/prepare` snapshots up to five researched ideas after 05:00 Tehran.
   This endpoint alone sends nothing. The day's snapshot is immutable on repeat calls.

## Local research provider
Install and validate an appropriate Persian-capable Ollama model separately, then set
`STUDIO_OLLAMA_MODEL` to its installed name before starting the API. Calls target only
`http://127.0.0.1:11434/api/chat`. No model is downloaded by the app and no paid APIs are used.
Model responses require schema validation and founder fact checking; schema validity is not
proof of truth, Persian fluency or original quality. Without a model, reviewed research still works.

## Private Telegram worker
Set a dedicated `STUDIO_TELEGRAM_TOKEN`, positive comma-separated `STUDIO_TELEGRAM_USERS`,
and the same `STUDIO_ADMIN_TOKEN` as the API, securely in environment settings. Never reuse
Espadna credentials. Explicitly set `STUDIO_TELEGRAM_ENABLED=1` only when private bot operation
is authorized; the worker otherwise exits without network requests. With the API running:

```sh
uv run python -m studio.worker
```

`--once` runs one cycle and exits nonzero on failure. Commands: send a URL; `/metadata ID`;
`/transcript ID` followed by a provenance line and the authorized transcript; `/analyze ID`;
`/today`; `/ideas`; `/idea ID`; `/approve ID`; `/reject ID`; `/save ID`; `/research ID` (request more research).
Only approved users in private chats are accepted. No automatic publication or script generation.

The worker checks for current-day reports after 05:00 Asia/Tehran. Healthy cycle latency can
include a 20-second long poll and a five-second wait; exact-second dispatch is not guaranteed.
One worker per shared database/token; process lock defaults to ignored `studio-worker.lock`.
Do not move/change the lock path while another worker is running. See OPERATIONS.md for
uncertain delivery recovery. A private bot session was validated in cloud development; it is not a production service.
New reports include inline approval buttons; every callback checks the sender allowlist.

## Official feeds
`POST /sources` accepts `name`, HTTPS `url`, and optional `enabled` (default true).
Supported hosts: developers.google.com, status.search.google.com, blog.google. Configure a
real published RSS/Atom URL; the app does not guess endpoints. `GET /sources` lists sources;
`POST /sources/{id}/refresh` ingests up to 50 feed entries. Reposting a source URL updates
its name/enabled flag. Refresh is explicit, not an automatic discovery schedule. Excerpts
are identified as limited evidence and never presented as full-article/video transcripts.
