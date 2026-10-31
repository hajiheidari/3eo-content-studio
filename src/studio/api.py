import hashlib
import hmac
import json
import os
import re
from datetime import datetime, timezone
from typing import Literal
from zoneinfo import ZoneInfo

from fastapi import Depends, FastAPI, HTTPException, Query, Request
from fastapi.responses import JSONResponse
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm.exc import StaleDataError

from .ai import AIInputLimit, ResearchBlocked, ResearchQuotaExceeded, configured_provider
from .domain import TRANSITIONS, normalize_url, rank, report_day
from .feeds import SOURCES, FeedClient, FeedCoolingDown, FeedUnavailable, collect
from .metadata import SourceMetadata, UnconfiguredMetadata, YouTubeMetadata, reserve_quota
from .research import Research
from .similarity import candidates, profile
from .storage import (
    Audit,
    Cursor,
    Delivery,
    FeedEntry,
    FeedState,
    Item,
    Receipt,
    Report,
    ResearchAttempt,
    Usage,
    database,
)


def serialize(item):
    metadata = json.loads(item.source_metadata) if item.source_metadata else None
    return {
        "id": item.id, "url": item.url,
        "author": item.author or (metadata or {}).get("author"),
        "published_at": item.published_at or (metadata or {}).get("published_at"),
        "status": item.status, "score": item.score, "metadata": metadata,
        "version": item.version,
        "research": json.loads(item.research) if item.research else None,
        "research_provenance": json.loads(item.research_provenance) if item.research_provenance else None,
    }


