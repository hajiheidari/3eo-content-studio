# 3EO Content Studio

Private, approval-driven Persian SEO research and production system. The Scout manual path,
opt-in Telegram polling and durable daily-report outbox are implemented. M1 is **not complete**:
metadata retrieval, an AI network adapter, discovery and inline buttons remain pending.
Video production and the dashboard are not implemented. See [status](DEVELOPMENT_STATUS.md)
and [original brief](REQUIREMENTS.md).

## Isolated local development
Python 3.12+ and uv required. From this repository:

```sh
uv sync --frozen
uv run --frozen alembic upgrade head
uv run --frozen pytest -q
uv run --frozen ruff check src tests migrations
uv run --frozen uvicorn studio.api:create_app --factory --host 127.0.0.1 --port 8000
```

Set `STUDIO_ADMIN_TOKEN` securely in the process environment before starting for authenticated
operations. Without a token, content requests are denied. Never commit credentials. Default DB
is ignored local `studio.db`; set `DATABASE_URL` to select another database. `/health` checks the
migrated database, not external readiness. Run migrations with this same DATABASE_URL.

## Manual API workflow
Use `Authorization: Bearer <admin token>`. No external credentials are needed.

1. `POST /items` with `{"url":"https://youtu.be/abcdefghijk"}`.
2. `PUT /items/{id}/transcript` with `text`, `provenance`, optional `author`/`published_at`.
   Supply only a transcript you are authorized to use. Metadata is explicitly user supplied.
3. `POST /items/{id}/research` with reviewed research JSON, or without a body to use an injected
   provider. The default provider is unavailable (503); malformed provider output returns 502
   without changing the item. Provider error messages are not exposed.
4. `GET /items/{id}` to review the result. `POST /items/{id}/transition` with `status` equal to
   IDEA_APPROVED, REJECTED, SAVED or MORE_RESEARCH. No producer/publication states are accepted.

Reviewed research example (scores are the reviewer's assessments, not source engagement metrics):

```json
{
  "title_fa": "آزمایش یک روش تحلیل سئو",
  "summary_fa": "خلاصه بازبینی‌شده منبع را اینجا بنویسید.",
  "angle_fa": "اجرای یک آزمایش مستقل با داده‌های مجاز",
  "why_it_matters_fa": "کاربرد عملی روش برای متخصص سئو",
  "recommended_format_fa": "نمایش واقعی صفحه با توضیح فارسی",
  "brand_connection_fa": "ارتباط مشخص با ابزار مناسب 3EO یا نبود ارتباط",
  "claims_to_verify": ["ادعای اصلی را با مستندات و آزمایش بررسی کنید"],
  "limitations": ["این پژوهش بر متن ارائه‌شده توسط کاربر متکی است"],
  "criteria": {
    "relevance": 80, "usefulness": 80, "brand_fit": 80,
    "freshness": 80, "short_video": 80, "evidence": 80
  }
}
```

Mutations accept `Idempotency-Key` (1–100 ASCII letters/digits/colon/underscore/hyphen).
A successful replay returns the stored response; changing the payload with the same key gives
409. Receipts and changes commit atomically. Conflicting concurrent writes return 409.

## Telegram worker (disabled by default)
The code is ready for an isolated bot integration test, not production deployment. No bot was
connected during development. Configure these environment values securely; do not paste tokens
into chat, command arguments or GitHub:

| Variable | Purpose |
|---|---|
| `STUDIO_TELEGRAM_API_TOKEN` | Dedicated gateway-to-API secret; must differ from admin token |
| `STUDIO_TELEGRAM_USERS` | Comma-separated approved positive numeric Telegram user IDs |
| `STUDIO_REPORT_USERS` | Report recipients, a subset of the approved users |
| `STUDIO_BOT_TOKEN` | A dedicated 3EO bot token; never Espadna Sim's bot |
| `STUDIO_API_URL` | Default `http://127.0.0.1:8000`; literal loopback only |
| `DATABASE_URL` | Same application database used by the API and migrations |
| `STUDIO_TELEGRAM_ENABLED` | Set to `1` only when intentionally starting the worker |

The API needs the gateway token and approved-user list too. Start it first, then explicitly run
`uv run --frozen python -m studio.worker` in a separate foreground process. Importing modules
or starting the API does not start a bot. Existing webhooks are not deleted or changed; polling
requires a dedicated bot without a webhook. No cron/systemd/container installation is provided.

Private-chat commands:

- Send a YouTube/Instagram link to receive its idea ID.
- `/transcript ID`, newline, authorization/provenance, newline, transcript text.
- `/review ID`, newline, reviewed research JSON in the format above.
- `/analyze ID` uses a configured provider; default is unavailable.
- `/idea ID` shows the research, evidence limitations and available decisions.
- `/ideas`, `/approve ID`, `/reject ID`, `/save ID`, `/research ID`, `/help`.

Every mutation records the authenticated Telegram user rather than a generic admin actor.
The gateway credential is trusted to assert only allowlisted users; do not share it with clients.

## Reports and delivery
`POST /reports/prepare` alone sends nothing. The worker checks the Tehran date on each tick and,
at the first tick at/after 05:00, prepares one immutable snapshot of up to five RESEARCHED ideas.
It queues the snapshot separately for each recipient. An empty report says no researched ideas
are available. Delivery can span ticks; this is not a hard real-time 05:00 guarantee. Starting
late catches up the current day, not every missed historical day.

Outbox keys and polling offsets survive restart. Confirmed sends store Telegram message IDs.
Safe failures retry with bounded backoff (at most five attempts) and a shared send cooldown.
Timeouts/ambiguous responses or an interrupted send become `uncertain` and are **not** blindly
resent: Telegram sendMessage does not offer an idempotency key. See [operations](OPERATIONS.md).
Admin-only `GET /operations/telegram` lists the latest 100 delivery states and polling offset.

Do not expose publicly or deploy until [deployment gates](DEPLOYMENT.md) are satisfied.
