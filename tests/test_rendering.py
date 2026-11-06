import hashlib
import json
import subprocess

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from studio.api import create_app
from studio.storage import Base, Item, ScriptDraft


@pytest.fixture(scope="module")
def samples(tmp_path_factory):
    root = tmp_path_factory.mktemp("render-fixtures")
    audio = root / "signal.wav"
    video = root / "screen.mp4"
    subprocess.run(
        [
            "ffmpeg",
            "-nostdin",
            "-v",
            "error",
            "-f",
            "lavfi",
            "-i",
            "sine=frequency=440:duration=2",
            "-c:a",
            "pcm_s16le",
            str(audio),
        ],
        check=True,
        timeout=20,
    )
    subprocess.run(
        [
            "ffmpeg",
            "-nostdin",
            "-v",
            "error",
            "-f",
            "lavfi",
            "-i",
            "testsrc2=size=320x240:rate=15:duration=2",
            "-c:v",
            "libx264",
            "-threads",
            "1",
            "-pix_fmt",
            "yuv420p",
            str(video),
        ],
        check=True,
        timeout=20,
    )
    return audio.read_bytes(), video.read_bytes()


@pytest.fixture
def setup(tmp_path, samples):
    app = create_app(
        f"sqlite:///{tmp_path}/render.db", token="test", media_root=tmp_path / "private"
    )
    Base.metadata.create_all(app.state.engine)
    with Session(app.state.engine) as s:
        s.add(
            Item(id=1, platform="text", content_id="test", url="urn:test", status="SCRIPT_APPROVED")
        )
        # Deliberately tiny lower-layer timing fixture, not a generated production script.
        s.add(
            ScriptDraft(
                id=1,
                item_id=1,
                revision=1,
                state="approved",
                content=json.dumps({"duration_seconds": 2}),
                snapshot="{}",
                content_hash="a" * 64,
            )
        )
        s.commit()
    with TestClient(app, headers={"Authorization": "Bearer test"}) as c:
        a = c.post(
            "/scripts/1/assets/voice",
            content=samples[0],
            headers={
                "Content-Type": "audio/wav",
                "X-Rights-Confirmed": "1",
                "X-Founder-Voice": "1",
            },
        )
        a.raise_for_status()
        voice = a.json()["id"]
        c.post(f"/assets/{voice}/process-audio").raise_for_status()
        v = c.post(
            "/scripts/1/assets/screen",
            content=samples[1],
            headers={"Content-Type": "video/mp4", "X-Rights-Confirmed": "1"},
        )
        v.raise_for_status()
        yield c, {"voice_asset_id": voice, "screen_asset_id": v.json()["id"]}, tmp_path / "private"
    app.state.engine.dispose()


def test_genuine_video_preview_exact_approval_and_manual_export(setup):
    c, assets, _ = setup
    response = c.post("/scripts/1/preview", json=assets)
    assert response.status_code == 200, response.text
    video = response.json()
    assert video["metadata"]["width"] == 1080 and video["metadata"]["height"] == 1920
    assert video["metadata"]["video_codec"] == "h264" and video["metadata"]["audio_codec"] == "aac"
    assert video["metadata"]["publication"] is False
    body = c.get(f"/renders/{video['id']}/file").content
    assert hashlib.sha256(body).hexdigest() == video["sha256"]
    assert c.post("/scripts/1/preview", json=assets).json()["id"] == video["id"]
    assert c.post(f"/renders/{video['id']}/export").status_code == 409
    assert c.post(f"/renders/{video['id']}/approve", json={"sha256": "0" * 64}).status_code == 409
    c.post(f"/renders/{video['id']}/approve", json={"sha256": video["sha256"]}).raise_for_status()
    c.post(f"/renders/{video['id']}/export").raise_for_status()
    assert c.get("/items/1").json()["status"] == "EXPORTED"
    assert c.get(f"/renders/{video['id']}/file?variant=export").content == body
    assert (
        c.get(f"/renders/{video['id']}/file", headers={"Authorization": "Bearer wrong"}).status_code
        == 401
    )


def test_partial_recording_cannot_receive_final_approval(setup):
    c, assets, _ = setup
    with Session(c.app.state.engine) as s:
        s.get(ScriptDraft, 1).content = json.dumps({"duration_seconds": 55})
        s.commit()
    result = c.post("/scripts/1/preview", json=assets)
    assert result.status_code == 200, result.text
    video = result.json()
    assert video["metadata"]["duration_matches_script"] is False
    assert (
        c.post(f"/renders/{video['id']}/approve", json={"sha256": video["sha256"]}).status_code
        == 409
    )


def test_changed_script_and_tampered_video_are_not_exportable(setup):
    c, assets, root = setup
    result = c.post("/scripts/1/preview", json=assets)
    result.raise_for_status()
    video = result.json()
    path = next((root / "renders").glob("*/preview.mp4"))
    path.write_bytes(b"tampered")
    assert (
        c.post(f"/renders/{video['id']}/approve", json={"sha256": video["sha256"]}).status_code
        == 409
    )
    assert c.get(f"/renders/{video['id']}/file").status_code == 409
    with Session(c.app.state.engine) as s:
        s.get(ScriptDraft, 1).state = "revision_requested"
        s.get(Item, 1).status = "REVISION_REQUESTED"
        s.commit()
    assert c.post("/scripts/1/preview", json=assets).status_code == 409


def test_telegram_preview_review_and_export_use_exact_digest(setup):
    from studio.telegram import TelegramGateway

    c, assets, _ = setup
    video = c.post("/scripts/1/preview", json=assets).json()
    bot = TelegramGateway({123}, c)

    def message(text):
        return {"message": {"from": {"id": 123}, "chat": {"type": "private"}, "text": text}}

    reply = bot.handle(message(f"/videoview {video['id']}"))
    assert hashlib.sha256(reply.video_preview).hexdigest() == video["sha256"]
    data = reply.keyboard["inline_keyboard"][0][0]["callback_data"]
    assert len(data.encode()) <= 64
    approved = bot.handle(
        {
            "callback_query": {
                "id": "final",
                "from": {"id": 123},
                "message": {"chat": {"type": "private"}},
                "data": data,
            }
        }
    )
    assert "تأیید شد" in approved
    exported = bot.handle(message(f"/exportvideo {video['id']}"))
    assert exported.video_document is True and exported.video_preview == reply.video_preview


def test_old_preview_cannot_approve_a_newer_selected_render(setup, samples):
    c, assets, _ = setup
    old = c.post("/scripts/1/preview", json=assets).json()
    replacement = c.post(
        "/scripts/1/assets/screen",
        content=samples[1] + b"\0" * 8,
        headers={"Content-Type": "video/mp4", "X-Rights-Confirmed": "1"},
    )
    replacement.raise_for_status()
    current = c.post(
        "/scripts/1/preview", json={**assets, "screen_asset_id": replacement.json()["id"]}
    )
    current.raise_for_status()
    assert current.json()["id"] != old["id"]
    assert (
        c.post(f"/renders/{old['id']}/approve", json={"sha256": old["sha256"]}).status_code == 409
    )
    assert (
        c.post(
            f"/renders/{current.json()['id']}/approve", json={"sha256": current.json()["sha256"]}
        ).status_code
        == 200
    )
