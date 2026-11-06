"""Original RTL instructional motion cards, generated locally without source footage."""

import hashlib
import json
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont, features

from .media import MediaError, execute, inspect

TEMPLATE_VERSION = "rtl-cards-v1"
FONT = Path("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf")


def plan(content):
    shots = content.get("storyboard", [])
    if not 1 <= len(shots) <= 8:
        raise MediaError("A bounded storyboard is required")
    total = 0
    for shot in shots:
        duration = shot.get("duration_seconds", 0)
        if not isinstance(duration, (float, int)) or not 0.5 <= duration <= 15:
            raise MediaError("Unsupported scene timing")
        for key in ("on_screen_fa", "narration_fa"):
            if not isinstance(shot.get(key), str) or not 1 <= len(shot[key]) <= 400:
                raise MediaError("Bounded Persian scene text is required")
        total += duration
    if total > 90 or abs(total - content.get("duration_seconds", 0)) > 0.1:
        raise MediaError("Storyboard duration mismatch")
    return shots


def key_for(content, script_hash):
    return hashlib.sha256(
        json.dumps(
            [TEMPLATE_VERSION, script_hash, content], sort_keys=True, ensure_ascii=False
        ).encode()
    ).hexdigest()


def card(shot, number, count, path):
    if not features.check_feature("raqm") or not FONT.is_file():
        raise MediaError("Persian shaping/font unavailable")
    image = Image.new("RGB", (720, 1280), "#10182b")
    draw = ImageDraw.Draw(image)
    font = ImageFont.truetype(str(FONT), 32)
    small = ImageFont.truetype(str(FONT), 23)
    title = ImageFont.truetype(str(FONT), 43)
    draw.rounded_rectangle((38, 160, 682, 1110), radius=35, fill="#1c2b46")
    draw.text((60, 65), "3EO / STUDIO", fill="#58e3cc", font=small)
    draw.text((660, 195), f"{number} / {count}", anchor="ra", fill="#58e3cc", font=small)

    def lines(text, y, selected_font, max_lines):
        words, current, result = text.split(), "", []
        for word in words:
            candidate = f"{current} {word}".strip()
            if draw.textlength(candidate, font=selected_font, direction="rtl") <= 560:
                current = candidate
            else:
                if not current:
                    raise MediaError("Scene text cannot fit the visual layout")
                result.append(current)
                current = word
        if current:
            result.append(current)
        if len(result) > max_lines:
            raise MediaError("Scene text needs shortening for the visual layout")
        for line in result:
            draw.text(
                (640, y), line, font=selected_font, direction="rtl", anchor="ra", fill="white"
            )
            y += 65

    lines(shot["on_screen_fa"], 290, title, 3)
    draw.rounded_rectangle((70, 520, 650, 575), radius=15, fill="#314766")
    draw.rounded_rectangle((70, 590, 440, 645), radius=15, fill="#58e3cc")
    draw.line((120, 680, 600, 680), fill="#58e3cc", width=3)
    for x in [120, 360, 600]:
        draw.ellipse((x - 12, 668, x + 12, 692), fill="#58e3cc")
    lines(shot["narration_fa"], 755, font, 5)
    draw.text(
        (660, 1160),
        "تصویر آموزشی شماتیک؛ ضبط واقعی سایت نیست",
        font=small,
        direction="rtl",
        anchor="ra",
        fill="#afc0db",
    )
    image.save(path)
    path.chmod(0o600)


def generate_visuals(content, directory):
    shots = plan(content)
    clips = []
    for i, shot in enumerate(shots):
        png = directory / f"scene-{i}.png"
        clip = directory / f"scene-{i}.mp4"
        card(shot, i + 1, len(shots), png)
        frames = round(shot["duration_seconds"] * 25)
        # Gentle camera movement, advancing highlight and progress; source text is never executable.
        filters = (
            f"zoompan=z='min(zoom+0.00008,1.015)':x='iw/2-iw/zoom/2':"
            f"y='ih/2-ih/zoom/2':d={frames}:s=720x1280:fps=25,"
            f"drawbox=x=40:y=1220:w=640:h=6:color=0x314766:t=fill,"
            f"drawbox=x=40:y=1220:w=640:h=6:color=0x58e3cc:t=fill:enable='gte(t,{shot['duration_seconds'] / 2})',"
            "drawbox=x=70:y=590:w=370:h=55:color=white@0.25:t=3:enable='between(t,0.5,2.5)',"
            "format=yuv420p"
        )
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
                "-i",
                str(png),
                "-vf",
                filters,
                "-an",
                "-c:v",
                "libx264",
                "-preset",
                "ultrafast",
                "-crf",
                "25",
                "-threads",
                "1",
                "-map_metadata",
                "-1",
                "-n",
                str(clip),
            ],
            timeout=90,
        )
        clips.append(clip)
    listing = directory / "clips.txt"
    listing.write_text("\n".join(f"file '{p.name}'" for p in clips))
    output = directory / "original.bin"
    execute(
        [
            "ffmpeg",
            "-nostdin",
            "-v",
            "error",
            "-protocol_whitelist",
            "file,pipe",
            "-f",
            "concat",
            "-safe",
            "1",
            "-i",
            str(listing),
            "-c",
            "copy",
            "-map_metadata",
            "-1",
            "-movflags",
            "+faststart",
            "-f",
            "mp4",
            "-n",
            str(output),
        ],
        timeout=90,
    )
    output.chmod(0o600)
    info = inspect(output, "screen")
    if abs(info["duration_seconds"] - content["duration_seconds"]) > 0.2 or info["audio_present"]:
        raise MediaError("Generated visual timing invalid")
    for p in [*clips, listing, *directory.glob("*.png")]:
        p.unlink()
    return {
        **info,
        "generated": True,
        "template": TEMPLATE_VERSION,
        "source_footage_used": False,
        "illustrative": True,
        "speech_transcript_verified": False,
        "subtitles": False,
    }
