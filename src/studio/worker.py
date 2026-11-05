"""Single-instance private Telegram worker; no automatic activation on import."""

import argparse
import json
import os
import time
from datetime import datetime, timezone
from pathlib import Path

import httpx
from sqlalchemy import select, update
from sqlalchemy.exc import IntegrityError

from .domain import report_day
from .reports import format_report, report_keyboard
from .storage import BotCursor, BotUpdate, Delivery, Report, database
from .telegram import TelegramGateway


class DeliveryUncertain(RuntimeError):
    pass


class RetryLater(RuntimeError):
    def __init__(self, delay):
        self.delay = max(1, min(int(delay), 3600))


class TelegramAPI:
    def __init__(self, token, client=None):
        if not token or any(c in token for c in "/?#\n\r"):
            raise ValueError("Valid dedicated Telegram token required")
        self.token = token
        self.client = client or httpx.Client(timeout=35)

    def call(self, method, payload):
        # All methods are fixed by application code. Never log token-bearing URLs.
        url = f"https://api.telegram.org/bot{self.token}/{method}"
        try:
            with self.client.stream("POST", url, json=payload, follow_redirects=False) as response:
                raw = bytearray()
                for chunk in response.iter_bytes():
                    raw.extend(chunk)
                    if len(raw) > 1048576:
                        raise DeliveryUncertain("Telegram response exceeded limit")
                data = json.loads(raw)
                if not isinstance(data, dict):
                    raise DeliveryUncertain("Invalid Telegram response")
                if response.status_code == 429 and data.get("ok") is False:
                    raise RetryLater(data.get("parameters", {}).get("retry_after", 60))
                if response.status_code != 200 or data.get("ok") is not True:
                    raise DeliveryUncertain("Telegram request not confirmed")
                return data["result"]
        except (httpx.HTTPError, ValueError, KeyError, TypeError):
            raise DeliveryUncertain("Telegram request not confirmed") from None

    def updates(self, offset):
        return self.call(
            "getUpdates",
            {
                "offset": offset,
                "timeout": 20,
                "limit": 20,
                "allowed_updates": ["message", "callback_query"],
            },
        )

    def answer_callback(self, query_id):
        return self.call("answerCallbackQuery", {"callback_query_id": query_id})

    def send(self, recipient, text, keyboard=None):
        text = text.encode("utf-16-le")[:7800].decode("utf-16-le", errors="ignore")
        result = self.call(
            "sendMessage",
            {
                "chat_id": recipient,
                "text": text,
                "link_preview_options": {"is_disabled": True},
                **(
                    {"reply_markup": keyboard}
                    if keyboard and keyboard.get("inline_keyboard")
                    else {}
                ),
            },
        )
        if not isinstance(result, dict) or not isinstance(result.get("message_id"), int):
            raise DeliveryUncertain("Telegram message confirmation missing")
        return str(result["message_id"])


