# 3EO Content Studio

Private, approval-driven Persian SEO research and production system. The Scout manual path,
opt-in Telegram polling and durable daily-report outbox are implemented. M1 is **not complete**:
scheduled discovery and live acceptance tests remain pending.
An opt-in public-feed discovery inbox is available through the admin API.
An optional OpenAI research adapter is implemented and disabled by default.
Optional official YouTube metadata and versioned Persian inline decisions are implemented.
Video production and the dashboard are not implemented. See [status](DEVELOPMENT_STATUS.md)
and [original brief](REQUIREMENTS.md).

## Isolated local development
Python 3.12+ and uv required. From this repository:

```sh
uv sync --frozen
uv run --frozen alembic upgrade head
uv run --frozen pytest -q
uv run --frozen ruff check src tests migrations scripts
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
   Supply only a transcript you are authorized to use. Metadata can be entered manually or
   retrieved through the optional official YouTube adapter described below.
3. `POST /items/{id}/research` with reviewed research JSON, or without a body to use an injected
   provider. The default provider is unavailable (503); malformed provider output returns 502
   without changing the item. Provider error messages are not exposed.
4. `GET /items/{id}` to review the result. `POST /items/{id}/transition` with `status` equal to
   IDEA_APPROVED, REJECTED, SAVED or MORE_RESEARCH. No producer/publication states are accepted. `expected_version` can bind a decision to the
   reviewed item version; all inline buttons supply it and reject outdated decisions.

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
- `/metadata ID` requests official YouTube metadata if the optional adapter is configured.
- `/idea ID` shows the research, evidence limitations and available decisions.
- `/ideas`, `/saved`, `/approved` list ideas; use the displayed numeric cursor to continue.
- `/similar ID` checks lexical overlap; `/similar ID BEFORE_ID` continues through older records.
- `/approve ID`, `/reject ID`, `/save ID`, `/research ID`, `/help`.

Research detail and daily reports include Persian inline buttons for the actions permitted by
the current state. Buttons contain the item version; a button from an earlier research revision
is rejected with instructions to reopen the idea. Old snapshots without a version remain
readable but do not generate new buttons. Private callback sender/chat checks match the command
checks, and callback popups are acknowledged after the reply/offset commit.

Every mutation records the authenticated Telegram user rather than a generic admin actor.
The gateway credential is trusted to assert only allowlisted users; do not share it with clients.

## Optional YouTube metadata
Disabled by default: `STUDIO_METADATA_PROVIDER=none`. To intentionally enable it, set
`STUDIO_METADATA_PROVIDER=youtube` and supply `STUDIO_YOUTUBE_API_KEY` securely using a dedicated
project/key. No API key was used during development; all adapter tests mock the network.

`POST /items/{id}/metadata` (or `/metadata ID`) retrieves only the video's title, creator and
publication date from the official fixed Google endpoint. It never downloads media or obtains
a transcript. Instagram continues to use manual metadata. The default manual workflow still
works without any YouTube key.

Successful metadata is cached for one hour. The default cap is 50 requests per Tehran calendar
day, configurable with `STUDIO_METADATA_DAILY_LIMIT` (1–1000). Reservations are committed before
HTTP requests; timeouts and failed responses consume a reservation. Cached hits consume none.
The application cap counts requests, not Google's complete project quota; other applications
using the same key are outside its accounting. No automatic retries or quota-exhaustion bypass.

The adapter refuses redirects, compressed/oversized responses, mismatched source IDs and invalid
fields. Once an idea is researched, expired metadata cannot be refreshed until MORE_RESEARCH.
Manual author/date overrides are preserved separately from the original API metadata. Requests
are explicit; submitting a link alone never starts a metadata call.

## Optional AI research (disabled by default)
The default `STUDIO_AI_PROVIDER=none` never calls an external AI service. The manual reviewed
research path remains available. No real model/key or live paid generation was used in tests.

An optional OpenAI Responses adapter is implemented following the official
[Structured Outputs documentation](https://developers.openai.com/api/docs/guides/structured-outputs?api-mode=responses).
To prepare an isolated live acceptance test, first choose an explicitly supported model and
approve its budget, then supply these values securely to the API process:

| Variable | Meaning |
|---|---|
| `STUDIO_AI_PROVIDER` | `openai` to intentionally select the adapter |
| `STUDIO_OPENAI_API_KEY` | Dedicated project API key; never an Espadna Sim credential |
| `STUDIO_AI_MODEL` | Explicit model ID supporting Responses and strict structured output; no default |
| `STUDIO_AI_BUDGET_APPROVED` | `1` only after the founder has approved live usage |
| `STUDIO_AI_DAILY_LIMIT` | Explicit reserved-request cap, 1–100 per Tehran calendar day; no enabled default |
| `STUDIO_AI_MAX_INPUT_BYTES` | Transcript byte limit, default 16000, configurable 256–64000 |
| `STUDIO_AI_MAX_OUTPUT_TOKENS` | Output/reasoning token limit, default 2048, configurable 256–8192 |

No setting was enabled by the agent. This approval flag records an operator's prior decision;
it is not a substitute for obtaining approval. Keep the adapter disabled until model, budget,
transcript privacy and a secure dedicated-key setup have been reviewed. No key is needed to
run the mock suite. No model is automatically substituted, installed or downloaded.

With explicit configuration, `/analyze ID` or bodyless `POST /items/{id}/research` submits the
authorized transcript as untrusted data. The adapter uses a fixed official endpoint, no tools,
no redirects, `store: false`, strict JSON schema, bounded input/output and sanitized errors.
Refusals, incomplete responses and invalid research do not become researched/approved items.
AI results are labeled as drafts, linked to their provider/model/attempt and require founder
fact checking and explicit idea approval.

A durable attempt claim and daily request reservation commit **before** the HTTP call.
Identical successful requests reuse their stored result across restart without another call.
Concurrent duplicates, interrupted submissions and uncertain timeouts are blocked rather than
blindly regenerated. Only known safe connection failures/rate limits permit a later explicit
retry after cooldown, at most three total attempts. No automatic network retry loop exists.
Failed attempts consume reservations; the daily limit covers all configured models in this
application database, not other applications using the provider account.

These controls bound requests and input/output size, **not a dollar invoice**. Set provider-side
project controls and review current model pricing separately before activation. Admin-only
`GET /operations/research` shows attempt states, reservations, response IDs and reported token
usage without transcripts, output text or credentials. See [operations](OPERATIONS.md) and
[costs](COSTS.md). Operator reconciliation of blocked attempts remains a deployment gate.

## Advisory similarity and review lists
Exact platform/content-ID deduplication still prevents the same link being ingested twice.
For different source IDs, local lexical matching can flag identical normalized text or high
text overlap. No embeddings, model calls or external services are used.

`GET /items/{id}/similar` compares authorized transcripts and, separately, Persian research
(title, summary and original angle). `/idea ID` and new daily-report snapshots show the same
advisory warnings, including the other idea ID/link and status. Rejected or approved ideas can
appear for historical context. No warning automatically merges, deletes, suppresses, rejects or
approves either item; founder approval is still explicit and version-checked.

Normalization covers case, Unicode compatibility forms, Persian/Arabic yeh/kaf, digit variants,
diacritics, punctuation and half-space variants. Very short/repetitive text is ignored: at least
12 tokens and eight distinct tokens are required. Full normalized equality is distinguished
from a heuristic overlap score using bounded word/five-word-shingle hash samples. Near matches
need a length ratio of at least 0.6 and weighted overlap of at least 0.80. The score is lexical
overlap, not a probability of duplication, quality or plagiarism. Titles alone are insufficient.
Translations, substantial paraphrases and short excerpts may not match; common text can also
produce false positives. This feature has synthetic regression tests, not a measured semantic
accuracy benchmark.

Each query checks up to 200 indexed records, newest IDs first, and returns up to five matches
(`limit` may be 1–10). `more_to_scan`, `next_before_id`, `scanned`, `unindexed_count` and
`sufficient_text` explain coverage. Supply `before_id` to inspect older pages. Empty results
never prove originality. The main idea list additionally supports `status`, `before_id` and
`limit` (1–100), which power the saved/approved Telegram lists.

New transcript/research writes maintain bounded profiles automatically. Old records need an
explicit backfill after migration 0006; a read never silently updates them:

```sh
uv run --frozen python -m studio.similarity --limit 1000 --batch-size 50
```

This updates only missing derived profiles in the DATABASE_URL selected for this application,
without network access or workflow transitions. It reports indexed/conflicted/invalid counts.
Concurrent edits are protected by item versions; conflicting batches can be retried explicitly.
Indexing increments item versions, so reopen an idea if an old approval button becomes stale.
Backfill was tested only against disposable databases; it was not run on production.

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

## Public-feed discovery inbox (disabled by default)
No YouTube key or AI provider is required. Migration 0007 adds separate `feed_states` and
`feed_entries` tables; it does not promote news into source items or reports.

- `GET /discovery/sources`: supported sources, last check/success/error and cooldown.
- Set `STUDIO_FEEDS_ENABLED=1` deliberately, then admin-authenticated
  `POST /discovery/sources/google-search-central/collect` performs one bounded collection.
- `GET /discovery/entries?source=google-search-central&limit=20`: unverified title/date/link
  metadata with publisher-feed provenance. Follow `next_after_key` using `after_key` for stable
  key order (not publication-date order). A walk is not a snapshot during new collections.

The first built-in source is the RSS link advertised by the
[Google Search Central blog](https://developers.google.com/search/blog):
`https://feeds.feedburner.com/blogspot/amDG`. Additional origins require code review; arbitrary
feed URLs, schedules and Telegram inbox controls are not implemented. Canonical article links
must be on `developers.google.com/search/blog/YYYY/MM/slug`. Links are stored, never fetched.
No article body, transcript, research, approval or publication is generated. Use the inbox for
manual source selection; promoting an article into the authorized research workflow is pending.
Disable collection with `STUDIO_FEEDS_ENABLED=0`; existing inbox reads stay available to admins.
