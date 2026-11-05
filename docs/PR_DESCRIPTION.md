# M0 architecture and M1 manual Content Scout workflow

The repository previously contained only README/gitignore. Add a private FastAPI/SQLAlchemy
Scout workflow: canonical manual links, authorized transcripts, optional public YouTube metadata,
validated Persian research through reviewed input or a local Ollama adapter, ranking, advisory
duplicate checks, audited approvals and stale-write protection. Add official feed ingestion and
an explicitly enabled private Telegram worker with durable update offsets and daily report outbox.

Reports become due at 05:00 Asia/Tehran. Repeated preparation and restart do not blindly resend
messages; ambiguous sends are held for operator review. No paid calls, model downloads,
publication, public exposure, deployment or Espadna modifications.

Validation: 79 tests pass, Ruff passes, four SQLite migrations apply, populated-database upgrade
preserves data, schema consistency passes, and a real isolated loopback HTTP smoke passes.
Research adapters use mocked integration tests. Live private Telegram link submission,
persistence, reply and current-day report delivery were validated in cloud development.
Inline approval buttons and full idea/today views are added with authorization tests.
Live YouTube metadata was blocked by proxy 403; Ollama, PostgreSQL and unattended scheduled
delivery remain unvalidated. No model is installed or selected.

Remaining M1: pre-deadline automatic collection/research, official YouTube discovery/quota,
production controls. M2–M4 remain pending. This is not production-ready.


Automatic conversational intake now binds plain text to a durable per-user source context,
classifies description/transcript/user text, automatically calls a schema-constrained local
research adapter, stores actual output and returns review buttons. No multi-line command is
required. Titles alone are rejected; provider failure retains source evidence for retry.
Limited descriptions get a deterministic limitation and confidence ceiling. The founder's
submitted video description is saved as description for item 1, not mislabeled as transcript.

Added verified-checksum CPU runtime/model preparation and startup helpers for llama.cpp and
Qwen3-4B GGUF. Runtime binary is downloaded/verified; model download remains blocked by
Hugging Face proxy policy pending saved network draft application. No live inference success
is claimed. Model weights and all local data stay out of Git. See docs/LOCAL_AI.md for the
specific remaining activation/acceptance steps. No new required model variable was added.
