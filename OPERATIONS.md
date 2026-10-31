# Operations

No cron, systemd, polling process, container or render worker is installed by this repository.
Use README's foreground commands only in an isolated development environment. Run migrations
before the API and worker. Both must use the same DATABASE_URL and approved-user configuration.
Bind the API to loopback. `/health` checks migrated report storage, not external service health.

## Delivery and restart
The opt-in worker holds a renewable-per-tick 10-minute database lease, preventing a second
worker from polling concurrently. Each tick is bounded by batches of five updates/sends and
30-second network timeouts; do not increase these without reviewing the lease duration.
After an abrupt stop a new worker may need to wait for the lease to expire. Graceful completion
releases it. A single dedicated bot/database pair is supported.

Successful mutations and their replay receipts commit together. Reply outbox rows and the
polling offset commit together. A crash between these transactions replays the same mutation
key, returning its stored result without repeating the write. Unauthorized updates are skipped
without replying. Receipts, cursor, reports and outbox must be retained together during backups.

Report preparation is distinct from delivery. Each message has one of these states:

- `pending`: not sent yet.
- `sending`: claimed, awaiting a result; expired claims become uncertain.
- `sent`: Telegram confirmed a message ID.
- `retry`: a safe retry is deferred, respecting backoff/flood-control cooldown.
- `failed`: permanent failure or five safe attempts exhausted.
- `uncertain`: timeout, ambiguous result, or interruption during a send.

Admin-only `GET /operations/telegram` shows the latest 100 states, attempt counts and confirmed
message IDs without message text or credentials. A prepared daily report does not prove any
message was delivered. Polling offset does not prove a response was delivered either.

Never bulk-reset uncertain rows to pending. Inspect the dedicated private chat first. If the
message exists, retain the evidence and reconcile the row under a reviewed operator procedure;
if it does not, explicitly decide whether to retry that exact message. An operator reconciliation
UI/command and automated failure notifications are not yet implemented. Delivery is deliberately
not claimed as exactly-once across Telegram and the database. Do not deploy without monitoring.

## Data and credentials
Never log HTTP exception objects/URLs: Telegram URLs contain the bot token. Worker network
errors use fixed sanitized messages. Do not enable HTTP debug logging with live credentials.
Disable the worker by stopping only its own foreground process. Do not delete webhooks or
restart unrelated services. Changing allowed users blocks queued messages to removed users.

Local SQLite backup: stop only this application's API/worker, copy studio.db to protected
storage, and verify restoration into a temporary database. PostgreSQL requires pg_dump,
encrypted off-host retention and restore tests before production. Receipt/outbox retention,
log rotation, disk limits, worker monitoring and alerting remain pending. Do not purge replay
receipts while the corresponding Telegram updates can still be replayed.
