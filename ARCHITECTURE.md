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
never fabricated analysis. Source URLs are identifiers only; no automatic URL fetch occurs.

Implemented schema: source_items (unique platform/content_id), audit_logs, daily_reports
(unique Tehran date). Transcript provenance and structured research are stored with their
source. Further normalized roles, scripts, storyboards, media, jobs, settings, quotas and
publication records are planned before their respective features. The full schema in the
brief is a target, not implemented functionality.

Manual flow: authenticated link → normalized identifier → authorized transcript and
user-supplied metadata → validated reviewed research or injected provider → weighted score
→ explicit approval. Rejected items cannot progress. Reports snapshot up to five researched
ideas after 05:00 Tehran with one durable record per day. Report preparation is not delivery.

Next: verified metadata adapters; configured AI adapter with mocked integration tests;
durable Telegram polling offsets and delivery outbox; scheduler; PostgreSQL integration;
producer and script approvals; media processing; dashboard and security hardening.