def create_app(database_url=None, token=None, provider=None, telegram_token=None,
               allowed_users=None, metadata_provider=None, metadata_daily_limit=None,
               feed_client=None):
    engine, sessions = database(database_url or os.getenv("DATABASE_URL", "sqlite:///./studio.db"))
    secret = token or os.getenv("STUDIO_ADMIN_TOKEN")
    gateway_secret = telegram_token or os.getenv("STUDIO_TELEGRAM_API_TOKEN")
    if secret and gateway_secret and hmac.compare_digest(secret, gateway_secret):
        raise ValueError("Admin and Telegram gateway tokens must be different")
    users = allowed_users if allowed_users is not None else {
        int(x) for x in os.getenv("STUDIO_TELEGRAM_USERS", "").split(",") if x.strip()
    }
    provider = provider if provider is not None else configured_provider(sessions)
    if metadata_provider is None:
        selected = os.getenv("STUDIO_METADATA_PROVIDER", "none")
        if selected not in {"none", "youtube"}:
            raise ValueError("Unsupported metadata provider")
        metadata_provider = (YouTubeMetadata(os.getenv("STUDIO_YOUTUBE_API_KEY"))
                             if selected == "youtube" else UnconfiguredMetadata())
    daily_limit = (metadata_daily_limit if metadata_daily_limit is not None
                   else int(os.getenv("STUDIO_METADATA_DAILY_LIMIT", "50")))
    if not 1 <= daily_limit <= 1000:
        raise ValueError("Metadata daily limit must be between 1 and 1000")
    app = FastAPI(title="3EO Content Studio", docs_url=None, redoc_url=None, openapi_url=None)
    app.state.engine = engine
    auth = HTTPBearer(auto_error=False)

    def authorized(request: Request,
                   credentials: HTTPAuthorizationCredentials | None = Depends(auth)):
        supplied = credentials.credentials if credentials else ""
        if secret and supplied and hmac.compare_digest(supplied, secret):
            return "admin"
        if gateway_secret and supplied and hmac.compare_digest(supplied, gateway_secret):
            user = request.headers.get("X-Studio-Telegram-User", "")
            if re.fullmatch(r"[1-9][0-9]{0,15}", user) and int(user) in users:
                return f"telegram:{int(user)}"
        raise HTTPException(401, "Unauthorized")

    @app.exception_handler(StaleDataError)
    def stale_state(request, exc):
        return JSONResponse(status_code=409, content={"detail": "Item changed; reload and retry"})

    def get_item(session, item_id):
        item = session.get(Item, item_id)
        if item is None:
            raise HTTPException(404, "Item not found")
        return item

    def mutate(request, actor, body, action):
        raw_key = request.headers.get("Idempotency-Key")
        key = None
        if raw_key:
            if not re.fullmatch(r"[A-Za-z0-9:_-]{1,100}", raw_key):
                raise HTTPException(422, "Invalid idempotency key")
            key = hashlib.sha256(f"{actor}:{raw_key}".encode()).hexdigest()
        fingerprint = hashlib.sha256(json.dumps(
            [request.method, request.url.path, body], sort_keys=True, ensure_ascii=False,
        ).encode()).hexdigest()

        def replay(session):
            receipt = session.get(Receipt, key) if key else None
            if receipt:
                if receipt.fingerprint != fingerprint:
                    raise HTTPException(409, "Idempotency key already used for another request")
                return json.loads(receipt.payload)
            return None

        with sessions() as session:
            cached = replay(session)
            if cached is not None:
                return cached
            try:
                result = action(session)
                if key:
                    session.add(Receipt(key=key, fingerprint=fingerprint,
                                        payload=json.dumps(result, ensure_ascii=False)))
                session.commit()
                return result
            except (IntegrityError, StaleDataError):
                session.rollback()
                cached = replay(session)
                if cached is not None:
                    return cached
                raise HTTPException(409, "Concurrent change; reload and retry") from None

    @app.get("/health")
    def health():
        with sessions() as session:
            session.execute(select(Report).limit(1)).all()
        return {"status": "ok", "publication_enabled": False}

    @app.get("/operations/telegram")
    def telegram_status(actor=Depends(authorized)):
        if actor != "admin":
            raise HTTPException(403, "Administrator required")
        with sessions() as session:
            cursor = session.get(Cursor, "telegram")
            deliveries = [{"key": d.key, "status": d.status, "attempts": d.attempts,
                           "message_id": d.message_id, "error": d.error}
                          for d in session.scalars(select(Delivery).order_by(
                              Delivery.available_at.desc(), Delivery.key).limit(100))]
            return {"offset": cursor.offset if cursor else 0, "deliveries": deliveries}

    @app.post("/items")
    def submit(body: Submission, request: Request, actor=Depends(authorized)):
        try:
            platform, content_id, url = normalize_url(body.url)
        except ValueError as exc:
            raise HTTPException(422, str(exc)) from exc

        def action(session):
            item = session.scalar(select(Item).where(
                Item.platform == platform, Item.content_id == content_id))
            if item is None:
                item = Item(platform=platform, content_id=content_id, url=url)
                session.add(item)
                session.flush()
            return {"id": item.id, "url": item.url, "status": item.status,
                    "next": "Supply an authorized transcript; metadata is user supplied"}
        return mutate(request, actor, body.model_dump(), action)

    @app.get("/operations/research")
    def research_status(actor=Depends(authorized)):
        if actor != "admin":
            raise HTTPException(403, "Administrator required")
        with sessions() as session:
            attempts = [{"key": a.key, "provider": a.provider, "model": a.model,
                         "status": a.status, "attempts": a.attempts, "error": a.error,
                         "updated_at": a.updated_at, "available_at": a.available_at,
                         "response_id": a.response_id, "input_tokens": a.input_tokens,
                         "output_tokens": a.output_tokens}
                        for a in session.scalars(select(ResearchAttempt).order_by(
                            ResearchAttempt.updated_at.desc()).limit(100))]
            usage = [{"key": u.key, "reserved_requests": u.count} for u in session.scalars(
                select(Usage).where(Usage.key.like("research:%")).order_by(Usage.key.desc()).limit(31))]
            return {"attempts": attempts, "usage": usage}

    @app.get("/items", dependencies=[Depends(authorized)])
    def items(status: Literal["DISCOVERED", "RESEARCHED", "SAVED", "IDEA_APPROVED",
                              "REJECTED", "MORE_RESEARCH"] | None = None,
              before_id: int | None = Query(default=None, gt=0),
              limit: int = Query(default=100, ge=1, le=100)):
        with sessions() as session:
            query = select(Item)
            if status:
                query = query.where(Item.status == status)
            if before_id is not None:
                query = query.where(Item.id < before_id)
            return [serialize(i) for i in session.scalars(query.order_by(Item.id.desc()).limit(limit))]

    @app.get("/items/{item_id}/similar", dependencies=[Depends(authorized)])
    def similar_items(item_id: int, before_id: int | None = Query(default=None, gt=0),
                      limit: int = Query(default=5, ge=1, le=10)):
        with sessions() as session:
            item = get_item(session, item_id)
            return {"item_id": item.id, "source_version": item.version,
                    **candidates(session, item, before_id, limit)}

    @app.get("/items/{item_id}", dependencies=[Depends(authorized)])
    def item_detail(item_id: int):
        with sessions() as session:
            item = get_item(session, item_id)
            return serialize(item) | {"similarity": candidates(session, item)}

    @app.put("/items/{item_id}/transcript")
    def transcript(item_id: int, body: Transcript, request: Request, actor=Depends(authorized)):
        def action(session):
            item = get_item(session, item_id)
            if item.status not in {"DISCOVERED", "MORE_RESEARCH"}:
                raise HTTPException(409, "Transcript is locked after research")
            item.transcript, item.transcript_provenance = body.text, body.provenance
            if "author" in body.model_fields_set:
                item.author = body.author
            if "published_at" in body.model_fields_set:
                item.published_at = body.published_at
            item.similarity_profile = profile(item.transcript, item.research)
            return {"status": "stored", "metadata_source": "user supplied"}
        return mutate(request, actor, body.model_dump(exclude_unset=True), action)

    @app.post("/items/{item_id}/metadata")
    def fetch_metadata(item_id: int, request: Request, actor=Depends(authorized)):
        def action(session):
            item = get_item(session, item_id)
            now = datetime.now(timezone.utc)
            cached = json.loads(item.source_metadata) if item.source_metadata else None
            if cached and 0 <= now.timestamp() - cached["fetched_at"] < 3600:
                return {"metadata": cached, "cached": True}
            if item.status not in {"DISCOVERED", "MORE_RESEARCH"}:
                raise HTTPException(409, "Metadata is locked after research")
            if item.platform != "youtube":
                raise HTTPException(422, "Instagram metadata requires manual entry")
            if isinstance(metadata_provider, UnconfiguredMetadata):
                raise HTTPException(503, "Metadata provider disabled; supply metadata manually")
            day = now.astimezone(ZoneInfo("Asia/Tehran")).date().isoformat()
            if not reserve_quota(sessions, day, daily_limit):
                raise HTTPException(429, "Daily metadata request limit reached")
            try:
                result = SourceMetadata.model_validate(metadata_provider.fetch(item.url))
                if result.content_id != item.content_id:
                    raise ValueError("Metadata source mismatch")
            except ValueError:
                raise HTTPException(502, "Metadata provider returned invalid output") from None
            except (RuntimeError, TimeoutError, ConnectionError):
                raise HTTPException(503, "Metadata service unavailable; use manual entry") from None
            data = result.model_dump(mode="json") | {"fetched_at": now.timestamp()}
            item.source_metadata = json.dumps(data, ensure_ascii=False)
            return {"metadata": data, "cached": False}
        return mutate(request, actor, None, action)

    @app.post("/items/{item_id}/research")
    def research(item_id: int, request: Request, body: Research | None = None,
                 actor=Depends(authorized)):
        def action(session):
            item = get_item(session, item_id)
            if not item.transcript:
                raise HTTPException(409, "Authorized transcript required; content has not been analyzed")
            if item.status not in {"DISCOVERED", "MORE_RESEARCH"}:
                raise HTTPException(409, "Research not allowed in this state")
            try:
                result = Research.model_validate(body or provider.analyze(item.transcript, item.url))
            except AIInputLimit:
                raise HTTPException(422, "Transcript exceeds the configured AI byte limit") from None
            except ResearchQuotaExceeded:
                raise HTTPException(429, "Daily research request limit reached") from None
            except ResearchBlocked:
                raise HTTPException(409, "Previous research attempt requires review or cooldown") from None
            except ValueError:
                raise HTTPException(502, "Research provider returned invalid output") from None
            except (RuntimeError, TimeoutError, ConnectionError):
                # Provider messages can contain credentials or source text; never return them.
                raise HTTPException(503, "Research provider unavailable; submit reviewed research") from None
            item.research = result.model_dump_json()
            item.similarity_profile = profile(item.transcript, item.research)
            if body is not None:
                origin = {"kind": "reviewed_manual", "basis": "authorized_transcript"}
            elif hasattr(provider, "provenance"):
                origin = provider.provenance(item.transcript, item.url)
            else:
                origin = {"kind": "provider_draft", "basis": "authorized_transcript",
                          "independent_fact_check": False}
            item.research_provenance = json.dumps(origin)
            item.score = rank(result.criteria)
            session.add(Audit(item_id=item.id, actor=actor,
                              previous=item.status, current="RESEARCHED"))
            item.status = "RESEARCHED"
            return {"status": item.status, "score": item.score}
        return mutate(request, actor, body.model_dump() if body else None, action)

    @app.post("/items/{item_id}/transition")
    def transition(item_id: int, body: Transition, request: Request, actor=Depends(authorized)):
        if body.status not in {"IDEA_APPROVED", "REJECTED", "SAVED", "MORE_RESEARCH"}:
            raise HTTPException(422, "Unsupported M1 action")

        def action(session):
            item = get_item(session, item_id)
            previous = item.status
            if body.expected_version is not None and body.expected_version != item.version:
                raise HTTPException(409, "Item changed since this decision was shown")
            if body.status not in TRANSITIONS.get(previous, set()):
                raise HTTPException(409, "Invalid approval transition")
            item.status = body.status
            session.add(Audit(item_id=item.id, actor=actor, previous=previous, current=body.status))
            return {"status": body.status}
        return mutate(request, actor, body.model_dump(), action)

    @app.post("/reports/prepare", dependencies=[Depends(authorized)])
    def prepare_report():
        day = report_day(datetime.now(timezone.utc))
        if not day:
            raise HTTPException(409, "Report is not due before 05:00 Asia/Tehran")
        with sessions() as session:
            existing = session.get(Report, day)
            if existing:
                return {"day": day, "ideas": json.loads(existing.payload), "duplicate": True}
            ideas = [serialize(i) | {"similarity": candidates(session, i)} for i in session.scalars(
                select(Item).where(Item.status == "RESEARCHED")
                .order_by(Item.score.desc(), Item.id).limit(5))]
            session.add(Report(day=day, payload=json.dumps(ideas, ensure_ascii=False)))
            try:
                session.commit()
            except IntegrityError:
                session.rollback()
                return {"day": day, "ideas": json.loads(session.get(Report, day).payload),
                        "duplicate": True}
            return {"day": day, "ideas": ideas, "duplicate": False}

    def admin(actor):
        if actor != "admin":
            raise HTTPException(403, "Administrator required")

    @app.get("/discovery/sources")
    def feed_sources(actor=Depends(authorized)):
        admin(actor)
        with sessions() as session:
            result = []
            for key, definition in SOURCES.items():
                state = session.get(FeedState, key)
                result.append({"id": key, **definition,
                               "status": state.status if state else "never_collected",
                               "checked_at": state.checked_at if state else None,
                               "success_at": state.success_at if state else None,
                               "next_at": state.next_at if state else 0,
                               "error": state.error if state else None})
            return {"enabled": os.getenv("STUDIO_FEEDS_ENABLED", "0") == "1",
                    "sources": result, "automatic_research": False}

    @app.post("/discovery/sources/{source}/collect")
    def collect_feed(source: str, actor=Depends(authorized)):
        admin(actor)
        if source not in SOURCES:
            raise HTTPException(404, "Unknown feed source")
        if os.getenv("STUDIO_FEEDS_ENABLED", "0") != "1":
            raise HTTPException(409, "Feed collection disabled")
        try:
            return collect(sessions, source, feed_client or FeedClient())
        except FeedCoolingDown as exc:
            raise HTTPException(409, str(exc)) from None
        except FeedUnavailable:
            raise HTTPException(502, "Feed unavailable or invalid; retry after cooldown") from None

    @app.get("/discovery/entries")
    def feed_entries(source: str | None = None, after_key: str | None = Query(None, pattern=r"^[a-f0-9]{64}$"),
                     limit: int = Query(20, ge=1, le=100), actor=Depends(authorized)):
        admin(actor)
        if source is not None and source not in SOURCES:
            raise HTTPException(404, "Unknown feed source")
        with sessions() as session:
            query = select(FeedEntry)
            if source:
                query = query.where(FeedEntry.source == source)
            if after_key:
                query = query.where(FeedEntry.key > after_key)
            rows = list(session.scalars(query.order_by(FeedEntry.key).limit(limit + 1)))
            more = len(rows) > limit
            rows = rows[:limit]
            return {"entries": [{"key": e.key, "source": e.source, "url": e.url,
                                 "title": e.title, "published_at": e.published_at,
                                 "discovered_at": e.discovered_at, "verified": False,
                                 "provenance": "publisher_feed_metadata_only"} for e in rows],
                    "next_after_key": rows[-1].key if more else None,
                    "order": "stable_key", "research_started": False}

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
    expected_version: int | None = Field(default=None, gt=0)
