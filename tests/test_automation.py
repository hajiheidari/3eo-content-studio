import json
import subprocess

import httpx
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from studio.api import create_app
from studio.motion import generate_visuals
from studio.storage import Audit, Base, Item, ProductionTask, ScriptDraft
from studio.telegram import TelegramGateway
from studio.youtube import YouTubeCatalog


@pytest.fixture
def client(tmp_path):
    app = create_app(
        f"sqlite:///{tmp_path}/auto.db",
        token="test",
        media_root=tmp_path / "media",
        catalog=YouTubeCatalog(key=""),
    )
    Base.metadata.create_all(app.state.engine)
    with TestClient(app, headers={"Authorization": "Bearer test"}) as c:
        yield c
    app.state.engine.dispose()


def content():
    return {
        "duration_seconds": 2,
        "storyboard": [
            {
                "duration_seconds": 1,
                "on_screen_fa": "نیت جست‌وجو",
                "narration_fa": "اول نیاز مخاطب را مشخص کن.",
            },
            {
                "duration_seconds": 1,
                "on_screen_fa": "پاسخ مناسب",
                "narration_fa": "سپس پاسخ مرتبط و مفید بساز.",
            },
        ],
    }


def approved(c):
    with Session(c.app.state.engine) as s:
        s.add(
            Item(id=1, platform="text", content_id="test", url="urn:test", status="SCRIPT_APPROVED")
        )
        s.add(
            ScriptDraft(
                id=1,
                item_id=1,
                revision=1,
                state="approved",
                content=json.dumps(content()),
                snapshot="{}",
                content_hash="a" * 64,
            )
        )
        s.commit()


def test_100_links_dedup_atomic_and_block_without_evidence(client):
    entries = [{"url": f"https://youtu.be/{i:011d}"} for i in range(100)]
    first = client.post("/production/import", json={"entries": entries})
    assert first.status_code == 200
    second = client.post("/production/import", json={"entries": entries})
    assert second.json() == first.json()
    assert len(first.json()["tasks"]) == 100
    assert client.post("/production/claim").json()["state"] == "idle"
    assert (
        client.post(
            "/production/import", json={"entries": [entries[0], {"url": "https://evil.test"}]}
        ).status_code
        == 422
    )
    assert len(client.get("/production/status").json()["tasks"]) == 100
    assert client.post("/production/import", json={"entries": entries * 3}).status_code == 422


def test_evidence_unblocks_queue_and_automatic_selection_audit(client):
    response = client.post(
        "/production/import", json={"entries": [{"url": "https://youtu.be/abcdefghijk"}]}
    )
    task = response.json()["tasks"][0]
    assert task["state"] == "needs_source"
    client.put(
        f"/items/{task['item_id']}/evidence",
        json={
            "text": "source description " * 10,
            "kind": "description",
            "provenance": "user supplied",
        },
    ).raise_for_status()
    assert client.post("/production/claim").json()["id"] == task["id"]
    assert client.post("/production/claim").json()["state"] == "idle"
    with Session(client.app.state.engine) as s:
        item = s.get(Item, task["item_id"])
        item.status, item.research, item.score = "RESEARCHED", '{"confidence":0.4}', 60
        s.commit()
    client.post(f"/production/tasks/{task['id']}/select").raise_for_status()
    with Session(client.app.state.engine) as s:
        audit = s.scalar(select(Audit))
        assert audit.actor == "system:automatic_selection"
        assert s.get(Item, task["item_id"]).status == "IDEA_APPROVED"
    assert (
        client.post(
            f"/production/tasks/{task['id']}/finish",
            json={"state": "script_ready", "script_id": 999},
        ).status_code
        == 409
    )


def test_real_generated_motion_then_founder_audio_only_to_export(client, tmp_path):
    approved(client)
    response = client.post("/scripts/1/visuals")
    assert response.status_code == 200, response.text
    asset_id = response.json()["asset_id"]
    assert client.post("/scripts/1/visuals").json()["asset_id"] == asset_id
    assert client.get(f"/assets/{asset_id}/file").status_code == 200
    audio = tmp_path / "signal.wav"
    subprocess.run(
        ["ffmpeg", "-v", "error", "-f", "lavfi", "-i", "sine=duration=2.4", str(audio)],
        check=True,
        timeout=20,
    )
    voice = client.post(
        "/scripts/1/assets/voice",
        content=audio.read_bytes(),
        headers={"Content-Type": "audio/wav", "X-Rights-Confirmed": "1", "X-Founder-Voice": "1"},
    ).json()["id"]
    client.post(f"/assets/{voice}/process-audio").raise_for_status()
    preview = client.post(
        "/scripts/1/preview", json={"voice_asset_id": voice, "screen_asset_id": asset_id}
    )
    assert preview.status_code == 200, preview.text
    video = preview.json()
    assert video["metadata"]["generated_visuals"]
    assert video["metadata"]["scene_timing"] == "proportional; not speech-aligned"
    assert client.post(f"/renders/{video['id']}/export").status_code == 409
    client.post(
        f"/renders/{video['id']}/approve", json={"sha256": video["sha256"]}
    ).raise_for_status()
    client.post(f"/renders/{video['id']}/export").raise_for_status()


