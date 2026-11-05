# Private Scout: conversational text research and Telegram review

Build the M0 architecture and manual Scout workflow in the previously empty repository.
The private bot accepts a YouTube/Instagram link and the next plain description/authorized
transcript, or an independent text. It stores per-user source context, invokes actual local
AI, validates Persian research/ranking and returns review buttons. A new-idea menu prevents
accidental attachment to old sources. Inaccessible media is never represented as watched.

Add safe YouTube metadata/official feed adapters, exact/advisory duplicate checks, classified
provenance, optimistic approval writes, audit logs, durable Telegram offsets and a daily report
outbox. Uncertain sends are held rather than blindly retried. Explicit approval never publishes.

The local default is pinned/checksummed official Qwen2.5-14B GGUF with llama.cpp, CPU only,
four threads/one slot. Suggestions require a concrete topic/input/action/comparison plan;
repeated claims/generic fields are rejected. Evidence boundaries come from stored input.
Model artifacts/DB/secrets remain outside Git. No paid API, production or Espadna changes.

Validation: 84 tests, Ruff, migration/schema consistency and real loopback smoke pass.
Actual item 1 description → live model/API → stored draft → Telegram result/keyboard passed
(117.5s, score 53/confidence 0.4). Founder approval remains pending. Repeated setup on the
running model passes after fixing native-library re-extraction. Observed model RSS ~16 GiB;
this is a cloud development pilot, not an inspected production sizing recommendation.

Remaining: live YouTube access is proxy-blocked; use supplied descriptions/authorized text.
Pre-deadline discovery/research scheduling, official API quotas, PostgreSQL integration,
production hardening and M2–M4 producer/media/dashboard remain pending. CPU inference can
delay one sequential worker; no unattended scheduling SLA or editorial quality guarantee.
No deployment or automatic publication is authorized.
