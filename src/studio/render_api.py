import hashlib
import json
import re
import shutil
import time
import uuid
from pathlib import Path

from fastapi import Depends, HTTPException
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field
from sqlalchemy import select, update

from .media import MediaBusy, MediaError
from .rendering import render_preview
from .storage import Audit, Item, MediaAsset, RenderJob, ScriptDraft


class RenderInput(BaseModel):
    voice_asset_id: int = Field(gt=0)
    screen_asset_id: int = Field(gt=0)


class FinalApproval(BaseModel):
    sha256: str = Field(pattern=r"^[a-f0-9]{64}$")


def register_render(app, sessions, authorized, root):
    root = Path(root).resolve()
    render_root = root / "renders"

    def asset_path(asset, name):
        if not re.fullmatch(r"[a-f0-9]{32}", asset.storage_key):
            raise HTTPException(500, "Invalid storage key")
        return root / asset.storage_key / name

    def target(job):
        if not re.fullmatch(r"[a-f0-9]{32}", job.storage_key):
            raise HTTPException(500, "Invalid render key")
        return render_root / job.storage_key / "preview.mp4"

    def current(session, script_id):
        script = session.get(ScriptDraft, script_id)
        if not script:
            raise HTTPException(404, "Script not found")
        item = session.get(Item, script.item_id)
        latest = session.scalar(
            select(ScriptDraft.id)
            .where(ScriptDraft.item_id == item.id)
            .order_by(ScriptDraft.revision.desc())
            .limit(1)
        )
        if (
            script.state != "approved"
            or latest != script.id
            or item.status
            not in {
                "SCRIPT_APPROVED",
                "AWAITING_ASSETS",
                "EDITING",
                "PREVIEW_READY",
                "FINAL_APPROVED",
                "EXPORTED",
            }
        ):
            raise HTTPException(409, "Current script approval required")
        return script, item

    def view(job):
        return {
            "id": job.id,
            "script_id": job.script_id,
            "state": job.state,
            "sha256": job.sha256,
            "metadata": json.loads(job.metadata_json) if job.metadata_json else None,
        }

    @app.get("/renders/{render_id}", dependencies=[Depends(authorized)])
    def details(render_id: int):
        with sessions() as s:
            job = s.get(RenderJob, render_id)
            if not job:
                raise HTTPException(404, "Render not found")
            return view(job)

    @app.post("/scripts/{script_id}/preview")
    def preview(script_id: int, body: RenderInput, actor=Depends(authorized)):
        with sessions() as s:
            script, item = current(s, script_id)
            voice = s.get(MediaAsset, body.voice_asset_id)
            screen = s.get(MediaAsset, body.screen_asset_id)
            if (
                not voice
                or not screen
                or voice.kind != "voice"
                or screen.kind != "screen"
                or voice.state != "processed"
            ):
                raise HTTPException(
                    409, "Processed narration and verified screen recording required"
                )
            if any(
                a.script_id != script_id or a.script_hash != script.content_hash
                for a in [voice, screen]
            ):
                raise HTTPException(409, "Assets must match the exact approved script")
            existing = s.scalar(
                select(RenderJob).where(
                    RenderJob.script_id == script_id,
                    RenderJob.voice_asset_id == voice.id,
                    RenderJob.screen_asset_id == screen.id,
                )
            )
            newest = s.scalar(
                select(RenderJob)
                .where(RenderJob.script_id == script_id)
                .order_by(RenderJob.started_at.desc(), RenderJob.id.desc())
                .limit(1)
            )
            if (
                item.status == "EDITING"
                and newest
                and newest.id != (existing.id if existing else None)
                and newest.state == "processing"
            ):
                raise HTTPException(409, "Another render is in progress")
            if existing and existing.state in {"ready", "approved", "exported"}:
                coherent = (
                    (existing.state == "ready" and item.status == "PREVIEW_READY")
                    or (existing.state == "approved" and item.status == "FINAL_APPROVED")
                    or (existing.state == "exported" and item.status == "EXPORTED")
                )
                if not coherent or newest.id != existing.id:
                    previous = item.status
                    existing.state = "ready"
                    existing.started_at = time.time()
                    item.status = "PREVIEW_READY"
                    s.add(
                        Audit(item_id=item.id, actor=actor, previous=previous, current=item.status)
                    )
                    s.commit()
                return view(existing)
            if (
                existing
                and existing.state == "processing"
                and time.time() - existing.started_at < 600
            ):
                return view(existing)
            original_voice = asset_path(voice, "processed.wav")
            original_screen = asset_path(screen, "original.bin")
            if not original_voice.is_file() or not original_screen.is_file():
                raise HTTPException(409, "Media files unavailable")
            if shutil.disk_usage(root).free < 512 * 1024**2:
                raise HTTPException(507, "Insufficient disk space")
            if existing:
                claimed = s.execute(
                    update(RenderJob)
                    .where(
                        RenderJob.id == existing.id,
                        RenderJob.state == existing.state,
                        RenderJob.started_at == existing.started_at,
                    )
                    .values(state="processing", started_at=time.time())
                ).rowcount
                if not claimed:
                    raise HTTPException(409, "Render reservation changed")
                job = existing
            else:
                job = RenderJob(
                    script_id=script_id,
                    script_hash=script.content_hash,
                    voice_asset_id=voice.id,
                    screen_asset_id=screen.id,
                    state="processing",
                    storage_key=uuid.uuid4().hex,
                    started_at=time.time(),
                )
                s.add(job)
            previous = item.status
            item.status = "EDITING"
            s.add(Audit(item_id=item.id, actor=actor, previous=previous, current="EDITING"))
            s.commit()
            job_id = job.id
            planned = json.loads(script.content)["duration_seconds"]
            generated = json.loads(screen.metadata_json).get("generated", False)
            path = target(job)
            render_root.mkdir(exist_ok=True, mode=0o700)
            path.parent.mkdir(exist_ok=True, mode=0o700)
        path.unlink(missing_ok=True)
        try:
            metadata = render_preview(original_screen, original_voice, path, planned, generated=generated)
            with path.open("rb") as output:
                digest = hashlib.file_digest(output, "sha256").hexdigest()
        except MediaError as exc:
            path.unlink(missing_ok=True)
            with sessions() as s:
                s.get(RenderJob, job_id).state = "failed"
                item = s.get(Item, script.item_id)
                if item.status == "EDITING":
                    item.status = "AWAITING_ASSETS"
                    s.add(
                        Audit(item_id=item.id, actor=actor, previous="EDITING", current=item.status)
                    )
                s.commit()
            raise HTTPException(503 if isinstance(exc, MediaBusy) else 422, str(exc)) from None
        with sessions() as s:
            job = s.get(RenderJob, job_id)
            try:
                script, item = current(s, script_id)
                if script.content_hash != job.script_hash or item.status != "EDITING":
                    raise HTTPException(409, "Project changed during render")
            except HTTPException:
                job.state = "failed"
                s.commit()
                path.unlink(missing_ok=True)
                raise
            job.state = "ready"
            job.sha256 = digest
            job.metadata_json = json.dumps(metadata)
            item.status = "PREVIEW_READY"
            s.add(Audit(item_id=item.id, actor=actor, previous="EDITING", current=item.status))
            s.commit()
            return view(job)

    @app.post("/renders/{render_id}/approve")
    def approve(render_id: int, body: FinalApproval, actor=Depends(authorized)):
        with sessions() as s:
            job = s.get(RenderJob, render_id)
            if not job:
                raise HTTPException(404, "Render not found")
            script, item = current(s, job.script_id)
            if script.content_hash != job.script_hash:
                raise HTTPException(409, "Video belongs to another script content revision")
            latest = s.scalar(
                select(RenderJob.id)
                .where(RenderJob.script_id == job.script_id)
                .order_by(RenderJob.started_at.desc(), RenderJob.id.desc())
                .limit(1)
            )
            if latest != job.id:
                raise HTTPException(409, "Review the newest selected preview")
            if job.sha256 != body.sha256 or job.state not in {"ready", "approved", "exported"}:
                raise HTTPException(409, "Review this exact video")
            if not json.loads(job.metadata_json)["duration_matches_script"]:
                raise HTTPException(409, "Narration duration does not match the script")
            with target(job).open("rb") as stream:
                if hashlib.file_digest(stream, "sha256").hexdigest() != job.sha256:
                    raise HTTPException(409, "Video integrity mismatch")
            if job.state in {"approved", "exported"}:
                if item.status not in {"FINAL_APPROVED", "EXPORTED"}:
                    raise HTTPException(409, "Project assets changed; rebuild the preview")
                return {"state": job.state, "duplicate": True}
            if item.status != "PREVIEW_READY":
                raise HTTPException(409, "Project not awaiting video approval")
            job.state = "approved"
            item.status = "FINAL_APPROVED"
            s.add(
                Audit(item_id=item.id, actor=actor, previous="PREVIEW_READY", current=item.status)
            )
            s.commit()
            return view(job)

    @app.post("/renders/{render_id}/export")
    def export(render_id: int, actor=Depends(authorized)):
        with sessions() as s:
            job = s.get(RenderJob, render_id)
            if not job:
                raise HTTPException(404, "Render not found")
            script, item = current(s, job.script_id)
            if script.content_hash != job.script_hash:
                raise HTTPException(409, "Video belongs to another script content revision")
            latest = s.scalar(
                select(RenderJob.id)
                .where(RenderJob.script_id == job.script_id)
                .order_by(RenderJob.started_at.desc(), RenderJob.id.desc())
                .limit(1)
            )
            if latest != job.id:
                raise HTTPException(409, "Review the newest selected preview")
            if job.state == "exported":
                return view(job)
            if job.state != "approved" or item.status != "FINAL_APPROVED":
                raise HTTPException(409, "Explicit final-video approval required")
            with target(job).open("rb") as stream:
                if hashlib.file_digest(stream, "sha256").hexdigest() != job.sha256:
                    raise HTTPException(409, "Video integrity mismatch")
            job.state = "exported"
            item.status = "EXPORTED"
            s.add(
                Audit(item_id=item.id, actor=actor, previous="FINAL_APPROVED", current=item.status)
            )
            s.commit()
            return view(job)

    @app.get("/renders/{render_id}/file", dependencies=[Depends(authorized)])
    def file(render_id: int, variant: str = "preview"):
        if variant not in {"preview", "export"}:
            raise HTTPException(422, "Invalid video variant")
        with sessions() as s:
            job = s.get(RenderJob, render_id)
            if not job:
                raise HTTPException(404, "Render not found")
            if job.state not in {"ready", "approved", "exported"} or (
                variant == "export" and job.state != "exported"
            ):
                raise HTTPException(409, "Video is not ready or approved")
            path = target(job)
            if not path.is_file():
                raise HTTPException(404, "Video file unavailable")
            with path.open("rb") as stream:
                if hashlib.file_digest(stream, "sha256").hexdigest() != job.sha256:
                    raise HTTPException(409, "Video integrity mismatch")
            return FileResponse(
                path, media_type="video/mp4", filename=f"3eo-{variant}-{render_id}.mp4"
            )
