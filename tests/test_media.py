import hashlib
import subprocess

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from studio.api import create_app
from studio.storage import Base, Item, ScriptDraft


@pytest.fixture(scope="module")
def samples(tmp_path_factory):
    root = tmp_path_factory.mktemp("media-samples")
    voice = root / "voice.wav"
    screen = root / "screen.mp4"
    silent = root / "silent.wav"
    for args in [
        ["-f", "lavfi", "-i", "sine=frequency=440:duration=2", "-c:a", "pcm_s16le", str(voice)],
        [
            "-f",
            "lavfi",
            "-i",
            "color=c=blue:s=320x240:d=2:r=15",
            "-c:v",
            "libx264",
            "-pix_fmt",
            "yuv420p",
            str(screen),
        ],
        [
            "-f",
            "lavfi",
            "-i",
            "anullsrc=r=48000:cl=mono",
            "-t",
            "2",
            "-c:a",
            "pcm_s16le",
            str(silent),
        ],
    ]:
        subprocess.run(
            ["ffmpeg", "-nostdin", "-v", "error", "-threads", "1"] + args, check=True, timeout=20
        )
    return voice.read_bytes(), screen.read_bytes(), silent.read_bytes()


@pytest.fixture
def setup(tmp_path):
    app = create_app(
        f"sqlite:///{tmp_path}/media.db", token="test", media_root=tmp_path / "private"
    )
    Base.metadata.create_all(app.state.engine)
    with Session(app.state.engine) as s:
        s.add(
            Item(id=1, platform="text", content_id="text", url="urn:test", status="SCRIPT_APPROVED")
        )
        s.add(
            ScriptDraft(
                id=1,
                item_id=1,
                revision=1,
                state="approved",
                snapshot="{}",
                content="{}",
                content_hash="a" * 64,
            )
        )
        s.commit()
    with TestClient(app, headers={"Authorization": "Bearer test"}) as c:
        yield c, tmp_path / "private"
    app.state.engine.dispose()


def upload(client, data, kind="voice", **headers):
    return client.post(
        f"/scripts/1/assets/{kind}",
        content=data,
        headers={
            "Content-Type": "audio/wav" if kind == "voice" else "video/mp4",
            "X-Rights-Confirmed": "1",
            "X-Founder-Voice": "1",
            **headers,
        },
    )


def test_original_preserved_and_voice_processed_privately(setup, samples):
    c, root = setup
    original = samples[0]
    response = upload(c, original)
    assert response.status_code == 200, response.text
    asset = response.json()
    assert asset["sha256"] == hashlib.sha256(original).hexdigest()
    assert c.get("/items/1").json()["status"] == "AWAITING_ASSETS"
    processed = c.post(f"/assets/{asset['id']}/process-audio")
    assert processed.status_code == 200, processed.text
    assert processed.json()["processing"]["voice_synthesis"] is False
    assert processed.json()["processing"]["original_preserved"] is True
    assert c.get(f"/assets/{asset['id']}/file").content == original
    audio = c.get(f"/assets/{asset['id']}/file?variant=processed")
    assert audio.status_code == 200 and audio.content.startswith(b"RIFF")
    assert (
        c.get(f"/assets/{asset['id']}/file", headers={"Authorization": "Bearer wrong"}).status_code
        == 401
    )
    assert len(list(root.iterdir())) == 1
    assert c.post(f"/assets/{asset['id']}/process-audio").json()["state"] == "processed"


def test_duplicate_upload_reuses_asset(setup, samples):
    c, root = setup
    a = upload(c, samples[0]).json()
    b = upload(c, samples[0]).json()
    assert a["id"] == b["id"]
    assert len(list(root.iterdir())) == 1


def test_screen_metadata_verified(setup, samples):
    c, _ = setup
    r = upload(c, samples[1], "screen")
    assert r.status_code == 200, r.text
    assert r.json()["metadata"]["width"] == 320
    assert r.json()["metadata"]["height"] == 240


def test_rejects_spoofed_type_and_cleans_temp_files(setup, samples):
    c, root = setup
    assert upload(c, b"not media").status_code == 422
    assert upload(c, samples[1]).status_code == 422
    assert upload(c, samples[0], **{"Content-Type": "text/html"}).status_code == 415
    assert list(root.iterdir()) == []


def test_requires_rights_and_real_script_approval(setup, samples):
    c, root = setup
    assert upload(c, samples[0], **{"X-Founder-Voice": "0"}).status_code == 422
    assert upload(c, samples[0], **{"X-Rights-Confirmed": "0"}).status_code == 422
    with Session(c.app.state.engine) as s:
        s.get(ScriptDraft, 1).state = "ready"
        s.get(Item, 1).status = "SCRIPT_DRAFT"
        s.commit()
    assert upload(c, samples[0]).status_code == 409
    assert list(root.iterdir()) == []


def test_silent_audio_requests_new_recording(setup, samples):
    c, _ = setup
    r = upload(c, samples[2])
    assert r.status_code == 200, r.text
    processed = c.post(f"/assets/{r.json()['id']}/process-audio")
    assert processed.status_code == 422
    assert c.get(f"/assets/{r.json()['id']}/file").content == samples[2]


def test_script_revision_blocks_old_audio_processing(setup, samples):
    c, _ = setup
    asset = upload(c, samples[0]).json()
    with Session(c.app.state.engine) as s:
        s.get(ScriptDraft, 1).state = "revision_requested"
        s.get(Item, 1).status = "REVISION_REQUESTED"
        s.commit()
    assert c.post(f"/assets/{asset['id']}/process-audio").status_code == 409


