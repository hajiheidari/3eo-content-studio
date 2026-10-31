# 3EO Content Studio

Private, approval-driven Persian SEO research and production system. This branch implements
an M1 foundation; automatic discovery, live bot scheduling and video production are pending.
See [implementation status](DEVELOPMENT_STATUS.md) and [original brief](REQUIREMENTS.md).

## Local development
Python 3.12+ and uv required. From this repository:

```sh
export UV_CACHE_DIR=/workspace/.cache/uv
export UV_PROJECT_ENVIRONMENT="$PWD/.venv"
uv sync --frozen
uv run alembic upgrade head
uv run pytest -q
uv run uvicorn studio.api:create_app --factory --host 127.0.0.1 --port 8000
```

Set `STUDIO_ADMIN_TOKEN` securely in your process environment before starting for authenticated
content operations; without it, content requests are denied. Do not commit it. Default DB is
local ignored `studio.db`; set DATABASE_URL for another database (PostgreSQL driver supported,
not yet integration-tested). No external credentials or production connection is needed.
`GET /health` checks DB readiness. Content routes require `Authorization: Bearer <token>`.

API: `POST /items` with `{ "url": "https://youtu.be/abcdefghijk" }`; then
`PUT /items/{id}/transcript` with `text`, `provenance`, optional `author`/`published_at`.
`POST /items/{id}/research` accepts reviewed research fields defined in `Research`, or uses
an injected provider (default returns 503). `POST /items/{id}/transition` accepts `status`
IDEA_APPROVED, REJECTED, SAVED or MORE_RESEARCH. `GET /items` lists the latest 100 entries.
`POST /reports/prepare` snapshots up to five researched ideas after 05:00 Tehran; it sends
nothing. TelegramGateway is a tested command handler, not a running polling service.

Do not expose publicly or deploy until [deployment gates](DEPLOYMENT.md) are satisfied.
