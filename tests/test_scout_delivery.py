import json
from datetime import datetime, timezone

import httpx
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.orm.exc import StaleDataError

from studio.api import create_app
from studio.domain import WEIGHTS
from studio.storage import Audit, Base, Cursor, Delivery, Item, Receipt
from studio.telegram import TelegramGateway
from studio.worker import TelegramFailure, TelegramHTTP, Worker, chunks

RESEARCH = dict(
    title_fa="پژوهش سئو", summary_fa="خلاصه آموزشی", angle_fa="آزمایش عملی",
    why_it_matters_fa="کاهش خطای تحلیل", recommended_format_fa="نمایش صفحه",
    brand_connection_fa="آزمایش ابزارهای سئو", claims_to_verify=["بررسی مستندات"],
    limitations=["متن را کاربر ارائه کرده است"], criteria={k: 80 for k in WEIGHTS},
)
NOW = datetime(2026, 10, 31, 1, 30, tzinfo=timezone.utc)


def submit(client):
    item = client.post("/items", json={"url": "https://youtu.be/abcdefghijk"}).json()["id"]
    client.put(f"/items/{item}/transcript", json={"text": "authorized", "provenance": "permission"})
    return item


@pytest.mark.parametrize("failure,status", [
    ({"title_fa": "invalid"}, 502), (RuntimeError("secret-token"), 503),
    (TimeoutError("secret-token"), 503), (ConnectionError("secret-token"), 503),
])
def test_provider_failure_is_safe_and_transactional(tmp_path, failure, status):
    class Provider:
        def analyze(self, *args):
            if isinstance(failure, Exception):
                raise failure
            return failure
    app = create_app(f"sqlite:///{tmp_path}/db", token="test", provider=Provider())
    Base.metadata.create_all(app.state.engine)
    with TestClient(app, headers={"Authorization": "Bearer test"}) as client:
        item = submit(client)
        response = client.post(f"/items/{item}/research")
        assert response.status_code == status
        assert "secret-token" not in response.text
        stored = client.get(f"/items/{item}").json()
        assert stored["status"] == "DISCOVERED" and stored["research"] is None
    with Session(app.state.engine) as session:
        assert list(session.scalars(select(Audit))) == []
    app.state.engine.dispose()


def test_invalid_manual_research_is_422(client):
    item = submit(client)
    assert client.post(f"/items/{item}/research", json={"title_fa": "invalid"}).status_code == 422


def test_identity_requires_dedicated_token_and_allowlist(client):
    for token, user in [("wrong", "123"), ("gateway-test", "999"), ("gateway-test", "")]:
        assert client.get("/items", headers={"Authorization": f"Bearer {token}",
                                             "X-Studio-Telegram-User": user}).status_code == 401
    assert client.get("/items", headers={"Authorization": "Bearer gateway-test",
                                         "X-Studio-Telegram-User": "123"}).status_code == 200
    with pytest.raises(ValueError):
        create_app(token="same", telegram_token="same")


def test_full_manual_telegram_flow_and_replay(app):
    with TestClient(app, headers={"Authorization": "Bearer gateway-test"}) as client:
        gateway = TelegramGateway({123}, client)
        def handle(number, text):
            return gateway.handle({"update_id": number, "message": {
                "from": {"id": 123}, "chat": {"type": "private", "id": 123}, "text": text}})
        assert "شناسه" in handle(1, "https://youtu.be/abcdefghijk")
        assert handle(2, "/transcript 1\nCreator permission\nAuthorized transcript") == "ثبت شد."
        review = "/review 1\n" + json.dumps(RESEARCH, ensure_ascii=False)
        assert handle(3, review) == "ثبت شد."
        assert handle(3, review) == "ثبت شد."
        detail = handle(4, "/idea 1")
        assert "کاهش خطای تحلیل" in detail and "محدودیت‌ها" in detail
        assert handle(5, "/approve 1") == "ثبت شد."
        assert handle(5, "/approve 1") == "ثبت شد."
        assert "ثبت نشد" in handle(5, "/reject 1")
    with Session(app.state.engine) as session:
        audit = list(session.scalars(select(Audit)))
        assert len(audit) == 2 and all(a.actor == "telegram:123" for a in audit)
        assert len(list(session.scalars(select(Receipt)))) == 4


