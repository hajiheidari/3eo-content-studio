# Operations
Run only the local commands in README. `/health` verifies access to migrated report storage;
it does not establish external service readiness. No cron, systemd, polling or background
render processes are installed. Report preparation is explicit and idempotent by Tehran date;
delivery/outbox recovery is pending. Never mark a report delivered from preparation alone.

Local SQLite backup: stop only this application's process, copy studio.db to protected storage,
then verify restoration into a temporary database. Production PostgreSQL will require pg_dump,
encrypted off-host retention and restore tests. Media backups, log rotation, disk-watermark
checks, job timeouts, retry/backoff and worker monitoring must precede production workers.
