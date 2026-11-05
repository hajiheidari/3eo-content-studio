from datetime import datetime, timezone

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from studio.api import create_app
from studio.domain import WEIGHTS, normalize_url, rank, report_day
from studio.storage import Audit, Base


@pytest.fixture
def client(tmp_path):
    from studio.integrations import IntegrationError

    class NoMetadata:
        def fetch(self, url):
            raise IntegrationError("Test metadata unavailable")

    app = create_app(f"sqlite:///{tmp_path}/test.db", token="test-only", metadata=NoMetadata())
    Base.metadata.create_all(app.state.engine)
    with TestClient(app, headers={"Authorization": "Bearer test-only"}) as client:
        yield client
    app.state.engine.dispose()


@pytest.mark.parametrize(
    "url",
    [
        "http://youtube.com/watch?v=abcdefghijk",
        "https://youtube.com.evil.test/watch?v=abcdefghijk",
        "https://127.0.0.1/",
        "https://youtube.com@evil.test/",
        "https://youtube.com:443/watch?v=abcdefghijk",
        "https://youtu.be/abc",
        "https://www.instagram.com/stories/x",
        "file:///etc/passwd",
    ],
)
def test_ssrf(url):
    with pytest.raises(ValueError):
        normalize_url(url)


def test_duplicate(client):
    first = client.post("/items", json={"url": "https://youtu.be/abcdefghijk"}).json()
    second = client.post(
        "/items", json={"url": "https://www.youtube.com/watch?v=abcdefghijk&utm_source=x"}
    ).json()
    assert first["id"] == second["id"]
    assert len(client.get("/items").json()) == 1


def test_workflow(client):
    item = client.post("/items", json={"url": "https://youtu.be/abcdefghijk"}).json()["id"]
    assert client.post(f"/items/{item}/research").status_code == 409
    assert (
        client.post(f"/items/{item}/transition", json={"status": "IDEA_APPROVED"}).status_code
        == 409
    )
    assert (
        client.put(
            f"/items/{item}/transcript",
            json={"text": "Authorized source transcript", "provenance": "Creator permission"},
        ).status_code
        == 200
    )
    assert client.post(f"/items/{item}/research").status_code == 503
    research = dict(
        title_fa="پژوهش سئو",
        summary_fa="خلاصه آموزشی",
        angle_fa="آزمایش عملی",
        claims_to_verify=["Verify claim"],
        limitations=["User supplied transcript"],
        criteria={k: 80 for k in WEIGHTS},
    )
    assert client.post(f"/items/{item}/research", json=research).json()["score"] == 80
    assert (
        client.post(f"/items/{item}/transition", json={"status": "IDEA_APPROVED"}).status_code
        == 200
    )
    assert client.post(f"/items/{item}/transition", json={"status": "EXPORTED"}).status_code == 422
    assert (
        client.post(f"/items/{item}/transition", json={"status": "IDEA_APPROVED"}).status_code
        == 409
    )
    with Session(client.app.state.engine) as session:
        assert len(session.scalars(select(Audit)).all()) == 2


def test_auth(client):
    assert client.get("/items", headers={"Authorization": "Bearer wrong"}).status_code == 401


def test_rank():
    assert rank({k: 100 for k in WEIGHTS}) == 100
    with pytest.raises(ValueError):
        rank({k: 101 for k in WEIGHTS})


def test_timezone():
    assert report_day(datetime(2026, 10, 31, 1, 29, tzinfo=timezone.utc)) is None
    assert report_day(datetime(2026, 10, 31, 1, 30, tzinfo=timezone.utc)) == "2026-10-31"


def test_reports(client, monkeypatch):
    monkeypatch.setattr("studio.api.report_day", lambda _: "2026-10-31")
    assert client.post("/reports/prepare").json()["duplicate"] is False
    assert client.post("/reports/prepare").json()["duplicate"] is True


def test_invalid_ai_response():
    from studio.research import Research

    with pytest.raises(ValueError):
        Research.model_validate({"title_fa": "Fabricated"})


