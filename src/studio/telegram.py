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
            r"(script|scriptview|scriptrevise|assets|voiceupload|screenupload|confirmvoice|confirmscreen|preview|videoview|exportvideo):([1-9][0-9]{0,18})",
            query.get("data", ""),
        )
        video_approval = re.fullmatch(
            r"videoapprove:([1-9][0-9]{0,18}):([a-f0-9]{16})", query.get("data", "")
        )
        if video_approval:
            return {
                "from": query.get("from", {}),
                "chat": query.get("message", {}).get("chat", {}),
                "text": f"/approvevideo {video_approval[1]} {video_approval[2]}",
            }
        script_approval = re.fullmatch(
            r"scriptapprove:([1-9][0-9]{0,18}):([a-f0-9]{16})", query.get("data", "")
        )
        if script_action or script_approval:
            command = (
                f"/approvescript {script_approval[1]} {script_approval[2]}"
                if script_approval
                else f"/{ {'script': 'script', 'scriptview': 'scriptview', 'scriptrevise': 'revisescript', 'assets': 'assets', 'voiceupload': 'voiceupload', 'screenupload': 'screenupload', 'confirmvoice': 'confirmvoice', 'confirmscreen': 'confirmscreen', 'preview': 'preview', 'videoview': 'videoview', 'exportvideo': 'exportvideo'}[script_action[1]] } {script_action[2]}"
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

    def video_reply(self, data, actor, exported=False):
        if data["state"] == "processing":
            return "پیش‌نمایش در حال ساخته‌شدن است؛ کار تکراری شروع نمی‌شود."
        if not data.get("sha256"):
            return "پیش‌نمایش هنوز آماده نیست."
        response = self.studio.get(
            f"/renders/{data['id']}/file?variant={'export' if exported else 'preview'}",
            headers=actor,
        )
        if response.status_code != 200:
            return "فایل خروجی آماده یا تأیید نیست."
        if len(response.content) > 45 * 1024**2:
            return "خروجی از سقف ارسال خصوصی تلگرام بزرگ‌تر است؛ نسخهٔ کم‌حجم‌تر لازم است."
        text = (
            "خروجی تأییدشده برای انتشار دستی آماده است؛ خودکار منتشر نشده است."
            if exported
            else "پیش‌نمایش خصوصی آماده است: ۱۰۸۰×۱۹۲۰، صدای ضبط‌شدهٔ خودت، بدون زیرنویس یا انتشار خودکار. ویدئو را کامل ببین."
        )
        keyboard = None
        if not exported:
            if data["metadata"]["duration_matches_script"]:
                keyboard = {
                    "inline_keyboard": [
                        [
                            {
                                "text": "تأیید همین ویدئو",
                                "callback_data": f"videoapprove:{data['id']}:{data['sha256'][:16]}",
                            }
                        ],
                        [{"text": "تغییر رسانه", "callback_data": f"assets:{data['script_id']}"}],
                    ]
                }
            else:
                text += " مدت صدا با سناریو مطابقت ندارد؛ برای تأیید نهایی ضبط کامل لازم است."
                keyboard = {
                    "inline_keyboard": [
                        [{"text": "ارسال ضبط کامل", "callback_data": f"assets:{data['script_id']}"}]
                    ]
                }
        reply = BotReply(text, keyboard)
        reply.video_preview = response.content
        reply.video_document = exported
        return reply

    def progress_message(self, update):
        message = self.authorize(update)
        text = message.get("text", "").strip()
        if text.startswith("/preview "):
            return "در حال ساخت پیش‌نمایش با صدای خودت و ضبط صفحه هستم. هیچ انتشار خودکاری انجام نمی‌شود."
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
        if text.startswith("/preview "):
            script_id = text.removeprefix("/preview ").strip()
            if not script_id.isdigit():
                return "شناسه سناریو لازم است."
            assets = self.studio.get(f"/scripts/{script_id}/assets", headers=actor)
            if assets.status_code != 200:
                return "رسانه‌های سناریو پیدا نشد."
            voice = [a for a in assets.json() if a["kind"] == "voice" and a["state"] == "processed"]
            screen = [a for a in assets.json() if a["kind"] == "screen"]
            if not voice or not screen:
                return BotReply(
                    "برای پیش‌نمایش، صدای پردازش‌شده و ضبط صفحهٔ همین سناریو لازم است.",
                    {
                        "inline_keyboard": [
                            [{"text": "بارگذاری رسانه", "callback_data": f"assets:{script_id}"}]
                        ]
                    },
                )
            response = self.studio.post(
                f"/scripts/{script_id}/preview",
                json={"voice_asset_id": voice[-1]["id"], "screen_asset_id": screen[-1]["id"]},
                headers=actor,
            )
            if response.status_code != 200:
                return "ساخت پیش‌نمایش انجام نشد؛ تأیید سناریو، مدت ضبط صفحه و کامل‌بودن صدای واقعی را بررسی کن."
            return self.video_reply(response.json(), actor)
        if text.startswith(("/videoview ", "/exportvideo ", "/approvevideo ")):
            parts = text.split()
            if len(parts) < 2 or not parts[1].isdigit():
                return "شناسه ویدئو لازم است."
            response = self.studio.get(f"/renders/{parts[1]}", headers=actor)
            if response.status_code != 200:
                return "ویدئو پیدا نشد."
            data = response.json()
            if parts[0] == "/videoview":
                return self.video_reply(data, actor)
            if parts[0] == "/approvevideo":
                if len(parts) != 3 or not data.get("sha256") or parts[2] != data["sha256"][:16]:
                    return "دکمه با محتوای ویدئو مطابقت ندارد."
                result = self.studio.post(
                    f"/renders/{data['id']}/approve", json={"sha256": data["sha256"]}, headers=actor
                )
                if result.status_code != 200:
                    return "این ویدئو برای تأیید نهایی مناسب نیست یا نسخهٔ جدیدتری وجود دارد."
                return BotReply(
                    "همین ویدئو تأیید شد. می‌توانی فایل اصلی را برای انتشار دستی بگیری؛ چیزی منتشر نشده است.",
                    {
                        "inline_keyboard": [
                            [
                                {
                                    "text": "دریافت فایل اصلی",
                                    "callback_data": f"exportvideo:{data['id']}",
                                }
                            ]
                        ]
                    },
                )
            exported = self.studio.post(f"/renders/{data['id']}/export", headers=actor)
            if exported.status_code != 200:
                return "ابتدا همین ویدئو باید تأیید نهایی شود."
            return self.video_reply(exported.json(), actor, exported=True)
        if text.startswith(
            ("/assets ", "/voiceupload ", "/screenupload ", "/confirmvoice ", "/confirmscreen ")
        ):
            command, _, script_id = text.partition(" ")
            if not script_id.isdigit():
                return "شناسه سناریو لازم است."
            response = self.studio.get(f"/scripts/{script_id}", headers=actor)
            if response.status_code != 200 or response.json()["state"] != "approved":
                return "ابتدا همین نسخهٔ سناریو را تأیید کن؛ فایل دریافت نمی‌شود."
            data = response.json()
            if command == "/assets":
                return BotReply(
                    "نوع فایل را انتخاب کن. اصل فایل خصوصی و محفوظ می‌ماند.",
                    {
                        "inline_keyboard": [
                            [
                                {
                                    "text": "صدای ضبط‌شدهٔ خودم",
                                    "callback_data": f"voiceupload:{script_id}",
                                },
                                {"text": "ضبط صفحه", "callback_data": f"screenupload:{script_id}"},
                            ],
                            [{"text": "ساخت پیش‌نمایش", "callback_data": f"preview:{script_id}"}],
                        ]
                    },
                )
            kind = "voice" if command in {"/voiceupload", "/confirmvoice"} else "screen"
            if command in {"/voiceupload", "/screenupload"}:
                return BotReply(
                    "فقط صدای واقعیِ ضبط‌شدهٔ خودت را بفرست؛ شبیه‌سازی صدا پذیرفته نیست."
                    if kind == "voice"
                    else "فقط ضبط صفحه‌ای را بفرست که متعلق به توست یا اجازهٔ استفاده‌اش را داری.",
                    {
                        "inline_keyboard": [
                            [
                                {
                                    "text": "تأیید می‌کنم؛ آمادهٔ ارسال فایل",
                                    "callback_data": f"{'confirmvoice' if kind == 'voice' else 'confirmscreen'}:{script_id}",
                                }
                            ]
                        ]
                    },
                )
            selected = self.studio.put(
                "/conversation",
                json={
                    "item_id": data["item_id"],
                    "upload_script_id": int(script_id),
                    "upload_kind": kind,
                },
                headers=actor,
            )
            if selected.status_code != 200:
                return "نسخهٔ جاری برای بارگذاری تأیید نیست؛ ابتدا سناریو را بررسی کن."
            return (
                "اکنون صدای خودت را به‌صورت ویس یا MP3/WAV/M4A/OGG، حداکثر ۲۰ مگابایت بفرست. پیش‌نمایش پردازش‌شده برمی‌گردد."
                if kind == "voice"
                else "اکنون ضبط صفحه را به‌صورت MP4 یا WebM، حداکثر ۲۰ مگابایت بفرست."
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
            return BotReply(
                "همین نسخهٔ سناریو تأیید شد. حالا می‌توانی صدای واقعی خودت و ضبط صفحه را بارگذاری کنی. هیچ انتشار خودکاری انجام نمی‌شود.",
                {
                    "inline_keyboard": [
                        [{"text": "بارگذاری رسانه", "callback_data": f"assets:{data['id']}"}]
                    ]
                },
            )
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
                        "AWAITING_ASSETS",
                        "EDITING",
                        "PREVIEW_READY",
                        "FINAL_APPROVED",
                        "EXPORTED",
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
