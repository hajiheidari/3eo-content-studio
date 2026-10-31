"""Private Telegram update handler. Network polling/delivery is deliberately opt-in."""


class TelegramGateway:
    def __init__(self, allowed_users: set[int], studio):
        if not allowed_users:
            raise ValueError("Approved Telegram user IDs required")
        self.allowed_users, self.studio = allowed_users, studio

    def handle(self, update: dict) -> str:
        message = update.get("message", {})
        if (
            message.get("from", {}).get("id") not in self.allowed_users
            or message.get("chat", {}).get("type") != "private"
        ):
            raise PermissionError("Unauthorized Telegram user or chat")
        text = message.get("text", "").strip()
        if text.startswith("https://"):
            response = self.studio.post("/items", json={"url": text})
            if response.status_code != 200:
                return "لینک معتبر یوتیوب یا اینستاگرام لازم است."
            return f"شناسه ایده: {response.json()['id']} — متن مجاز ویدئو را در سامانه ثبت کنید."
        if text.startswith(("/approve ", "/reject ", "/save ", "/research ")):
            command, _, item_id = text.partition(" ")
            if not item_id.isdigit():
                return "شناسه عددی ایده لازم است."
            status = {
                "/approve": "IDEA_APPROVED",
                "/reject": "REJECTED",
                "/save": "SAVED",
                "/research": "MORE_RESEARCH",
            }[command]
            response = self.studio.post(f"/items/{item_id}/transition", json={"status": status})
            return "ثبت شد." if response.status_code == 200 else "تغییر وضعیت مجاز نیست."
        if text == "/ideas":
            response = self.studio.get("/items")
            response.raise_for_status()
            return (
                "\n".join(f"{i['id']}: {i['status']} {i['url']}" for i in response.json())
                or "ایده‌ای ثبت نشده است."
            )
        return "لینک ویدئو را ارسال کنید. /ideas /approve ID /reject ID /save ID /research ID"
