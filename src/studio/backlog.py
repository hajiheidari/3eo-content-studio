"""Persistent source backlog. No inference from inaccessible video URLs."""

import json
import os
import time
from datetime import datetime
from typing import Literal
from zoneinfo import ZoneInfo

from fastapi import Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select, update
from sqlalchemy.exc import IntegrityError

from .domain import normalize_url
from .storage import Audit, DiscoverySweep, Item, ProductionTask


class ImportEntry(BaseModel):
    url: str = Field(max_length=2048)
    text: str | None = Field(default=None, min_length=80, max_length=12000)
    kind: Literal["description", "transcript"] = "description"


class BulkInput(BaseModel):
    entries: list[ImportEntry] = Field(min_length=1, max_length=200)


class DiscoveryInput(BaseModel):
    query: str = Field(min_length=3, max_length=100)
    days: int = Field(default=30, ge=1, le=90)
    limit: int = Field(default=10, ge=1, le=20)


class TaskResult(BaseModel):
    state: Literal["needs_source", "failed", "held", "script_ready"]
    script_id: int | None = None


def register_backlog(app, sessions, authorized, catalog):
    def view(task):
        return {
            "id": task.id,
            "item_id": task.item_id,
            "state": task.state,
            "script_id": task.script_id,
            "delivery_state": task.delivery_state,
        }

    def ingest(entries, actor):
        # Validate the complete request before any mutation.
        try:
            urls = [normalize_url(e.url) for e in entries]
        except ValueError as exc:
            raise HTTPException(422, str(exc)) from None
        results = []
        with sessions() as s:
            for e, (platform, content_id, url) in zip(entries, urls):
                if platform != "youtube":
                    raise HTTPException(422, "The production backlog accepts YouTube sources")
                item = s.scalar(
                    select(Item).where(Item.platform == platform, Item.content_id == content_id)
                )
                if not item:
                    item = Item(platform=platform, content_id=content_id, url=url)
                    s.add(item)
                    s.flush()
                if (
                    e.text
                    and item.status in {"DISCOVERED", "MORE_RESEARCH"}
                    and not item.transcript
                ):
                    item.transcript, item.evidence_kind = e.text, e.kind
                    item.transcript_provenance = (
                        "User-supplied bulk source text; not independently retrieved"
                    )
                task = s.scalar(select(ProductionTask).where(ProductionTask.item_id == item.id))
                if not task:
                    task = ProductionTask(
                        item_id=item.id,
                        actor=actor,
                        state="queued" if item.transcript or catalog.configured else "needs_source",
                    )
                    s.add(task)
                    s.flush()
                elif task.state == "needs_source" and item.transcript:
                    task.state = "queued"
                results.append(view(task))
            try:
                s.commit()
            except IntegrityError:
                raise HTTPException(409, "Concurrent import; retry safely") from None
        return {"tasks": results, "publication": False}

    @app.post("/production/import")
    def bulk(body: BulkInput, actor=Depends(authorized)):
        return ingest(body.entries, actor)

    @app.get("/production/status", dependencies=[Depends(authorized)])
    def status():
        with sessions() as s:
            tasks = list(s.scalars(select(ProductionTask).order_by(ProductionTask.id).limit(1000)))
            return {
                "youtube_discovery_configured": catalog.configured,
                "tasks": [view(t) for t in tasks],
                "source_access_required": True,
            }

    @app.post("/youtube/discover")
    def discover(body: DiscoveryInput, actor=Depends(authorized)):
        try:
            videos = catalog.discover(body.query, body.days, body.limit)
        except RuntimeError:
            raise HTTPException(
                503, "Official YouTube API key/network unavailable; use bulk sources"
            ) from None
        response = (
            ingest([ImportEntry(url=e["url"]) for e in videos], actor) if videos else {"tasks": []}
        )
        response["videos"] = videos
        response["ranking"] = (
            "YouTube search viewCount order within query/date window; not global trends"
        )
        # Store API descriptions with their true provenance; never claim a transcript.
        with sessions() as s:
            for task, video in zip(response["tasks"], videos):
                item = s.get(Item, task["item_id"])
                if (
                    not item.transcript
                    and len(video["description"]) >= 80
                    and item.status == "DISCOVERED"
                ):
                    item.transcript, item.evidence_kind = video["description"], "description"
                    item.transcript_provenance = (
                        "Official YouTube Data API description only; video not watched"
                    )
                    item.title, item.published_at = video["title"], video["published_at"]
                    item.metadata_provenance = "Official YouTube Data API"
                    t = s.get(ProductionTask, task["id"])
                    if t.state == "needs_source":
                        t.state = "queued"
                    task["state"] = t.state
            s.commit()
        return response

    @app.post("/youtube/refresh")
    def daily_discovery(actor=Depends(authorized)):
        if not catalog.configured:
            return {"state": "disabled", "reason": "Official API not configured"}
        day = datetime.now(ZoneInfo("Asia/Tehran")).date().isoformat()
        with sessions() as s:
            old = s.get(DiscoverySweep, day)
            if old:
                return {"state": old.state, "duplicate": True}
            s.add(DiscoverySweep(day=day, state="processing"))
            try:
                s.commit()
            except IntegrityError:
                return {"state": "processing", "duplicate": True}
        state = "complete"
        try:
            discover(
                DiscoveryInput(query=os.getenv("STUDIO_YOUTUBE_QUERY", "SEO AI search")), actor
            )
        except (HTTPException, ValueError):
            state = "failed"
        with sessions() as s:
            s.get(DiscoverySweep, day).state = state
            s.commit()
        return {"state": state, "daily_search_limit": 1}

    @app.post("/production/claim", dependencies=[Depends(authorized)])
    def claim():
        with sessions() as s:
            # A crashed inference is recoverable; provider reservations have their own leases.
            stale = list(
                s.scalars(
                    select(ProductionTask).where(
                        ProductionTask.state == "processing",
                        ProductionTask.started_at < time.time() - 1800,
                    )
                )
            )
            for task in stale:
                task.state = "queued"
            s.commit()
            candidates = list(
                s.scalars(
                    select(ProductionTask)
                    .where(ProductionTask.state.in_(["queued", "needs_source"]))
                    .order_by(ProductionTask.id)
                    .limit(200)
                )
            )
            for task in candidates:
                item = s.get(Item, task.item_id)
                if not item.transcript and (not catalog.configured or task.state != "queued"):
                    continue
                claimed = s.execute(
                    update(ProductionTask)
                    .where(ProductionTask.id == task.id, ProductionTask.state == task.state)
                    .values(state="processing", started_at=time.time())
                ).rowcount
                s.commit()
                if claimed:
                    return {**view(task), "state": "processing", "actor": task.actor}
        return {"state": "idle"}

    @app.post("/production/tasks/{task_id}/source", dependencies=[Depends(authorized)])
    def retrieve_source(task_id: int):
        with sessions() as s:
            task = s.get(ProductionTask, task_id)
            if not task or task.state != "processing":
                raise HTTPException(409, "Task not claimed")
            item = s.get(Item, task.item_id)
            if item.transcript:
                return {"available": True}
            content_id = item.content_id
        try:
            video = catalog.describe(content_id)
        except RuntimeError:
            raise HTTPException(503, "Source description unavailable") from None
        if len(video["description"]) < 80:
            raise HTTPException(409, "Insufficient source text")
        with sessions() as s:
            task = s.get(ProductionTask, task_id)
            item = s.get(Item, task.item_id)
            if task.state != "processing" or item.status not in {"DISCOVERED", "MORE_RESEARCH"}:
                raise HTTPException(409, "Task changed")
            if not item.transcript:
                item.transcript, item.evidence_kind = video["description"], "description"
                item.transcript_provenance = (
                    "Official YouTube Data API description only; video not watched"
                )
                item.title, item.published_at = video["title"], video["published_at"]
                item.metadata_provenance = "Official YouTube Data API"
            s.commit()
        return {"available": True, "evidence": "description only"}

    @app.post("/production/tasks/{task_id}/select", dependencies=[Depends(authorized)])
    def select_idea(task_id: int):
        with sessions() as s:
            task = s.get(ProductionTask, task_id)
            if not task or task.state != "processing":
                raise HTTPException(409, "Claim the queued task first")
            item = s.get(Item, task.item_id)
            if item.status == "RESEARCHED" and item.research:
                confidence = json.loads(item.research).get("confidence")
                if item.score is None or item.score < 50 or confidence is None or confidence < 0.35:
                    return {"status": "HELD", "reason": "Research quality threshold not met"}
                item.status = "IDEA_APPROVED"
                s.add(
                    Audit(
                        item_id=item.id,
                        actor="system:automatic_selection",
                        previous="RESEARCHED",
                        current="IDEA_APPROVED",
                    )
                )
                s.commit()
            return {"status": item.status}

    @app.post("/production/tasks/{task_id}/retry", dependencies=[Depends(authorized)])
    def retry(task_id: int):
        with sessions() as s:
            task = s.get(ProductionTask, task_id)
            if not task or task.state not in {"failed", "needs_source", "held"}:
                raise HTTPException(409, "Only stopped tasks can be retried")
            item = s.get(Item, task.item_id)
            if not item.transcript and not catalog.configured:
                raise HTTPException(409, "Source text or official catalog access is required")
            task.state = "queued"
            s.commit()
            return view(task)

    @app.post("/production/tasks/{task_id}/finish", dependencies=[Depends(authorized)])
    def finish(task_id: int, body: TaskResult):
        from .storage import ScriptDraft

        with sessions() as s:
            task = s.get(ProductionTask, task_id)
            if not task or task.state != "processing":
                raise HTTPException(409, "Task is not processing")
            if body.state == "script_ready":
                script = s.get(ScriptDraft, body.script_id) if body.script_id else None
                if (
                    not script
                    or script.item_id != task.item_id
                    or script.state not in {"ready", "approved"}
                ):
                    raise HTTPException(409, "A completed script for this item is required")
            task.state, task.script_id = body.state, body.script_id
            s.commit()
            return view(task)