def test_telegram_authorization(client):
    from studio.telegram import TelegramGateway

    bot = TelegramGateway({123}, client)
    with pytest.raises(PermissionError):
        bot.handle({"message": {"from": {"id": 9}}})
    with pytest.raises(PermissionError):
        bot.handle({"message": {"from": {"id": 123}, "chat": {"type": "group"}}})
    result = bot.handle(
        {
            "message": {
                "from": {"id": 123},
                "chat": {"type": "private"},
                "text": "https://youtu.be/abcdefghijk",
            }
        }
    )
    assert "شناسه" in result


def test_unicode_wrong_token_is_denied(client):
    # HTTP headers are bytes on the wire; token comparisons must not raise TypeError.
    import httpx

    request = httpx.Request(
        "GET", "http://testserver/items", headers={b"Authorization": "Bearer فارسی".encode()}
    )
    # Starlette decodes raw headers as Latin-1, matching ASGI.
    response = client.send(request)
    assert response.status_code == 401


def test_near_duplicates_are_advisory(client):
    ids = []
    for video in ["abcdefghijk", "abcdefghijl"]:
        item = client.post("/items", json={"url": f"https://youtu.be/{video}"}).json()["id"]
        ids.append(item)
        client.put(
            f"/items/{item}/transcript",
            json={"text": "متن آموزشی سئو برای آزمایش", "provenance": "authorized"},
        )
    result = client.get(f"/items/{ids[0]}/duplicates").json()
    assert result["advisory"] is True
    assert result["matches"][0]["id"] == ids[1]
    assert result["matches"][0]["similarity"] == 1


def test_telegram_transcript_and_provider_flow(client):
    from studio.telegram import TelegramGateway

    bot = TelegramGateway({123}, client)

    def command(text):
        return bot.handle(
            {"message": {"from": {"id": 123}, "chat": {"type": "private"}, "text": text}}
        )

    command("https://youtu.be/abcdefghijk")
    assert "ثبت شد" in command("/transcript 1\ncreator permission\nAuthorized transcript")
    assert "ساخته نشد" in command("/analyze 1")


@pytest.mark.parametrize(
    "url",
    [
        "https://youtube.com:0/watch?v=abcdefghijk",
        "https://youtube.com:/watch?v=abcdefghijk",
        "https://@youtube.com/watch?v=abcdefghijk",
        "https://youtube.com/watch?v=abcdefghijk&v=abcdefghijl",
        "https://youtube.com/shorts/extra/abcdefghijk",
        "https://you\ntube.com/watch?v=abcdefghijk",
    ],
)
def test_ambiguous_urls_are_rejected(url):
    with pytest.raises(ValueError):
        normalize_url(url)


def test_callback_authorization_and_item_details(client):
    from studio.telegram import TelegramGateway

    bot = TelegramGateway({123}, client)
    item = client.post("/items", json={"url": "https://youtu.be/abcdefghijk"}).json()["id"]

    def callback(user, action, chat="private"):
        return {
            "callback_query": {
                "id": "query-test",
                "from": {"id": user},
                "message": {"chat": {"type": chat}},
                "data": f"{action}:{item}",
            }
        }

    with pytest.raises(PermissionError):
        bot.handle(callback(999, "reject"))
    with pytest.raises(PermissionError):
        bot.handle(callback(123, "reject", "group"))
    with pytest.raises(PermissionError):
        bot.handle(callback(123, "publish"))
    assert bot.handle(callback(123, "reject")) == "ثبت شد."
    assert client.get(f"/items/{item}").json()["status"] == "REJECTED"
    with Session(client.app.state.engine) as session:
        assert session.scalar(select(Audit)).actor == "telegram:123"


def test_today_report_is_read_only(client, monkeypatch):
    monkeypatch.setattr("studio.api.report_day", lambda _: "2026-11-05")
    assert client.get("/reports/today").status_code == 404
    client.post("/reports/prepare")
    assert client.get("/reports/today").json() == {"day": "2026-11-05", "ideas": []}