def test_stale_writes_cannot_override_approval(client, app):
    item = submit(client)
    client.post(f"/items/{item}/research", json=RESEARCH)
    with Session(app.state.engine) as first, Session(app.state.engine) as second:
        approved, rejected = first.get(Item, item), second.get(Item, item)
        approved.status = "IDEA_APPROVED"
        first.commit()
        rejected.status = "REJECTED"
        with pytest.raises(StaleDataError):
            second.commit()
        second.rollback()
    assert client.get(f"/items/{item}").json()["status"] == "IDEA_APPROVED"


class FakeTelegram:
    def __init__(self):
        self.incoming, self.sent, self.failure = [], [], None
        self.offsets = []
        self.markups, self.answers = [], []

    def updates(self, offset):
        self.offsets.append(offset)
        return [u for u in self.incoming if u["update_id"] >= offset]

    def send(self, chat_id, text, reply_markup=None):
        if self.failure:
            raise self.failure
        self.sent.append((chat_id, text))
        self.markups.append(reply_markup)
        return len(self.sent)

    def answer(self, callback_id):
        self.answers.append(callback_id)


def worker(app, client, telegram, clock=None):
    return Worker(sessionmaker(app.state.engine), client, telegram, {123}, {123},
                  clock=clock or (lambda: NOW))


def test_schedule_restart_and_daily_dedup(app, client, monkeypatch):
    item = submit(client)
    client.post(f"/items/{item}/research", json=RESEARCH)
    monkeypatch.setattr("studio.api.report_day", lambda _: "2026-10-31")
    telegram = FakeTelegram()
    first = worker(app, client, telegram)
    first.tick()
    assert len(telegram.sent) == 2
    assert "پژوهش سئو" in telegram.sent[1][1]
    worker(app, client, telegram).tick()
    assert len(telegram.sent) == 2
    with Session(app.state.engine) as session:
        assert {d.status for d in session.scalars(select(Delivery))} == {"sent"}


def test_no_schedule_before_tehran_deadline(app, client):
    telegram = FakeTelegram()
    worker(app, client, telegram, clock=lambda: NOW.replace(minute=29)).tick()
    assert telegram.sent == []
    with Session(app.state.engine) as session:
        assert list(session.scalars(select(Delivery))) == []


def test_poll_replay_after_api_commit_before_cursor(app, client):
    telegram = FakeTelegram()
    incoming = {"update_id": 42, "message": {"from": {"id": 123},
                "chat": {"type": "private", "id": 123}, "text": "https://youtu.be/abcdefghijk"}}
    telegram.incoming = [incoming]
    first = worker(app, client, telegram)
    first.gateway.handle(incoming)  # Crash window: API committed, offset not persisted.
    worker(app, client, telegram).poll()
    worker(app, client, telegram).poll()
    assert len(client.get("/items").json()) == 1
    with Session(app.state.engine) as session:
        assert session.get(Cursor, "telegram").offset == 43
        assert len(list(session.scalars(select(Delivery)))) == 1
    assert telegram.offsets == [0, 43]


def test_unauthorized_updates_are_acknowledged_without_reply(app, client):
    telegram = FakeTelegram()
    telegram.incoming = [{"update_id": 9, "message": {"from": {"id": 999}}}]
    worker(app, client, telegram).poll()
    with Session(app.state.engine) as session:
        assert session.get(Cursor, "telegram").offset == 10
        assert list(session.scalars(select(Delivery))) == []


@pytest.mark.parametrize("kind,expected", [("retry", "retry"), ("uncertain", "uncertain"),
                                           ("failed", "failed")])
def test_delivery_failure_state_and_no_blind_resend(app, client, kind, expected):
    telegram = FakeTelegram()
    telegram.failure = TelegramFailure(kind, 60)
    runner = worker(app, client, telegram)
    with Session(app.state.engine) as session:
        session.add(Delivery(key="sample", chat_id=123, text="آزمون"))
        session.commit()
    runner.deliver(NOW)
    with Session(app.state.engine) as session:
        assert session.get(Delivery, "sample").status == expected
    telegram.failure = None
    runner.deliver(NOW)
    assert telegram.sent == []
    runner.deliver(NOW.replace(minute=32))
    assert len(telegram.sent) == (1 if kind == "retry" else 0)