class Worker:
    def __init__(self, sessions, studio, telegram, users):
        if not users or any(not isinstance(u, int) or u <= 0 for u in users):
            raise ValueError("Positive private Telegram user IDs required")
        self.sessions, self.studio, self.telegram, self.users = sessions, studio, telegram, users
        self.gateway = TelegramGateway(users, studio)

    def poll(self):
        with self.sessions() as session:
            cursor = session.get(BotCursor, 1)
            offset = cursor.offset if cursor else 0
        for event in self.telegram.updates(offset):
            update_id = event.get("update_id")
            if not isinstance(update_id, int) or update_id < offset:
                continue
            # Durable reservation before any action. A crash leaves processing for review,
            # rather than replaying approvals or reply messages after restart.
            with self.sessions() as session:
                handled = session.get(BotUpdate, update_id)
                if handled is None:
                    session.add(BotUpdate(id=update_id, status="processing"))
                    session.commit()
            if handled is None:
                state = "handled"
                try:
                    reply = self.gateway.handle(event)
                    recipient = self.gateway.recipient(event)
                    if "callback_query" in event:
                        self.telegram.answer_callback(event["callback_query"]["id"])
                    self.telegram.send(recipient, reply)
                except PermissionError:
                    state = "ignored"
                except Exception:
                    # No exception details: upstream request objects may contain credentials.
                    state = "uncertain"
                with self.sessions() as session:
                    session.get(BotUpdate, update_id).status = state
                    session.commit()
            offset = update_id + 1
            with self.sessions() as session:
                cursor = session.get(BotCursor, 1)
                if cursor:
                    cursor.offset = offset
                else:
                    session.add(BotCursor(id=1, offset=offset))
                session.commit()

    def reports(self, now=None):
        now = now or datetime.now(timezone.utc)
        day = report_day(now)
        if day is None:
            return
        response = self.studio.post("/reports/prepare")
        response.raise_for_status()
        # The API owns the date. A clock disagreement must never send the wrong snapshot.
        if response.json()["day"] != day:
            raise RuntimeError("Report clock mismatch")
        with self.sessions() as session:
            report = session.get(Report, day)
            if not report:
                raise RuntimeError("API and worker must share a database")
            for user in sorted(self.users):
                if not session.scalar(
                    select(Delivery).where(Delivery.day == day, Delivery.recipient == str(user))
                ):
                    session.add(Delivery(day=day, recipient=str(user)))
            try:
                session.commit()
            except IntegrityError:
                session.rollback()
        with self.sessions() as session:
            deliveries = session.scalars(select(Delivery).where(Delivery.day == day)).all()
            payload = json.loads(session.get(Report, day).payload)
        for delivery in deliveries:
            if int(delivery.recipient) not in self.users:
                continue
            if (
                delivery.status not in {"pending", "retry"}
                or delivery.next_attempt > now.timestamp()
            ):
                continue
            with self.sessions() as session:
                claimed = session.execute(
                    update(Delivery)
                    .where(
                        Delivery.id == delivery.id,
                        Delivery.status == delivery.status,
                        Delivery.attempts == delivery.attempts,
                    )
                    .values(status="sending", attempts=Delivery.attempts + 1)
                ).rowcount
                session.commit()
            if not claimed:
                continue
            status, message_id, next_attempt = "sent", None, 0
            try:
                message_id = self.telegram.send(
                    int(delivery.recipient),
                    format_report(day, payload),
                    keyboard=report_keyboard(payload),
                )
            except RetryLater as exc:
                status = "retry" if delivery.attempts < 4 else "failed"
                next_attempt = now.timestamp() + max(exc.delay, 2 ** (delivery.attempts + 1))
            except Exception:
                # A timeout may mean Telegram already accepted the message. Never resend
                # automatically. An interrupted 'sending' record is likewise not eligible.
                status = "uncertain"
            with self.sessions() as session:
                record = session.get(Delivery, delivery.id)
                record.status, record.message_id, record.next_attempt = (
                    status,
                    message_id,
                    next_attempt,
                )
                session.commit()


def main():
    parser = argparse.ArgumentParser(description="Private 3EO bot and 05:00 Tehran reports")
    parser.add_argument("--once", action="store_true", help="One poll/report cycle")
    args = parser.parse_args()
    required = ["STUDIO_TELEGRAM_TOKEN", "STUDIO_TELEGRAM_USERS", "STUDIO_ADMIN_TOKEN"]
    if os.getenv("STUDIO_TELEGRAM_ENABLED") != "1" or any(not os.getenv(k) for k in required):
        raise SystemExit(
            "Worker disabled: configure dedicated credentials/users and explicitly set STUDIO_TELEGRAM_ENABLED=1"
        )
    try:
        users = {int(u.strip()) for u in os.environ["STUDIO_TELEGRAM_USERS"].split(",")}
    except ValueError:
        raise SystemExit("STUDIO_TELEGRAM_USERS must contain numeric IDs") from None
    # Fixed loopback API; never send the admin token to an arbitrary configured URL.
    import fcntl

    lock_path = Path(os.getenv("STUDIO_WORKER_LOCK", "./studio-worker.lock"))
    with lock_path.open("a") as lock:
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            raise SystemExit("Another worker already owns this lock") from None
        engine, sessions = database(os.getenv("DATABASE_URL", "sqlite:///./studio.db"))
        try:
            with httpx.Client(
                base_url="http://127.0.0.1:8000",
                timeout=100,
                headers={"Authorization": f"Bearer {os.environ['STUDIO_ADMIN_TOKEN']}"},
            ) as studio:
                worker = Worker(
                    sessions, studio, TelegramAPI(os.environ["STUDIO_TELEGRAM_TOKEN"]), users
                )
                studio.get("/health").raise_for_status()
                while True:
                    try:
                        worker.reports()  # delivery first, before long-polling
                        worker.poll()
                    except Exception:
                        print(
                            "Worker cycle failed; details suppressed to protect credentials",
                            flush=True,
                        )
                        if args.once:
                            raise SystemExit(1) from None
                    if args.once:
                        break
                    time.sleep(5)
        finally:
            engine.dispose()


if __name__ == "__main__":
    main()
