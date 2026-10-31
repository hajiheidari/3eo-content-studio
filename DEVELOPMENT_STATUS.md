# Implementation status

## Scope and deployment
M0 architecture, costs and isolation boundaries are documented. Production inspection has not
occurred; development-machine resources are not evidence about the Ubuntu production server.
No production, Espadna Sim, 08:00 schedule, reverse proxy or external bot was modified.
No paid calls or publication occurred. M2–M4 (producer, media, dashboard) are unimplemented.

## M1 progress
The original foundation is extended with:

- Safe AI failure handling: invalid provider output returns 502; unavailable providers return
  sanitized 503; no partial research or audit is committed. Manual bad input remains 422.
- Telegram manual transcript/reviewed-research submission, research detail and approval commands.
- Separate gateway credential, approved-user attribution and admin-only delivery status.
- Atomic mutation receipts for replay after API commit but before polling-offset commit.
- Optimistic item version checks so concurrent changes cannot overwrite an approval.
- Opt-in official Telegram HTTP adapter, persistent polling offset, a database worker lease,
  Tehran-date scheduling, stable report/outbox keys, per-message delivery receipts, bounded
  retries/backoff and shared send cooldown. No background process starts implicitly.
- Conservative uncertain-send handling: do not automatically resend a possible successful send.
- Migration 0002 and integration tests that upgrade existing 0001 data to head twice and check
  schema/model parity. CI includes a disposable PostgreSQL service and its integration test.

Existing URL normalization, exact deduplication, authorized transcript/provenance, research
validation/ranking, approval guards and audit persistence remain in place. Metadata is user
supplied. Added report fields use explicit incomplete placeholders for backward compatibility;
these placeholders do not constitute completed research.

## Validation (2026-10-31)
Local Python 3.12 with the committed dependency lock: 44 tests passed, 1 PostgreSQL test skipped;
ruff passed. SQLite upgrade from 0001 with existing data, repeated upgrade to head, schema parity
and health are covered. Mocked Telegram transport and crash/replay scenarios pass. Remaining
warning: Starlette httpx TestClient deprecation.

PostgreSQL is not installed in this local review environment; its real result must be checked
in CI. The original remote run 41211744795 failed before any visible job steps (runner_id 0).
Job logs were unavailable through the connector and the browser was not signed into the private
repository. Root cause is unconfirmed; do not claim it was fixed or that CI is green without
inspecting the new run. No live Telegram or external AI/metadata integration was exercised.

## Remaining M1 work
Do not mark M1 complete. Pending: verified metadata adapters; configured AI network provider
with budget/timeout tests; near-duplicate detection; discovery, quotas and caching; Telegram
inline buttons/callbacks and friendlier research entry; live isolated bot acceptance test;
confirmed PostgreSQL/CI results. Delivery monitoring/alerting, retention, tested operator
reconciliation, production rate limits and authentication hardening remain before deployment.

Next gate: review this PR and CI, complete an isolated dedicated-bot acceptance test using
secure environment configuration, then implement the metadata/provider adapters. No keys are
needed for the current mock tests. Never reuse Espadna Sim credentials or deploy from this PR.