def test_crash_during_send_becomes_uncertain(app, client):
    with Session(app.state.engine) as session:
        session.add(Delivery(key="crashed", chat_id=123, text="آزمون", status="sending",
                             available_at=NOW.timestamp() - 1))
        session.commit()
    telegram = FakeTelegram()
    worker(app, client, telegram).deliver(NOW)
    assert telegram.sent == []
    with Session(app.state.engine) as session:
        assert session.get(Delivery, "crashed").status == "uncertain"


def test_second_worker_cannot_take_unexpired_lease(app, client):
    one, two = worker(app, client, FakeTelegram()), worker(app, client, FakeTelegram())
    assert one.lease(NOW.timestamp())
    assert not two.lease(NOW.timestamp() + 1)
    assert two.lease(NOW.timestamp() + 601)
    one.release()
    assert not one.lease(NOW.timestamp() + 602)
    two.release()
    assert one.lease(NOW.timestamp() + 602)


@pytest.mark.parametrize("status,body,kind", [
    (429, {"ok": False, "error_code": 429, "parameters": {"retry_after": 90}}, "retry"),
    (403, {"ok": False, "error_code": 403}, "failed"),
    (500, {"ok": False}, "uncertain"), (200, {"ok": True, "result": {}}, "uncertain"),
])
def test_telegram_transport_errors_are_sanitized(status, body, kind):
    with httpx.Client(transport=httpx.MockTransport(
        lambda _: httpx.Response(status, json=body))) as client:
        with pytest.raises(TelegramFailure) as exc:
            TelegramHTTP("secret-bot-token", client).send(123, "آزمون")
        assert exc.value.kind == kind
        assert "secret-bot-token" not in str(exc.value)


def test_transport_uses_official_endpoint_and_confirmed_message_id():
    def handler(request):
        assert request.url.host == "api.telegram.org"
        assert request.url.path.endswith("/sendMessage")
        assert json.loads(request.content)["chat_id"] == 123
        return httpx.Response(200, json={"ok": True, "result": {"message_id": 7}})
    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        assert TelegramHTTP("test-bot", client).send(123, "آزمون") == 7


def test_split_preserves_text_and_telegram_limit():
    text = "متن فارسی\n😀" * 2000
    parts = chunks(text)
    assert "".join(parts) == text
    assert all(len(p.encode("utf-16-le")) // 2 <= 3500 for p in parts)


def test_send_cooldown_applies_to_other_queued_messages(app, client):
    telegram = FakeTelegram()
    telegram.failure = TelegramFailure("retry", 90)
    runner = worker(app, client, telegram)
    with Session(app.state.engine) as session:
        session.add_all([Delivery(key=str(i), chat_id=123, text="آزمون") for i in range(2)])
        session.commit()
    runner.deliver(NOW)
    telegram.failure = None
    runner.deliver(NOW.replace(minute=31))
    assert telegram.sent == []
    runner.deliver(NOW.replace(minute=32))
    assert len(telegram.sent) == 2


def test_removed_user_never_receives_old_queue(app, client):
    telegram = FakeTelegram()
    with Session(app.state.engine) as session:
        session.add(Delivery(key="old-user", chat_id=999, text="آزمون"))
        session.commit()
    worker(app, client, telegram).deliver(NOW)
    assert telegram.sent == []
    with Session(app.state.engine) as session:
        assert session.get(Delivery, "old-user").status == "failed"


def test_delivery_status_requires_admin(app):
    with TestClient(app, headers={"Authorization": "Bearer gateway-test",
                                 "X-Studio-Telegram-User": "123"}) as client:
        assert client.get("/operations/telegram").status_code == 403


def test_telegram_timeout_is_uncertain_without_leaking_token():
    def handler(request):
        raise httpx.ReadTimeout("secret-bot-token", request=request)
    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        with pytest.raises(TelegramFailure) as exc:
            TelegramHTTP("secret-bot-token", client).send(123, "آزمون")
        assert exc.value.kind == "uncertain"
        assert "secret-bot-token" not in str(exc.value)
