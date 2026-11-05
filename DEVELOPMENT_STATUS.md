# Implementation status

Updated: 2026-11-05. Branch: `codex/m1-foundation`.

## M0
Repository inspected; initial main contained README and gitignore only. Architecture,
schema direction, cost assumptions and deployment gates documented. Production Ubuntu
inspection remains blocked on an approved access route. Development cloud resources are
not evidence about the production host. No production or Espadna Sim changes.

## M1 implemented in this branch
- Authenticated private API, safe manual YouTube/Instagram identifiers and exact deduplication.
- Authorized transcript/provenance storage; Persian research validation and weighted ranking.
- Public YouTube oEmbed metadata adapter with fixed host, no redirects, time/size bounds;
  publication date remains unknown when not supplied. Instagram is manual/authorized only.
- Opt-in local Ollama research adapter with structured output validation. No paid provider,
  automatic model download, fabricated metadata or transcript scraping.
- Official RSS/Atom source registration, enable/disable and explicit ingestion with safe XML,
  size/entry limits and idempotent URL hashes. Hosts are restricted to developers.google.com,
  status.search.google.com and blog.google. Linked articles are not fetched. Feed excerpts
  remain labeled as excerpts. No feeds are silently enabled or assigned invented URLs.
- Advisory near-duplicate checks over the latest 100 other items, capped text length.
- Optimistic item versioning prevents stale research/approval writes; transitions are audited.
- Private allowlisted Telegram command handler: submit URL, transcript with provenance,
  metadata, analyze, ideas, approve/reject/save/request more research. Telegram actor IDs
  are recorded for research and approval transitions.
- Explicitly enabled worker with durable polling cursor/update reservations and a process lock.
  Current-day report delivery begins after 05:00 Asia/Tehran, checked each worker cycle.
  Report delivery takes priority over polling. Requires an always-running healthy worker;
  exact-second dispatch is not guaranteed. Restart catch-up is for the current day only.
- One report/day and one outbox record/day/recipient. Confirmed 429 responses use bounded
  exponential backoff; uncertain send/timeouts and interrupted sends are held for operator
  review, preventing blind duplicate sends. No exactly-once network guarantee is claimed.
- Inline report buttons support approve/reject/save/more research; callback senders are
  independently authorized and callback query acknowledgements are sent. /today reads the
  prepared report and /idea ID exposes the complete research details.
- Three Alembic revisions, frozen dependencies and CI including migration consistency checks.

## Validation
67 automated tests pass, including the mocked manual Telegram → authorized transcript →
local-model research → report → approval flow. Tests cover SSRF inputs, redirects, oversized
responses, invalid AI output, unsafe XML, missing evidence, duplicate ingestion/reporting,
private user access, Tehran deadline, restart/outbox behavior, stale approval writes and
upgrading an existing database without losing its data. Ruff passes. SQLite migration is
at 0003; repeated upgrades and Alembic schema consistency pass. A fresh migrated database
and a real loopback HTTP server pass health, persistence, transcript gate and auth checks.
One upstream Starlette/httpx TestClient deprecation warning remains. PostgreSQL and live
external APIs are not validated; mocked tests do not establish research quality or delivery.

## Remaining M1 work and actual blockers
Dedicated Telegram credentials, approved user IDs and the local admin token are now bound.
Read-only getMe succeeded, no webhook was configured, and the private worker was explicitly
started in this cloud development session. A current-day report has a confirmed sent outbox
record. The founder submitted a real YouTube link: the inbound update was handled, item #1
was persisted as DISCOVERED and Telegram accepted the reply. New /today and /idea routes
were checked against the running loopback API after a controlled restart. The local model
is still absent; no automatic analysis, paid calls or model downloads occurred. Inline buttons
have mocked tests; no live approval callback is claimed.

A live metadata attempt for the submitted video failed with proxy 403 Forbidden despite the
configured YouTube host allowance. No metadata, publication date or transcript was invented.
Manual authorized transcript and user-supplied metadata remain the fallback. Diagnose upstream
proxy access before claiming live YouTube readiness; do not bypass proxy/TLS verification.

GitHub API access now works. Draft PR #2 against main is open for this branch:
https://github.com/hajiheidari/3eo-content-studio/pull/2
The separate PR #1 targets codex/m1-scout-delivery; it was inspected only to distinguish it
from this branch and was not modified. Development processes are ephemeral and do not imply
production deployment or guaranteed 24-hour uptime. Persistent STUDIO_TELEGRAM_ENABLED
was not changed; this session used an explicit per-process enablement override.

Automatic source collection/research scheduling before the report deadline, official YouTube
search/channel discovery and quota accounting, Telegram dedicated roles,
production rate limiting and wider trusted feed configuration remain pending. Current feeds
are refreshed explicitly; daily delivery reports ideas already researched by the cutoff.
M1 is not yet accepted as a complete, live-tested MVP.

## Later milestones
M2–M4 are not implemented: producer/scripts, media uploads/audio/video/subtitles, Remotion,
dashboard, full hardening and controlled deployment. The full production/export workflow
has not been tested. Production host inspection and explicit approval remain mandatory.
