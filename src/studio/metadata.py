"""Optional official YouTube metadata only. No transcripts, scraping or submitted-URL fetches."""

import json
import time
from datetime import datetime
from typing import Literal

import httpx
from pydantic import BaseModel, ConfigDict, Field, field_validator
from sqlalchemy import update
from sqlalchemy.exc import IntegrityError

from .domain import normalize_url
from .storage import Usage


class SourceMetadata(BaseModel):
    model_config = ConfigDict(extra="forbid")
    provider: Literal["youtube_data_api"] = "youtube_data_api"
    content_id: str = Field(pattern=r"^[A-Za-z0-9_-]{11}$")
    title: str = Field(min_length=1, max_length=300)
    author: str = Field(min_length=1, max_length=200)
    published_at: datetime

    @field_validator("published_at")
    @classmethod
    def timezone_required(cls, value):
        if value.tzinfo is None:
            raise ValueError("Metadata publication date must include timezone")
        return value


class UnconfiguredMetadata:
    def fetch(self, url):
        raise RuntimeError("Metadata provider disabled")


class YouTubeMetadata:
    def __init__(self, key, transport=None):
        if not key:
            raise ValueError("A dedicated YouTube API key is required")
        self._key, self._transport = key, transport

    def fetch(self, url):
        platform, video_id, _ = normalize_url(url)
        if platform != "youtube":
            raise ValueError("Only YouTube metadata is supported")
        params = {"id": video_id, "part": "snippet", "key": self._key,
                  "fields": "items(id,snippet(title,channelTitle,publishedAt))"}
        deadline = time.monotonic() + 15
        try:
            with httpx.Client(timeout=10, follow_redirects=False, trust_env=False,
                              transport=self._transport) as client:
                with client.stream("GET", "https://www.googleapis.com/youtube/v3/videos",
                                   params=params, headers={"Accept-Encoding": "identity"}) as response:
                    if response.status_code != 200:
                        raise RuntimeError("Metadata unavailable")
                    if response.headers.get("content-type", "").split(";")[0] != "application/json":
                        raise ValueError("Invalid metadata content type")
                    if response.headers.get("content-encoding", "identity") != "identity":
                        raise ValueError("Compressed metadata response unsupported")
                    payload = bytearray()
                    for chunk in response.iter_bytes(chunk_size=8192):
                        if time.monotonic() > deadline:
                            raise RuntimeError("Metadata deadline exceeded")
                        payload.extend(chunk)
                        if len(payload) > 65536:
                            raise ValueError("Metadata response too large")
            data = json.loads(payload)
            items = data.get("items") if isinstance(data, dict) else None
            if not isinstance(items, list) or len(items) != 1:
                raise RuntimeError("Source metadata not available")
            item = items[0]
            if not isinstance(item, dict) or item.get("id") != video_id:
                raise ValueError("Metadata source ID mismatch")
            snippet = item.get("snippet")
            if not isinstance(snippet, dict):
                raise ValueError("Invalid metadata snippet")
            result = SourceMetadata(content_id=video_id, title=snippet.get("title"),
                                    author=snippet.get("channelTitle"),
                                    published_at=snippet.get("publishedAt"))
            return result
        except httpx.HTTPError:
            # Exception URLs include the key. Do not return or log the exception.
            raise RuntimeError("Metadata service unavailable") from None


def reserve_quota(sessions, day, limit):
    """Reserve before making a request; failures consume their reservation conservatively."""
    key = f"youtube:{day}"
    with sessions() as session:
        if session.get(Usage, key) is None:
            session.add(Usage(key=key, count=0))
            try:
                session.commit()
            except IntegrityError:
                session.rollback()
        changed = session.execute(update(Usage).where(
            Usage.key == key, Usage.count < limit,
        ).values(count=Usage.count + 1)).rowcount
        session.commit()
        return bool(changed)
