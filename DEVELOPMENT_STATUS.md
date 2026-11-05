# Implementation status

Branch: codex/m1-foundation. PR: https://github.com/hajiheidari/3eo-content-studio/pull/2
Updated: 2026-11-06.

## Working private development workflow
Supported link → persistent per-user context → plain description/authorized transcript →
actual local AI research → stored Persian idea/ranking → Telegram review buttons. Independent
text and a Persian new-idea menu are supported. Metadata is attempted automatically on links;
source bodies remain bounded, classified and provenance-labeled. Short titles are insufficient.
Failures retain evidence for retry; source and approval changes use optimistic concurrency.
A local schema-constrained demonstration plan requires topic/input/action/comparison, with
checks against repeated claims/generic duplicate fields. Actual evidence boundaries override
unsupported model-generated limitations. Descriptions have confidence capped at 0.5.

Active model: official Qwen2.5-14B-Instruct GGUF Q4_K_M, verified across three pinned shards.
CPU runtime llama.cpp b12129 is verified and private. Four threads, one slot, 8192 context,
24 GiB virtual ceiling; observed RSS ~16 GiB. No paid API, new credentials or GPU required.
See docs/LOCAL_AI.md for complete setup and startup. Network/model blockers are now resolved.

## Evidence
86 tests pass; Ruff and SQLite migration/schema consistency pass (revision 0004).
Tests cover URL/SSRF/body limits, metadata, safe feeds, source/context isolation, plain-text
intake, provider schemas/failures, research quality gates, scoring, audits, callbacks, Telegram
authorization, timezone, outbox/restart behavior, existing-data migrations and artifact integrity.
Actual item 1 was analyzed by the running local model without supplied research output. The
final structured-plan run returned HTTP 200 in 117.5s, status RESEARCHED, score 53/confidence
0.4. Actual persisted output was delivered to the approved Telegram user with review buttons.
The founder subsequently confirmed approval in chat after repeated unresponsive bot clicks; it was reconciled as an admin-audited IDEA_APPROVED transition and a private confirmation was delivered. This is a preliminary idea based on a public description,
not full-video analysis or proven SEO advice. No made-up metrics, creator or publication date.

Early small-model outputs were weak and held for more research rather than published. Retired
4B/8B downloads were removed. An initial repeat-install test rewrote native files while running
and stopped the model; fixed by archive-content verification and no in-place replacement.
Repeated installer execution with the live model now preserves native files and passes health.
One upstream Starlette/httpx TestClient deprecation warning remains.

## Remaining M1/production limits
Live YouTube metadata still receives proxy 403; no access bypass or transcript scraping.
Official feed registration/refresh is implemented, but automatic pre-deadline discovery/research,
YouTube official API channel/search and quota management are pending. Reports are prepared
from existing researched items after 05:00 Asia/Tehran with durable per-recipient outbox.
Uncertain sends are held; rate limits have bounded retries. A sequential CPU inference can
delay worker cycles. No unattended 05:00/SLA or distributed exactly-once claim is made.
PostgreSQL and broad model editorial quality/performance remain unvalidated. Private pilot
use still requires founder fact checking and explicit idea approval; no automatic publication.

## M0 and later milestones
Architecture, costs, security and deployment plan are documented. Production Ubuntu access
and infrastructure inspection are still absent. No production or Espadna Sim commands were
run. Runtime is cloud development only; processes must restart after a snapshot restore.
M2–M4 remain pending: script/producer, media/audio/video/subtitles, Remotion, dashboard,
full hardening and controlled deployment. The entire original project is not complete.


## Approval incident (2026-11-06)
After development-environment publication/recreation, model/API/worker processes were absent;
filesystem persistence had not kept the bot online. Item 1 was still RESEARCHED and no approval
transition existed. No pending Telegram callbacks were available when checked. The founder's
explicit reported approval was reconciled through the authenticated API (actor admin, not a
fabricated Telegram callback), then verified as IDEA_APPROVED and confirmed through the bot.

Fixed a second failure mode: expired answerCallbackQuery/acknowledgement errors no longer
skip the authorized approval action. Repeated approvals now return a clear already-recorded
message with one transition. Approval messages explain that script/video generation remains
unimplemented. Model, API and private worker were restarted only in this development machine.
86 tests pass, including expired callback and repeated-approval regressions. Continuous bot
availability still requires a persistent runtime; this ephemeral cloud task is not a permanent
server deployment. Production deployment remains blocked on infrastructure inspection and
explicit founder approval. Publishing/restoring the dev snapshot requires service restart.
