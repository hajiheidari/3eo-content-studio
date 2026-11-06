# CODEX IMPLEMENTATION BRIEF
## Project: 3EO Content Studio — AI SEO Content Automation

You are the lead software architect, senior full-stack engineer, AI automation engineer, and DevOps engineer responsible for implementing **3EO Content Studio**.

Build a production-oriented, self-hosted content research and production system for the Persian AI SEO brand **3EO (https://3eo.ir)**.

The founder is an experienced SEO professional who wants to publish original, high-quality Persian educational content on Instagram and YouTube without showing his face.

The system consists of two cooperating AI agents:

1. **Content Scout:** Discover, analyze, rank, and recommend English-language AI/SEO content.
2. **Content Producer:** Convert approved ideas into original Persian scripts, storyboards, motion graphics, edited videos, captions, and publication-ready assets.

The founder will record narration using his own voice. Never clone, synthesize, replace, or imitate his voice.

## 1. Operating principles

- Work autonomously through implementation, testing, and documentation wherever possible.
- Use existing infrastructure and free/open-source components where practical.
- Do not purchase services, activate paid APIs, or incur usage charges without explicit founder approval.
- Do not publish content or send external promotional messages without explicit approval.
- Do not deploy unfinished functionality as publicly accessible.
- Never assume a command succeeded; verify the result.
- Preserve all existing services, files, databases, containers, schedules, firewall rules, and secrets.
- Keep a detailed implementation status document.
- Continue implementation until genuinely blocked by missing credentials, access, or a decision requiring founder approval.

## 2. Existing infrastructure and isolation

The founder has an existing Ubuntu server in France.

An unrelated project, **Espadna Sim Content Agent**, is already being configured on this server and has a scheduled Telegram workflow at 08:00 Iran time.

Before making changes:

1. Inspect Ubuntu version, CPU, RAM, disk space, available ports, Docker, systemd, cron, reverse proxy, and existing applications.
2. Identify running containers and scheduled tasks.
3. Identify existing project directories without accessing unrelated business data unnecessarily.
4. Check available resources and estimate video-rendering requirements.
5. Report any resource or configuration risks.

**Critical isolation requirements:**

- Do not modify or restart Espadna Sim.
- Do not overwrite existing environment files or secrets.
- Do not change unrelated cron jobs or systemd units.
- Do not reuse another project's Telegram bot token.
- Do not modify global reverse-proxy configuration without a reviewed plan.
- Use a separate application directory, database, environment file, service name, logs, and processing queues.
- Use CPU, RAM, disk, and concurrency limits.
- Ensure content-rendering jobs cannot disrupt the 08:00 Espadna Sim workflow.

If deployment could affect existing services, stop and request approval before proceeding.

## 3. Proposed technology stack

Prefer:

- Python 3.12+ for backend and AI orchestration.
- FastAPI for internal APIs.
- PostgreSQL for persistent data.
- Redis with a lightweight background worker, if justified.
- Python Telegram Bot or aiogram.
- FFmpeg for audio and video processing.
- Remotion for programmatic motion graphics.
- OBS-compatible screen recordings.
- Docker Compose for isolated deployment.
- A lightweight responsive Persian RTL admin dashboard.
- Structured logging and basic monitoring.

Evaluate the server before finalizing the stack.

Do not introduce Kubernetes, GPU requirements, paid video-generation APIs, or unnecessarily complex microservices.

Use interchangeable adapters for AI providers. Never hardcode credentials.

## 4. Agent One — Content Scout

### Mission

Find valuable English-language content about:

- AI-assisted SEO
- Technical SEO
- Google Search Console automation
- Keyword research and clustering
- Search intent analysis
- Content optimization
- AI agents for SEO
- n8n and workflow automation
- SEO reporting
- GEO, AEO, and AI search visibility
- ChatGPT, Claude, Gemini, and other AI tools relevant to SEO
- New practical SEO tools and techniques

### 4.1 Manual URL submission

This is a mandatory MVP feature.

The founder must be able to submit a YouTube or Instagram URL through Telegram or the admin dashboard.

Workflow:

1. Validate and normalize the URL.
2. Identify the platform and content ID.
3. Retrieve legally accessible metadata.
4. Retrieve an authorized transcript or subtitles where available.
5. If no transcript is accessible, ask for a transcript or authorized media upload.
6. Never pretend to have watched or analyzed inaccessible content.
7. Summarize the content in Persian.
8. Extract actionable ideas and claims requiring verification.
9. Propose an original Persian content angle.
10. Save the source URL, author, date, and analysis status.

Protect against SSRF, malicious URLs, oversized downloads, and unsupported domains.

### 4.2 YouTube discovery

Use the official YouTube Data API when credentials and quota are available.

Implement:

- Configurable list of English-language channels.
- Configurable search keywords.
- Search by topic and recency.
- Metadata retrieval.
- Deduplication by video ID.
- Quota tracking.
- Caching and incremental discovery.
- Graceful fallback when quota is exhausted.

Do not assume the YouTube Data API provides third-party video transcripts.

The founder must be able to use the system without a YouTube API key through manual links and supported public feeds.

Do not use unauthorized scraping or bypass platform restrictions.

### 4.3 Instagram discovery

Implement compliant discovery within available official API permissions.

Support manual Instagram URLs and authorized uploads.

If arbitrary competitor-Reels discovery is not supported by available API permissions, document that limitation clearly rather than implementing fragile login scraping.

### 4.4 Other research sources

Support configurable RSS feeds and public official sources, such as:

- Google Search Central
- Google Search Status Dashboard
- Google Search Central Blog
- Google Search documentation
- Relevant AI-provider release notes
- Reputable SEO industry publications

Separate official announcements from third-party opinions.

### 4.5 Ranking system

Score each idea from 0 to 100:

| Criterion | Weight |
|---|---:|
| Relevance to professional SEO users | 25 |
| Practical usefulness | 20 |
| Relevance to 3EO tools | 20 |
| Novelty and freshness | 15 |
| Potential for a compelling short video | 10 |
| Evidence and reproducibility | 10 |

Make weights configurable.

Detect duplicates and near-duplicates.

Never invent engagement metrics, video views, or source facts.

### 4.6 Daily Telegram report

Schedule the Content Scout workflow using the `Asia/Tehran` timezone.

Target:

**05:00 every day, Iran local time.**

Prefer collecting and processing sources ahead of the delivery deadline, so the report can be delivered at 05:00.

Each daily report should include up to five high-quality ideas.

For each idea include:

- Persian suggested title
- Original source link
- Original creator
- Publication date, if known
- Summary
- Why it matters
- Recommended content format
- Proposed original Persian angle
- Connection to 3EO tools
- Confidence and evidence limitations
- Idea score

Telegram actions:

- Approve
- Reject
- Save for later
- Request more research
- Generate script

The report must not block indefinitely if some sources are unavailable.

Use idempotent scheduling to avoid duplicate reports after service restarts.

## 5. Agent Two — Content Producer

### Mission

Transform an approved idea into an original Persian educational video using a semi-automated production workflow.

Supported output formats:

1. Screen recording with Persian narration.
2. Motion graphics with Persian narration.
3. Hybrid video combining screen recording and motion graphics.
4. Instagram carousel.
5. Instagram Stories.
6. YouTube Shorts.

Do not simply translate and repost another creator's video.

Do not reuse copyrighted footage, music, graphics, or animation without appropriate rights.

### 5.1 Script generation

Generate:

- Three alternative hooks.
- Recommended video length.
- Original Persian script.
- Technical fact-checking checklist.
- Shot-by-shot storyboard.
- On-screen text.
- Screen-recording instructions.
- Motion-graphics instructions.
- CTA.
- Caption.
- Hashtags.
- Source references.

Default duration: 30–60 seconds.

Allow longer videos when justified.

All scripts must be written in natural, professional Persian.

Avoid exaggerated claims about Google rankings, GEO, AI citations, and guaranteed results.

The founder must approve the script before production continues.

### 5.2 Video composition

Support three production templates:

**Template A — Screen Recording**

- Actual screen recording.
- Dynamic zoom and crop.
- Cursor emphasis.
- On-screen annotations.
- Persian subtitles.
- Intro/outro branding.

**Template B — Motion Graphics**

- Original animated diagrams.
- Typography animation.
- Simple icons.
- Animated data flows.
- Professional transitions.
- Persian narration.

**Template C — Hybrid**

- Animated hook.
- Concept explanation.
- Actual product demonstration.
- Results.
- Branded closing.

Initially prioritize Template A and Template C.

Use Remotion where practical.

The system must render a genuine video, not just generate a storyboard or a collection of static images.

### 5.3 Founder voice processing

The founder records narration in his own voice.

Supported inputs:

- MP3
- WAV
- M4A
- OGG, including Telegram voice messages

Audio-processing pipeline:

1. Preserve the original file.
2. Detect and remove excessive background noise.
3. Apply conservative high-pass filtering where useful.
4. Normalize loudness.
5. Reduce excessive peaks.
6. Remove unnecessary silence without damaging natural speech.
7. Preserve natural vocal tone.
8. Synchronize audio with visual segments.
9. Produce a preview.

Use FFmpeg and other suitable open-source audio tools.

Do not use voice cloning or AI-generated imitation.

Never alter the meaning of the narration.

If the recording is too noisy or incomplete, request a new recording rather than overprocessing it.

### 5.4 Persian subtitles

Generate subtitles from the founder's actual audio using an appropriate Persian-capable speech-recognition solution.

Requirements:

- Editable transcript.
- Correct Persian RTL rendering.
- Proper mixed Persian/English text.
- Correct SEO terminology.
- Accurate timing.
- Readable mobile typography.
- Safe placement within Instagram UI boundaries.

The founder must be able to correct subtitle errors before final rendering.

### 5.5 Branding

Use the existing 3EO brand identity.

Do not invent a replacement logo.

Allow upload/configuration of:

- Transparent PNG/SVG logo.
- Brand colors.
- Persian font.
- Intro/outro.
- Lower thirds.
- Watermark.
- CTA templates.

If brand assets are unavailable, use neutral placeholders and request the real files.

### 5.6 Export formats

Produce:

- Instagram Reels: 1080×1920, MP4.
- Instagram Stories: 1080×1920.
- YouTube Shorts: 1080×1920.
- Instagram carousel: 1080×1350 images.

Use H.264/AAC for broadly compatible video exports.

Validate dimensions, audio, duration, and file integrity.

Create preview versions before final approval.

## 6. Telegram workflow

Use one dedicated Telegram bot for both agents.

Provide a Persian menu with:

- Today's ideas
- Submit video URL
- Research sources
- Saved ideas
- Approved ideas
- Generate script
- Production projects
- Upload voice
- Upload screen recording
- Preview video
- Request revisions
- Approve final output
- Settings
- Help

Implement role-based authorization.

Initially, only approved Telegram user IDs may access the bot.

Never expose the bot publicly by default.

Each content project must have a unique ID and a persistent status.

Suggested workflow:

`DISCOVERED → RESEARCHED → IDEA_APPROVED → SCRIPT_DRAFT → SCRIPT_APPROVED → AWAITING_ASSETS → EDITING → PREVIEW_READY → FINAL_APPROVED → EXPORTED`

Also support rejected, failed, and revision-requested states.

All transitions must be logged.

A rejected or unapproved item must never progress automatically to publication.

## 7. Admin dashboard

Build a responsive Persian RTL dashboard.

MVP pages:

1. Overview
2. Daily ideas
3. Source management
4. Manual URL submission
5. Content pipeline
6. Script editor
7. Media uploads
8. Video previews
9. Approval history
10. Settings and service health

Support filtering, searching, and status tracking.

Use secure authentication.

Do not expose the dashboard publicly until security checks and founder approval are complete.

## 8. Database

Design a normalized schema covering:

- users
- roles
- sources
- source_items
- transcripts
- research_reports
- content_ideas
- idea_scores
- scripts
- storyboards
- content_projects
- media_assets
- audio_processing_jobs
- rendering_jobs
- approvals
- publication_records
- scheduled_jobs
- api_usage
- audit_logs
- application_settings

Use database migrations.

Prevent duplicate source ingestion and duplicate daily reports.

Store large media files outside PostgreSQL.

## 9. Publication policy

MVP must support export and manual publication.

Prepare an extensible publishing adapter for future Instagram and YouTube integrations.

Do not implement unauthorized posting automation.

Any future publication must require explicit approval for the exact final content and destination.

Never publish automatically just because a script or video was approved for production.

## 10. Scheduling and resource management

Use `Asia/Tehran` for business schedules.

Required schedule:

- 3EO Content Scout report: 05:00 Iran time.
- Espadna Sim: existing 08:00 workflow remains unchanged.
- Content Producer: on demand.

Use resource-aware workers.

Prevent heavy rendering tasks from overlapping critical existing workloads.

Implement:

- Job timeouts.
- Retry with exponential backoff.
- Maximum concurrent renders.
- Disk-space checks.
- Temporary-file cleanup.
- Worker health checks.
- Error notifications.
- Log rotation.

Do not assume the server has GPU acceleration.

## 11. Security

Implement:

- Environment-based secrets.
- Strict Telegram user authorization.
- Secure file uploads.
- File-type and size validation.
- URL allowlisting.
- SSRF protection.
- Rate limits.
- Database backup strategy.
- No credentials in logs.
- No public media exposure by default.
- Dependency and container security checks.

Never print or commit secrets.

## 12. Development milestones

### M0 — Discovery and architecture

- Inspect infrastructure.
- Verify project isolation.
- Assess available resources.
- Define architecture.
- Create database design.
- Create deployment plan.
- Identify missing credentials.
- Document cost estimates.

### M1 — Content Scout MVP

- Telegram bot.
- Manual YouTube/Instagram URL submission.
- Source metadata.
- Authorized transcript handling.
- AI research summaries.
- Idea ranking.
- Daily 05:00 reporting.
- Idea approval workflow.

### M2 — Content Producer MVP

- Script generation.
- Script approval.
- Storyboard.
- Voice upload.
- Audio cleanup.
- Screen-recording upload.
- Video rendering.
- Persian subtitles.
- Preview and revision workflow.

### M3 — Motion Graphics

- Remotion templates.
- Hybrid-video templates.
- Branded intro/outro.
- Automatic scene composition.
- Export validation.

### M4 — Dashboard and hardening

- Persian dashboard.
- Monitoring.
- Backup.
- Automated tests.
- Security review.
- Documentation.
- Controlled deployment.

## 13. Testing requirements

Write automated tests for:

- URL validation.
- Duplicate detection.
- Source parsing.
- Missing transcripts.
- AI response validation.
- Ranking calculations.
- Telegram authorization.
- Approval-state transitions.
- Scheduling and timezone handling.
- Duplicate job prevention.
- Audio-processing failures.
- Video-rendering failures.
- RTL subtitle handling.
- Media upload security.
- Resource limits.

Provide integration tests with mocked external APIs.

Test one complete workflow:

Manual YouTube URL → Research → Idea approval → Persian script → Script approval → Voice upload → Media upload → Render → Preview → Final approval → Export.

Use an authorized sample video and media assets.

Do not claim the workflow works unless the relevant tests pass.

## 14. Documentation

Maintain:

- README.md
- AGENTS.md
- ARCHITECTURE.md
- REQUIREMENTS.md
- DEVELOPMENT_STATUS.md
- DEPLOYMENT.md
- OPERATIONS.md
- SECURITY.md
- COSTS.md
- TESTING.md

Record:

- Completed work.
- Pending work.
- Blockers.
- Test results.
- Deployment state.
- Resource usage.
- Required founder decisions.
- Next steps.

## 15. GitHub and deployment

If an existing repository for 3EO Content Studio is available, inspect it first.

Otherwise propose a dedicated repository.

Do not mix this project with the 3eo.ir website repository or Espadna Sim repository.

Use feature branches and pull requests.

Do not overwrite existing branches or force-push.

Do not deploy or publish publicly without explicit approval.

A local or isolated staging deployment may be prepared after verifying that it cannot disrupt existing services.

## 16. First execution instructions

Start immediately with M0.

1. Inspect the actual environment and available repository context.
2. Do not assume SSH access or GitHub access exists.
3. If server access is unavailable, proceed with repository-independent architecture and implementation preparation.
4. Report precisely which access or credentials are missing.
5. Do not request API keys until the relevant integration is ready.
6. Prioritize a working manual-link workflow before advanced automatic discovery.
7. Keep the existing Espadna Sim system untouched.
8. Implement the milestones in order, validating each one.
9. Do not stop for routine technical choices that can be made safely.
10. Stop for approval only when necessary for credentials, external costs, risky infrastructure changes, or publication.

### Founder priorities

- High-quality original Persian SEO education.
- Real screen demonstrations.
- Professional motion graphics.
- Real founder voice.
- Minimal recurring cost.
- Full control before publication.
- Reliable self-hosting.
- Independent operation from Espadna Sim.
- A reusable architecture for future brands.

Begin with M0 and provide an infrastructure assessment, architecture, cost estimate, and implementation plan. Then proceed with safe implementation work without waiting for unnecessary confirmations.