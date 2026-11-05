import json

import httpx
import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session
from sqlalchemy.orm.exc import StaleDataError

from studio.api import create_app
from studio.domain import WEIGHTS
from studio.integrations import IntegrationError, OllamaResearch, YouTubeMetadata
from studio.storage import Base, Item


def research_data():
    return dict(
        title_fa="آزمایش سئو",
        summary_fa="خلاصه مبتنی بر متن",
        angle_fa="اجرای آزمایش مستقل",
        claims_to_verify=["Verify source claim"],
        limitations=["Only authorized transcript reviewed"],
        criteria={k: 70 for k in WEIGHTS},
    )


def mock_client(handler):
    return httpx.Client(transport=httpx.MockTransport(handler))


def test_youtube_fixed_host_and_no_fabricated_date():
    def handler(request):
        assert request.url.host == "www.youtube.com"
        assert request.url.path == "/oembed"
        assert request.url.params["url"] == "https://www.youtube.com/watch?v=abcdefghijk"
        return httpx.Response(200, json={"title": "SEO lesson", "author_name": "Creator"})

    metadata = YouTubeMetadata(mock_client(handler)).fetch("https://youtu.be/abcdefghijk")
    assert metadata.author == "Creator"
    assert metadata.published_at is None


@pytest.mark.parametrize(
    "response",
    [
        httpx.Response(302, headers={"location": "http://127.0.0.1"}),
        httpx.Response(200, content=b"x" * 262145),
        httpx.Response(200, json={"title": "Missing author"}),
        httpx.Response(403),
        httpx.Response(200, json=[]),
    ],
)
def test_metadata_failures(response):
    calls = []

    def handler(request):
        calls.append(request)
        return response

    with pytest.raises(IntegrationError):
        YouTubeMetadata(mock_client(handler)).fetch("https://youtu.be/abcdefghijk")
    assert len(calls) == 1


def test_instagram_never_scraped():
    def handler(request):
        pytest.fail("Instagram must not fetch without permissions")

    with pytest.raises(IntegrationError):
        YouTubeMetadata(mock_client(handler)).fetch("https://instagram.com/reel/authorized")


def test_ollama_complete_pipeline(tmp_path):
    def handler(request):
        assert str(request.url) == "http://127.0.0.1:11434/api/chat"
        body = json.loads(request.content)
        assert body["stream"] is False
        assert "authorized_transcript" in body["messages"][1]["content"]
        assert body["format"]["additionalProperties"] is False
        return httpx.Response(
            200, json={"done": True, "message": {"content": json.dumps(research_data())}}
        )

    provider = OllamaResearch("preinstalled-test-model", mock_client(handler))
    app = create_app(f"sqlite:///{tmp_path}/provider.db", token="test", provider=provider)
    Base.metadata.create_all(app.state.engine)
    with TestClient(app, headers={"Authorization": "Bearer test"}) as client:
        item = client.post("/items", json={"url": "https://youtu.be/abcdefghijk"}).json()["id"]
        client.put(
            f"/items/{item}/transcript",
            json={"text": "Source material", "provenance": "Creator authorized"},
        )
        assert client.post(f"/items/{item}/research").json()["score"] == 70
        assert (
            client.post(f"/items/{item}/transition", json={"status": "IDEA_APPROVED"}).status_code
            == 200
        )
    app.state.engine.dispose()


@pytest.mark.parametrize(
    "payload",
    [
        [],
        {"done": False},
        {"done": True, "message": {"content": "bad json"}},
        {"done": True, "message": {"content": "{}"}},
    ],
)
def test_bad_model_output(payload):
    with pytest.raises(IntegrationError):
        OllamaResearch("test", mock_client(lambda _: httpx.Response(200, json=payload))).analyze(
            "text", "url"
        )


def test_optimistic_concurrency(tmp_path):
    app = create_app(f"sqlite:///{tmp_path}/race.db", token="test")
    Base.metadata.create_all(app.state.engine)
    with Session(app.state.engine) as seed:
        seed.add(
            Item(
                platform="youtube",
                content_id="abcdefghijk",
                url="https://youtu.be/abcdefghijk",
                status="RESEARCHED",
            )
        )
        seed.commit()
    with Session(app.state.engine) as first, Session(app.state.engine) as second:
        a, b = first.get(Item, 1), second.get(Item, 1)
        a.status = "REJECTED"
        first.commit()
        b.status = "IDEA_APPROVED"
        with pytest.raises(StaleDataError):
            second.commit()
    app.state.engine.dispose()


def test_manual_link_to_telegram_report_and_approval(tmp_path, monkeypatch):
    from datetime import datetime, timezone

    from sqlalchemy import select
    from sqlalchemy.orm import sessionmaker

    from studio.storage import Audit
    from studio.worker import Worker

    def model(request):
        return httpx.Response(
            200, json={"done": True, "message": {"content": json.dumps(research_data())}}
        )

    app = create_app(
        f"sqlite:///{tmp_path}/workflow.db",
        token="test",
        provider=OllamaResearch("test", mock_client(model)),
    )
    Base.metadata.create_all(app.state.engine)
    monkeypatch.setattr("studio.api.report_day", lambda _: "2026-11-03")

    class Bot:
        def __init__(self):
            self.sent = []
            self.events = []

        def send(self, user, text, keyboard=None):
            self.sent.append((user, text))
            return str(len(self.sent))

        def updates(self, offset):
            return [e for e in self.events if e["update_id"] >= offset]

    bot = Bot()

    def event(number, text):
        return {
            "update_id": number,
            "message": {"from": {"id": 123}, "chat": {"id": 123, "type": "private"}, "text": text},
        }

    bot.events = [
        event(1, "https://youtu.be/abcdefghijk"),
        event(2, "/transcript 1\nCreator permission\nAuthorized source transcript"),
        event(3, "/analyze 1"),
    ]
    with TestClient(app, headers={"Authorization": "Bearer test"}) as studio:
        worker = Worker(sessionmaker(app.state.engine, expire_on_commit=False), studio, bot, {123})
        worker.poll()
        assert studio.get("/items").json()[0]["status"] == "RESEARCHED"
        now = datetime(2026, 11, 3, 1, 30, tzinfo=timezone.utc)
        worker.reports(now)
        assert "آزمایش سئو" in bot.sent[-1][1]
        assert "https://www.youtube.com/watch?v=abcdefghijk" in bot.sent[-1][1]
        sends = len(bot.sent)
        worker.reports(now)
        assert len(bot.sent) == sends
        bot.events.append(event(4, "/approve 1"))
        worker.poll()
        assert studio.get("/items").json()[0]["status"] == "IDEA_APPROVED"
        with Session(app.state.engine) as session:
            assert [a.actor for a in session.scalars(select(Audit).order_by(Audit.id))] == [
                "telegram:123",
                "telegram:123",
            ]
    app.state.engine.dispose()
