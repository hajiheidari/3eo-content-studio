"""Official YouTube Data API only; descriptions are not video transcripts."""

import os
from datetime import datetime, timedelta, timezone

import httpx

from .integrations import IntegrationError, bounded_json


class YouTubeCatalog:
    def __init__(self, key=None, client=None):
        self.key = key or os.getenv("STUDIO_YOUTUBE_API_KEY")
        self.client = client

    @property
    def configured(self):
        return bool(self.key)

    def request(self, client, endpoint, **params):
        if not self.configured:
            raise IntegrationError("YouTube discovery needs an official API key and network access")
        return bounded_json(
            client,
            "GET",
            f"https://www.googleapis.com/youtube/v3/{endpoint}",
            limit=524288,
            params=params,
            headers={"X-Goog-Api-Key": self.key},
        )

    def describe(self, video_id):
        def run(client):
            data = self.request(client, "videos", part="snippet,statistics", id=video_id)
            entries = data.get("items", [])
            if not entries:
                raise IntegrationError("Video metadata unavailable")
            e = entries[0]
            snippet = e.get("snippet", {})
            return {
                "url": f"https://www.youtube.com/watch?v={video_id}",
                "title": snippet.get("title", "")[:1000],
                "description": snippet.get("description", "")[:12000],
                "published_at": snippet.get("publishedAt"),
                "views": int(e.get("statistics", {}).get("viewCount", 0)),
            }

        if self.client:
            return run(self.client)
        with httpx.Client(timeout=15, follow_redirects=False) as client:
            return run(client)

    def discover(self, query, days=30, limit=10):
        def run(client):
            since = (
                (datetime.now(timezone.utc) - timedelta(days=days))
                .isoformat()
                .replace("+00:00", "Z")
            )
            data = self.request(
                client,
                "search",
                part="snippet",
                q=query,
                type="video",
                order="viewCount",
                publishedAfter=since,
                maxResults=limit,
            )
            ids = [e.get("id", {}).get("videoId", "") for e in data.get("items", [])]
            import re

            ids = [i for i in ids if re.fullmatch(r"[A-Za-z0-9_-]{11}", i)]
            if not ids:
                return []
            data = self.request(client, "videos", part="snippet,statistics", id=",".join(ids))
            entries = []
            for e in data.get("items", []):
                if e.get("id") not in ids:
                    continue
                sn = e.get("snippet", {})
                entries.append(
                    {
                        "url": f"https://www.youtube.com/watch?v={e['id']}",
                        "title": sn.get("title", "")[:1000],
                        "description": sn.get("description", "")[:12000],
                        "published_at": sn.get("publishedAt"),
                        "views": int(e.get("statistics", {}).get("viewCount", 0)),
                    }
                )
            return sorted(entries, key=lambda e: e["views"], reverse=True)

        if self.client:
            return run(self.client)
        with httpx.Client(timeout=15, follow_redirects=False) as client:
            return run(client)
