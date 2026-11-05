"""Private Telegram update handler. Network polling/delivery is deliberately opt-in."""

import re

from .reports import format_report, report_keyboard
from .script_messages import script_review


class BotReply(str):
    def __new__(cls, text, keyboard=None, parts=None):
        reply = super().__new__(cls, text)
        reply.keyboard = keyboard
        reply.parts = parts
        return reply


class TelegramGateway:
    def __init__(self, allowed_users: set[int], studio):
        if not allowed_users:
            raise ValueError("Approved Telegram user IDs required")
        self.allowed_users, self.studio = allowed_users, studio

    def message(self, update):
        if "callback_query" not in update:
            return update.get("message", {})
        query = update["callback_query"]
        script_action = re.fullmatch(
            r"(script|scriptview|scriptrevise):([1-9][0-9]{0,18})", query.get("data", "")
        )
        script_approval = re.fullmatch(
            r"scriptapprove:([1-9][0-9]{0,18}):([a-f0-9]{16})", query.get("data", "")
        )
        if script_action or script_approval:
            command = (
                f"/approvescript {script_approval[1]} {script_approval[2]}"
                if script_approval
                else f"/{ {'script': 'script', 'scriptview': 'scriptview', 'scriptrevise': 'revisescript'}[script_action[1]] } {script_action[2]}"
            )
            return {
                "from": query.get("from", {}),
                "chat": query.get("message", {}).get("chat", {}),
                "text": command,
            }
        match = re.fullmatch(
            r"(approve|reject|save|research|analyze|description|transcript|usertext):([1-9][0-9]{0,18})",
            query.get("data", ""),
        )
        if not match:
            raise PermissionError("Unsupported callback")
        action = match[1]
        command = (
            f"/evidence {match[2]} { {'description': 'description', 'transcript': 'transcript', 'usertext': 'user_text'}[action] }"
            if action in {"description", "transcript", "usertext"}
            else f"/{action} {match[2]}"
        )
        return {
            "from": query.get("from", {}),
            "chat": query.get("message", {}).get("chat", {}),
            "text": command,
        }

    def recipient(self, update):
        return self.message(update)["from"]["id"]

    def authorize(self, update):
        message = self.message(update)
        if (
            message.get("from", {}).get("id") not in self.allowed_users
            or message.get("chat", {}).get("type") != "private"
        ):
            raise PermissionError("Unauthorized Telegram user or chat")
        return message

    def analyze(self, item_id, actor):
        response = self.studio.post(f"/items/{item_id}/research", headers=actor)
        if response.status_code not in {200, 409}:
            return BotReply(
                "متن ذخیره است، اما تحلیل انجام نشد و نتیجه‌ای ساخته نشد. اگر مدل آماده نیست، بعد از راه‌اندازی آن دکمهٔ تلاش مجدد را بزن. اگر این ایده قبلاً پژوهش شده، جزئیاتش را ببین.",
                {
                    "inline_keyboard": [
                        [{"text": "تلاش مجدد تحلیل", "callback_data": f"analyze:{item_id}"}]
                    ]
                },
            )
        detail = self.studio.get(f"/items/{item_id}", headers=actor)
        detail.raise_for_status()
        idea = detail.json()
        r = idea["research"]
        if not r:
            return "متن کافی برای پژوهش ثبت نشده است. توضیحات یا رونوشت مجاز را بفرست؛ نتیجه‌ای ساخته نشد."
        return BotReply(
            f"پژوهش ایدهٔ #{item_id}\n{r['title_fa']}\n\nخلاصه: {r['summary_fa'][:1500]}\n"
            f"زاویهٔ مستقل 3EO: {r['angle_fa'][:800]}\n"
            f"ادعاهای نیازمند بررسی: {'؛ '.join(r['claims_to_verify'])[:500]}\n"
            f"محدودیت‌ها: {'؛ '.join(r['limitations'])[:600]}\nامتیاز: {idea['score']}\n"
            "برای ادامه، ایده را تأیید یا رد کن. تأیید به معنی انتشار نیست.",
            report_keyboard([idea]),
        )

    def script(self, item_id, actor):
        response = self.studio.post(f"/items/{item_id}/scripts", headers=actor)
        if response.status_code != 200:
            return "ساخت سناریو انجام نشد؛ ایده باید تأیید شده و سرویس نویسنده آماده باشد. تأیید ایده از بین نرفته است."
        return self.script_reply(response.json())

    def script_reply(self, data):
        if data["state"] == "generating":
            return "ساخت سناریو در جریان است؛ درخواست دیگری ساخته نمی‌شود."
        if not data.get("content"):
            return "این سناریو هنوز آماده نیست."
        parts, keyboard = script_review(data)
        return BotReply(parts[0], keyboard, parts=parts)

    def progress_message(self, update):
        message = self.authorize(update)
        text = message.get("text", "").strip()
        if text.startswith("/script "):
            return (
                "در حال آماده‌سازی سناریو برای بازبینی هستم؛ این مرحله ممکن است چند دقیقه طول بکشد."
            )
        if text and not text.startswith(("/", "https://")):
            if 80 <= len(text) <= 12000:
                return "متن دریافت شد؛ در حال آماده‌سازی نتیجه هستم. آن را همین‌جا می‌فرستم."
            if 5 <= len(text) <= 1000:
                user = message["from"]["id"]
                current = self.studio.get(
                    "/conversation", headers={"X-Studio-Actor": f"telegram:{user}"}
                )
                if current.status_code == 200 and current.json().get("pending_script_id"):
                    return "درخواست اصلاح دریافت شد؛ نسخهٔ تازه را آماده می‌کنم."
        return None

    def handle(self, update: dict) -> str:
        message = self.authorize(update)
        actor = {"X-Studio-Actor": f"telegram:{message['from']['id']}"}
        text = message.get("text", "").strip()
        text = {"ایده جدید": "/new", "فهرست ایده‌ها": "/ideas", "گزارش امروز": "/today"}.get(
            text, text
        )
        if text in {"/start", "/new"}:
            if text == "/new":
                self.studio.delete("/conversation", headers=actor).raise_for_status()
            return BotReply(
                "لینک یا متن مستقلِ قابل استفاده‌ات را بفرست. بعد از لینک، توضیحات یا رونوشت را در پیام بعدی بفرست تا پژوهش شود. برای شروع موضوع دیگری، «ایده جدید» را بزن.",
                {
                    "keyboard": [
                        [{"text": "ایده جدید"}, {"text": "فهرست ایده‌ها"}],
                        [{"text": "گزارش امروز"}],
                    ],
                    "resize_keyboard": True,
                },
            )
        if text.startswith("/script "):
            item_id = text.removeprefix("/script ").strip()
            return (
                self.script(int(item_id), actor)
                if item_id.isdigit()
                else "شناسه عددی ایده لازم است."
            )
        if text.startswith(("/scriptview ", "/revisescript ", "/approvescript ")):
            parts = text.split()
            if len(parts) < 2 or not parts[1].isdigit():
                return "شناسه سناریو مشخص نیست."
            response = self.studio.get(f"/scripts/{parts[1]}", headers=actor)
            if response.status_code != 200:
                return "سناریو پیدا نشد."
            data = response.json()
            if parts[0] == "/scriptview":
                return self.script_reply(data)
            if parts[0] == "/revisescript":
                self.studio.put(
                    "/conversation",
                    json={"item_id": data["item_id"], "pending_script_id": data["id"]},
                    headers=actor,
                ).raise_for_status()
                return "تغییرات موردنظرت را در پیام بعد بنویس؛ نسخهٔ تازه برای بررسی ساخته می‌شود و تأیید قبلی به آن منتقل نمی‌شود."
            if (
                len(parts) != 3
                or not data.get("content_hash")
                or parts[2] != data["content_hash"][:16]
            ):
                return "دکمه با محتوای سناریو مطابقت ندارد؛ نسخهٔ فعلی را دوباره ببین."
            result = self.studio.post(
                f"/scripts/{data['id']}/approve",
                json={"content_hash": data["content_hash"]},
                headers=actor,
            )
            if result.status_code != 200:
                return "این نسخه دیگر در انتظار تأیید نیست؛ نسخهٔ تازه را بررسی کن."
            return "همین نسخهٔ سناریو تأیید شد. هیچ انتشار یا تولید صدایی انجام نشده است؛ مرحلهٔ دریافت و پردازش رسانه هنوز فعال نشده است."
        if text.startswith("https://"):
            response = self.studio.post("/items", json={"url": text}, headers=actor)
            if response.status_code != 200:
                return "لینک معتبر یوتیوب یا اینستاگرام لازم است."
            item_id = response.json()["id"]
            selected = self.studio.put(
                "/conversation",
                json={"item_id": item_id, "evidence_kind": "description"},
                headers=actor,
            )
            selected.raise_for_status()
            metadata_response = self.studio.post(f"/items/{item_id}/metadata", headers=actor)
            metadata_note = (
                "اطلاعات عمومی منبع دریافت شد؛ این به معنی دسترسی به متن ویدئو نیست."
                if metadata_response.status_code == 200
                else "دسترسی خودکار به اطلاعات این منبع فراهم نشد؛ چیزی از محتوای آن حدس نمی‌زنم."
            )
            return BotReply(
                f"شناسه ایده: {item_id}\n{metadata_note}\nلینک ثبت شد. توضیحات ویدئو را همین‌جا بفرست؛ خودکار به همین ایده وصل می‌شود و تحلیل می‌شود. برای رونوشت یا متن مستقل، نوع متن را انتخاب کن. فقط محتوایی را بفرست که حق استفاده از آن را داری. از عنوان تنها، تحلیل کامل ویدئو نمی‌سازیم.",
                {
                    "inline_keyboard": [
                        [
                            {"text": "توضیحات ویدئو", "callback_data": f"description:{item_id}"},
                            {"text": "رونوشت مجاز", "callback_data": f"transcript:{item_id}"},
                        ]
                    ]
                },
            )
        if text.startswith("/evidence "):
            parts = text.split()
            if (
                len(parts) != 3
                or not parts[1].isdigit()
                or parts[2] not in {"description", "transcript", "user_text"}
            ):
                return "نوع متن مشخص نیست."
            selected = self.studio.put(
                "/conversation",
                json={"item_id": int(parts[1]), "evidence_kind": parts[2]},
                headers=actor,
            )
            if selected.status_code != 200:
                return "ایده پیدا نشد."
            return "متن را در پیام بعدی بفرست؛ فقط متنی که حق استفاده از آن را داری. تحلیل به همین شواهد محدود خواهد بود."
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
            if command == "/analyze":
                return self.analyze(int(item_id), actor)
            action = "metadata"
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
            if response.status_code == 200 and status == "MORE_RESEARCH":
                self.studio.put(
                    "/conversation",
                    json={"item_id": int(item_id), "evidence_kind": "description"},
                    headers=actor,
                ).raise_for_status()
                return "پژوهش بیشتر ثبت شد. متن تکمیلی را بفرست؛ به همین ایده وصل می‌شود. اگر رونوشت است نوع متن را انتخاب کن."
            if response.status_code == 409:
                existing = self.studio.get(f"/items/{item_id}", headers=actor)
                if (
                    existing.status_code == 200
                    and status == "IDEA_APPROVED"
                    and existing.json()["status"]
                    in {
                        "SCRIPT_GENERATING",
                        "SCRIPT_DRAFT",
                        "SCRIPT_APPROVED",
                        "REVISION_REQUESTED",
                    }
                ):
                    return BotReply(
                        "ایده قبلاً تأیید شده و وارد مرحلهٔ سناریو شده است؛ نیازی به تأیید دوبارهٔ ایده نیست.",
                        {
                            "inline_keyboard": [
                                [{"text": "دیدن سناریو", "callback_data": f"script:{item_id}"}]
                            ]
                        },
                    )
                if existing.status_code == 200 and existing.json()["status"] == status:
                    return f"این وضعیت برای ایدهٔ #{item_id} قبلاً ثبت شده است؛ نیازی به کلیک دوباره نیست."
            if response.status_code == 200 and status == "IDEA_APPROVED":
                return BotReply(
                    f"ایدهٔ #{item_id} تأیید شد. برای آماده‌سازی پیش‌نویس، «ساخت سناریو» را بزن. هیچ انتشار خودکاری انجام نمی‌شود.",
                    {
                        "inline_keyboard": [
                            [{"text": "ساخت سناریو", "callback_data": f"script:{item_id}"}]
                        ]
                    },
                )
            return "ثبت شد." if response.status_code == 200 else "تغییر وضعیت مجاز نیست."
        if text == "/today":
            response = self.studio.get("/reports/today")
            if response.status_code == 404:
                return "گزارش امروز هنوز آماده نشده است."
            response.raise_for_status()
            data = response.json()
            return format_report(data["day"], data["ideas"])
        if text.startswith("/idea "):
            item_id = text.removeprefix("/idea ").strip()
            if not item_id.isdigit():
                return "شناسه عددی ایده لازم است."
            response = self.studio.get(f"/items/{item_id}")
            if response.status_code == 404:
                return "ایده پیدا نشد."
            response.raise_for_status()
            idea = response.json()
            if not idea["research"]:
                return f"ایده #{idea['id']} — {idea['status']}\n{idea['url']}\nپژوهش هنوز انجام نشده است."
            r = idea["research"]
            return (
                f"#{idea['id']} {r['title_fa']}\n{idea['url']}\n"
                f"خلاصه: {r['summary_fa']}\nزاویه پیشنهادی: {r['angle_fa']}\n"
                f"ادعاهای نیازمند بررسی: {'؛ '.join(r['claims_to_verify'])}\n"
                f"محدودیت‌ها: {'؛ '.join(r['limitations'])}\nامتیاز: {idea['score']}"
            )
        if text == "/ideas":
            response = self.studio.get("/items")
            response.raise_for_status()
            return (
                "\n".join(f"{i['id']}: {i['status']} {i['url']}" for i in response.json()[:10])
                or "ایده‌ای ثبت نشده است."
            )
        if text and not text.startswith("/"):
            current = self.studio.get("/conversation", headers=actor)
            context = current.json() if current.status_code == 200 else {}
            if context.get("pending_script_id"):
                if not 5 <= len(text) <= 1000:
                    return "توضیح اصلاح را بین ۵ تا ۱۰۰۰ نویسه بنویس."
                revised = self.studio.post(
                    f"/scripts/{context['pending_script_id']}/revise",
                    json={"notes": text},
                    headers=actor,
                )
                if revised.status_code != 200:
                    return "این نسخه قابل اصلاح نیست؛ نسخهٔ فعلی را بررسی کن."
                self.studio.put(
                    "/conversation",
                    json={"item_id": context["item_id"], "pending_script_id": None},
                    headers=actor,
                ).raise_for_status()
                return self.script(context["item_id"], actor)
            if len(text) < 80:
                return "این متن برای پژوهش کافی نیست و ممکن است فقط عنوان باشد. توضیحات ویدئو، رونوشت مجاز یا متن مستقلِ دست‌کم ۸۰ نویسه‌ای را بفرست؛ لازم نیست دستور بنویسی."
            if len(text) > 12000:
                return "برای این نسخه، متن را به یک بخش مستقل تا ۱۲۰۰۰ نویسه محدود کن؛ متن بلند بدون اطلاع تو بریده نمی‌شود."
            current = self.studio.get("/conversation", headers=actor)
            if current.status_code == 200:
                context = current.json()
                item_id, kind = context["item_id"], context["evidence_kind"]
                saved = self.studio.put(
                    f"/items/{item_id}/evidence",
                    json={
                        "text": text,
                        "kind": kind,
                        "provenance": f"User supplied {kind}; sender {actor['X-Studio-Actor']}; rights not independently verified",
                    },
                    headers=actor,
                )
                if saved.status_code != 200:
                    return "متن جایگزین نشد؛ این ایده پژوهش شده یا تأیید شده است. برای تغییر متن، ابتدا «پژوهش بیشتر» را انتخاب کن."
            elif current.status_code == 404:
                saved = self.studio.post(
                    "/items/text",
                    json={
                        "text": text,
                        "kind": "user_text",
                        "provenance": f"Independent text supplied by {actor['X-Studio-Actor']}; rights not independently verified",
                    },
                    headers=actor,
                )
                saved.raise_for_status()
                item_id = saved.json()["id"]
                self.studio.put(
                    "/conversation",
                    json={"item_id": item_id, "evidence_kind": "user_text"},
                    headers=actor,
                ).raise_for_status()
            else:
                current.raise_for_status()
            return self.analyze(item_id, actor)
        return "لینک یا متن قابل‌استفاده‌ات را بفرست. توضیحات یا رونوشت بعدی به همان لینک متصل می‌شود. /today /ideas /idea ID"
