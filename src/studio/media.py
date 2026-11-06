"""Private local media inspection/processing; no remote decoder protocols or synthesized voice."""

import json
import math
import os
import subprocess
import threading
from fractions import Fraction
from pathlib import Path

AUDIO_LIMIT = 20 * 1024 * 1024
VIDEO_LIMIT = 100 * 1024 * 1024
MIMES = {
    "voice": {
        "audio/mpeg",
        "audio/mp3",
        "audio/wav",
        "audio/x-wav",
        "audio/mp4",
        "audio/x-m4a",
        "audio/ogg",
        "application/ogg",
    },
    "screen": {"video/mp4", "video/webm", "video/quicktime"},
}


class MediaError(RuntimeError):
    pass


class MediaBusy(MediaError):
    pass


_WORKER = threading.BoundedSemaphore(1)


def execute(arguments, timeout=45):
    if not _WORKER.acquire(timeout=5):
        raise MediaBusy("Media worker busy; retry later")
    try:
        result = subprocess.run(
            ["prlimit", "--as=1073741824", "--cpu=90", "--fsize=157286400", "--nofile=64", "--"]
            + arguments,
            stdin=subprocess.DEVNULL,
            capture_output=True,
            timeout=timeout,
            check=False,
            env={
                "PATH": os.environ.get("PATH", os.defpath),
                "LANG": "C",
                "OPENBLAS_NUM_THREADS": "1",
                "OMP_NUM_THREADS": "1",
            },
        )
    except (OSError, subprocess.TimeoutExpired):
        raise MediaError("Media tool unavailable or timed out") from None
    finally:
        _WORKER.release()
    if result.returncode:
        raise MediaError("Invalid or unsupported media; decoder failed")
    return result


def inspect(path: Path, kind: str):
    result = execute(
        [
            "ffprobe",
            "-v",
            "error",
            "-threads",
            "1",
            "-protocol_whitelist",
            "file,pipe",
            "-format_whitelist",
            "mov,mp3,wav,ogg,matroska,webm",
            "-max_streams",
            "8",
            "-show_entries",
            "format=duration:stream=index,codec_type,codec_name,channels,width,height,avg_frame_rate:stream_disposition=attached_pic",
            "-of",
            "json",
            str(path),
        ]
    )
    try:
        data = json.loads(result.stdout)
        duration = float(data["format"]["duration"])
        if not math.isfinite(duration) or not 0.5 <= duration <= 300:
            raise MediaError("Duration must be between 0.5 and 300 seconds")
        streams = data["streams"]
        audio = [s for s in streams if s.get("codec_type") == "audio"]
        video = [
            s
            for s in streams
            if s.get("codec_type") == "video" and not s.get("disposition", {}).get("attached_pic")
        ]
        if kind == "voice":
            if len(audio) != 1 or video or audio[0].get("channels", 0) not in {1, 2}:
                raise MediaError("A mono/stereo audio recording without video is required")
            codec = audio[0].get("codec_name", "")
            if codec not in {"mp3", "aac", "opus", "vorbis", "flac"} and not codec.startswith(
                "pcm_"
            ):
                raise MediaError("Unsupported recording codec")
            return {
                "duration_seconds": duration,
                "audio_codec": codec,
                "channels": audio[0]["channels"],
            }
        if kind != "screen" or len(video) != 1:
            raise MediaError("A single screen-recording video stream is required")
        v = video[0]
        width, height = int(v["width"]), int(v["height"])
        fps = float(Fraction(v.get("avg_frame_rate", "0/1")))
        if (
            not 1 <= width <= 3840
            or not 1 <= height <= 3840
            or width * height > 3840 * 2160
            or not 0 < fps <= 60
        ):
            raise MediaError("Video dimensions or frame rate exceed supported limits")
        if v.get("codec_name") not in {"h264", "hevc", "vp8", "vp9", "av1", "mpeg4"}:
            raise MediaError("Unsupported video codec")
        return {
            "duration_seconds": duration,
            "width": width,
            "height": height,
            "fps": fps,
            "video_codec": v["codec_name"],
            "audio_present": bool(audio),
            "audio_codec": audio[0].get("codec_name") if audio else None,
        }
    except (KeyError, TypeError, ValueError, ZeroDivisionError):
        raise MediaError("Media metadata is incomplete or invalid") from None


def process_voice(original: Path, destination: Path):
    before = inspect(original, "voice")
    # Low peak levels/silence should not be amplified into a misleading successful recording.
    analysis = execute(
        [
            "ffmpeg",
            "-nostdin",
            "-v",
            "info",
            "-threads",
            "1",
            "-protocol_whitelist",
            "file,pipe",
            "-format_whitelist",
            "mov,mp3,wav,ogg,matroska,webm",
            "-i",
            str(original),
            "-map",
            "0:a:0",
            "-af",
            "volumedetect",
            "-f",
            "null",
            "-",
        ],
        timeout=90,
    )
    import re

    match = re.search(rb"max_volume:\s*(-?\d+(?:\.\d+)?|[-+]?inf) dB", analysis.stderr)
    if not match or float(match[1]) < -65:
        raise MediaError("Recording is silent or too quiet; record it again")
    # Preserve duration/meaning. No silence deletion, pitch transformation, TTS or voice cloning.
    execute(
        [
            "ffmpeg",
            "-nostdin",
            "-v",
            "error",
            "-threads",
            "1",
            "-filter_threads",
            "1",
            "-protocol_whitelist",
            "file,pipe",
            "-format_whitelist",
            "mov,mp3,wav,ogg,matroska,webm",
            "-i",
            str(original),
            "-map",
            "0:a:0",
            "-vn",
            "-af",
            "highpass=f=60,afftdn=nr=6,loudnorm=I=-16:TP=-1.5:LRA=11",
            "-ar",
            "48000",
            "-c:a",
            "pcm_s16le",
            "-map_metadata",
            "-1",
            "-n",
            str(destination),
        ],
        timeout=90,
    )
    destination.chmod(0o600)
    preview = destination.with_name("preview.mp3")
    execute(
        [
            "ffmpeg",
            "-nostdin",
            "-v",
            "error",
            "-threads",
            "1",
            "-protocol_whitelist",
            "file,pipe",
            "-i",
            str(destination),
            "-map",
            "0:a:0",
            "-ac",
            "1",
            "-c:a",
            "libmp3lame",
            "-b:a",
            "128k",
            "-map_metadata",
            "-1",
            "-n",
            str(preview),
        ],
        timeout=90,
    )
    preview.chmod(0o600)
    after = inspect(destination, "voice")
    if abs(after["duration_seconds"] - before["duration_seconds"]) > 0.2:
        destination.unlink(missing_ok=True)
        raise MediaError("Processed recording duration changed; original retained")
    return {
        **after,
        "original_preserved": True,
        "review_required": True,
        "peak_db_before": float(match[1]),
        "silence_removal": False,
        "voice_synthesis": False,
        "preview_available": True,
    }
