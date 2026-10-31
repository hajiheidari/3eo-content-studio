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
never fabricated analysis. Submitted URLs are identifiers only. The opt-in YouTube metadata operation calls a fixed
official Google endpoint with a validated video ID; submitted URLs and redirects are never fetched.

Implemented schema: source_items (unique platform/content_id and optimistic version), audit_logs, daily_reports
(unique Tehran date). Transcript provenance and structured research are stored with their
source. Further normalized roles, scripts, storyboards, media, jobs, settings, quotas and
publication records are planned before their respective features. Migration 0002 adds atomic
mutation_receipts, worker_cursors (offsets/lease/cooldown), and a per-message telegram_outbox.
Migrations 0003–0004 add durable inline keyboards, cached source metadata and daily
api_usage request reservations. The full schema in the brief is a target, not implemented functionality.

Manual flow: authenticated link → normalized identifier → authorized transcript and
user-supplied metadata → validated reviewed research or injected provider → weighted score
→ explicit approval. Rejected items cannot progress. Reports snapshot up to five researched
ideas after 05:00 Tehran with one durable record per day. Report preparation is not delivery.

The opt-in worker prepares reports on the first tick at/after 05:00 Tehran and queues durable
private messages. Polling offsets, replay receipts and outbox recovery are implemented, tested
with mocked Telegram transport. Confirmed message IDs distinguish sent messages from uncertain
outcomes; uncertain sends are held for review rather than automatically resent. A dedicated
gateway credential asserts allowlisted Telegram identities. No worker is installed or running.

PostgreSQL 16.2 integration was verified in an isolated temporary local instance. Versioned
inline decisions bind approval to the reviewed revision, and callback acknowledgement is
separate from durable command/reply processing. The YouTube metadata adapter has a one-hour
cache and atomic Tehran-date request limits; it is disabled by default and tested with mocks.

Next: verify PostgreSQL 17 CI and isolated live bot acceptance; Instagram metadata permissions;
configured AI adapter; producer and script approvals; media processing;
dashboard, operator reconciliation, monitoring and security hardening.
