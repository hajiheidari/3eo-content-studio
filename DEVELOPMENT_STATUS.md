# Implementation status

## M0
Repository inspected; initial main contained README and gitignore only. Branch:
`codex/m1-foundation`. Architecture, schema direction, costs and deployment gate documented.
Production infrastructure inspection remains blocked on an approved access route; cloud
resources are documented separately. No production or Espadna Sim changes.

## M1 foundation
Implemented authenticated private API, URL normalization, exact duplicate prevention,
authorized transcript/provenance storage, user-supplied metadata, validated Persian research,
provider interface with fail-closed default, configurable ranking function, guarded approval
transitions and audit logs, idempotent Tehran-date report preparation, private authorized
Telegram command handler, SQLAlchemy persistence and initial Alembic migration.

Not complete: metadata retrieval, AI provider network implementation, near-duplicate detection,
RSS/YouTube discovery, quota/caching, live Telegram polling and callbacks, scheduled 05:00
delivery/outbox and per-user audit identity. No API credentials needed for current tests.
Do not call M1 complete or claim automatic delivery. No credentials requested prematurely.

M2–M4 not implemented: script/producer, uploads/audio/video/subtitles, Remotion, dashboard,
production hardening and deployment. Full media workflow has not been tested.

## Validation
16 automated tests pass: hostile URLs, duplicate links, missing transcript/provider,
research and approval path, audit persistence, auth, ranking, Tehran boundary, duplicate
reports, invalid provider output and Telegram access/command handling. SQLite migration
upgrade/current verified. Starlette emits an httpx TestClient deprecation warning.
PostgreSQL and live external APIs not tested. See TESTING.md for reproduction.
