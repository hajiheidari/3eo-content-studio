"""Private command handler; no network calls or implicit bot startup."""

import json
import re
from dataclasses import dataclass


def idea_text(item):
    research = item.get("research") or {}
    metadata = item.get("metadata") or {}
    source = (f"\nعنوان منبع: {metadata['title']}\nمشخصات: API رسمی یوتیوب"
              if metadata else "\nمشخصات منبع: ورود دستی یا نامشخص")
    if not research:
        return (f"ایده {item['id']} — {item['status']}\n{item['url']}{source}\n"
                "پژوهش هنوز ثبت نشده است.")
    return "\n".join([
        f"ایده {item['id']} — {item['status']} — امتیاز {item.get('score')}",
        research["title_fa"], item["url"] + source,
        f"سازنده: {item.get('author') or 'نامشخص'}",
        f"تاریخ منبع: {item.get('published_at') or 'نامشخص'}",
        research["summary_fa"],
        f"اهمیت: {research.get('why_it_matters_fa', 'ثبت نشده')}",
        f"قالب: {research.get('recommended_format_fa', 'ثبت نشده')}",
        f"زاویه فارسی: {research['angle_fa']}",
        f"ارتباط با 3EO: {research.get('brand_connection_fa', 'ثبت نشده')}",
        "ادعاهای نیازمند بررسی: " + "؛ ".join(research["claims_to_verify"]),
        "محدودیت‌ها: " + "؛ ".join(research["limitations"]),
        f"/approve {item['id']}\n/reject {item['id']}\n/save {item['id']}\n/research {item['id']}",
    ])


HELP = (
    "لینک یوتیوب یا اینستاگرام را بفرستید.\n"
    "/ideas — فهرست ایده‌ها\n/idea ID — مشاهده پژوهش\n"
    "/transcript ID سپس خط جدید، منشأ مجاز متن، خط جدید و متن ویدئو\n"
    "/review ID سپس خط جدید و JSON پژوهش بازبینی‌شده\n"
    "/analyze ID — پژوهش با ارائه‌دهنده تنظیم‌شده\n"
    "/metadata ID — مشخصات رسمی یوتیوب، در صورت تنظیم اتصال\n"
    "/approve ID /reject ID /save ID /research ID\n"
    "تولید سناریو و ویدئو هنوز فعال نیست."
)


