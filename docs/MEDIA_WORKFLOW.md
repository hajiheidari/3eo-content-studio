# M2 media and basic preview workflow

The approved script is the gate. Nothing accepts/uses production media for an unapproved,
old or revised script. Assets pin the exact script ID/hash. Original media is private outside
PostgreSQL and never overwritten by processing. No TTS, voice cloning or source-video reuse.

## Founder workflow in the private bot
1. After approving the script, open «بارگذاری رسانه» (or /assets SCRIPT_ID).
2. Choose own recorded voice or screen recording. Confirm that the recording is your real voice
   or that you own/have rights to the screen footage, then send one file. This is a user declaration,
   not a forensic proof of identity/rights. Telegram downloads are limited to 20 MiB/file.
3. Voice accepts MP3/WAV/M4A/OGG/Telegram voice. Actual container/streams are inspected; silent
   recordings request replacement. Original SHA-256 is verified before and after processing.
   Gentle denoising/high-pass/loudness processing produces WAV plus a private MP3 preview to
   listen to. Speech is not trimmed, pitch-shifted, synthesized or cloned. Noise/speech quality
   still needs human listening. No automatic speech transcript validation is claimed.
4. Upload your screen recording (MP4/WebM/MOV), then press «ساخت پیش‌نمایش». Both processed
   voice and a verified screen recording for this exact script are required. Screen footage must
   cover the narration; it is not silently looped to invent a longer demonstration.
5. Basic preview is a genuine 1080×1920 H.264/AAC MP4 combining your own screen and voice,
   fitting/padding footage without cropping it. It has no subtitles, automatic cursor effects,
   branded assets or Remotion animation. Real motion templates/Persian ASR remain future work.
6. Watch the video before «تأیید همین ویدئو». Only then is «دریافت فایل اصلی» allowed. Export is
   a private original MP4/document for manual publication, never an Instagram/YouTube post.

The video is delivered before its approval controls. Exact file digest, current selected preview
and script revision are checked. Bad duration match (difference >20% or 3s) prevents final
approval. Duration matching is not proof the narration matches the script: founder listening is
still required. Replacing media resets the preview/final gate. Old script media/preview cannot
approve a new revision. Previously owned originals remain available through authenticated APIs.

## API
- POST /scripts/{id}/assets/voice or /screen: raw streamed bytes, MIME Content-Type,
  X-Rights-Confirmed: 1 and (voice only) X-Founder-Voice: 1. Limits: audio 20 MiB, API video
  100 MiB; no user filename/path is used. GET /scripts/{id}/assets lists metadata.
- POST /assets/{id}/process-audio; GET /assets/{id}/file?variant=original|processed|preview.
- POST /scripts/{id}/preview with voice_asset_id and screen_asset_id. GET /renders/{id}.
- POST /renders/{id}/approve with full sha256; POST /renders/{id}/export after exact approval.
  GET /renders/{id}/file?variant=preview|export. All file routes require existing admin auth.

Files use random UUID directories under .local/media (700), originals/outputs 600, and no static
public directory. Uploads are streamed with byte and 120s time limits; invalid partial files are
removed. SHA deduplication is scoped to the script/kind. Fewer than 512 MiB free disk blocks
work. Input durations 0.5–300s; previews at most 90s; video max 4K area/60fps. Inputs are parsed
with ffprobe, not trusted extensions/MIME. Telegram file paths are fixed-host, no redirects,
no traversal, and downloads enforce declared bytes plus timeout. Credential-bearing URLs are
never printed; child decoders do not inherit application tokens.

Linux ffmpeg/ffprobe and util-linux prlimit are required (present in this cloud image; installed
in CI). Decoder/encoder processes have 1 GiB memory, 90 CPU seconds, 150 MiB output and 64 FD
limits, one media subprocess at a time, safe fixed arguments and file/pipe-only protocols with
allowed demuxers. Operation timeouts and stale reservations prevent indefinite jobs. The slot
is process-local: use one API worker until a durable distributed resource queue is implemented.

## Actual evidence vs pending acceptance
121 tests pass, including actual FFmpeg-generated test-signal/screen-pattern fixtures, real audio
processing and a genuine vertical H.264/AAC file, exact approval/export, stale/tampered preview,
script revision gates, body/time caps, deduplication, decoder environment isolation and Telegram
mock transfers. Tests are deliberately tiny lower-layer timing fixtures, not the founder's video.
The real project's script 2 is approved and upload controls are delivered, but no founder media
has been received yet. No personal video, subtitle, final approval/export or publication is claimed.

Schema: 0006 adds private media and upload context; 0007 adds rendering jobs. Back up the DB
and the private media tree together. Processes still need restart after development snapshot
publication/restoration. No production services or Espadna files/schedules have been modified.
