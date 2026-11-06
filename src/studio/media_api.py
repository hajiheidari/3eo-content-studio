import hashlib
import json
import re
import shutil
import time
import uuid
from pathlib import Path
from typing import Literal

import anyio
from fastapi import Depends, Header, HTTPException, Request
from fastapi.responses import FileResponse
from sqlalchemy import select, update
from sqlalchemy.exc import IntegrityError

from .media import AUDIO_LIMIT, MIMES, VIDEO_LIMIT, MediaBusy, MediaError, inspect, process_voice
from .storage import Audit, Item, MediaAsset, ScriptDraft

UPLOAD_TIMEOUT = 120


def register_media(app, sessions, authorized, root):
    root = Path(root).resolve()
    root.mkdir(mode=0o700, parents=True, exist_ok=True)

    def approved(session, script_id):
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
            not in {"SCRIPT_APPROVED", "AWAITING_ASSETS", "PREVIEW_READY", "FINAL_APPROVED"}
        ):
            raise HTTPException(409, "Approve the current exact script before media production")
        return script, item

    def view(asset):
        return {
            "id": asset.id,
            "script_id": asset.script_id,
            "kind": asset.kind,
            "sha256": asset.sha256,
            "byte_count": asset.byte_count,
            "state": asset.state,
            "metadata": json.loads(asset.metadata_json),
            "processing": json.loads(asset.processing_json) if asset.processing_json else None,
        }

    def directory(asset):
        if not re.fullmatch(r"[a-f0-9]{32}", asset.storage_key):
            raise HTTPException(500, "Invalid media storage record")
        return root / asset.storage_key

    @app.get("/scripts/{script_id}/assets", dependencies=[Depends(authorized)])
    def assets(script_id: int):
        with sessions() as session:
            return [
                view(a)
                for a in session.scalars(
                    select(MediaAsset)
                    .where(MediaAsset.script_id == script_id)
                    .order_by(MediaAsset.id)
                )
            ]

    @app.post("/scripts/{script_id}/assets/{kind}")
    async def upload(
        script_id: int,
        kind: Literal["voice", "screen"],
        request: Request,
        actor=Depends(authorized),
        rights: str = Header(default="", alias="X-Rights-Confirmed"),
        founder: str = Header(default="", alias="X-Founder-Voice"),
    ):
        if rights != "1" or (kind == "voice" and founder != "1"):
            raise HTTPException(
                422, "Rights confirmation and founder-recorded voice declaration required"
            )
        mime = request.headers.get("content-type", "").split(";")[0].strip().lower()
        if mime not in MIMES[kind]:
            raise HTTPException(415, "Unsupported media type")
        maximum = AUDIO_LIMIT if kind == "voice" else VIDEO_LIMIT
        try:
            declared = int(request.headers.get("content-length", "0"))
        except ValueError:
            raise HTTPException(400, "Invalid content length") from None
        if declared < 0 or declared > maximum:
            raise HTTPException(413, "File exceeds size limit")
        with sessions() as session:
            script, _ = approved(session, script_id)
            script_hash = script.content_hash
        if shutil.disk_usage(root).free < 512 * 1024**2 + maximum:
            raise HTTPException(507, "Insufficient disk space")
        key = uuid.uuid4().hex
        folder = root / key
        folder.mkdir(mode=0o700)
        original = folder / "original.bin"
        keep = False
        try:
            digest, count = hashlib.sha256(), 0
            with original.open("xb") as output:
                original.chmod(0o600)
                try:
                    with anyio.fail_after(UPLOAD_TIMEOUT):
                        async for block in request.stream():
                            count += len(block)
                            if count > maximum:
                                raise HTTPException(413, "File exceeds size limit")
                            digest.update(block)
                            output.write(block)
                except TimeoutError:
                    raise HTTPException(408, "Upload timed out") from None
            if not count:
                raise HTTPException(422, "Empty upload")
            # Blocking decoder work must not occupy the asynchronous HTTP event loop.
            from starlette.concurrency import run_in_threadpool

            try:
                metadata = await run_in_threadpool(inspect, original, kind)
            except MediaError as exc:
                raise HTTPException(503 if isinstance(exc, MediaBusy) else 422, str(exc)) from None
            with sessions() as session:
                script, item = approved(session, script_id)
                if script.content_hash != script_hash:
                    raise HTTPException(409, "Script changed during upload")
                existing = session.scalar(
                    select(MediaAsset).where(
                        MediaAsset.script_id == script_id,
                        MediaAsset.kind == kind,
                        MediaAsset.sha256 == digest.hexdigest(),
                    )
                )
                if existing:
                    return view(existing)
                asset = MediaAsset(
                    script_id=script_id,
                    script_hash=script_hash,
                    kind=kind,
                    storage_key=key,
                    sha256=digest.hexdigest(),
                    byte_count=count,
                    mime_type=mime,
                    metadata_json=json.dumps(metadata),
                    actor=actor,
                )
                session.add(asset)
                if item.status != "AWAITING_ASSETS":
                    previous = item.status
                    item.status = "AWAITING_ASSETS"
                    session.add(
                        Audit(
                            item_id=item.id,
                            actor=actor,
                            previous=previous,
                            current=item.status,
                        )
                    )
                try:
                    session.commit()
                except IntegrityError:
                    session.rollback()
                    existing = session.scalar(
                        select(MediaAsset).where(
                            MediaAsset.script_id == script_id,
                            MediaAsset.kind == kind,
                            MediaAsset.sha256 == digest.hexdigest(),
                        )
                    )
                    if existing:
                        return view(existing)
                    raise
                keep = True
                return view(asset)
        finally:
            if not keep:
                shutil.rmtree(folder, ignore_errors=True)

    @app.post("/assets/{asset_id}/process-audio")
    def clean_audio(asset_id: int, actor=Depends(authorized)):
        with sessions() as session:
            asset = session.get(MediaAsset, asset_id)
            if not asset:
                raise HTTPException(404, "Asset not found")
            script, _ = approved(session, asset.script_id)
            if asset.kind != "voice" or asset.script_hash != script.content_hash:
                raise HTTPException(409, "Audio must belong to the current approved script")
            if asset.state == "processed":
                return view(asset)
            if (
                asset.state == "processing"
                and asset.processing_started
                and time.time() - asset.processing_started < 600
            ):
                raise HTTPException(409, "Audio processing already running")
            original = directory(asset) / "original.bin"
            if not original.is_file():
                raise HTTPException(404, "Original recording unavailable")
            with original.open("rb") as source:
                if hashlib.file_digest(source, "sha256").hexdigest() != asset.sha256:
                    raise HTTPException(409, "Original recording integrity mismatch")
            previous = asset.state
            claimed = session.execute(
                update(MediaAsset)
                .where(
                    MediaAsset.id == asset.id,
                    MediaAsset.state == previous,
                    MediaAsset.processing_started == asset.processing_started,
                )
                .values(state="processing", processing_started=time.time())
            ).rowcount
            session.commit()
            if not claimed:
                raise HTTPException(409, "Asset changed; retry after reload")
        target = original.with_name("processed.wav")
        target.unlink(missing_ok=True)
        target.with_name("preview.mp3").unlink(missing_ok=True)
        try:
            metadata = process_voice(original, target)
        except MediaError as exc:
            target.unlink(missing_ok=True)
            target.with_name("preview.mp3").unlink(missing_ok=True)
            with sessions() as session:
                session.get(MediaAsset, asset_id).state = "failed"
                session.commit()
            raise HTTPException(503 if isinstance(exc, MediaBusy) else 422, str(exc)) from None
        with sessions() as session:
            asset = session.get(MediaAsset, asset_id)
            try:
                script, _ = approved(session, asset.script_id)
                if script.content_hash != asset.script_hash:
                    raise HTTPException(409, "Script changed during processing")
            except HTTPException:
                asset.state = "stored"
                session.commit()
                target.unlink(missing_ok=True)
                target.with_name("preview.mp3").unlink(missing_ok=True)
                raise
            with original.open("rb") as source:
                if hashlib.file_digest(source, "sha256").hexdigest() != asset.sha256:
                    asset.state = "failed"
                    session.commit()
                    target.unlink(missing_ok=True)
                    target.with_name("preview.mp3").unlink(missing_ok=True)
                    raise HTTPException(409, "Original recording changed during processing")
            asset.state = "processed"
            asset.processing_json = json.dumps(metadata)
            session.commit()
            return view(asset)

    @app.get("/assets/{asset_id}/file", dependencies=[Depends(authorized)])
    def download(asset_id: int, variant: Literal["original", "processed", "preview"] = "original"):
        with sessions() as session:
            asset = session.get(MediaAsset, asset_id)
            if not asset:
                raise HTTPException(404, "Asset not found")
            if variant != "original" and asset.state != "processed":
                raise HTTPException(409, "Processed audio not ready")
            path = (
                directory(asset)
                / {
                    "original": "original.bin",
                    "processed": "processed.wav",
                    "preview": "preview.mp3",
                }[variant]
            )
            if not path.is_file():
                raise HTTPException(404, "Stored file unavailable")
            return FileResponse(
                path,
                media_type=asset.mime_type
                if variant == "original"
                else ("audio/mpeg" if variant == "preview" else "audio/wav"),
                filename=f"3eo-asset-{asset_id}.bin"
                if variant == "original"
                else f"3eo-voice-{asset_id}.{'mp3' if variant == 'preview' else 'wav'}",
            )
