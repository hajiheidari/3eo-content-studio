import json

import httpx
import pytest
from fastapi.testclient import TestClient

from studio.api import create_app
from studio.domain import WEIGHTS
from studio.integrations import IntegrationError, LlamaResearch
from studio.storage import Base
from studio.telegram import TelegramGateway


class UnavailableMetadata:
    def fetch(self, url):
        raise IntegrationError("Unavailable metadata in this test")


TEXT = "This public description introduces keyword research, search intent and a thirty-day SEO plan. It does not contain the actual video lesson."


def output():
    return dict(
        title_fa="قبل از تولید محتوا، نیت جست‌وجو را مشخص کن",
        summary_fa="این توضیحات، موضوعات کلی آموزش سئو را معرفی می‌کند.",
        angle_fa="یک نمونه فارسی از تفاوت نیت آموزشی و خرید نشان بده.",
        limitations=["فقط توضیحات منبع در دسترس است."],
        claims_to_verify=["وعدهٔ رتبه‌گیری نیازمند بررسی است."],
        criteria={k: 60 for k in WEIGHTS},
        confidence=0.9,
    )


@pytest.fixture
def setup(tmp_path):
    calls = []

    def model(request):
        calls.append(json.loads(request.content))
        return httpx.Response(
            200,
            json={
                "choices": [{"finish_reason": "stop", "message": {"content": json.dumps(output())}}]
            },
        )

    provider = LlamaResearch(httpx.Client(transport=httpx.MockTransport(model)))
    app = create_app(
        f"sqlite:///{tmp_path}/conversation.db",
        token="test",
        provider=provider,
        metadata=UnavailableMetadata(),
    )
    Base.metadata.create_all(app.state.engine)
    with TestClient(app, headers={"Authorization": "Bearer test"}) as client:
        yield client, calls
    app.state.engine.dispose()


def message(user, text):
    return {"message": {"from": {"id": user}, "chat": {"type": "private"}, "text": text}}


def test_link_then_plain_description_runs_analysis_and_approval(setup):
    client, calls = setup
    bot = TelegramGateway({123}, client)
    first = bot.handle(message(123, "https://youtu.be/abcdefghijk"))
    assert "شناسه ایده: 1" in first and first.keyboard
    assert calls == []
    result = bot.handle(message(123, TEXT))
    assert "نیت جست‌وجو" in result
    assert result.keyboard["inline_keyboard"][0][0]["callback_data"] == "approve:1"
    item = client.get("/items/1").json()
    assert item["status"] == "RESEARCHED" and item["evidence_kind"] == "description"
    assert item["research"]["confidence"] == 0.5
    assert "ویدئو یا مقالهٔ کامل بررسی نشده" in item["research"]["limitations"][-1]
    source = calls[0]["messages"][1]["content"]
    assert "description" in source and TEXT in source
    assert calls[0]["response_format"]["type"] == "json_schema"
    assert (
        bot.handle(
            {
                "callback_query": {
                    "id": "approve",
                    "from": {"id": 123},
                    "message": {"chat": {"type": "private"}},
                    "data": "approve:1",
                }
            }
        )
        == "ثبت شد."
    )
    assert client.get("/items/1").json()["status"] == "IDEA_APPROVED"


def test_standalone_text_needs_no_link_or_command(setup):
    client, calls = setup
    reply = TelegramGateway({123}, client).handle(message(123, TEXT))
    assert "پژوهش ایده" in reply and len(calls) == 1
    assert client.get("/items/1").json()["url"].startswith("urn:3eo:text:")
    assert client.get("/items/1").json()["evidence_kind"] == "user_text"


def test_title_alone_is_not_analyzed(setup):
    client, calls = setup
    reply = TelegramGateway({123}, client).handle(message(123, "راهنمای سئو با هوش مصنوعی"))
    assert "عنوان" in reply and not calls
    assert client.get("/items").json() == []


def test_two_users_keep_separate_contexts(setup):
    client, calls = setup
    bot = TelegramGateway({123, 456}, client)
    bot.handle(message(123, "https://youtu.be/abcdefghijk"))
    bot.handle(message(456, "https://youtu.be/abcdefghijl"))
    bot.handle(message(123, TEXT))
    assert client.get("/items/1").json()["status"] == "RESEARCHED"
    assert client.get("/items/2").json()["status"] == "DISCOVERED"


def test_model_failure_retains_text_for_retry(tmp_path):
    app = create_app(f"sqlite:///{tmp_path}/missing.db", token="test")
    Base.metadata.create_all(app.state.engine)
    with TestClient(app, headers={"Authorization": "Bearer test"}) as client:
        reply = TelegramGateway({123}, client).handle(message(123, TEXT))
        assert "متن ذخیره است" in reply
        assert reply.keyboard["inline_keyboard"][0][0]["callback_data"] == "analyze:1"
        assert client.get("/items/1").json()["status"] == "DISCOVERED"
    app.state.engine.dispose()


@pytest.mark.parametrize(
    "choice",
    [
        {"finish_reason": "length", "message": {"content": json.dumps(output())}},
        {"finish_reason": "stop", "message": {"content": "{}"}},
    ],
)
def test_local_output_must_finish_and_validate(choice):
    provider = LlamaResearch(
        httpx.Client(
            transport=httpx.MockTransport(lambda r: httpx.Response(200, json={"choices": [choice]}))
        )
    )
    with pytest.raises(IntegrationError):
        provider.analyze(TEXT, "source")


def test_unconfigured_model_health_is_explicit(tmp_path):
    app = create_app(f"sqlite:///{tmp_path}/health.db", token="test")
    with TestClient(app, headers={"Authorization": "Bearer test"}) as client:
        assert client.get("/research/health").json() == {
            "configured": False,
            "ready": False,
            "provider": None,
        }
    app.state.engine.dispose()


def test_request_more_research_selects_the_right_source(setup):
    client, _ = setup
    bot = TelegramGateway({123}, client)
    bot.handle(message(123, "https://youtu.be/abcdefghijk"))
    bot.handle(message(123, TEXT))
    bot.handle(message(123, "https://youtu.be/abcdefghijl"))
    bot.handle(message(123, "/research 1"))
    assert (
        client.get("/conversation", headers={"X-Studio-Actor": "telegram:123"}).json()["item_id"]
        == 1
    )


def test_evidence_type_selection_is_persistent(setup):
    client, _ = setup
    bot = TelegramGateway({123}, client)
    bot.handle(message(123, "https://youtu.be/abcdefghijk"))
    event = {
        "callback_query": {
            "id": "kind",
            "from": {"id": 123},
            "message": {"chat": {"type": "private"}},
            "data": "transcript:1",
        }
    }
    bot.handle(event)
    # A fresh gateway instance after restart uses the saved conversation type.
    TelegramGateway({123}, client).handle(message(123, TEXT))
    assert client.get("/items/1").json()["evidence_kind"] == "transcript"
