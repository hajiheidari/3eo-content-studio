# Validation

Run `uv sync --frozen`, `uv run --frozen pytest -q`, and
`uv run --frozen ruff check src tests migrations scripts`.

Current full result: 82 passed, no skips, one Starlette TestClient deprecation warning. This was
run with a temporary PostgreSQL 16.2 instance on loopback, which was stopped on completion.
Without an explicit PostgreSQL test URL the ordinary run passes 80 tests and skips two.

Tests use temporary SQLite, an in-process API and mocked Telegram/YouTube transports. No live
messages, external API keys, paid calls, production services or actual videos are accessed.
The local test server is separate test tooling; it is not an application runtime dependency.

Coverage includes manual flow through approval, callback authorization and stale revision
rejection, mutation replay and crash windows, worker lease, outbox recovery and uncertainty,
UTF-16 limits and durable keyboard placement; official metadata source/shape validation,
redirect/size/timeout protections, caching, manual overrides and concurrent daily request caps.

Database tests upgrade preserved 0001 source data through 0002 pending outbox data to head,
repeat upgrade, verify schema/model parity and health, and exercise atomic quota limits on
both engines. CI provisions PostgreSQL 17; its remote run must still be verified independently.

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
