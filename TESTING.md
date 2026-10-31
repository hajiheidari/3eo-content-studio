# Validation

Run `uv sync --frozen`, `uv run --frozen pytest -q`, and
`uv run --frozen ruff check src tests migrations scripts`.

Current full result: 179 passed, no skips, one Starlette TestClient deprecation warning. This was
run with a temporary PostgreSQL 16.2 instance on loopback, which was stopped on completion.
Without an explicit PostgreSQL test URL the ordinary run passes 174 tests and skips five.

Tests use temporary SQLite, an in-process API and mocked Telegram/YouTube/OpenAI transports. No live
messages, external API keys, paid calls, production services or actual videos are accessed.
The local test server is separate test tooling; it is not an application runtime dependency.

Coverage includes manual flow through approval, callback authorization and stale revision
rejection, mutation replay and crash windows, worker lease, outbox recovery and uncertainty,
UTF-16 limits and durable keyboard placement; official metadata source/shape validation,
redirect/size/timeout protections, caching, manual overrides and concurrent daily request caps.

Database tests upgrade preserved 0001 source data through 0002 pending outbox data to head,
repeat upgrade, verify schema/model parity and health, and exercise atomic quota limits on
both engines. AI tests additionally cover disabled/budget gates, schema/prompt boundaries,
result reuse across restart, pre-HTTP claims, concurrent duplicate/cap races, timezone resets,
refusal/incomplete/malformed output, redirects, safe retries and uncertain outcomes. Migration
0005 preserves legacy rows and validates research-attempt model parity. Migration 0006 adds
nullable similarity profiles; explicit backfill and read-only matching/status filters are tested
on both databases. Baseline GitHub CI passed all 144 pre-feed tests with PostgreSQL 17.11;
check the PR for current-head CI independently.

## Disposable PostgreSQL
To use an existing isolated loopback database named `studio_test`, supply
`STUDIO_TEST_POSTGRES_URL` securely. Tests create/drop only random test schemas and refuse other
database names or remote hosts. Never supply a production URL.

Alternatively, use existing local PostgreSQL binaries without installing a system service:

```sh
uv run --frozen python scripts/check_local_postgres.py --postgres-bin /path/to/postgres/bin
```

The script creates a temporary cluster under .pytest_cache, chooses a free loopback port,
disables Unix sockets, runs the suite, then stops the cluster and removes its temporary data.
It does not download/install software or touch other PostgreSQL services. Validation used
PostgreSQL binaries from pgserver 0.1.4 installed in separate local test tooling; no application
lockfile change was needed. The temporary cluster uses trust authentication and is for local
throwaway tests only.

Live bot/metadata/provider acceptance, discovery, complete media rendering/export and production
resource limits are not covered. Default AI and metadata adapters remain disabled/unavailable;
real credentials are not required to run these tests.

The AI suite clears live provider/key settings and uses fake keys and httpx.MockTransport.
No actual OpenAI request/model evaluation or monetary budget assertion is part of these results.

Similarity regression cases cover Persian/Arabic spelling and digits, Unicode forms, normalized
copies and small edits, short/reordered/unrelated/cross-language negatives, profile bounds,
old-research suppression, warning-only approvals, immutable report snapshots, scan cursors,
missing legacy profiles and saved/approved pagination. This is a lexical heuristic regression
suite, not a real-world semantic duplicate-detection accuracy benchmark.


Feed tests use synthetic RSS/Atom and mocked transport. They cover metadata-only extraction,
canonical deduplication, untrusted/unsupported URLs, DTD/entities/UTF-16 rejection, malformed and
bounded XML, response size/type/encoding/redirect/deadline failures, conditional 304/validators,
atomic competing claims and stale-owner fencing, preserved state on errors, disabled and admin
access gates, sanitized failure status and paginated inbox reads. Migration 0007 schema parity,
claim concurrency, cached validators and distinct inbox rows run on SQLite and PostgreSQL.
A separate direct public-feed smoke attempt failed at TLS connection, so live RSS acceptance
is pending. Tests never disable TLS verification and never fetch article links.
