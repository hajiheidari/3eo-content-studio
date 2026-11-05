import json
import threading
from concurrent.futures import ThreadPoolExecutor

import httpx
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from studio.api import create_app
from studio.domain import WEIGHTS
from studio.producer import LocalScriptProvider, Screenplay
from studio.script_messages import split_telegram
from studio.storage import Audit, Base, Item
from studio.telegram import TelegramGateway


def screenplay():
    return Screenplay.model_validate(
        {
            "title_fa": "قبل از نوشتن، نیت جست‌وجو را بررسی کن",
            "hooks_fa": [
                "کاربر دنبال چه پاسخی است؟",
                "قبل از نوشتن این مرحله را انجام بده.",
                "آیا نوع صفحه را درست انتخاب کرده‌ای؟",
            ],
            "shots": [
                {
                    "duration_seconds": 8,
                    "narration_fa": f"مرحله {n} یک عبارت نمونه انتخاب کن و نوع صفحه‌های نتایج جست‌وجو را با دقت یادداشت کن.",
                    "on_screen_fa": f"مرحله {n}",
                    "visual_type": "screen_recording",
                    "visual_instruction_fa": "نتایج یک عبارت فرضی را در مرورگر نمایش بده؛ داده شخصی روی صفحه نباشد.",
                }
                for n in range(1, 6)
            ],
            "fact_check_fa": ["پیش از ضبط، واقعی بودن مثال و نتایج را بررسی کن."],
            "cta_fa": "این روش را برای موضوع خودت امتحان کن.",
            "caption_fa": "این یک روش مشاهدهٔ نیت جست‌وجو است؛ به معنی تضمین رتبه گرفتن نیست.",
            "hashtags": ["#سئو", "#آموزش"],
        }
    )


class Provider:
    def __init__(self):
        self.calls = []

    def generate(self, snapshot, notes):
        self.calls.append((snapshot, notes))
        return screenplay()


@pytest.fixture
def setup(tmp_path):
    provider = Provider()
    app = create_app(f"sqlite:///{tmp_path}/producer.db", token="test", script_provider=provider)
    Base.metadata.create_all(app.state.engine)
    with Session(app.state.engine) as s:
        research = {
            "title_fa": "نیت کاربر",
            "summary_fa": "بررسی متن ارسالی",
            "angle_fa": "بررسی نتایج جست‌وجو",
            "limitations": ["فقط توضیحات در دسترس است."],
            "claims_to_verify": ["نتایج نیازمند مشاهده واقعی است."],
            "criteria": {k: 60 for k in WEIGHTS},
        }
        s.add(
            Item(
                id=1,
                platform="youtube",
                content_id="abcdefghijk",
                url="https://www.youtube.com/watch?v=abcdefghijk",
                status="IDEA_APPROVED",
                research=json.dumps(research),
                evidence_kind="description",
            )
        )
        s.commit()
    with TestClient(app, headers={"Authorization": "Bearer test"}) as client:
        yield client, provider
    app.state.engine.dispose()


def test_approved_idea_to_exact_script_approval(setup):
    client, provider = setup
    first = client.post("/items/1/scripts")
    assert first.status_code == 200
    draft = first.json()
    assert draft["state"] == "ready" and draft["revision"] == 1
    content = draft["content"]
    assert content["duration_seconds"] == 40
    assert content["voice_policy"] == "founder_recorded_only"
    assert content["source_references"] == ["https://www.youtube.com/watch?v=abcdefghijk"]
    assert content["storyboard"][0]["start_seconds"] == 0
    assert content["storyboard"][-1]["end_seconds"] == 40
    assert client.post("/items/1/scripts").json()["id"] == draft["id"]
    assert len(provider.calls) == 1
    assert (
        client.post(f"/scripts/{draft['id']}/approve", json={"content_hash": "0" * 64}).status_code
        == 409
    )
    approved = client.post(
        f"/scripts/{draft['id']}/approve", json={"content_hash": draft["content_hash"]}
    )
    assert approved.json()["status"] == "SCRIPT_APPROVED"
    assert client.post(
        f"/scripts/{draft['id']}/approve", json={"content_hash": draft["content_hash"]}
    ).json()["duplicate"]
    assert client.get("/items/1").json()["status"] == "SCRIPT_APPROVED"
    with Session(client.app.state.engine) as session:
        assert (
            len(session.scalars(select(Audit).where(Audit.current == "SCRIPT_APPROVED")).all()) == 1
        )


def test_revisions_preserve_old_content_and_reject_stale_buttons(setup):
    client, provider = setup
    first = client.post("/items/1/scripts").json()
    client.post(
        f"/scripts/{first['id']}/revise", json={"notes": "مثال را ساده‌تر و کوتاه‌تر کن."}
    ).raise_for_status()
    second = client.post("/items/1/scripts").json()
    assert second["revision"] == 2 and second["id"] != first["id"]
    assert provider.calls[-1][1] == "مثال را ساده‌تر و کوتاه‌تر کن."
    assert client.get(f"/scripts/{first['id']}").json()["content"] == first["content"]
    assert (
        client.post(
            f"/scripts/{first['id']}/approve", json={"content_hash": first["content_hash"]}
        ).status_code
        == 409
    )
    assert client.get("/items/1").json()["status"] == "SCRIPT_DRAFT"


