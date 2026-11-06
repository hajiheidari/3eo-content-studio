# M2 entry: script generation and exact-revision review

Scope: original Persian script, three hooks, five timed shots, on-screen text and recording/
motion instructions, fact-check list, CTA, caption, hashtags and canonical source references.
Timing is derived from five 6–12 second shots (30–60 seconds total), not trusted model maths.
Narration is only a draft for the founder to record; there is no synthesized/cloned voice.
This feature does not yet accept/process media or render/export video.

## Private Telegram flow
Approve the idea, then press «ساخت سناریو» (or /script ITEM_ID). A receipt precedes slow local
inference. The whole review is sent in bounded Unicode-safe messages, with approval buttons
only on the last message. Press «درخواست اصلاح», then write notes in the next plain message;
the resulting revision must be reviewed again. /scriptview SCRIPT_ID retrieves a stored draft
without generating it again. Old source-approval buttons explain when a project already moved
into the script stage instead of reporting an unexplained invalid transition.

## API and data
- POST /items/{id}/scripts requires IDEA_APPROVED or REVISION_REQUESTED. It first commits a
  generating reservation and source snapshot, then releases the DB transaction before inference.
  Duplicate/in-flight requests return the same draft without a second model call.
- GET /items/{id}/scripts and GET /scripts/{id} expose authenticated versioned drafts.
- POST /scripts/{id}/approve requires the exact stored SHA-256 in content_hash. Telegram
  callbacks bind immutable script ID plus hash prefix, then the API verifies the full hash and
  latest revision. Duplicate approval is idempotent; old revision/hash approval is rejected.
- POST /scripts/{id}/revise accepts notes (5–1000 characters), invalidates script approval and
  moves the project to REVISION_REQUESTED. Subsequent generation creates a new immutable
  content revision; old narration/storyboards remain available.

Revision 0005 adds scripts and an optional per-actor pending-script context. Source snapshot,
content digest, state, revision, UTC creation time and revision notes are retained. Transitions:
IDEA_APPROVED → SCRIPT_GENERATING → SCRIPT_DRAFT → SCRIPT_APPROVED. Revision requests
return to REVISION_REQUESTED. Generic item transitions cannot bypass script approval.

On provider failure the idea's previous approved/revision state is restored and a failed attempt
is retained. An interrupted generation can be recovered on a new request after a 15-minute
lease. This exceeds the local script provider's 600-second timeout. The worker HTTP budget is
720 seconds. No unapproved script proceeds to recording, rendering, exporting or publication.

## Validation and real instance
97 automated tests pass, including authorization/state gates, failure recovery, in-flight
deduplication, frozen revisions, exact hash approval, stale buttons, dialogue revisions,
Unicode-complete multipart delivery and populated SQLite migration checks.
Real generation for approved item 1 produced script ID 2/revision 2: a 55-second draft with
five scenes and three hooks. It was persisted and delivered with review buttons. Revision 1
had timed out at 420 seconds; revision 2 used tighter output limits and finished in 384.3s.
A repeated generation request returned ID 2 in 0.009s without another inference.
No real script approval is simulated; it remains the founder's decision. No media was generated.

Local CPU output is an editable draft, not a fact-checked final script. Verify claims, narration
quality, screen examples and timing before approval. The source is a video description, not a
watched video/transcript. Model fact-check suggestions do not establish truth. This is cloud
development only; publishing/restoring a snapshot stops processes. Permanent bot operation
requires a separately inspected and explicitly approved hosting deployment.
