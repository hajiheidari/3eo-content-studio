"""Basic genuine screen-recording preview; no publication or synthetic narration."""

from pathlib import Path

from .media import MediaError, execute, inspect


def render_preview(screen: Path, voice: Path, destination: Path, planned_seconds: float):
    audio = inspect(voice, "voice")
    video = inspect(screen, "screen")
    duration = audio["duration_seconds"]
    if duration > 90:
        raise MediaError("Preview narration must be at most 90 seconds")
    if video["duration_seconds"] + 0.2 < duration:
        raise MediaError("Screen recording is shorter than narration; supply a complete recording")
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
            str(screen),
            "-protocol_whitelist",
            "file,pipe",
            "-format_whitelist",
            "mov,mp3,wav,ogg,matroska,webm",
            "-i",
            str(voice),
            "-map",
            "0:v:0",
            "-map",
            "1:a:0",
            "-vf",
            "scale=1080:1920:force_original_aspect_ratio=decrease:force_divisible_by=2,pad=1080:1920:(ow-iw)/2:(oh-ih)/2,setsar=1,fps=30,format=yuv420p",
            "-c:v",
            "libx264",
            "-preset",
            "ultrafast",
            "-crf",
            "28",
            "-maxrate",
            "4M",
            "-bufsize",
            "8M",
            "-threads",
            "1",
            "-c:a",
            "aac",
            "-b:a",
            "128k",
            "-t",
            str(duration),
            "-map_metadata",
            "-1",
            "-movflags",
            "+faststart",
            "-n",
            str(destination),
        ],
        timeout=120,
    )
    destination.chmod(0o600)
    output = inspect(destination, "screen")
    if (
        output["width"] != 1080
        or output["height"] != 1920
        or output["video_codec"] != "h264"
        or not output["audio_present"]
        or output["audio_codec"] != "aac"
        or abs(output["duration_seconds"] - duration) > 0.3
    ):
        raise MediaError("Rendered preview failed integrity checks")
    return {
        **output,
        "voice_source": "founder_recording",
        "speech_transcript_verified": False,
        "subtitles": False,
        "planned_seconds": planned_seconds,
        "duration_matches_script": abs(duration - planned_seconds) <= max(3, planned_seconds * 0.2),
        "publication": False,
    }