def test_unapproved_idea_cannot_generate_or_bypass_script_approval(setup):
    client, provider = setup
    with Session(client.app.state.engine) as s:
        s.get(Item, 1).status = "REJECTED"
        s.commit()
    assert client.post("/items/1/scripts").status_code == 409
    assert not provider.calls
    assert client.post("/items/1/transition", json={"status": "SCRIPT_APPROVED"}).status_code == 422


def test_provider_failure_preserves_idea_approval(setup):
    client, provider = setup

    def fail(snapshot, notes):
        raise RuntimeError("provider unavailable")

    provider.generate = fail
    assert client.post("/items/1/scripts").status_code == 503
    assert client.get("/items/1").json()["status"] == "IDEA_APPROVED"
    assert client.get("/items/1/scripts").json()[0]["state"] == "failed"


def test_duplicate_inflight_request_does_not_start_second_generation(setup):
    client, provider = setup
    entered, release = threading.Event(), threading.Event()

    def block(snapshot, notes):
        provider.calls.append((snapshot, notes))
        entered.set()
        assert release.wait(5)
        return screenplay()

    provider.generate = block
    with ThreadPoolExecutor(max_workers=1) as pool:
        future = pool.submit(client.post, "/items/1/scripts")
        assert entered.wait(5)
        duplicate = client.post("/items/1/scripts").json()
        assert duplicate["state"] == "generating"
        release.set()
        assert future.result().status_code == 200
    assert len(provider.calls) == 1


def test_full_telegram_script_review_and_revision_notes(setup):
    client, _ = setup
    bot = TelegramGateway({123}, client)

    def event(text):
        return {"message": {"from": {"id": 123}, "chat": {"type": "private"}, "text": text}}

    result = bot.handle(event("/script 1"))
    assert result.parts and "سه هوک" in "".join(result.parts)
    assert "استوری‌بورد" in "".join(result.parts)
    callback = result.keyboard["inline_keyboard"][0][0]["callback_data"]
    assert len(callback.encode()) <= 64
    approval = bot.handle(
        {
            "callback_query": {
                "id": "review",
                "from": {"id": 123},
                "message": {"chat": {"type": "private"}},
                "data": callback,
            }
        }
    )
    assert "سناریو تأیید شد" in approval
    bot.handle(event("/revisescript 1"))
    revised = bot.handle(event("متن را ساده‌تر کن."))
    assert "نسخهٔ 2" in "".join(revised.parts)
    assert client.get("/items/1").json()["status"] == "SCRIPT_DRAFT"


def test_split_messages_never_drop_unicode():
    text = "الف😀\n" * 3000
    parts = split_telegram(text)
    assert "".join(parts) == text
    assert all(len(p.encode("utf-16-le")) <= 7000 for p in parts)


def test_local_script_provider_schema_boundary():
    def handler(request):
        body = json.loads(request.content)
        assert body["response_format"]["json_schema"]["name"] == "screenplay"
        return httpx.Response(
            200,
            json={
                "choices": [
                    {
                        "finish_reason": "stop",
                        "message": {"content": screenplay().model_dump_json()},
                    }
                ]
            },
        )

    result = LocalScriptProvider(httpx.Client(transport=httpx.MockTransport(handler))).generate(
        {"source_url": "https://example.com"}, ""
    )
    assert len(result.shots) == 5


def test_interrupted_generation_can_recover_after_lease_timeout(setup):
    from datetime import datetime, timedelta, timezone

    from studio.storage import ScriptDraft

    client, provider = setup
    with Session(client.app.state.engine) as session:
        session.get(Item, 1).status = "SCRIPT_GENERATING"
        session.add(
            ScriptDraft(
                item_id=1,
                revision=1,
                state="generating",
                snapshot=json.dumps({"previous_status": "IDEA_APPROVED"}),
                created_at=datetime.now(timezone.utc) - timedelta(minutes=20),
            )
        )
        session.commit()
    response = client.post("/items/1/scripts")
    assert response.status_code == 200 and response.json()["revision"] == 2
    assert len(provider.calls) == 1
    assert client.get("/items/1/scripts").json()[-1]["state"] == "failed"


def test_old_idea_approval_button_explains_script_progress(setup):
    client, provider = setup
    client.post("/items/1/scripts").raise_for_status()
    bot = TelegramGateway({123}, client)
    reply = bot.handle(
        {"message": {"from": {"id": 123}, "chat": {"type": "private"}, "text": "/approve 1"}}
    )
    assert "مرحلهٔ سناریو" in reply
    assert reply.keyboard["inline_keyboard"][0][0]["callback_data"] == "script:1"
    assert len(provider.calls) == 1
    assert client.get("/items/1").json()["status"] == "SCRIPT_DRAFT"
