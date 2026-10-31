"""Opt-in polling and durable delivery. No publication or media work."""

import os
import time
import uuid
from datetime import datetime, timezone
from urllib.parse import urlsplit

import httpx
from sqlalchemy import or_, select, update
from sqlalchemy.exc import IntegrityError, SQLAlchemyError

from .domain import report_day
from .storage import Cursor, Delivery, database
from .telegram import TelegramGateway, idea_text


def chunks(text, limit=3500):
    # Telegram counts UTF-16 units; split without discarding any source text.
    result, current, units = [], [], 0
    for character in text:
        size = len(character.encode("utf-16-le")) // 2
        if units + size > limit:
            result.append("".join(current))
            current, units = [], 0
        current.append(character)
        units += size
    if current:
        result.append("".join(current))
    return result


class TelegramFailure(Exception):
    def __init__(self, kind, delay=0):
        super().__init__(f"Telegram {kind}")
        self.kind, self.delay = kind, delay


class TelegramHTTP:
    def __init__(self, token, client):
        if not token:
            raise ValueError("Dedicated bot token required")
        self._token, self._client = token, client

    def call(self, method, payload):
        try:
            response = self._client.post(
                f"https://api.telegram.org/bot{self._token}/{method}", json=payload)
        except (httpx.ConnectError, httpx.ConnectTimeout):
            raise TelegramFailure("retry", 30) from None
        except httpx.HTTPError:
            raise TelegramFailure("uncertain") from None
        try:
            data = response.json()
        except ValueError:
            raise TelegramFailure("uncertain") from None
        if not isinstance(data, dict):
            raise TelegramFailure("uncertain")
        code = data.get("error_code", response.status_code)
        if code == 429:
            delay = data.get("parameters", {}).get("retry_after", 60)
            if type(delay) is not int or not 0 < delay <= 86400:
                delay = 60
            raise TelegramFailure("retry", delay)
        if 400 <= response.status_code < 500 or (data.get("ok") is False and code in {400, 401, 403, 404, 409}):
            raise TelegramFailure("failed")
        if response.status_code != 200 or data.get("ok") is not True or "result" not in data:
            raise TelegramFailure("uncertain")
        return data["result"]

    def updates(self, offset):
        result = self.call("getUpdates", {"offset": offset, "limit": 5, "timeout": 20,
                                          "allowed_updates": ["message"]})
        if not isinstance(result, list):
            raise TelegramFailure("uncertain")
        return result

    def send(self, chat_id, text):
        result = self.call("sendMessage", {"chat_id": chat_id, "text": text,
                                           "link_preview_options": {"is_disabled": True}})
        if not isinstance(result, dict) or type(result.get("message_id")) is not int:
            raise TelegramFailure("uncertain")
        return result["message_id"]


