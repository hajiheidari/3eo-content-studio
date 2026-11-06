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
133 tests pass; Ruff and SQLite migration/schema consistency pass (revision 0008).
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
M2–M4 remain partial: subtitles, advanced Remotion production, dashboard,
full hardening and controlled deployment. The entire original project is not complete.


## Approval incident (2026-11-06)
After development-environment publication/recreation, model/API/worker processes were absent;
filesystem persistence had not kept the bot online. Item 1 was still RESEARCHED and no approval
transition existed. No pending Telegram callbacks were available when checked. The founder's
explicit reported approval was reconciled through the authenticated API (actor admin, not a
fabricated Telegram callback), then verified as IDEA_APPROVED and confirmed through the bot.

Fixed a second failure mode: expired answerCallbackQuery/acknowledgement errors no longer
skip the authorized approval action. Repeated approvals now return a clear already-recorded
message with one transition. At that milestone, approval messages explained the then-unimplemented production steps. Model, API and private worker were restarted only in this development machine.
121 tests pass, including expired callback and repeated-approval regressions. Continuous bot
availability still requires a persistent runtime; this ephemeral cloud task is not a permanent
server deployment. Production deployment remains blocked on infrastructure inspection and
explicit founder approval. Publishing/restoring the dev snapshot requires service restart.


## M2 entry implemented: script and revision approval
Added versioned script generation from approved research with frozen source context, three
hooks, narration, five timed shots, recording/motion instructions, fact-check list, CTA/caption,
hashtags and trusted source references. Exact content-hash/latest-revision approval is separate
from idea approval. Revisions preserve prior content and reset the approval gate. Duplicate
requests reuse one reservation/draft; failed inference preserves the approved idea. Interrupted
reservations recover after a 15-minute lease. Telegram supports multipart review, revision
notes as the next message, progress receipts and clear old-button responses.

Real item 1 → script ID 2/revision 2 (55 seconds) → persisted draft → confirmed private Telegram
delivery succeeded. First attempt timed out; tightened generation bounds completed in 384.3s.
The founder has since approved this draft. A repeated request reused ID 2 in 0.009s.
See docs/SCRIPT_WORKFLOW.md for the script milestone; the media milestone below extends it. No synthesized voice, public content, production or Espadna changes occurred.


## M2 media/preview implementation
The founder approved script 2 (actual state SCRIPT_APPROVED). Added secure private media
upload, kind/stream/size/duration validation, rights/own-voice declaration, version/hash binding,
original preservation and checksum deduplication. Conservative audio processing creates private
WAV/MP3 previews with no silence/pitch/voice synthesis. Added bounded Telegram getFile streaming
and audio preview delivery. No real founder voice/screen file is present yet.

Implemented basic screen+founder-audio MP4 preview with real FFmpeg, 1080×1920 H.264/AAC,
final video digest/latest-version approval and private manual export. Preview is sent before
approval controls. Media replacements/revisions invalidate gates; mismatched narration duration
cannot get final approval. No automatic publication or invented test narration. All rendered
acceptance fixtures are test patterns/signals in temporary test databases, not this project.
121 tests pass, including genuine codec output and security/resource checks. Revision 0007
schema is current. See docs/MEDIA_WORKFLOW.md. Real end-to-end acceptance waits for the founder's
own recorded narration and authorized screen recording. ASR/editable RTL subtitles, advanced
motion/cursor templates, dashboard and production hardening remain pending.


## Narration-only direction implemented (2026-11-06)
The founder no longer needs to screen-record. Added an original RTL educational motion-card
renderer, private silent visual drafts and automatic voice-upload -> visual generation -> MP4
assembly. Generated scene timing is proportional, not speech-aligned; advanced motion and ASR
subtitles remain pending. The existing real script 2 produces a genuine silent 55-second draft.
No founder speech or approved final video is claimed.

Added a persistent 200-entry source backlog, 100-link TXT/multiline Telegram intake, deduplication,
source-blocked states, bounded sequential background research/script drafting, quality holds,
explicit retries, truthful system automatic-selection audits, and durable script delivery.
Founder approval remains required for the exact script and video. Migration 0008 is current.

Official YouTube recent/view-count search, description metadata and once-per-Tehran-day discovery
are implemented behind an optional official API key. The key is absent; actual YouTube oEmbed
access still fails with proxy 403. Discovery and full-video/transcript access are NOT demonstrated.
100 links alone do not grant source-text access. See docs/FOUNDER_NARRATION_WORKFLOW.md for setup,
limits and acceptance evidence. No paid calls, publication, production or Espadna changes.

Final verification: 133 tests pass, Ruff and Alembic schema checks pass. The actual silent visual
draft and its narration text were delivered to the approved private Telegram user.

Reusable environment draft saved: optional STUDIO_YOUTUBE_API_KEY binding restricted to
www.googleapis.com, existing domains preserved, refreshed dependency checks and startup
instructions. Save confirmed; not published/applied and no API key supplied. Current services
remain development-only. Publishing/restoration requires restarting and rechecking the bot.


## Remotion design prototype (2026-11-06)
The founder rejected the original text-card visual quality. Added a separate Remotion 4.0.541
project in motion-studio with a silent 15-second internal-link explainer: page entrances, drawn
curves, cursor interaction, path-following packet, destination highlight and camera reframing.
Includes shaped Persian local fonts, editable named timeline elements and a connected PageCard
composition. No copied source footage, generated speech, paid calls or production deployment.

This prototype is not yet approved or integrated into the bot's automatic renderer. It is a
visual design review, not evidence that arbitrary scripts now produce professional motion.
ESLint/TypeScript and actual Chromium still-frame inspections pass; Studio HTTP responds 200.
Full MP4 export was not requested and was not run. Node preview validation is added to CI.
See motion-studio/README.md. The existing 133-test Python workflow is unchanged.


## Remote preview access workaround (2026-11-06)
Founder reported a white page at the localhost Studio link. Loopback routes still returned
HTTP 200; remote viewer access was not established. Rendered the existing prototype into an
actual 15-second H.264 MP4 (1080×1920, 450 frames, 2,518,814 bytes), verified it with ffprobe,
and received private Telegram delivery confirmation. This is a silent design-review sample,
not an approved final asset or a production deployment. The live remote Studio access issue
is not claimed fixed; use the delivered file for review.
