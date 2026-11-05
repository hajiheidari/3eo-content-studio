from datetime import datetime, timezone

import httpx
import pytest
from sqlalchemy import select

from studio.storage import Base, BotCursor, BotUpdate, Delivery, Report, database
from studio.worker import DeliveryUncertain, RetryLater, TelegramAPI, Worker, format_report

NOW = datetime(2026, 11, 3, 1, 30, tzinfo=timezone.utc)


class Studio:
    def __init__(self, day="2026-11-03"):
        self.day = day
        self.calls = []

    def put(self, path, **kwargs):
        return httpx.Response(200, json={"item_id": 1}, request=httpx.Request("PUT", "http://test"))

    def post(self, path, **kwargs):
        self.calls.append((path, kwargs))
        return httpx.Response(
            200, json={"day": self.day, "id": 1}, request=httpx.Request("POST", "http://test")
        )


class Telegram:
    def __init__(self):
        self.sent = []
        self.keyboards = []
        self.events = []
        self.error = None

    def updates(self, offset):
        return [e for e in self.events if e["update_id"] >= offset]

    def send(self, user, text, keyboard=None):
        self.sent.append((user, text))
        self.keyboards.append(keyboard)
        if self.error:
            raise self.error
        return "123"


@pytest.fixture
def setup(tmp_path):
    engine, sessions = database(f"sqlite:///{tmp_path}/worker.db")
    Base.metadata.create_all(engine)
    with sessions() as session:
        session.add(Report(day="2026-11-03", payload="[]"))
        session.commit()
    telegram, studio = Telegram(), Studio()
    yield sessions, studio, telegram
    engine.dispose()


def test_report_due_and_restart_idempotence(setup):
    sessions, studio, telegram = setup
    worker = Worker(sessions, studio, telegram, {123})
    worker.reports(datetime(2026, 11, 3, 1, 29, tzinfo=timezone.utc))
    assert not telegram.sent and not studio.calls
    worker.reports(NOW)
    Worker(sessions, studio, telegram, {123}).reports(NOW)
    assert len(telegram.sent) == 1
    with sessions() as session:
        record = session.scalar(select(Delivery))
        assert record.status == "sent" and record.message_id == "123"


def test_ambiguous_delivery_never_retried(setup):
    sessions, studio, telegram = setup
    telegram.error = DeliveryUncertain("timeout")
    Worker(sessions, studio, telegram, {123}).reports(NOW)
    telegram.error = None
    Worker(sessions, studio, telegram, {123}).reports(NOW)
    assert len(telegram.sent) == 1
    with sessions() as session:
        assert session.scalar(select(Delivery)).status == "uncertain"


def test_interrupted_send_not_replayed(setup):
    sessions, studio, telegram = setup
    with sessions() as session:
        session.add(Delivery(day="2026-11-03", recipient="123", status="sending"))
        session.commit()
    Worker(sessions, studio, telegram, {123}).reports(NOW)
    assert not telegram.sent


def test_explicit_rate_limit_retry(setup):
    sessions, studio, telegram = setup
    telegram.error = RetryLater(60)
    worker = Worker(sessions, studio, telegram, {123})
    worker.reports(NOW)
    worker.reports(NOW)
    assert len(telegram.sent) == 1
    telegram.error = None
    worker.reports(datetime(2026, 11, 3, 1, 31, tzinfo=timezone.utc))
    assert len(telegram.sent) == 2
    with sessions() as session:
        assert session.scalar(select(Delivery)).status == "sent"


def test_update_cursor_restart_and_unauthorized(setup):
    sessions, studio, telegram = setup
    telegram.events = [
        {
            "update_id": 10,
            "message": {
                "from": {"id": 9},
                "chat": {"id": 9, "type": "private"},
                "text": "https://youtu.be/abcdefghijk",
            },
        },
        {
            "update_id": 11,
            "message": {
                "from": {"id": 123},
                "chat": {"id": 123, "type": "private"},
                "text": "https://youtu.be/abcdefghijk",
            },
        },
    ]
    Worker(sessions, studio, telegram, {123}).poll()
    Worker(sessions, studio, telegram, {123}).poll()
    assert len(studio.calls) == 2 and len(telegram.sent) == 1
    with sessions() as session:
        assert session.get(BotCursor, 1).offset == 12
        assert session.get(BotUpdate, 10).status == "ignored"
        assert session.get(BotUpdate, 11).status == "handled"


