import re
from datetime import datetime
from urllib.parse import parse_qs, urlsplit
from zoneinfo import ZoneInfo

WEIGHTS = dict(relevance=25, usefulness=20, brand_fit=20, freshness=15, short_video=10, evidence=10)


def normalize_url(value: str) -> tuple[str, str, str]:
    if len(value) > 2048:
        raise ValueError("URL too long")
    url = urlsplit(value)
    if url.scheme != "https" or url.username or url.password or url.port:
        raise ValueError("An HTTPS platform URL without credentials or port is required")
    host = (url.hostname or "").lower()
    if url.fragment:
        raise ValueError("Fragments are unsupported")
    if host in {"youtube.com", "www.youtube.com", "m.youtube.com", "youtu.be"}:
        if host == "youtu.be":
            video = url.path.lstrip("/")
        elif url.path == "/watch":
            video = parse_qs(url.query).get("v", [""])[0]
        elif url.path.startswith(("/shorts/", "/embed/")):
            video = url.path.split("/")[-1]
        else:
            raise ValueError("Unsupported YouTube URL")
        if not re.fullmatch(r"[A-Za-z0-9_-]{11}", video):
            raise ValueError("Invalid YouTube ID")
        return "youtube", video, f"https://www.youtube.com/watch?v={video}"
    if host in {"instagram.com", "www.instagram.com"}:
        match = re.fullmatch(r"/(?:reel|p)/([A-Za-z0-9_-]{1,100})/?", url.path)
        if match:
            video = match[1]
            return "instagram", video, f"https://www.instagram.com/p/{video}/"
    raise ValueError("Unsupported platform URL")


def rank(criteria: dict[str, float], weights: dict[str, int] = WEIGHTS) -> float:
    if set(criteria) != set(weights) or sum(weights.values()) != 100:
        raise ValueError("All criteria and weights totaling 100 are required")
    if any(v < 0 for v in weights.values()) or any(not 0 <= v <= 100 for v in criteria.values()):
        raise ValueError("Scores must be between 0 and 100")
    return round(sum(criteria[k] * w / 100 for k, w in weights.items()), 2)


def report_day(now: datetime) -> str | None:
    if now.tzinfo is None:
        raise ValueError("Timezone-aware time required")
    local = now.astimezone(ZoneInfo("Asia/Tehran"))
    return local.date().isoformat() if local.hour >= 5 else None


TRANSITIONS = {
    "DISCOVERED": {"RESEARCHED", "REJECTED"},
    "RESEARCHED": {"IDEA_APPROVED", "REJECTED", "SAVED", "MORE_RESEARCH"},
    "SAVED": {"IDEA_APPROVED", "REJECTED", "MORE_RESEARCH"},
    "MORE_RESEARCH": {"RESEARCHED", "REJECTED"},
    "IDEA_APPROVED": {"SCRIPT_DRAFT"},
    "SCRIPT_DRAFT": {"SCRIPT_APPROVED", "REVISION_REQUESTED"},
    "REVISION_REQUESTED": {"SCRIPT_DRAFT"},
    "SCRIPT_APPROVED": {"AWAITING_ASSETS"},
}
