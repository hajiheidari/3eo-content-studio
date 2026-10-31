"""Opt-in, fixed-origin RSS/Atom discovery inbox. Never fetch entry URLs or run research."""

import hashlib
import re
import time
import uuid
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from html.parser import HTMLParser
from urllib.parse import urlsplit, urlunsplit

import httpx
from sqlalchemy import update
from sqlalchemy.exc import IntegrityError

from .storage import FeedEntry, FeedState

SOURCES = {
    "google-search-central": {
        "title": "Google Search Central",
        "url": "https://feeds.feedburner.com/blogspot/amDG",
        "publisher_type": "official",
    },
}
MAX_BYTES = 524288
ATOM = "{http://www.w3.org/2005/Atom}"


class FeedUnavailable(RuntimeError):
    pass


class FeedCoolingDown(RuntimeError):
    pass


class _Text(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.parts = []

    def handle_data(self, data):
        self.parts.append(data)


def plain(value, maximum):
    parser = _Text()
    parser.feed(value)
    return " ".join(" ".join(parser.parts).split())[:maximum]


def article_url(value):
    """Only canonical publisher articles; links remain inert discovery data."""
    if len(value) > 2048 or any(ord(c) < 33 for c in value):
        raise ValueError("Invalid article link")
    parts = urlsplit(value)
    if (parts.scheme != "https" or parts.netloc != "developers.google.com"
            or not re.fullmatch(r"/search/blog/[0-9]{4}/[0-9]{2}/[a-zA-Z0-9_-]+/?", parts.path)):
        raise ValueError("Unsupported article link")
    return urlunsplit(("https", parts.netloc, parts.path.rstrip("/"), "", ""))


def parse_feed(payload):
    if len(payload) > MAX_BYTES:
        raise ValueError("Feed too large")
    # UTF-8 only: a raw-byte DTD check alone would miss UTF-16 declarations.
    text = payload.decode("utf-8-sig")
    if re.search(r"<!\s*(DOCTYPE|ENTITY)", text, flags=re.I):
        raise ValueError("XML declarations forbidden")
    root = ET.fromstring(text)
    stack, nodes = [(root, 1)], 0
    while stack:
        element, depth = stack.pop()
        nodes += 1
        if nodes > 10000 or depth > 32:
            raise ValueError("Feed structure too large")
        stack.extend((child, depth + 1) for child in element)
    if root.tag == "rss" and root.find("channel") is not None:
        entries, atom = root.findall("channel/item"), False
    elif root.tag == ATOM + "feed":
        entries, atom = root.findall(ATOM + "entry"), True
    else:
        raise ValueError("Unsupported feed format")
    if len(entries) > 200:
        raise ValueError("Too many feed entries")
    result, skipped, seen = [], 0, set()
    for entry in entries:
        if atom:
            links = [e.get("href", "") for e in entry.findall(ATOM + "link")
                     if e.get("rel", "alternate") == "alternate"]
            link = next((url for url in links if url.startswith("https://developers.google.com/")), "")
            title = entry.findtext(ATOM + "title", "")
            date = entry.findtext(ATOM + "published") or entry.findtext(ATOM + "updated", "")
        else:
            link, title = entry.findtext("link", ""), entry.findtext("title", "")
            date = entry.findtext("pubDate", "")
        try:
            url = article_url(link.strip())
            title = plain(title, 300)
            if not title:
                raise ValueError("Missing title")
        except ValueError:
            skipped += 1
            continue
        if url not in seen:
            result.append({"url": url, "title": title, "published_at": plain(date, 100) or None})
            seen.add(url)
    if entries and not result:
        raise ValueError("No supported entries")
    return result, skipped


def validator(value):
    return value if value and len(value) <= 500 and all(32 <= ord(c) < 127 for c in value) else None


@dataclass
class FeedResponse:
    entries: list
    skipped: int = 0
    not_modified: bool = False
    etag: str | None = None
    modified: str | None = None


class FeedClient:
    def __init__(self, transport=None):
        self.transport = transport

    def fetch(self, source, etag=None, modified=None):
        url = SOURCES[source]["url"]  # No user-supplied request URL.
        headers = {"Accept-Encoding": "identity", "Accept": "application/atom+xml, application/rss+xml, text/xml"}
        if validator(etag):
            headers["If-None-Match"] = etag
        if validator(modified):
            headers["If-Modified-Since"] = modified
        deadline = time.monotonic() + 20
        try:
            with httpx.Client(timeout=10, follow_redirects=False, trust_env=False,
                              transport=self.transport) as client:
                with client.stream("GET", url, headers=headers) as response:
                    if response.status_code == 304:
                        if not (validator(etag) or validator(modified)):
                            raise ValueError("Unexpected not modified response")
                        return FeedResponse([], not_modified=True)
                    if response.status_code != 200:
                        raise ValueError("Feed HTTP status rejected")
                    media = response.headers.get("content-type", "").split(";")[0].lower().strip()
                    if media not in {"application/atom+xml", "application/rss+xml", "application/xml", "text/xml"}:
                        raise ValueError("Unsupported feed content type")
                    if response.headers.get("content-encoding", "identity").lower() != "identity":
                        raise ValueError("Compressed feeds unsupported")
                    payload = bytearray()
                    for chunk in response.iter_bytes(chunk_size=8192):
                        if time.monotonic() > deadline:
                            raise ValueError("Feed deadline exceeded")
                        payload.extend(chunk)
                        if len(payload) > MAX_BYTES:
                            raise ValueError("Feed too large")
                    entries, skipped = parse_feed(bytes(payload))
                    return FeedResponse(entries, skipped=skipped,
                                        etag=validator(response.headers.get("etag")),
                                        modified=validator(response.headers.get("last-modified")))
        except (httpx.HTTPError, ValueError, ET.ParseError):
            # External text, exception URLs and XML parser details are never returned/logged.
            raise FeedUnavailable("Feed unavailable or invalid") from None


def collect(sessions, source, client, now=None):
    """Durable claim/cooldown, cached validators and inserts; old workers cannot overwrite new ones."""
    if source not in SOURCES:
        raise ValueError("Unknown feed source")
    now = time.time() if now is None else now
    owner = uuid.uuid4().hex
    with sessions() as session:
        if session.get(FeedState, source) is None:
            session.add(FeedState(source=source, next_at=0))
            try:
                session.commit()
            except IntegrityError:
                session.rollback()
        claimed = session.execute(update(FeedState).where(
            FeedState.source == source, FeedState.next_at <= now,
        ).values(owner=owner, next_at=now + 300, checked_at=now, status="fetching", error=None))
        session.commit()
        if not claimed.rowcount:
            raise FeedCoolingDown("Feed collection already active or cooling down")
        state = session.get(FeedState, source)
        etag, modified = state.etag, state.modified
    try:
        response = client.fetch(source, etag, modified)
    except FeedUnavailable:
        with sessions() as session:
            session.execute(update(FeedState).where(
                FeedState.source == source, FeedState.owner == owner,
            ).values(status="failed", error="unavailable_or_invalid", owner=None))
            session.commit()
        raise
    with sessions() as session:
        # Lock/fence before entry writes, keeping cache and rows in the same transaction.
        changed = session.execute(update(FeedState).where(
            FeedState.source == source, FeedState.owner == owner,
        ).values(status="not_modified" if response.not_modified else "ok",
                 success_at=now, next_at=now + 3600, owner=None, error=None))
        if not changed.rowcount:
            session.rollback()
            raise FeedCoolingDown("Feed claim expired; newer collection owns the source")
        state = session.get(FeedState, source)
        added = 0
        if not response.not_modified:
            state.etag, state.modified = response.etag, response.modified
            for entry in response.entries:
                key = hashlib.sha256(f"{source}:{entry['url']}".encode()).hexdigest()
                if session.get(FeedEntry, key) is None:
                    session.add(FeedEntry(key=key, source=source, discovered_at=now, **entry))
                    added += 1
        session.commit()
        return {"source": source, "added": added, "skipped": response.skipped,
                "not_modified": response.not_modified, "next_at": now + 3600,
                "research_started": False}