def test_streamed_body_limit_is_enforced_without_content_length(setup, monkeypatch):
    c, root = setup
    monkeypatch.setattr("studio.media_api.AUDIO_LIMIT", 16)

    def body():
        yield b"x" * 10
        yield b"x" * 10

    response = c.post(
        "/scripts/1/assets/voice",
        content=body(),
        headers={"Content-Type": "audio/wav", "X-Rights-Confirmed": "1", "X-Founder-Voice": "1"},
    )
    assert response.status_code == 413
    assert list(root.iterdir()) == []


def test_telegram_voice_rights_selection_to_real_processing(setup, samples):
    from contextlib import contextmanager

    from studio.telegram import TelegramGateway
    from studio.telegram_media import receive_media

    c, _ = setup
    gateway = TelegramGateway({123}, c)

    def message(text):
        return {"message": {"from": {"id": 123}, "chat": {"type": "private"}, "text": text}}

    prompt = gateway.handle(message("/voiceupload 1"))
    assert "صدای واقعی" in prompt and prompt.keyboard
    before = c.get("/conversation", headers={"X-Studio-Actor": "telegram:123"})
    assert before.status_code == 404
    gateway.handle(message("/confirmvoice 1"))
    downloaded = []

    class Telegram:
        @contextmanager
        def download(self, file_id, expected):
            downloaded.append(file_id)
            yield iter([samples[0]])

    event = {
        "message": {
            "from": {"id": 123},
            "chat": {"type": "private"},
            "voice": {
                "file_id": "approved-file",
                "file_size": len(samples[0]),
                "mime_type": "audio/wav",
            },
        }
    }
    reply = receive_media(gateway, c, Telegram(), event)
    assert "اصل صدا" in reply and reply.audio_preview
    assert downloaded == ["approved-file"]
    assert c.get("/scripts/1/assets").json()[0]["state"] == "processed"


def test_telegram_does_not_download_before_approved_context(setup, samples):
    from studio.telegram import TelegramGateway
    from studio.telegram_media import receive_media

    c, _ = setup

    class Telegram:
        def download(self, *args):
            pytest.fail("No download permitted without a selected approved source")

    event = {
        "message": {
            "from": {"id": 123},
            "chat": {"type": "private"},
            "audio": {"file_id": "unused", "file_size": 10, "mime_type": "audio/wav"},
        }
    }
    assert "دانلود نشد" in receive_media(TelegramGateway({123}, c), c, Telegram(), event)


def test_processed_preview_is_private_and_mp3(setup, samples):
    c, _ = setup
    asset = upload(c, samples[0]).json()
    c.post(f"/assets/{asset['id']}/process-audio").raise_for_status()
    preview = c.get(f"/assets/{asset['id']}/file?variant=preview")
    assert preview.status_code == 200 and preview.headers["content-type"].startswith("audio/mpeg")
    assert (
        c.get(
            f"/assets/{asset['id']}/file?variant=preview", headers={"Authorization": "Bearer bad"}
        ).status_code
        == 401
    )


def test_decoder_child_does_not_receive_application_credentials(monkeypatch):
    from studio.media import execute

    monkeypatch.setenv("STUDIO_ADMIN_TOKEN", "test-secret-never-for-decoder")
    result = execute(["python3", "-c", "import os; print('STUDIO_ADMIN_TOKEN' in os.environ)"])
    assert result.stdout.strip() == b"False"


def test_asset_decoder_busy_returns_retryable_status(setup, monkeypatch, samples):
    from studio.media import MediaBusy

    c, root = setup

    def busy(*args):
        raise MediaBusy("Busy")

    monkeypatch.setattr("studio.media_api.inspect", busy)
    result = upload(c, samples[0])
    assert result.status_code == 503
    assert list(root.iterdir()) == []


def test_upload_callback_selection_uses_same_private_actor(setup):
    from studio.telegram import TelegramGateway

    c, _ = setup
    bot = TelegramGateway({123}, c)

    def callback(action):
        return {
            "callback_query": {
                "id": "upload",
                "from": {"id": 123},
                "message": {"chat": {"type": "private"}},
                "data": f"{action}:1",
            }
        }

    assert bot.handle(callback("voiceupload")).keyboard
    assert "اکنون صدای خودت" in bot.handle(callback("confirmvoice"))
    context = c.get("/conversation", headers={"X-Studio-Actor": "telegram:123"}).json()
    assert context["upload_script_id"] == 1 and context["upload_kind"] == "voice"


def test_slow_upload_deadline_removes_partial_file(setup, monkeypatch):
    import asyncio

    import httpx

    c, root = setup
    monkeypatch.setattr("studio.media_api.UPLOAD_TIMEOUT", 0.01)

    async def run():
        async def body():
            yield b"partial"
            await asyncio.sleep(0.1)
            yield b"late"

        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=c.app), base_url="http://test"
        ) as client:
            return await client.post(
                "/scripts/1/assets/voice",
                content=body(),
                headers={
                    "Authorization": "Bearer test",
                    "Content-Type": "audio/wav",
                    "X-Rights-Confirmed": "1",
                    "X-Founder-Voice": "1",
                },
            )

    result = asyncio.run(run())
    assert result.status_code == 408
    assert list(root.iterdir()) == []


def test_original_integrity_is_checked_before_processing(setup, samples):
    c, root = setup
    asset = upload(c, samples[0]).json()
    next(root.glob("*/original.bin")).write_bytes(samples[2])
    assert c.post(f"/assets/{asset['id']}/process-audio").status_code == 409
    assert not list(root.glob("*/processed.wav"))
