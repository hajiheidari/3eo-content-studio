import hashlib
import json
import shutil
import time
import uuid
from pathlib import Path

from fastapi import Depends, HTTPException
from sqlalchemy import select, update
from sqlalchemy.exc import IntegrityError

from .media import MediaBusy, MediaError
from .motion import generate_visuals
from .storage import Audit, Item, MediaAsset, ScriptDraft, VisualJob


def register_visuals(app, sessions, authorized, root):
    root = Path(root).resolve()

    def valid(s, script_id):
        script = s.get(ScriptDraft, script_id)
        if not script:
            raise HTTPException(404, "Script not found")
        item = s.get(Item, script.item_id)
        latest = s.scalar(
            select(ScriptDraft.id)
            .where(ScriptDraft.item_id == item.id)
            .order_by(ScriptDraft.revision.desc())
            .limit(1)
        )
        if (
            script.state != "approved"
            or latest != script_id
            or item.status
            not in {
                "SCRIPT_APPROVED",
                "AWAITING_ASSETS",
                "PREVIEW_READY",
                "FINAL_APPROVED",
                "EXPORTED",
            }
        ):
            raise HTTPException(409, "Approve the current script before generating visuals")
        return script, item

    @app.post("/scripts/{script_id}/visuals")
    def visuals(script_id: int, actor=Depends(authorized)):
        with sessions() as s:
            script, item = valid(s, script_id)
            job = s.get(VisualJob, script_id)
            if job and job.state == "ready" and job.script_hash == script.content_hash:
                return {"state": "ready", "asset_id": job.asset_id, "generated": True}
            if job and job.state == "processing" and time.time() - job.started_at < 600:
                return {"state": "processing", "asset_id": None}
            if not root.exists():
                root.mkdir(parents=True, mode=0o700)
            if shutil.disk_usage(root).free < 512 * 1024**2:
                raise HTTPException(507, "Insufficient disk space")
            if job:
                claimed = s.execute(
                    update(VisualJob)
                    .where(
                        VisualJob.script_id == script_id,
                        VisualJob.state == job.state,
                        VisualJob.started_at == job.started_at,
                    )
                    .values(state="processing", started_at=time.time())
                ).rowcount
                if not claimed:
                    raise HTTPException(409, "Visual reservation changed")
            else:
                s.add(
                    VisualJob(
                        script_id=script_id,
                        script_hash=script.content_hash,
                        state="processing",
                        started_at=time.time(),
                    )
                )
            try:
                s.commit()
            except IntegrityError:
                raise HTTPException(409, "Visual generation already reserved") from None
            content, digest = json.loads(script.content), script.content_hash
        key = uuid.uuid4().hex
        directory = root / key
        directory.mkdir(mode=0o700)
        try:
            metadata = generate_visuals(content, directory)
            path = directory / "original.bin"
            with path.open("rb") as f:
                sha = hashlib.file_digest(f, "sha256").hexdigest()
            with sessions() as s:
                script, item = valid(s, script_id)
                if script.content_hash != digest:
                    raise HTTPException(409, "Script changed during generation")
                asset = MediaAsset(
                    script_id=script_id,
                    script_hash=digest,
                    kind="screen",
                    sha256=sha,
                    storage_key=key,
                    byte_count=path.stat().st_size,
                    mime_type="video/mp4",
                    metadata_json=json.dumps(metadata),
                    state="stored",
                    actor="system:motion",
                )
                s.add(asset)
                s.flush()
                job = s.get(VisualJob, script_id)
                job.asset_id, job.state = asset.id, "ready"
                previous = item.status
                item.status = "AWAITING_ASSETS"
                s.add(
                    Audit(
                        item_id=item.id,
                        actor="system:motion",
                        previous=previous,
                        current=item.status,
                    )
                )
                s.commit()
                return {"state": "ready", "asset_id": asset.id, "generated": True}
        except (MediaError, HTTPException) as exc:
            shutil.rmtree(directory, ignore_errors=True)
            with sessions() as s:
                s.get(VisualJob, script_id).state = "failed"
                s.commit()
            if isinstance(exc, HTTPException):
                raise
            raise HTTPException(503 if isinstance(exc, MediaBusy) else 422, str(exc)) from None
