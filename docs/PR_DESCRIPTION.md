# M0 architecture and M1 manual Content Scout workflow

The repository previously contained only README/gitignore. Add a private FastAPI/SQLAlchemy
Scout workflow: canonical manual links, authorized transcripts, optional public YouTube metadata,
validated Persian research through reviewed input or a local Ollama adapter, ranking, advisory
duplicate checks, audited approvals and stale-write protection. Add official feed ingestion and
an explicitly enabled private Telegram worker with durable update offsets and daily report outbox.

Reports become due at 05:00 Asia/Tehran. Repeated preparation and restart do not blindly resend
messages; ambiguous sends are held for operator review. No paid calls, model downloads,
publication, public exposure, deployment or Espadna modifications.

Validation: 63 tests pass, Ruff passes, three SQLite migrations apply, populated-database upgrade
preserves data, schema consistency passes, and a real isolated loopback HTTP smoke passes.
External adapters use mocked integration tests. Live Telegram/YouTube/Ollama, PostgreSQL and
real scheduled delivery have not been validated. Credentials/model and network review are needed.

Remaining M1: pre-deadline automatic collection/research, official YouTube discovery/quota,
inline callbacks and production controls. M2–M4 remain pending. This is not production-ready.