class TelegramGateway:
    def __init__(self, allowed_users: set[int], studio):
        if not allowed_users or any(type(x) is not int or x <= 0 for x in allowed_users):
            raise ValueError("Approved positive Telegram user IDs required")
        self.allowed_users, self.studio = allowed_users, studio

    def handle(self, update: dict) -> str:
        return self.process(update).text

    def process(self, update: dict):
        callback = update.get("callback_query")
        message = callback.get("message", {}) if isinstance(callback, dict) else update.get("message", {})
        sender = callback.get("from", {}) if isinstance(callback, dict) else message.get("from", {})
        user, chat = sender.get("id"), message.get("chat", {})
        if (type(user) is not int or user not in self.allowed_users
                or chat.get("type") != "private" or chat.get("id") != user
                or (callback is not None and message.get("date") == 0)):
            raise PermissionError("Unauthorized Telegram user or chat")
        headers = {"X-Studio-Telegram-User": str(user)}
        if "update_id" in update:
            if type(update["update_id"]) is not int or update["update_id"] < 0:
                raise PermissionError("Invalid update ID")
            headers["Idempotency-Key"] = f"tg:{update['update_id']}"
        expected_version, callback_id = None, None
        if callback is not None:
            callback_id = callback.get("id")
            data = callback.get("data")
            if not isinstance(callback_id, str) or not 1 <= len(callback_id) <= 128:
                raise PermissionError("Invalid callback ID")
            match = re.fullmatch(r"(approve|reject|save|research):([1-9][0-9]{0,9}):([1-9][0-9]{0,9})",
                                 data) if isinstance(data, str) else None
            if not match:
                return GatewayReply("دکمه معتبر نیست؛ ایده را دوباره باز کنید.", user,
                                    callback_id=callback_id)
            text = f"/{match[1]} {match[2]}"
            expected_version = int(match[3])
        else:
            text = message.get("text")
            text = text.strip() if isinstance(text, str) else ""
        result = self._command(text, headers, expected_version)
        text, markup = result if isinstance(result, tuple) else (result, None)
        return GatewayReply(text, user, markup, callback_id)

    def _command(self, text, headers, expected_version=None):
        if text.startswith("https://"):
            response = self.studio.post("/items", json={"url": text}, headers=headers)
            if response.status_code >= 500:
                response.raise_for_status()
            if response.status_code != 200:
                return "ثبت نشد؛ لینک معتبر لازم است. دوباره تلاش کنید."
            return (f"شناسه ایده: {response.json()['id']}\n"
                    "متن مجاز را با /transcript ID و راهنمای /help ثبت کنید.")
        command_line, _, content = text.partition("\n")
        command, _, item_id = command_line.partition(" ")
        if command in {"/approve", "/reject", "/save", "/research", "/transcript",
                       "/review", "/analyze", "/metadata", "/idea"}:
            if not item_id.isascii() or not item_id.isdigit() or len(item_id) > 10:
                return "شناسه عددی ایده لازم است."
            path = f"/items/{int(item_id)}"
            if command == "/transcript":
                provenance, separator, transcript = content.partition("\n")
                if not separator or not provenance.strip() or not transcript.strip():
                    return "پس از /transcript ID، منشأ مجاز و متن را در دو خط جدا بفرستید."
                response = self.studio.put(path + "/transcript", headers=headers,
                                          json={"text": transcript, "provenance": provenance})
            elif command == "/review":
                try:
                    research = json.loads(content)
                except ValueError:
                    return "JSON پژوهش معتبر نیست؛ راهنمای README را ببینید."
                response = self.studio.post(path + "/research", headers=headers, json=research)
            elif command == "/analyze":
                response = self.studio.post(path + "/research", headers=headers)
            elif command == "/metadata":
                response = self.studio.post(path + "/metadata", headers=headers)
            elif command == "/idea":
                response = self.studio.get(path, headers=headers)
            else:
                status = {"/approve": "IDEA_APPROVED", "/reject": "REJECTED",
                          "/save": "SAVED", "/research": "MORE_RESEARCH"}[command]
                response = self.studio.post(path + "/transition", headers=headers,
                                           json={"status": status, **({"expected_version": expected_version}
                                                 if expected_version is not None else {})})
            if response.status_code >= 500 and command not in {"/analyze", "/review", "/metadata"}:
                response.raise_for_status()
            if response.status_code == 200:
                if command == "/idea":
                    item = response.json()
                    return idea_text(item), idea_keyboard(item)
                return "ثبت شد."
            if response.status_code == 409 and expected_version is not None:
                return "این دکمه قدیمی است یا وضعیت تغییر کرده؛ ایده را دوباره با /idea باز کنید."
            if command == "/metadata" and response.status_code in {429, 502, 503}:
                return "مشخصات دریافت نشد؛ اتصال غیرفعال، سهمیه تمام یا منبع در دسترس نیست. ورود دستی ممکن است."
            if response.status_code in {502, 503}:
                return "پژوهش آماده نشد؛ ارائه‌دهنده در دسترس نیست یا خروجی معتبر نداد."
            return "ثبت نشد؛ شناسه، قالب ورودی و وضعیت فعلی ایده را بررسی کنید."
        if text == "/ideas":
            response = self.studio.get("/items", headers=headers)
            response.raise_for_status()
            return ("\n".join(f"{i['id']}: {i['status']} {i['url']}"
                              for i in response.json()) or "ایده‌ای ثبت نشده است.")
        return HELP


@dataclass(frozen=True)
class GatewayReply:
    text: str
    user_id: int
    markup: dict | None = None
    callback_id: str | None = None


def idea_keyboard(item):
    version = item.get("version")
    if type(version) is not int or version <= 0:
        return None  # Old report snapshots are viewable but cannot create unversioned buttons.
    actions = {
        "DISCOVERED": [("رد", "reject")],
        "RESEARCHED": [("تأیید ایده", "approve"), ("رد", "reject"),
                       ("ذخیره", "save"), ("پژوهش بیشتر", "research")],
        "SAVED": [("تأیید ایده", "approve"), ("رد", "reject"), ("پژوهش بیشتر", "research")],
        "MORE_RESEARCH": [("رد", "reject")],
    }.get(item.get("status"), [])
    if not actions:
        return None
    buttons = [{"text": label, "callback_data": f"{action}:{item['id']}:{version}"}
               for label, action in actions]
    return {"inline_keyboard": [buttons[i:i + 2] for i in range(0, len(buttons), 2)]}