class Worker:
    def __init__(self, sessions, studio, telegram, allowed_users, recipients, clock=None):
        if not recipients or not set(recipients) <= set(allowed_users):
            raise ValueError("Report recipients must be approved private users")
        self.sessions, self.studio, self.telegram = sessions, studio, telegram
        self.users, self.recipients = set(allowed_users), set(recipients)
        self.gateway = TelegramGateway(self.users, studio)
        self.clock = clock or (lambda: datetime.now(timezone.utc))
        self.owner = str(uuid.uuid4())

    def lease(self, now):
        with self.sessions() as session:
            if session.get(Cursor, "worker") is None:
                session.add(Cursor(name="worker"))
                try:
                    session.commit()
                except IntegrityError:
                    session.rollback()
            changed = session.execute(update(Cursor).where(
                Cursor.name == "worker",
                or_(Cursor.expires_at <= now, Cursor.owner == self.owner),
            ).values(owner=self.owner, expires_at=now + 600)).rowcount
            session.commit()
            return bool(changed)

    def release(self):
        with self.sessions() as session:
            session.execute(update(Cursor).where(
                Cursor.name == "worker", Cursor.owner == self.owner,
            ).values(owner=None, expires_at=0))
            session.commit()

    @staticmethod
    def enqueue(session, key, user, text):
        for part, content in enumerate(chunks(text)):
            delivery_key = f"{key}:{user}:{part}"
            if session.get(Delivery, delivery_key) is None:
                session.add(Delivery(key=delivery_key, chat_id=user, text=content))

    def prepare(self, now):
        if report_day(now) is None:
            return
        response = self.studio.post("/reports/prepare", headers={
            "X-Studio-Telegram-User": str(min(self.recipients))})
        response.raise_for_status()
        report = response.json()
        # The snapshot is immutable. A restart can reconstruct the same outbox keys.
        with self.sessions() as session:
            for user in self.recipients:
                header = f"گزارش ایده‌ها — {report['day']} — زمان تهران\n"
                self.enqueue(session, f"report:{report['day']}:header", user,
                             header if report["ideas"] else header + "ایده پژوهش‌شده‌ای موجود نیست.")
                for position, item in enumerate(report["ideas"]):
                    self.enqueue(session, f"report:{report['day']}:idea:{position:02d}:{item['id']}",
                                 user, idea_text(item))
            session.commit()

    def poll(self):
        with self.sessions() as session:
            cursor = session.get(Cursor, "telegram")
            offset = cursor.offset if cursor else 0
        updates = self.telegram.updates(offset)
        for incoming in sorted(updates, key=lambda x: x.get("update_id", -1)):
            update_id = incoming.get("update_id")
            if type(update_id) is not int or update_id < offset:
                continue
            try:
                reply = self.gateway.handle(incoming)
            except PermissionError:
                reply = None
            # Mutations use an API receipt; replay after a crash cannot repeat the write.
            # Offset and reply are committed together before acknowledging the update.
            with self.sessions() as session:
                cursor = session.get(Cursor, "telegram")
                if cursor is None:
                    cursor = Cursor(name="telegram", offset=0)
                    session.add(cursor)
                if cursor.offset <= update_id:
                    if reply:
                        user = incoming["message"]["from"]["id"]
                        self.enqueue(session, f"update:{update_id}", user, reply)
                    cursor.offset = update_id + 1
                session.commit()
            offset = update_id + 1

    def deliver(self, now):
        timestamp = now.timestamp()
        with self.sessions() as session:
            cooldown = session.get(Cursor, "telegram-send-cooldown")
            if cooldown and cooldown.offset > timestamp:
                return
            # A crash after send but before its receipt is an unknown outcome.
            # Never resend it automatically: Telegram has no sendMessage idempotency key.
            session.execute(update(Delivery).where(
                Delivery.status == "sending", Delivery.available_at <= timestamp,
            ).values(status="uncertain", error="Worker stopped during delivery"))
            keys = list(session.scalars(select(Delivery.key).where(
                Delivery.status.in_(["pending", "retry"]),
                Delivery.available_at <= timestamp,
            ).order_by(Delivery.key).limit(5)))
            session.commit()
        for key in keys:
            with self.sessions() as session:
                claimed = session.execute(update(Delivery).where(
                    Delivery.key == key, Delivery.status.in_(["pending", "retry"]),
                    Delivery.available_at <= timestamp,
                ).values(status="sending", attempts=Delivery.attempts + 1,
                         available_at=timestamp + 120)).rowcount
                session.commit()
                if not claimed:
                    continue
                delivery = session.get(Delivery, key)
                if delivery.chat_id not in self.users:
                    delivery.status, delivery.error = "failed", "Recipient no longer approved"
                    session.commit()
                    continue
                try:
                    message_id = self.telegram.send(delivery.chat_id, delivery.text)
                except TelegramFailure as exc:
                    delivery.error = f"Telegram {exc.kind}"
                    delivery.status = exc.kind
                    if exc.kind == "retry":
                        if delivery.attempts >= 5:
                            delivery.status = "failed"
                        else:
                            delivery.available_at = timestamp + max(
                                exc.delay, min(3600, 30 * 2 ** (delivery.attempts - 1)))
                            cooldown = session.get(Cursor, "telegram-send-cooldown")
                            if cooldown is None:
                                cooldown = Cursor(name="telegram-send-cooldown")
                                session.add(cooldown)
                            cooldown.offset = int(delivery.available_at)
                else:
                    delivery.status, delivery.message_id = "sent", message_id
                    delivery.error = None
                session.commit()
                if delivery.status == "retry":
                    break

    def tick(self):
        now = self.clock()
        if not self.lease(now.timestamp()):
            return False
        try:
            self.prepare(now)
            self.deliver(self.clock())
            self.poll()
            return True
        finally:
            self.release()


def main():
    if os.getenv("STUDIO_TELEGRAM_ENABLED") != "1":
        raise SystemExit("Telegram worker disabled; configure the dedicated bot first")
    api_url = os.getenv("STUDIO_API_URL", "http://127.0.0.1:8000")
    parsed = urlsplit(api_url)
    if (parsed.scheme != "http" or parsed.hostname not in {"127.0.0.1", "::1"}
            or parsed.username or parsed.password or parsed.query or parsed.fragment
            or parsed.path not in {"", "/"}):
        raise SystemExit("Worker API must use a literal loopback address without credentials")
    users = {int(x) for x in os.getenv("STUDIO_TELEGRAM_USERS", "").split(",") if x.strip()}
    recipients = {int(x) for x in os.getenv("STUDIO_REPORT_USERS", "").split(",") if x.strip()}
    api_token, bot_token = os.getenv("STUDIO_TELEGRAM_API_TOKEN"), os.getenv("STUDIO_BOT_TOKEN")
    if not api_token or not bot_token:
        raise SystemExit("Dedicated bot and gateway configuration required")
    engine, sessions = database(os.getenv("DATABASE_URL", "sqlite:///./studio.db"))
    try:
        with httpx.Client(base_url=api_url, timeout=30, trust_env=False,
                          headers={"Authorization": f"Bearer {api_token}"}) as studio:
            with httpx.Client(timeout=30, trust_env=False, follow_redirects=False) as client:
                worker = Worker(sessions, studio, TelegramHTTP(bot_token, client), users, recipients)
                while True:
                    try:
                        if not worker.tick():
                            time.sleep(5)
                    except (httpx.HTTPError, TelegramFailure):
                        # Never print exception URLs: Telegram URLs contain the bot token.
                        print("Worker network operation failed; persistent state retained", flush=True)
                        time.sleep(30)
                    except SQLAlchemyError:
                        print("Worker database operation failed; check migrations and storage", flush=True)
                        time.sleep(30)
    finally:
        engine.dispose()


if __name__ == "__main__":
    main()
