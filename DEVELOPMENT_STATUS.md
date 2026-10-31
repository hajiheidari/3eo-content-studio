# Implementation status

## Scope and deployment
M0 architecture, costs and isolation boundaries are documented; production inspection is still
pending. No production, Espadna Sim, 08:00 schedule, reverse proxy or external bot was modified.
No paid calls, live metadata requests, publication, model downloads or live AI calls occurred.
M2–M4 (producer, media, dashboard) remain unimplemented. This branch is a draft PR; no merge.

## M1 implemented
- Authenticated manual link/transcript/reviewed Persian research path, weighted ranking,
  guarded approvals and persistent audit identity. Missing providers fail closed.
- Sanitized AI errors with no partial writes; mutation receipts and optimistic versions prevent
  replayed or conflicting writes. User-supplied author/date remain distinct from API metadata.
- Separate trusted Telegram gateway credential and exact allowlisted private-chat checks.
- Manual transcript/research commands, full idea review, versioned Persian inline decisions,
  callback validation and post-commit popup acknowledgement. Old buttons cannot approve a new
  revision. Unversioned old report snapshots do not create new buttons.
- Opt-in Telegram transport, persistent polling offsets, a database worker lease, Tehran-date
  scheduling, stable outbox keys, confirmed-message receipts and bounded retries/cooldown.
  Ambiguous sends are held as uncertain; nothing starts implicitly.
- Official YouTube metadata adapter, disabled by default: title/creator/date only, fixed Google
  endpoint, validated source ID, no redirects/media/transcripts, bounded uncompressed responses.
  One-hour cache and atomic daily request reservations. Manual links still work without a key.
- Migrations 0001–0007. Existing source data and pending 0002 outbox messages survive upgrade;
  new keyboard/metadata fields remain nullable. Schema/model parity tested on both databases.
- Optional OpenAI Responses adapter, disabled by default; explicit model/key/budget/cap gates,
  strict structured output, input/output/time/response bounds, refusal/incomplete handling,
  research provenance and visible draft labeling. No default paid model or automatic fallback.
- Durable pre-HTTP research_attempts claims, shared daily reservations, completed-result reuse,
  conservative uncertain states and bounded explicit safe retries. Admin status omits content.
  These controls bound requests/tokens, not currency invoices.

- Advisory local lexical similarity for different IDs: normalized transcript/research profiles,
  bounded scans/cursors and visible coverage limits; warnings in idea details/reports. No model
  cost or automatic merge/rejection/approval. Explicit bounded legacy-profile backfill.
- Paginated API status filters and Telegram saved/approved lists. Derived profiles are maintained
  with transcript/research writes; pending research revisions are not treated as fresh evidence.

- Opt-in admin RSS/Atom metadata inbox with one reviewed official source, fixed request origin,
  bounded hardened parsing, conditional caching, persistent cooldown/owner fencing and URL
  deduplication. Separate tables preserve source/research states; no transcript/AI/approval
  or report inclusion. General source configuration and article promotion are not implemented.

## Validation (2026-10-31)
179 tests passed, none skipped, using the locked Python 3.12 environment and a temporary
loopback-only PostgreSQL 16.2 test instance. That instance was stopped after testing. SQLite
also passed. Ruff passed. The remaining warning is Starlette's httpx TestClient deprecation.

Coverage includes manual Telegram flow, actor identity, old/forged callback rejection, replay
and crash windows, delivery failures/cooldown, recipient removal, message chunking/keyboards,
metadata parsing/redirect/size/timeout protection, caching, preserved manual overrides, and
concurrent quota reservations. Similarity tests cover normalized copies/edits, unrelated and
short text, bounded profiles/coverage, immutable report warnings, profile refresh, explicit
legacy backfill and paginated saved/approved lists on both databases. Migrations run from 0001 with existing source data, through
0002 with a pending outbox row, to head twice, then check model parity and API health.

GitHub CI became green after the repository was made public and run 41235573994 was rerun:
120 tests passed with PostgreSQL 17.11, Ruff and both migration upgrades. That baseline was
commit b8e1597; the later e449aa9 run passed 144 tests. Check the PR for the current-head result. The original pre-run failure's exact
account-level cause was not established. Live Telegram, YouTube and real AI remain unverified.
AI transport, spend-approval configuration and all generation responses were mocked; no live
model quality, latency, availability or invoice estimate is claimed.

## Remaining work
Do not mark M1 complete. Pending: approved model/budget selection and real isolated
bot/metadata/AI acceptance tests; Instagram metadata permissions; semantic matching beyond
lexical warnings;
scheduled discovery, additional reviewed feed sources, article selection/promotion and
Telegram inbox controls. The first feed inbox and incremental cache are implemented. AI-generated facts still need
founder verification. Current report placeholders for incomplete research are not real findings.

Before production: current-head CI verification, delivery monitoring/alerts, operator reconciliation tools,
retention/backup restore, rate limits and authentication hardening, production resource inventory
and explicit deployment approval. No live integration credentials are needed for the mock suite.


Feed validation adds synthetic RSS/Atom, URL/XML/transport bounds, cache/cooldown races,
stale-owner fencing, admin authorization, error observability and inbox pagination. Both engines
pass migration parity and concurrent claim/cache tests. A direct public-feed smoke attempt
failed during TLS connection with WRONG_VERSION_NUMBER; no response was parsed or retained.
Live RSS availability/format remains an acceptance gate. No new application dependency.
Next code milestone: explicit human selection of a feed source into an authorized article
research workflow, preserving attribution and evidence limits; then isolated live acceptance.
