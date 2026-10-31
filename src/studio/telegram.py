"""Private command handler; no network calls or implicit bot startup."""

import json


def idea_text(item):
    research = item.get("research") or {}
    if not research:
        return f"ایده {item['id']} — {item['status']}\n{item['url']}\nپژوهش هنوز ثبت نشده است."
    return "\n".join([
        f"ایده {item['id']} — {item['status']} — امتیاز {item.get('score')}",
        research["title_fa"], item["url"],
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
    "/approve ID /reject ID /save ID /research ID\n"
    "تولید سناریو و ویدئو هنوز فعال نیست."
)


class TelegramGateway:
    def __init__(self, allowed_users: set[int], studio):
        if not allowed_users or any(type(x) is not int or x <= 0 for x in allowed_users):
            raise ValueError("Approved positive Telegram user IDs required")
        self.allowed_users, self.studio = allowed_users, studio

    def handle(self, update: dict) -> str:
        message = update.get("message", {})
        user = message.get("from", {}).get("id")
        chat = message.get("chat", {})
        if (type(user) is not int or user not in self.allowed_users
                or chat.get("type") != "private" or chat.get("id", user) != user):
            raise PermissionError("Unauthorized Telegram user or chat")
        headers = {"X-Studio-Telegram-User": str(user)}
        if "update_id" in update:
            headers["Idempotency-Key"] = f"tg:{update['update_id']}"
        text = message.get("text")
        text = text.strip() if isinstance(text, str) else ""
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
                       "/review", "/analyze", "/idea"}:
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
            elif command == "/idea":
                response = self.studio.get(path, headers=headers)
            else:
                status = {"/approve": "IDEA_APPROVED", "/reject": "REJECTED",
                          "/save": "SAVED", "/research": "MORE_RESEARCH"}[command]
                response = self.studio.post(path + "/transition", headers=headers,
                                           json={"status": status})
            if response.status_code >= 500 and command not in {"/analyze", "/review"}:
                response.raise_for_status()
            if response.status_code == 200:
                return idea_text(response.json()) if command == "/idea" else "ثبت شد."
            if response.status_code in {502, 503}:
                return "پژوهش آماده نشد؛ ارائه‌دهنده در دسترس نیست یا خروجی معتبر نداد."
            return "ثبت نشد؛ شناسه، قالب ورودی و وضعیت فعلی ایده را بررسی کنید."
        if text == "/ideas":
            response = self.studio.get("/items", headers=headers)
            response.raise_for_status()
            return ("\n".join(f"{i['id']}: {i['status']} {i['url']}"
                              for i in response.json()) or "ایده‌ای ثبت نشده است.")
        return HELP
