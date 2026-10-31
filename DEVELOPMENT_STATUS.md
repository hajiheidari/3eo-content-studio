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
- Migrations 0001–0004. Existing source data and pending 0002 outbox messages survive upgrade;
  new keyboard/metadata fields remain nullable. Schema/model parity tested on both databases.

## Validation (2026-10-31)
82 tests passed, none skipped, using the locked Python 3.12 environment and a temporary
loopback-only PostgreSQL 16.2 test instance. That instance was stopped after testing. SQLite
also passed. Ruff passed. The remaining warning is Starlette's httpx TestClient deprecation.

Coverage includes manual Telegram flow, actor identity, old/forged callback rejection, replay
and crash windows, delivery failures/cooldown, recipient removal, message chunking/keyboards,
metadata parsing/redirect/size/timeout protection, caching, preserved manual overrides, and
concurrent quota reservations. Migrations run from 0001 with existing source data, through
0002 with a pending outbox row, to head twice, then check model parity and API health.

GitHub-hosted runs still fail before visible job steps; logs are unavailable via the connector.
Root cause remains unconfirmed. Local PostgreSQL success is not a green GitHub CI result.
PostgreSQL 17 on the CI service, live Telegram, live YouTube and real AI remain unverified.

## Remaining work
Do not mark M1 complete. Pending: configured AI network provider and cost/timeout controls;
real isolated bot/metadata acceptance tests; Instagram metadata permissions; near-duplicates;
automatic discovery, quota-aware feeds and incremental caching. AI-generated facts still need
founder verification. Current report placeholders for incomplete research are not real findings.

Before production: CI diagnosis, delivery monitoring/alerts, operator reconciliation tools,
retention/backup restore, rate limits and authentication hardening, production resource inventory
and explicit deployment approval. No live integration credentials are needed for the mock suite.
