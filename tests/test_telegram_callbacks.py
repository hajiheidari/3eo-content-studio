import json

import httpx
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session
from test_scout_delivery import NOW, RESEARCH, FakeTelegram, submit, worker

from studio.storage import Audit, Cursor, Delivery
from studio.telegram import TelegramGateway, idea_keyboard
from studio.worker import TelegramFailure, TelegramHTTP, chunks


@pytest.fixture
def telegram_client(app):
    with TestClient(app, headers={"Authorization": "Bearer gateway-test"}) as connection:
        yield connection


def callback(number, data, user=123, chat=123, chat_type="private"):
    return {"update_id": number, "callback_query": {
        "id": f"query-{number}", "from": {"id": user}, "data": data,
        "message": {"message_id": 7, "date": 1, "from": {"id": 456, "is_bot": True},
                    "chat": {"id": chat, "type": chat_type}},
    }}


def researched(client):
    item = submit(client)
    assert client.post(f"/items/{item}/research", json=RESEARCH).status_code == 200
    return client.get(f"/items/{item}").json()


def test_button_decision_replay_and_user_audit(client, app, telegram_client):
    item = researched(client)
    gateway = TelegramGateway({123}, telegram_client)
    data = idea_keyboard(item)["inline_keyboard"][0][0]["callback_data"]
    update = callback(50, data)
    assert gateway.process(update).text == "ثبت شد."
    assert gateway.process(update).text == "ثبت شد."
    assert client.get(f"/items/{item['id']}").json()["status"] == "IDEA_APPROVED"
    with Session(app.state.engine) as session:
        audits = list(session.scalars(select(Audit)))
        assert len(audits) == 2
        assert audits[-1].actor == "telegram:123"


def test_old_button_cannot_approve_revised_research(client):
    item = researched(client)
    old_data = idea_keyboard(item)["inline_keyboard"][0][0]["callback_data"]
    gateway = TelegramGateway({123}, client)
    assert client.post(f"/items/{item['id']}/transition", json={"status": "MORE_RESEARCH"}).status_code == 200
    assert client.post(f"/items/{item['id']}/research", json=RESEARCH).status_code == 200
    assert "قدیمی" in gateway.process(callback(51, old_data)).text
    assert client.get(f"/items/{item['id']}").json()["status"] == "RESEARCHED"


@pytest.mark.parametrize("user,chat,kind", [(999, 999, "private"), (123, -1, "group"),
                                           (123, 999, "private"), (123, None, "private")])
def test_callback_requires_allowed_sender_and_exact_private_chat(client, user, chat, kind):
    with pytest.raises(PermissionError):
        TelegramGateway({123}, client).process(callback(52, "approve:1:1", user, chat, kind))


@pytest.mark.parametrize("data", ["EXPORTED:1:1", "approve:1", "approve:1:0", "approve:1:1\nevil",
                                  "approve:1:1:extra", None])
def test_malformed_callback_never_changes_item(client, data):
    item = researched(client)
    result = TelegramGateway({123}, client).process(callback(53, data))
    assert "معتبر نیست" in result.text
    assert client.get(f"/items/{item['id']}").json()["status"] == "RESEARCHED"


def test_worker_callback_commits_reply_offset_then_acknowledges(client, app):
    item = researched(client)
    telegram = FakeTelegram()
    telegram.incoming = [callback(54, f"save:{item['id']}:{item['version']}")]
    runner = worker(app, client, telegram)
    runner.poll()
    runner.poll()
    assert telegram.answers == ["query-54"]
    assert client.get(f"/items/{item['id']}").json()["status"] == "SAVED"
    with Session(app.state.engine) as session:
        assert session.get(Cursor, "telegram").offset == 55
        assert len(list(session.scalars(select(Delivery)))) == 1


def test_expired_popup_does_not_undo_or_replay_decision(client, app):
    item = researched(client)
    class ExpiredPopup(FakeTelegram):
        def answer(self, callback_id):
            raise TelegramFailure("failed")
    telegram = ExpiredPopup()
    telegram.incoming = [callback(55, f"reject:{item['id']}:{item['version']}")]
    worker(app, client, telegram).poll()
    assert client.get(f"/items/{item['id']}").json()["status"] == "REJECTED"
    with Session(app.state.engine) as session:
        assert session.get(Cursor, "telegram").offset == 56


def test_keyboard_persisted_on_last_chunk_only_and_sent(client, app):
    item = researched(client)
    markup = idea_keyboard(item)
    text = "متن فارسی 😀" * 2000
    with Session(app.state.engine) as session:
        worker(app, client, FakeTelegram()).enqueue(session, "long", 123, text, markup)
        session.commit()
        rows = list(session.scalars(select(Delivery).order_by(Delivery.key)))
        assert len(rows) == len(chunks(text))
        assert all(r.reply_markup is None for r in rows[:-1])
        assert json.loads(rows[-1].reply_markup) == markup
    telegram = FakeTelegram()
    runner = worker(app, client, telegram)
    for _ in range(3):
        runner.deliver(NOW)
    assert telegram.markups[-1] == markup
    assert "".join(text for _, text in telegram.sent) == text


def test_old_snapshot_has_no_unversioned_buttons():
    assert idea_keyboard({"id": 1, "status": "RESEARCHED"}) is None
    assert idea_keyboard({"id": 1, "version": 2, "status": "IDEA_APPROVED"}) is None


def test_transport_sends_keyboard_and_answers_popup():
    requests = []
    def handler(request):
        requests.append(request)
        result = True if request.url.path.endswith("answerCallbackQuery") else {"message_id": 8}
        return httpx.Response(200, json={"ok": True, "result": result})
    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        api = TelegramHTTP("test-only", client)
        markup = idea_keyboard({"id": 1, "version": 2, "status": "RESEARCHED"})
        api.send(123, "آزمون", markup)
        api.answer("popup-1")
    assert json.loads(requests[0].content)["reply_markup"] == markup
    assert json.loads(requests[1].content) == {"callback_query_id": "popup-1"}