def test_visuals_require_current_approval_and_no_text_injection(client, tmp_path):
    approved(client)
    with Session(client.app.state.engine) as s:
        s.get(ScriptDraft, 1).state = "ready"
        s.commit()
    assert client.post("/scripts/1/visuals").status_code == 409
    from studio.media import MediaError

    with pytest.raises(MediaError):
        generate_visuals({"storyboard": [], "duration_seconds": 1000}, tmp_path)


def test_catalog_uses_real_stats_and_no_transcript_claim():
    calls = []

    def handler(request):
        calls.append(request)
        assert request.headers["X-Goog-Api-Key"] == "test-key"
        assert "test-key" not in str(request.url)
        if request.url.path.endswith("/search"):
            assert request.url.params["order"] == "viewCount"
            assert "publishedAfter" in request.url.params
            return httpx.Response(200, json={"items": [{"id": {"videoId": "abcdefghijk"}}]})
        return httpx.Response(
            200,
            json={
                "items": [
                    {
                        "id": "abcdefghijk",
                        "snippet": {
                            "title": "SEO",
                            "description": "actual public description " * 8,
                            "publishedAt": "2026-11-01T00:00:00Z",
                        },
                        "statistics": {"viewCount": "1234"},
                    }
                ]
            },
        )

    with httpx.Client(transport=httpx.MockTransport(handler)) as c:
        catalog = YouTubeCatalog("test-key", c)
        data = catalog.discover("SEO")
        assert data[0]["views"] == 1234
        assert "transcript" not in data[0]
        assert len(calls) == 2


def test_bot_bulk_and_source_commands(client):
    gateway = TelegramGateway({123}, client)

    def event(text):
        return {"message": {"from": {"id": 123}, "chat": {"type": "private"}, "text": text}}

    assert "ثبت" in gateway.handle(
        event("https://youtu.be/abcdefghijk\nhttps://youtu.be/12345678901")
    )
    assert "نیازمند متن منبع" in gateway.handle(event("/production"))
    assert "ثبت شد" in gateway.handle(event("/source 1\n" + "actual description " * 10))
    assert client.post("/production/claim").json()["item_id"] == 1
    assert "فعال نیست" in gateway.handle(event("/discover SEO"))


def test_delivery_uncertain_is_not_resent(client):
    from unittest.mock import Mock, patch

    from studio.worker import Worker

    with Session(client.app.state.engine) as s:
        s.add(Item(id=1, platform="text", content_id="test", url="urn:test"))
        s.add(ProductionTask(item_id=1, actor="telegram:123", state="script_ready", script_id=None))
        s.commit()
    telegram = Mock()
    telegram.send.side_effect = RuntimeError("timeout")
    worker = Worker(lambda: Session(client.app.state.engine), client, telegram, {123})
    worker.gateway.script_reply = Mock(return_value="draft")
    # A successful script lookup with a prepared multipart reply, followed by uncertain delivery.
    from studio.telegram import BotReply

    worker.gateway.script_reply.return_value = BotReply("draft", parts=["draft"])
    with (
        patch("studio.worker.run_next"),
        patch.object(client, "get", return_value=Mock(status_code=200, json=lambda: {})),
    ):
        worker.production()
        worker.production()
    assert telegram.send.call_count == 1
    with Session(client.app.state.engine) as s:
        assert s.scalar(select(ProductionTask)).delivery_state == "uncertain"


def test_pipeline_generates_script_but_never_approves_it(tmp_path):
    from studio.domain import WEIGHTS
    from studio.pipeline import run_next
    from studio.producer import Screenplay

    class ResearchProvider:
        def analyze(self, text, url):
            return {
                "title_fa": "نیت جست‌وجو",
                "summary_fa": "بررسی نیاز مخاطب پیش از نگارش.",
                "angle_fa": "یک پرسش مشخص را به ساختار صفحه تبدیل کن.",
                "claims_to_verify": [],
                "limitations": ["منبع محدود است."],
                "criteria": {k: 60 for k in WEIGHTS},
                "confidence": 0.4,
            }

    class ScriptProvider:
        def generate(self, snapshot, notes):
            return Screenplay.model_validate(
                {
                    "title_fa": "بررسی نیاز مخاطب",
                    "hooks_fa": [
                        "مخاطب چه می‌خواهد؟",
                        "پیش از نوشتن بررسی کن",
                        "آیا پاسخ مرتبط است؟",
                    ],
                    "shots": [
                        {
                            "duration_seconds": 8,
                            "narration_fa": "پیش از نوشتن مطلب، یک پرسش مشخص انتخاب کن و نیاز مخاطب را برای پاسخ مرتبط بررسی کن.",
                            "on_screen_fa": "نیاز مخاطب",
                            "visual_type": "motion_graphic",
                            "visual_instruction_fa": "کارت پرسش و پاسخ مرتبط نمایش بده.",
                        }
                        for _ in range(5)
                    ],
                    "fact_check_fa": ["پاسخ باید با پرسش مرتبط باشد."],
                    "cta_fa": "یک پرسش انتخاب کن.",
                    "caption_fa": "از یک پرسش مشخص برای ساختار محتوا شروع کن.",
                    "hashtags": ["#سئو"],
                }
            )

    app = create_app(
        f"sqlite:///{tmp_path}/pipeline.db",
        token="test",
        provider=ResearchProvider(),
        script_provider=ScriptProvider(),
    )
    Base.metadata.create_all(app.state.engine)
    with TestClient(app, headers={"Authorization": "Bearer test"}) as c:
        c.post(
            "/production/import",
            json={
                "entries": [
                    {"url": "https://youtu.be/abcdefghijk", "text": "authorized description " * 10}
                ]
            },
        ).raise_for_status()
        result = run_next(c)
        assert result["state"] == "script_ready"
        script = c.get(f"/scripts/{result['script_id']}").json()
        assert script["state"] == "ready"
        assert c.post(f"/scripts/{result['script_id']}/visuals").status_code == 409
        assert run_next(c) is None
        assert c.get("/items/1").json()["status"] == "SCRIPT_DRAFT"
    app.state.engine.dispose()


