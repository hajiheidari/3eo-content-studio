import json
from datetime import datetime, timezone

from fastapi import Depends, HTTPException
from pydantic import BaseModel, Field, ValidationError
from sqlalchemy import select

from .producer import Screenplay, content_hash
from .storage import Audit, Item, ScriptDraft


class Approval(BaseModel):
    content_hash: str = Field(pattern=r"^[a-f0-9]{64}$")


class Revision(BaseModel):
    notes: str = Field(min_length=5, max_length=1000)


def register_producer(app, sessions, authorized, provider):
    def latest(session, item_id):
        return session.scalar(
            select(ScriptDraft)
            .where(ScriptDraft.item_id == item_id)
            .order_by(ScriptDraft.revision.desc())
            .limit(1)
        )

    def view(script):
        return {
            "id": script.id,
            "item_id": script.item_id,
            "revision": script.revision,
            "state": script.state,
            "content_hash": script.content_hash,
            "content": json.loads(script.content) if script.content else None,
        }

    @app.get("/scripts/{script_id}", dependencies=[Depends(authorized)])
    def script_detail(script_id: int):
        with sessions() as session:
            script = session.get(ScriptDraft, script_id)
            if not script:
                raise HTTPException(404, "Script not found")
            return view(script)

    @app.get("/items/{item_id}/scripts", dependencies=[Depends(authorized)])
    def script_list(item_id: int):
        with sessions() as session:
            return [
                view(s)
                for s in session.scalars(
                    select(ScriptDraft)
                    .where(ScriptDraft.item_id == item_id)
                    .order_by(ScriptDraft.revision.desc())
                )
            ]

    @app.post("/items/{item_id}/scripts")
    def generate_script(item_id: int, actor=Depends(authorized)):
        with sessions() as session:
            item = session.get(Item, item_id)
            if not item:
                raise HTTPException(404, "Item not found")
            old = latest(session, item_id)
            if old and item.status == "SCRIPT_GENERATING" and old.state == "generating":
                started = (
                    old.created_at.replace(tzinfo=timezone.utc)
                    if old.created_at.tzinfo is None
                    else old.created_at
                )
                if (datetime.now(timezone.utc) - started).total_seconds() > 900:
                    previous_state = json.loads(old.snapshot).get(
                        "previous_status",
                        "IDEA_APPROVED" if old.revision == 1 else "REVISION_REQUESTED",
                    )
                    old.state = "failed"
                    item.status = previous_state
                    session.add(
                        Audit(
                            item_id=item_id,
                            actor=actor,
                            previous="SCRIPT_GENERATING",
                            current=previous_state,
                        )
                    )
                    session.flush()
            if old and item.status in {
                "SCRIPT_GENERATING",
                "SCRIPT_DRAFT",
                "SCRIPT_APPROVED",
                "AWAITING_ASSETS",
                "EDITING",
                "PREVIEW_READY",
                "FINAL_APPROVED",
                "EXPORTED",
            }:
                return view(old)
            if item.status not in {"IDEA_APPROVED", "REVISION_REQUESTED"} or not item.research:
                raise HTTPException(409, "Approve the idea before generating a script")
            if provider is None:
                raise HTTPException(503, "Script provider is not configured")
            previous = item.status
            notes = old.revision_notes if old and previous == "REVISION_REQUESTED" else ""
            snapshot = {
                "previous_status": previous,
                "source_url": item.url,
                "evidence_kind": item.evidence_kind,
                "research": json.loads(item.research),
            }
            script = ScriptDraft(
                item_id=item_id,
                revision=(old.revision + 1 if old else 1),
                state="generating",
                snapshot=json.dumps(snapshot, ensure_ascii=False),
                revision_notes=notes,
            )
            session.add(script)
            item.status = "SCRIPT_GENERATING"
            session.add(Audit(item_id=item_id, actor=actor, previous=previous, current=item.status))
            session.commit()
            script_id = script.id
        try:
            generated = Screenplay.model_validate(provider.generate(snapshot, notes))
            content = generated.presentation()
            content["source_references"] = (
                [snapshot["source_url"]] if snapshot["source_url"].startswith("https://") else []
            )
            content["source_limitations"] = snapshot["research"]["limitations"]
        except (RuntimeError, ValidationError):
            with sessions() as session:
                script = session.get(ScriptDraft, script_id)
                item = session.get(Item, item_id)
                script.state = "failed"
                if item.status == "SCRIPT_GENERATING" and latest(session, item_id).id == script_id:
                    item.status = previous
                    session.add(
                        Audit(
                            item_id=item_id,
                            actor=actor,
                            previous="SCRIPT_GENERATING",
                            current=previous,
                        )
                    )
                session.commit()
            raise HTTPException(
                503, "Script generation failed; approved research is preserved"
            ) from None
        with sessions() as session:
            script = session.get(ScriptDraft, script_id)
            item = session.get(Item, item_id)
            if item.status != "SCRIPT_GENERATING" or latest(session, item_id).id != script_id:
                raise HTTPException(409, "Project changed while script was generated")
            script.content = json.dumps(content, ensure_ascii=False)
            script.content_hash = content_hash(content)
            script.state = "ready"
            item.status = "SCRIPT_DRAFT"
            session.add(
                Audit(
                    item_id=item_id, actor=actor, previous="SCRIPT_GENERATING", current=item.status
                )
            )
            session.commit()
            return view(script)

    @app.post("/scripts/{script_id}/approve")
    def approve_script(script_id: int, body: Approval, actor=Depends(authorized)):
        with sessions() as session:
            script = session.get(ScriptDraft, script_id)
            if not script:
                raise HTTPException(404, "Script not found")
            item = session.get(Item, script.item_id)
            if script.content_hash != body.content_hash or latest(session, item.id).id != script.id:
                raise HTTPException(409, "Review the current exact script revision")
            if script.state == "approved" and item.status in {"SCRIPT_APPROVED", "AWAITING_ASSETS"}:
                return {"status": "SCRIPT_APPROVED", "duplicate": True}
            if script.state != "ready" or item.status != "SCRIPT_DRAFT":
                raise HTTPException(409, "Script is not awaiting approval")
            script.state = "approved"
            item.status = "SCRIPT_APPROVED"
            session.add(
                Audit(item_id=item.id, actor=actor, previous="SCRIPT_DRAFT", current=item.status)
            )
            session.commit()
            return {"status": item.status, "duplicate": False}

    @app.post("/scripts/{script_id}/revise")
    def revise_script(script_id: int, body: Revision, actor=Depends(authorized)):
        with sessions() as session:
            script = session.get(ScriptDraft, script_id)
            if not script:
                raise HTTPException(404, "Script not found")
            item = session.get(Item, script.item_id)
            if latest(session, item.id).id != script.id or item.status not in {
                "SCRIPT_DRAFT",
                "SCRIPT_APPROVED",
                "AWAITING_ASSETS",
                "EDITING",
                "PREVIEW_READY",
                "FINAL_APPROVED",
                "EXPORTED",
            }:
                raise HTTPException(409, "Revision request must target the current script")
            previous = item.status
            script.revision_notes = body.notes
            script.state = "revision_requested"
            item.status = "REVISION_REQUESTED"
            session.add(Audit(item_id=item.id, actor=actor, previous=previous, current=item.status))
            session.commit()
            return {"status": item.status, "item_id": item.id}
