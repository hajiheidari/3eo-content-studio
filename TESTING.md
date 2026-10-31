# Validation

Run `uv sync --frozen`, `uv run --frozen pytest -q`, and
`uv run --frozen ruff check src tests migrations`.

Tests use temporary SQLite, an in-process API client and mocked Telegram transport. No paid
calls, production services, live messages or actual videos are accessed. Current local result:
44 passed, 1 PostgreSQL integration test skipped.

Coverage includes the manual Telegram flow through approval, authenticated actor attribution,
invalid AI output and sanitized failures without partial writes, idempotent mutation replay,
conflicting item versions, 05:00 Tehran boundary, daily outbox deduplication across restart,
polling crash window, unauthorized updates, worker lease takeover, retry/uncertain/permanent
send failures, UTF-16 message limits, migration of existing 0001 data, repeated upgrade and
schema/model parity. Existing foundation tests remain enabled.

CI starts an isolated PostgreSQL 17 service. To explicitly run the PostgreSQL integration test
locally, provision a disposable loopback database named `studio_test` and supply
`STUDIO_TEST_POSTGRES_URL` securely. The test creates a random schema and drops only that schema
on exit; it refuses other database names/remote hosts. Never supply a production connection.
SQLite integration always runs; PostgreSQL is skipped if no explicit test URL is provided.

Run `uv run --frozen alembic upgrade head` twice and `uv run --frozen alembic current` for a
manual migration smoke check. The automated integration test also checks `/health` against the
migrated database. Real bot credentials are needed only for a later isolated live acceptance
test. Discovery, external research providers, full media rendering/export and production
resource limits remain unverified and unimplemented.
