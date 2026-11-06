# Architecture and M0 assessment

The production Ubuntu host is unavailable in this session: no host, SSH identity,
service inventory, or approved inspection route was supplied. No production commands
were run. Espadna Sim's containers, data, 08:00 Tehran job, and reverse proxy are untouched.
The development machine is Debian 13, Python 3.12, 5 visible CPUs, approximately 33 GiB
available RAM and 60 GiB available disk at inspection. These are cloud development
resources, not evidence about the founder's server. GPU availability is not assumed.

Use one Python application with FastAPI and SQLAlchemy. SQLite supports isolated local
work; PostgreSQL is the production target, pending integration validation. Alembic owns
schema changes. Avoid Redis until durable worker concurrency warrants it. Large media
will live outside the database. Research providers are injected; default is unavailable,
never fabricated analysis. Manual source URLs are identifiers only. Explicit metadata retrieval uses a fixed YouTube
oEmbed endpoint; registered official feeds use exact approved hosts without redirect following.
No arbitrary linked pages, media or third-party transcripts are downloaded.

Implemented schema: source_items (unique platform/content_id and optimistic version),
audit_logs, daily_reports (unique Tehran date), sources, report_deliveries (unique day/recipient),
bot_updates and bot_cursor. Transcript provenance and structured research are stored with their
source. Further normalized roles, scripts, storyboards, media, jobs, settings, quotas and
publication records are planned before their respective features. The full schema in the
brief is a target, not implemented functionality.

Manual flow: authenticated link → normalized identifier → authorized transcript and
user-supplied metadata → validated reviewed research or injected provider → weighted score
→ explicit approval. Rejected items cannot progress. Reports snapshot up to five researched
ideas after 05:00 Tehran with one durable record per day. Report preparation is not delivery.

Implemented adapters: bounded YouTube oEmbed, official RSS/Atom and optional local Ollama,
validated with mocked integrations. A single explicitly enabled Telegram worker owns polling,
a durable inbox/cursor, and scheduled current-day report delivery/outbox. Uncertain external
delivery is held for reconciliation. See status for live configuration blockers and pending
source-collection scheduling, official discovery, PostgreSQL, producer and dashboard work.
