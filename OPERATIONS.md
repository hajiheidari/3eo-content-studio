# Operations
Use a development DB and loopback binding only. Read README for setup/API/worker commands.
No cron, systemd, reverse proxy, containers or production workers were installed. Processes
must restart after a cloud snapshot restore. The worker reports each current Tehran day
once after 05:00; report generation/delivery runs before polling. Ideas must already be
researched; automatic pre-deadline collection/research is pending. An outage extending into
the next day does not replay yesterday's reports. Do not alter Espadna's 08:00 workflow.

## Delivery recovery
`daily_reports` is the immutable report snapshot. `report_deliveries` tracks each private
recipient's pending/sending/sent/retry/uncertain/failed state and confirmed Telegram message ID.
Only pending/retry entries are eligible. A confirmed Telegram 429 can retry up to five total
attempts, honoring retry_after and bounded exponential backoff. Timeouts and unconfirmed
responses become uncertain. A crash during send leaves sending. These do NOT retry on restart:
Telegram has no client idempotency key, so an accepted-but-unacknowledged send cannot safely
be called unsent. Inspect the private chat and correlate day/message before any manual
reconciliation. Stop only this project's worker before maintenance. Do not delete report
or delivery rows to force replay. No automated reconciliation/reset endpoint exists yet.

`bot_updates` reserves each inbound update before executing it; `bot_cursor` persists the
acknowledged offset. Interrupted processing is held, not blindly replayed. An approved action
may succeed before a reply fails; inspect item/audit state before sending another command.
Do not delete Telegram offsets, share a bot token with another app, or run competing workers.
The file lock protects workers sharing its path on this host, not a distributed cluster.

`/health` verifies migrated database tables, not Telegram, model quality or outside connectivity.
Safe worker errors omit credential-bearing HTTP URLs and payloads. One-shot failures return
nonzero. Always investigate errors before claiming readiness; no live bot test has occurred.

## Backup and resources
For local SQLite, stop this application's writes, copy studio.db into protected backup storage,
and verify restoration into a temporary database. PostgreSQL needs pg_dump, encrypted off-host
retention and restore tests before deployment. Media backups, disk checks, worker concurrency,
render timeouts and log rotation remain gates for future producer workers. No rendering/model
download occurs automatically. Feed bodies are capped at 512 KiB/50 entries; at most 10 sources
may be registered. Metadata is capped at 256 KiB; local model responses at 128 KiB.


## Development environment restart
Publishing/recreating a cloud snapshot preserves files, not processes. An online environment
status is not proof the API or bot is running. Check actual processes and local health; restart
model/API/worker per docs/LOCAL_AI.md after restoration. Do not tell users this is an always-on
bot. Persistent production hosting requires a separate inspected/approved deployment.
Expired callback UI acknowledgements are best effort and must not prevent authorized state
transitions. Duplicate approval requests report existing state without duplicate audit writes.


Media/runtime additions: ffmpeg, ffprobe and prlimit must be available. Schema head is 0007.
Private originals, audio previews and render outputs live under .local/media and need backup
with the DB; no static public serving. The process-local media slot assumes one API process.
User rights/own-voice declarations are required; they are not forensic identity checks. Export
requires exact final approval and never posts to a platform. See docs/MEDIA_WORKFLOW.md.


Narration-only production uses Pillow/RAQM and `/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf`
(`fonts-dejavu-core`), with the existing ffmpeg/prlimit limits. Migration 0008 adds source tasks,
visual leases and daily discovery reservations. One background queue thread per private worker
keeps polling responsive; this is not a distributed queue. Review `processing`/`sending` records
after crashes before requeuing. YouTube discovery requires separately reviewed API-key/network
configuration; see docs/FOUNDER_NARRATION_WORKFLOW.md. No production deployment is implied.
