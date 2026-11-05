import hashlib
import hmac
import json
import os
from datetime import datetime, timezone
from typing import Literal

import httpx
from fastapi import Depends, FastAPI, Header, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import BaseModel, Field, ValidationError
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm.exc import StaleDataError

from .domain import TRANSITIONS, normalize_url, rank, report_day, text_similarity
from .feeds import FeedReader, feed_url
from .integrations import LlamaResearch, OllamaResearch, YouTubeMetadata
from .research import Research, UnconfiguredProvider
from .storage import Audit, Conversation, Delivery, Item, Report, Source, database


def create_app(database_url=None, token=None, provider=None, metadata=None, feeds=None):
    engine, sessions = database(database_url or os.getenv("DATABASE_URL", "sqlite:///./studio.db"))
    secret = token or os.getenv("STUDIO_ADMIN_TOKEN")
    provider = provider or (
        OllamaResearch(os.environ["STUDIO_OLLAMA_MODEL"])
        if os.getenv("STUDIO_OLLAMA_MODEL")
        else UnconfiguredProvider()
    )
    if os.getenv("STUDIO_LOCAL_AI") == "1" and provider.__class__ is UnconfiguredProvider:
        provider = LlamaResearch()
    metadata = metadata or YouTubeMetadata()
    feeds = feeds or FeedReader()
    app = FastAPI(title="3EO Content Studio", docs_url=None, redoc_url=None, openapi_url=None)
    app.state.engine = engine
    auth = HTTPBearer(auto_error=False)

    @app.exception_handler(StaleDataError)
    async def stale_write(request, exc):
        from fastapi.responses import JSONResponse

        return JSONResponse(
            status_code=409, content={"detail": "Item changed; reload before retrying"}
        )

    def authorized(
        credentials: HTTPAuthorizationCredentials | None = Depends(auth),
        actor: str = Header(
            default="admin", alias="X-Studio-Actor", pattern=r"^(admin|telegram:[0-9]{1,20})$"
        ),
    ):
        if (
            not secret
            or not credentials
            or not hmac.compare_digest(credentials.credentials.encode(), secret.encode())
        ):
            raise HTTPException(401, "Unauthorized")
        return actor

    def get_item(session, item_id):
        item = session.get(Item, item_id)
        if item is None:
            raise HTTPException(404, "Item not found")
        return item

    @app.get("/research/health", dependencies=[Depends(authorized)])
    def research_health():
        if isinstance(provider, UnconfiguredProvider):
            return {"configured": False, "ready": False, "provider": None}
        if isinstance(provider, LlamaResearch):
            try:
                response = httpx.get("http://127.0.0.1:8081/health", timeout=2)
                ready = response.status_code == 200
            except httpx.HTTPError:
                ready = False
            return {"configured": True, "ready": ready, "provider": "llama.cpp"}
        return {
            "configured": True,
            "ready": None,
            "provider": "ollama" if isinstance(provider, OllamaResearch) else "custom",
        }

    @app.get("/health")
    def health():
        with sessions() as session:
            session.execute(select(Report).limit(1)).all()
            session.execute(select(Item.version).limit(1)).all()
            session.execute(select(Source.id).limit(1)).all()
            session.execute(select(Delivery.id).limit(1)).all()
        return {"status": "ok", "publication_enabled": False}

    @app.get("/sources", dependencies=[Depends(authorized)])
    def list_sources():
        with sessions() as session:
            return [
                {
                    "id": s.id,
                    "name": s.name,
                    "url": s.url,
                    "enabled": s.enabled,
                    "classification": "official",
                }
                for s in session.scalars(select(Source).order_by(Source.id))
            ]

    @app.post("/sources", dependencies=[Depends(authorized)])
    def add_source(body: SourceInput):
        try:
            feed_url(body.url)
        except ValueError as exc:
            raise HTTPException(422, str(exc)) from None
        with sessions() as session:
            source = session.scalar(select(Source).where(Source.url == body.url))
            if source:
                source.name, source.enabled = body.name, body.enabled
            else:
                if len(session.scalars(select(Source.id)).all()) >= 10:
                    raise HTTPException(409, "At most ten feeds are supported")
                source = Source(name=body.name, url=body.url, enabled=body.enabled)
                session.add(source)
            try:
                session.commit()
            except IntegrityError:
                raise HTTPException(409, "Source changed; reload before retrying") from None
            return {"id": source.id, "enabled": source.enabled}

    @app.post("/sources/{source_id}/refresh", dependencies=[Depends(authorized)])
    def refresh_source(source_id: int):
        with sessions() as session:
            source = session.get(Source, source_id)
            if not source:
                raise HTTPException(404, "Source not found")
            if not source.enabled:
                raise HTTPException(409, "Source disabled")
            try:
                entries = feeds.fetch(source.url)
            except RuntimeError as exc:
                raise HTTPException(503, str(exc)) from None
            added = 0
            for entry in entries:
                if session.scalar(
                    select(Item.id).where(
                        Item.platform == "rss", Item.content_id == entry.content_id
                    )
                ):
                    continue
                try:
                    with session.begin_nested():
                        session.add(
                            Item(
                                platform="rss",
                                content_id=entry.content_id,
                                url=entry.url,
                                title=entry.title,
                                author=entry.author,
                                published_at=entry.published_at,
                                metadata_provenance=f"Official public feed: {source.name}",
                                transcript=entry.excerpt or None,
                                evidence_kind="feed_excerpt",
                                transcript_provenance=f"Public feed excerpt only from {source.url}; linked article not retrieved",
                            )
                        )
                        session.flush()
                    added += 1
                except IntegrityError:
                    pass  # concurrent ingestion already saved the same URL
            session.commit()
            return {"added": added, "entries": len(entries), "evidence": "feed excerpt only"}

    @app.get("/conversation")
    def conversation(actor=Depends(authorized)):
        with sessions() as session:
            current = session.get(Conversation, actor)
            if not current:
                raise HTTPException(404, "No active source")
            return {"item_id": current.item_id, "evidence_kind": current.evidence_kind}

    @app.delete("/conversation")
    def reset_conversation(actor=Depends(authorized)):
        with sessions() as session:
            current = session.get(Conversation, actor)
            if current:
                session.delete(current)
                session.commit()
        return {"status": "ready_for_new_idea"}

    @app.put("/conversation")
    def set_conversation(body: ConversationInput, actor=Depends(authorized)):
        with sessions() as session:
            item = get_item(session, body.item_id)
            current = session.get(Conversation, actor)
            if current:
                current.item_id, current.evidence_kind = item.id, body.evidence_kind
            else:
                session.add(
                    Conversation(actor=actor, item_id=item.id, evidence_kind=body.evidence_kind)
                )
            session.commit()
        return {"item_id": body.item_id, "evidence_kind": body.evidence_kind}

    @app.post("/items/text")
    def standalone_text(body: EvidenceInput, actor=Depends(authorized)):
        digest = hashlib.sha256(body.text.encode()).hexdigest()
        with sessions() as session:
            item = session.scalar(
                select(Item).where(Item.platform == "text", Item.content_id == digest)
            )
            if not item:
                item = Item(
                    platform="text",
                    content_id=digest,
                    url=f"urn:3eo:text:{digest}",
                    transcript=body.text,
                    transcript_provenance=body.provenance,
                    evidence_kind=body.kind,
                )
                session.add(item)
                try:
                    session.commit()
                except IntegrityError:
                    session.rollback()
                    item = session.scalar(
                        select(Item).where(Item.platform == "text", Item.content_id == digest)
                    )
            return {"id": item.id, "status": item.status}

    @app.put("/items/{item_id}/evidence")
    def store_evidence(item_id: int, body: EvidenceInput, actor=Depends(authorized)):
        with sessions() as session:
            item = get_item(session, item_id)
            if item.status not in {"DISCOVERED", "MORE_RESEARCH"}:
                raise HTTPException(
                    409, "Evidence locked; request more research before replacing it"
                )
            item.transcript, item.transcript_provenance = body.text, body.provenance
            item.evidence_kind = body.kind
            session.commit()
        return {"status": "stored", "kind": body.kind}

    @app.post("/items", dependencies=[Depends(authorized)])
    def submit(body: Submission):
        try:
            platform, content_id, url = normalize_url(body.url)
        except ValueError as exc:
            raise HTTPException(422, str(exc)) from exc
        with sessions() as session:
            item = Item(platform=platform, content_id=content_id, url=url)
            session.add(item)
            try:
                session.commit()
            except IntegrityError:
                session.rollback()
                item = session.scalar(
                    select(Item).where(Item.platform == platform, Item.content_id == content_id)
                )
            return {
                "id": item.id,
                "url": item.url,
                "status": item.status,
                "next": "Supply an authorized transcript; request metadata separately",
            }

    @app.get("/items", dependencies=[Depends(authorized)])
    def items():
        with sessions() as session:
            return [
                {
                    "id": i.id,
                    "url": i.url,
                    "title": i.title,
                    "metadata_provenance": i.metadata_provenance,
                    "author": i.author,
                    "published_at": i.published_at,
                    "status": i.status,
                    "score": i.score,
                    "research": json.loads(i.research) if i.research else None,
                }
                for i in session.scalars(select(Item).order_by(Item.id.desc()).limit(100))
            ]

    @app.get("/reports/today", dependencies=[Depends(authorized)])
    def today_report():
        day = report_day(datetime.now(timezone.utc))
        with sessions() as session:
            report = session.get(Report, day) if day else None
            if not report:
                raise HTTPException(404, "Report not prepared")
            return {"day": day, "ideas": json.loads(report.payload)}

    @app.get("/items/{item_id}", dependencies=[Depends(authorized)])
    def item_details(item_id: int):
        with sessions() as session:
            item = get_item(session, item_id)
            return {
                "id": item.id,
                "url": item.url,
                "status": item.status,
                "author": item.author,
                "published_at": item.published_at,
                "score": item.score,
                "research": json.loads(item.research) if item.research else None,
                "evidence_kind": item.evidence_kind,
            }

    @app.get("/items/{item_id}/duplicates", dependencies=[Depends(authorized)])
    def duplicates(item_id: int):
        with sessions() as session:
            item = get_item(session, item_id)
            original = item.transcript or item.title or ""
            candidates = session.scalars(
                select(Item).where(Item.id != item_id).order_by(Item.id.desc()).limit(100)
            ).all()
            matches = [
                {
                    "id": other.id,
                    "url": other.url,
                    "similarity": text_similarity(original, other.transcript or other.title or ""),
                }
                for other in candidates
            ]
            return {
                "advisory": True,
                "candidate_limit": 100,
                "matches": sorted(
                    [m for m in matches if m["similarity"] >= 0.85],
                    key=lambda m: m["similarity"],
                    reverse=True,
                ),
            }

    @app.post("/items/{item_id}/metadata", dependencies=[Depends(authorized)])
    def fetch_metadata(item_id: int):
        with sessions() as session:
            item = get_item(session, item_id)
            try:
                result = metadata.fetch(item.url)
            except RuntimeError as exc:
                raise HTTPException(503, str(exc)) from None
            item.title, item.author = result.title, result.author
            item.metadata_provenance = result.provenance
            if result.published_at:
                item.published_at = result.published_at
            session.commit()
            return result.model_dump()

    @app.put("/items/{item_id}/transcript", dependencies=[Depends(authorized)])
    def transcript(item_id: int, body: Transcript):
        with sessions() as session:
            item = get_item(session, item_id)
            if item.status not in {"DISCOVERED", "MORE_RESEARCH"}:
                raise HTTPException(409, "Transcript is locked after research")
            item.transcript, item.transcript_provenance = body.text, body.provenance
            item.evidence_kind = "transcript"
            if body.author is not None:
                item.author = body.author
                item.metadata_provenance = "User supplied"
            if body.published_at is not None:
                item.published_at = body.published_at
            session.commit()
        return {"status": "stored", "metadata_source": "user supplied"}

    @app.post("/items/{item_id}/research")
    def research(item_id: int, body: Research | None = None, actor=Depends(authorized)):
        with sessions() as session:
            item = get_item(session, item_id)
            if not item.transcript:
                raise HTTPException(
                    409, "Authorized transcript required; content has not been analyzed"
                )
            if item.status not in {"DISCOVERED", "MORE_RESEARCH"}:
                raise HTTPException(409, "Research not allowed in this state")
            try:
                result = Research.model_validate(
                    body
                    or provider.analyze(
                        f"Evidence kind: {item.evidence_kind or 'unclassified supplied text'}. "
                        f"Provenance (user supplied, not independently verified): {item.transcript_provenance}. "
                        "Analyze ONLY this material; do not claim to have watched a video or read a full article.\n"
                        + item.transcript,
                        item.url,
                    )
                )
            except ValidationError:
                raise HTTPException(502, "Research provider returned invalid output") from None
            except RuntimeError:
                raise HTTPException(
                    503, "Research provider unavailable; submit reviewed research"
                ) from None
            if item.evidence_kind in {"description", "feed_excerpt", "user_text"}:
                # Evidence boundaries come from stored input type, not model world knowledge.
                result.limitations = [
                    "این پژوهش فقط بر متن ارسالی استوار است؛ ویدئو یا مقالهٔ کامل بررسی نشده و ادعاها مستقلاً تأیید نشده‌اند."
                ]
                if item.author is None:
                    result.limitations.append("نام نویسنده به‌صورت مستقل تأیید نشده است.")
                if item.published_at is None:
                    result.limitations.append("تاریخ انتشار منبع مشخص نیست.")
                result.confidence = (
                    min(result.confidence, 0.5) if result.confidence is not None else None
                )
            item.research = result.model_dump_json()
            item.score = rank(result.criteria)
            session.add(
                Audit(item_id=item.id, actor=actor, previous=item.status, current="RESEARCHED")
            )
            item.status = "RESEARCHED"
            session.commit()
            return {"status": item.status, "score": item.score}

    @app.post("/items/{item_id}/transition")
    def transition(item_id: int, body: Transition, actor=Depends(authorized)):
        # Producer states are reserved until the producer and script review exist.
        if body.status not in {"IDEA_APPROVED", "REJECTED", "SAVED", "MORE_RESEARCH"}:
            raise HTTPException(422, "Unsupported M1 action")
        with sessions() as session:
            item = get_item(session, item_id)
            previous = item.status
            if body.status not in TRANSITIONS.get(previous, set()):
                raise HTTPException(409, "Invalid approval transition")
            item.status = body.status
            session.add(Audit(item_id=item.id, actor=actor, previous=previous, current=body.status))
            session.commit()
        return {"status": body.status}

    @app.post("/reports/prepare", dependencies=[Depends(authorized)])
    def prepare_report():
        day = report_day(datetime.now(timezone.utc))
        if not day:
            raise HTTPException(409, "Report is not due before 05:00 Asia/Tehran")
        with sessions() as session:
            existing = session.get(Report, day)
            if existing:
                return {"day": day, "ideas": json.loads(existing.payload), "duplicate": True}
            ideas = [
                {
                    "id": i.id,
                    "url": i.url,
                    "score": i.score,
                    "title": i.title,
                    "metadata_provenance": i.metadata_provenance,
                    "author": i.author,
                    "published_at": i.published_at,
                    "research": json.loads(i.research),
                }
                for i in session.scalars(
                    select(Item)
                    .where(Item.status == "RESEARCHED")
                    .order_by(Item.score.desc(), Item.id)
                    .limit(5)
                )
            ]
            session.add(Report(day=day, payload=json.dumps(ideas, ensure_ascii=False)))
            try:
                session.commit()
            except IntegrityError:
                session.rollback()
                return {
                    "day": day,
                    "ideas": json.loads(session.get(Report, day).payload),
                    "duplicate": True,
                }
            return {"day": day, "ideas": ideas, "duplicate": False}

    return app


class Submission(BaseModel):
    url: str = Field(max_length=2048)


class Transcript(BaseModel):
    text: str = Field(min_length=1, max_length=100000)
    provenance: str = Field(min_length=1, max_length=1000)
    author: str | None = Field(default=None, max_length=200)
    published_at: str | None = Field(default=None, max_length=100)


class Transition(BaseModel):
    status: str


class SourceInput(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    url: str = Field(min_length=1, max_length=2048)
    enabled: bool = True


class EvidenceInput(BaseModel):
    text: str = Field(min_length=80, max_length=12000)
    kind: Literal["description", "transcript", "user_text"]
    provenance: str = Field(min_length=1, max_length=1000)


class ConversationInput(BaseModel):
    item_id: int = Field(gt=0)
    evidence_kind: Literal["description", "transcript", "user_text"] = "description"
