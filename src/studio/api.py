import hmac
import json
import os
from datetime import datetime, timezone

from fastapi import Depends, FastAPI, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from .domain import TRANSITIONS, normalize_url, rank, report_day
from .research import Research, UnconfiguredProvider
from .storage import Audit, Item, Report, database


def create_app(database_url=None, token=None, provider=None):
    engine, sessions = database(database_url or os.getenv("DATABASE_URL", "sqlite:///./studio.db"))
    secret = token or os.getenv("STUDIO_ADMIN_TOKEN")
    provider = provider or UnconfiguredProvider()
    app = FastAPI(title="3EO Content Studio", docs_url=None, redoc_url=None, openapi_url=None)
    app.state.engine = engine
    auth = HTTPBearer(auto_error=False)

    def authorized(credentials: HTTPAuthorizationCredentials | None = Depends(auth)):
        if (
            not secret
            or not credentials
            or not hmac.compare_digest(credentials.credentials, secret)
        ):
            raise HTTPException(401, "Unauthorized")
        return "admin"

    def get_item(session, item_id):
        item = session.get(Item, item_id)
        if item is None:
            raise HTTPException(404, "Item not found")
        return item

    @app.get("/health")
    def health():
        with sessions() as session:
            session.execute(select(Report).limit(1)).all()
        return {"status": "ok", "publication_enabled": False}

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
                "next": "Supply an authorized transcript; metadata is not yet retrieved",
            }

    @app.get("/items", dependencies=[Depends(authorized)])
    def items():
        with sessions() as session:
            return [
                {
                    "id": i.id,
                    "url": i.url,
                    "author": i.author,
                    "published_at": i.published_at,
                    "status": i.status,
                    "score": i.score,
                    "research": json.loads(i.research) if i.research else None,
                }
                for i in session.scalars(select(Item).order_by(Item.id.desc()).limit(100))
            ]

    @app.put("/items/{item_id}/transcript", dependencies=[Depends(authorized)])
    def transcript(item_id: int, body: Transcript):
        with sessions() as session:
            item = get_item(session, item_id)
            if item.status not in {"DISCOVERED", "MORE_RESEARCH"}:
                raise HTTPException(409, "Transcript is locked after research")
            item.transcript, item.transcript_provenance = body.text, body.provenance
            item.author, item.published_at = body.author, body.published_at
            session.commit()
        return {"status": "stored", "metadata_source": "user supplied"}

    @app.post("/items/{item_id}/research", dependencies=[Depends(authorized)])
    def research(item_id: int, body: Research | None = None):
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
                    body or provider.analyze(item.transcript, item.url)
                )
            except RuntimeError as exc:
                raise HTTPException(503, str(exc)) from exc
            item.research = result.model_dump_json()
            item.score = rank(result.criteria)
            session.add(
                Audit(item_id=item.id, actor="admin", previous=item.status, current="RESEARCHED")
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
