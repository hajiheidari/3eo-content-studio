# Founder narration only

Accepted direction (2026-11-06): the founder should review the scenario and record narration.
Research, original visual production, audio cleanup and assembly belong to the studio. Founder
screen recording is optional, not an acceptance requirement. No source footage is downloaded
or copied, no voice is synthesized, and no public posting is performed.

## Implemented workflow

1. Send a UTF-8 TXT document to the private bot with one YouTube URL per line (1–200 URLs,
   128 KiB maximum), or send several URLs in one message. `/bulk` also accepts a single URL.
   Imports are normalized/deduplicated and stored in the database, not a process-local list.
   The API accepts up to 200 entries at `/production/import`; entries can include `text` and
   `kind: description|transcript` when authorized source text is available.
2. `/production` shows work IDs and source-item IDs. Link-only entries wait when source access
   is unavailable. `/source ITEM_ID` followed by a description on the next line supplies text.
   `/retryproduction TASK_ID` explicitly retries failed/held tasks after the cause is resolved.
3. The background worker processes one queued source at a time. It retrieves the official
   description if configured, performs research and automatically selects eligible ideas for
   drafting (score >=50, confidence >=0.35). This is recorded as `system:automatic_selection`,
   never as a fabricated founder approval. Lower quality is held. Failures are not retried in
   a tight loop. Interrupted task leases expire after 30 minutes; underlying script generation
   has its own reservation/recovery rules. Description-only confidence remains capped at 0.5.
4. The exact script revision is delivered for human approval. Sending state is durable;
   uncertain Telegram sends are held for inspection, not automatically duplicated. Heavy queue
   inference runs in one background thread so the main bot can keep polling. A single CPU model
   slot and media slot still limit throughput; 100 links do not mean 100 immediate videos.
5. Approve the scenario. `/visuals SCRIPT_ID` creates an original silent visual draft. The first
   template is Persian RTL educational cards with shaped text, camera movement, highlights and
   a schematic diagram. It is labeled illustrative, not an actual browser demonstration. It
   does not execute arbitrary instructions from source text or reuse someone else's footage.
6. Send only the founder's actual narration through the own-voice button. The original is
   preserved; conservative audio processing runs, missing visuals are generated, and an actual
   vertical H.264/AAC MP4 is assembled automatically. A separate screen recording is unnecessary.
   Generated visual timing scales proportionally to narration duration. It is NOT word/phoneme
   alignment or verified subtitles. A duration difference over max(3s, 20%) blocks final approval.
7. Watch the video, approve its exact digest, then obtain the private MP4 for manual publication.
   Source/revision/asset changes invalidate approval. No production deployment is authorized.

## Official YouTube discovery: implemented adapter, not currently connected

`/discover QUERY` searches official YouTube results ordered by real view counts within a bounded
publication window (default 30 days, maximum 20 results). This is a query-specific result set,
not proof of global trending status or educational quality. Statistics come from the API, not
an LLM guess. Descriptions are labeled descriptions: the system has not watched the video or
obtained its transcript. Sparse/marketing descriptions can still be held by the quality gate.

The worker's `/youtube/refresh` runs one persisted search sweep per Tehran calendar day when
configured. Default query is `SEO AI search`; `STUDIO_YOUTUBE_QUERY` can customize it. A sweep
reserves its day before network access; failure or interruption does not cause repeated automatic
searches that day. Manual `/discover` remains available. Notifications go to the first approved
private bot user; this is a single-founder pilot, not multi-tenant scheduling.

Activation needs a project with YouTube Data API v3 enabled, a restricted API key stored securely
as `STUDIO_YOUTUBE_API_KEY`, and HTTPS policy access to `www.googleapis.com`. Never paste the key
in chat, logs or Git. It is passed as an API header, not in a logged query string. Use normal free
quota, without paid API/billing activation. Platform quota limits still apply. An optional secure key binding, its `www.googleapis.com` destination and refreshed startup
instructions are saved in the environment draft for user review, not applied. To activate, enter
the key in environment settings, save and publish; then restart/recheck development services
after restoration. Publishing does not keep the current bot process alive. No such key is
currently configured; an actual public YouTube oEmbed request still fails with proxy 403. No
scraping, proxy bypass, unofficial transcript download or invented video analysis is used.

**100 links solve source curation, not inaccessible source content.** With official API access,
public descriptions can be obtained automatically. Without it, link-only entries remain marked
as needing source text. Authorized transcripts can improve fidelity, but the bot does not ask the
founder to screen-record source videos. Full-video understanding is not an implemented capability.

## Runtime and acceptance limits

Dependencies: Python/uv, Pillow with RAQM shaping, DejaVu Sans font at the documented system
path, ffmpeg/ffprobe, util-linux `prlimit`, and the existing local model. CI installs the system
font. `uv sync --frozen` installs the locked Pillow wheel. Child encoders retain the existing
resource/protocol limits and do not inherit application credentials. Generated assets and
reservations use migration 0008 and private media storage. Back up DB and media together.

Actual acceptance covers real small FFmpeg test fixtures, 100-link imports/deduplication, blocked
sources, source provenance, automatic selection audits, a draft remaining unapproved, RTL motion,
voice-only intake through automatic assembly, and digest-gated manual export. A silent 55-second
visual draft from the actual approved project script was generated. Founder speech has not yet
been received; personal voice-to-final acceptance and editorial quality remain unverified.

This is a basic motion template, not finished professional motion design. Advanced per-scene
visual layouts, real automatic browser demos, ASR/editable Persian subtitles, exact speech timing,
brand styling and the dashboard remain pending. The runtime is still ephemeral development;
publishing/restoring a snapshot requires service restart and is not permanent bot hosting.