def test_catalog_failure_does_not_guess_or_loop(client):
    client.post(
        "/production/import", json={"entries": [{"url": "https://youtu.be/abcdefghijk"}]}
    ).raise_for_status()
    assert client.post("/production/tasks/1/retry").status_code == 409
    for _ in range(2):
        assert client.post("/production/claim").json()["state"] == "idle"
    assert not client.get("/production/status").json()["youtube_discovery_configured"]


def test_telegram_text_file_import_100_links_without_upload_context(client):
    from contextlib import contextmanager

    from studio.telegram_media import receive_media

    data = "\n".join(f"https://youtu.be/{i:011d}" for i in range(100)).encode()

    class Telegram:
        @contextmanager
        def download(self, file_id, size):
            assert size == len(data)
            yield [data]

    event = {
        "message": {
            "from": {"id": 123},
            "chat": {"type": "private"},
            "document": {"file_id": "batch", "mime_type": "text/plain", "file_size": len(data)},
        }
    }
    reply = receive_media(TelegramGateway({123}, client), client, Telegram(), event)
    assert "100" in reply
    assert len(client.get("/production/status").json()["tasks"]) == 100
    with pytest.raises(PermissionError):
        receive_media(TelegramGateway({999}, client), client, Telegram(), event)


def test_daily_discovery_is_reserved_once_and_retains_provenance(tmp_path):
    class Catalog:
        configured = True
        calls = 0

        def discover(self, query, days, limit):
            self.calls += 1
            return [
                {
                    "url": "https://youtu.be/abcdefghijk",
                    "description": "official description " * 10,
                    "title": "SEO",
                    "published_at": "2026-11-01T00:00:00Z",
                    "views": 999,
                }
            ]

    catalog = Catalog()
    app = create_app(f"sqlite:///{tmp_path}/discovery.db", token="test", catalog=catalog)
    Base.metadata.create_all(app.state.engine)
    with TestClient(app, headers={"Authorization": "Bearer test"}) as c:
        assert c.post("/youtube/refresh").json()["state"] == "complete"
        assert c.post("/youtube/refresh").json()["duplicate"]
        assert catalog.calls == 1
        task = c.post("/production/claim").json()
        assert task["state"] == "processing"
        with Session(app.state.engine) as s:
            item = s.get(Item, task["item_id"])
            assert item.evidence_kind == "description"
            assert "video not watched" in item.transcript_provenance
    app.state.engine.dispose()


def test_voice_upload_automatically_builds_video_without_founder_screen(client, tmp_path):
    from contextlib import contextmanager

    from studio.telegram_media import receive_media

    approved(client)
    gateway = TelegramGateway({123}, client)
    gateway.handle(
        {"message": {"from": {"id": 123}, "chat": {"type": "private"}, "text": "/confirmvoice 1"}}
    )
    audio = tmp_path / "signal.wav"
    subprocess.run(
        ["ffmpeg", "-v", "error", "-f", "lavfi", "-i", "sine=duration=2", str(audio)],
        check=True,
        timeout=20,
    )
    data = audio.read_bytes()

    class Telegram:
        @contextmanager
        def download(self, file_id, size):
            yield [data]

    event = {
        "message": {
            "from": {"id": 123},
            "chat": {"type": "private"},
            "voice": {"file_id": "voice", "mime_type": "audio/wav", "file_size": len(data)},
        }
    }
    reply = receive_media(gateway, client, Telegram(), event)
    assert reply.video_preview and reply.audio_preview
    assert reply.keyboard["inline_keyboard"][0][0]["callback_data"].startswith("videoapprove:")
    assert client.get("/items/1").json()["status"] == "PREVIEW_READY"
