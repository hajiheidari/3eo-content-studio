# Implementation status

Updated: 2026-11-03. Branch: `codex/m1-foundation`.

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
- Three Alembic revisions, frozen dependencies and CI including migration consistency checks.

## Validation
63 automated tests pass, including the mocked manual Telegram → authorized transcript →
local-model research → report → approval flow. Tests cover SSRF inputs, redirects, oversized
responses, invalid AI output, unsafe XML, missing evidence, duplicate ingestion/reporting,
private user access, Tehran deadline, restart/outbox behavior, stale approval writes and
upgrading an existing database without losing its data. Ruff passes. SQLite migration is
at 0003; repeated upgrades and Alembic schema consistency pass. A fresh migrated database
and a real loopback HTTP server pass health, persistence, transcript gate and auth checks.
One upstream Starlette/httpx TestClient deprecation warning remains. PostgreSQL and live
external APIs are not validated; mocked tests do not establish research quality or delivery.

## Remaining M1 work and actual blockers
Live bot/model validation needs a dedicated Telegram token, approved Telegram user ID(s),
a securely set local admin token and an installed/selected local model. None are present
in this machine. No messages, paid calls or model downloads have been performed.
Network currently blocks GitHub API and external integrations. A configuration draft saves
install/start instructions, domain additions, the dedicated Telegram secret requirement and
variable requirements for review. Saving does not apply runtime changes or publish it.
Git push works; PR operations return Forbidden. Apply reviewed network configuration before
retesting API access; an absent CLI login is not proof a new GitHub token is needed.

Automatic source collection/research scheduling before the report deadline, official YouTube
search/channel discovery and quota accounting, Telegram inline callbacks, dedicated roles,
production rate limiting and wider trusted feed configuration remain pending. Current feeds
are refreshed explicitly; daily delivery reports ideas already researched by the cutoff.
M1 is not yet accepted as a complete, live-tested MVP.

## Later milestones
M2–M4 are not implemented: producer/scripts, media uploads/audio/video/subtitles, Remotion,
dashboard, full hardening and controlled deployment. The full production/export workflow
has not been tested. Production host inspection and explicit approval remain mandatory.
