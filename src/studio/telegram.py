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
        actor = {"X-Studio-Actor": f"telegram:{message['from']['id']}"}
        text = message.get("text", "").strip()
        if text.startswith("https://"):
            response = self.studio.post("/items", json={"url": text}, headers=actor)
            if response.status_code != 200:
                return "لینک معتبر یوتیوب یا اینستاگرام لازم است."
            return f"شناسه ایده: {response.json()['id']} — متن مجاز ویدئو را در سامانه ثبت کنید."
        if text.startswith("/transcript "):
            # Three lines: command + ID, provenance, authorized transcript.
            parts = text.split("\n", 2)
            item_id = parts[0].removeprefix("/transcript ").strip()
            if (
                len(parts) != 3
                or not item_id.isdigit()
                or not parts[1].strip()
                or not parts[2].strip()
            ):
                return "سه خط بفرستید: /transcript ID سپس منشأ مجوز، سپس متن ویدئو."
            response = self.studio.put(
                f"/items/{item_id}/transcript",
                json={"provenance": parts[1], "text": parts[2]},
                headers=actor,
            )
            return (
                "متن مجاز ثبت شد."
                if response.status_code == 200
                else "ثبت متن انجام نشد؛ وضعیت ایده را بررسی کنید."
            )
        if text.startswith(("/analyze ", "/metadata ")):
            command, _, item_id = text.partition(" ")
            if not item_id.isdigit():
                return "شناسه عددی ایده لازم است."
            action = "research" if command == "/analyze" else "metadata"
            response = self.studio.post(f"/items/{item_id}/{action}", headers=actor)
            return (
                "انجام شد؛ /ideas را ببینید."
                if response.status_code == 200
                else "اطلاعات یا سرویس لازم در دسترس نیست؛ نتیجه‌ای ساخته نشد."
            )
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
            response = self.studio.post(
                f"/items/{item_id}/transition", json={"status": status}, headers=actor
            )
            return "ثبت شد." if response.status_code == 200 else "تغییر وضعیت مجاز نیست."
        if text == "/ideas":
            response = self.studio.get("/items")
            response.raise_for_status()
            return (
                "\n".join(f"{i['id']}: {i['status']} {i['url']}" for i in response.json()[:10])
                or "ایده‌ای ثبت نشده است."
            )
        return "لینک ویدئو را ارسال کنید. /ideas /metadata ID /transcript ID /analyze ID /approve ID /reject ID /save ID /research ID"