def test_clock_mismatch_stops_send(setup):
    sessions, studio, telegram = setup
    studio.day = "2026-11-02"
    with pytest.raises(RuntimeError):
        Worker(sessions, studio, telegram, {123}).reports(NOW)
    assert not telegram.sent


def test_telegram_timeout_redacts_token():
    def handler(request):
        raise httpx.ReadTimeout("credential-bearing request", request=request)

    api = TelegramAPI("secret-test-token", httpx.Client(transport=httpx.MockTransport(handler)))
    with pytest.raises(DeliveryUncertain) as caught:
        api.send(123, "test")
    assert "secret-test-token" not in str(caught.value)


def test_telegram_redirect_not_followed():
    calls = []

    def handler(request):
        calls.append(request)
        return httpx.Response(302, headers={"location": "https://evil.test"})

    api = TelegramAPI("test", httpx.Client(transport=httpx.MockTransport(handler)))
    with pytest.raises(DeliveryUncertain):
        api.send(123, "test")
    assert len(calls) == 1


def test_report_unicode_bound():
    idea = {
        "id": 1,
        "score": 70,
        "url": "https://www.youtube.com/watch?v=abcdefghijk",
        "research": {
            "title_fa": "آزمون" * 100,
            "summary_fa": "😀" * 10000,
            "angle_fa": "آزمایش" * 100,
            "limitations": ["متن مجاز" * 100],
        },
    }
    text = format_report("2026-11-03", [idea] * 5)
    assert len(text.encode("utf-16-le")) <= 7800


def test_report_keyboard_sent_to_telegram():
    import json

    from studio.reports import report_keyboard

    payloads = []

    def handler(request):
        payloads.append(json.loads(request.content))
        return httpx.Response(200, json={"ok": True, "result": {"message_id": 7}})

    api = TelegramAPI("test", httpx.Client(transport=httpx.MockTransport(handler)))
    keyboard = report_keyboard([{"id": 42}])
    assert api.send(123, "گزارش", keyboard=keyboard) == "7"
    assert payloads[0]["reply_markup"]["inline_keyboard"][0][0]["callback_data"] == "approve:42"


def test_callback_worker_acknowledges_and_replies(setup):
    sessions, studio, telegram = setup
    acknowledged = []
    telegram.answer_callback = acknowledged.append
    telegram.events = [
        {
            "update_id": 20,
            "callback_query": {
                "id": "query-id",
                "from": {"id": 123},
                "message": {"chat": {"type": "private"}},
                "data": "approve:1",
            },
        }
    ]
    Worker(sessions, studio, telegram, {123}).poll()
    assert acknowledged == ["query-id"]
    assert len(telegram.sent) == 1
    assert studio.calls[0][0] == "/items/1/transition"


def test_expired_callback_ack_does_not_drop_authorized_approval(setup):
    sessions, studio, telegram = setup

    def expired(query):
        raise DeliveryUncertain("expired query")

    telegram.answer_callback = expired
    telegram.events = [
        {
            "update_id": 90,
            "callback_query": {
                "id": "old-query",
                "from": {"id": 123},
                "message": {"chat": {"type": "private"}},
                "data": "approve:1",
            },
        }
    ]
    worker = Worker(sessions, studio, telegram, {123})
    worker.poll()
    assert studio.calls[0][0] == "/items/1/transition"
    assert len(telegram.sent) == 1
    worker.poll()
    assert len(studio.calls) == 1 and len(telegram.sent) == 1
    with sessions() as session:
        assert session.get(BotUpdate, 90).status == "handled"


def test_script_review_sends_every_part_and_keyboard_only_at_end(setup):
    from studio.script_messages import split_telegram
    from studio.telegram import BotReply

    sessions, studio, telegram = setup
    worker = Worker(sessions, studio, telegram, {123})
    text = "سناریو😀" * 1200
    parts = split_telegram(text)
    keyboard = {
        "inline_keyboard": [
            [{"text": "تأیید", "callback_data": "scriptapprove:1:0123456789abcdef"}]
        ]
    }
    worker.gateway.handle = lambda event: BotReply(parts[0], keyboard, parts=parts)
    telegram.events = [
        {
            "update_id": 91,
            "message": {"from": {"id": 123}, "chat": {"type": "private"}, "text": "/script 1"},
        }
    ]
    worker.poll()
    assert "چند دقیقه" in telegram.sent[0][1]
    assert "".join(message for _, message in telegram.sent[1:]) == text
    assert all(k is None for k in telegram.keyboards[:-1])
    assert telegram.keyboards[-1] == keyboard
