"""Authorized, size-bounded Telegram asset intake; no scraping or arbitrary file URLs."""

from .media import AUDIO_LIMIT, MIMES
from .telegram import BotReply

TELEGRAM_LIMIT = AUDIO_LIMIT


def receive_media(gateway, studio, telegram, event):
    message = gateway.authorize(event)
    actor = {"X-Studio-Actor": f"telegram:{message['from']['id']}"}
    document = message.get("document", {})
    if document.get("mime_type") == "text/plain":
        size = document.get("file_size")
        if not isinstance(size, int) or not 0 < size <= 128 * 1024:
            return "فایل لینک‌ها باید UTF-8 و حداکثر ۱۲۸ کیلوبایت باشد."
        data = bytearray()
        with telegram.download(document["file_id"], size) as chunks:
            for chunk in chunks:
                data.extend(chunk)
                if len(data) > 128 * 1024:
                    return "فایل لینک‌ها بیش از سقف مجاز است."
        try:
            links = bytes(data).decode("utf-8-sig").strip().splitlines()
        except UnicodeDecodeError:
            return "فایل لینک‌ها باید متن UTF-8 باشد."
        if not 1 <= len(links) <= 200 or not all(
            line.strip().startswith("https://") for line in links
        ):
            return "در فایل فقط ۱ تا ۲۰۰ لینک یوتیوب بنویس؛ هر لینک در یک خط."
        return gateway.handle(
            {
                "message": {
                    "from": message["from"],
                    "chat": message["chat"],
                    "text": "/bulk\n" + "\n".join(links),
                }
            }
        )
    current = studio.get("/conversation", headers=actor)
    if current.status_code != 200 or not current.json().get("upload_script_id"):
        return "ابتدا سناریوی تأییدشده و نوع فایل را از دکمهٔ بارگذاری انتخاب کن؛ فایل دانلود نشد."
    context = current.json()
    kind = context["upload_kind"]
    script_id = context["upload_script_id"]
    script = studio.get(f"/scripts/{script_id}", headers=actor)
    item = studio.get(f"/items/{context['item_id']}", headers=actor)
    if (
        script.status_code != 200
        or script.json()["state"] != "approved"
        or item.status_code != 200
        or item.json()["status"]
        not in {"SCRIPT_APPROVED", "AWAITING_ASSETS", "PREVIEW_READY", "FINAL_APPROVED"}
    ):
        return "این سناریو اکنون تأیید نیست؛ فایل دانلود نشد."
    files = [
        message.get(key) for key in ["voice", "audio", "video", "document"] if message.get(key)
    ]
    if len(files) != 1:
        return "هر بار فقط یک فایل بفرست."
    file = files[0]
    size = file.get("file_size")
    mime = file.get("mime_type", "")
    if not isinstance(size, int) or not 0 < size <= TELEGRAM_LIMIT:
        return "برای بارگذاری تلگرام، فایل باید حداکثر ۲۰ مگابایت و اندازه‌اش مشخص باشد."
    if mime not in MIMES[kind]:
        return "نوع فایل با انتخابت مطابقت ندارد؛ صدا یا ضبط صفحهٔ مناسب را انتخاب کن."
    # Preflight approval before touching Telegram's file API; backend rechecks after streaming.
    with telegram.download(file["file_id"], size) as chunks:
        response = studio.post(
            f"/scripts/{script_id}/assets/{kind}",
            content=chunks,
            headers={
                **actor,
                "Content-Type": mime,
                "X-Rights-Confirmed": "1",
                "X-Founder-Voice": "1" if kind == "voice" else "0",
            },
        )
    if response.status_code != 200:
        return "فایل پذیرفته نشد؛ نوع واقعی، حجم، مدت یا نسخهٔ سناریو را بررسی کن. اصل فایل در تلگرام باقی است."
    asset = response.json()
    if kind == "screen":
        return f"ضبط صفحه با شناسهٔ #{asset['id']} ذخیره و بررسی شد؛ هنوز ویدئویی تولید یا منتشر نشده است."
    result = studio.post(f"/assets/{asset['id']}/process-audio", headers=actor)
    if result.status_code == 409:
        return "پردازش این صدا در جریان است یا نسخهٔ سناریو تغییر کرده؛ اصل فایل محفوظ است و کار تکراری ساخته نشد."
    if result.status_code == 503:
        return "اصل صدا محفوظ است؛ پردازشگر فعلاً مشغول است. بعداً همان فایل را دوباره بفرست؛ فایل تکراری ساخته نمی‌شود."
    if result.status_code != 200:
        return f"اصل صدا با شناسهٔ #{asset['id']} محفوظ است، اما پردازش موفق نبود. فایل ممکن است بی‌صدا یا ناقص باشد؛ ضبط را بررسی کن."
    preview = studio.get(f"/assets/{asset['id']}/file?variant=preview", headers=actor)
    preview.raise_for_status()
    if len(preview.content) > 20 * 1024**2:
        return "صدا پردازش شد؛ پیش‌نمایش برای ارسال در تلگرام بیش از حد بزرگ است."
    # The only founder asset required is narration. Generate original visuals and combine it now.
    rendered = gateway.handle(
        {
            "message": {
                "from": message["from"],
                "chat": message["chat"],
                "text": f"/preview {script_id}",
            }
        }
    )
    if isinstance(rendered, BotReply):
        reply = rendered
    else:
        reply = BotReply(
            str(rendered),
            {
                "inline_keyboard": [
                    [{"text": "تلاش مجدد ساخت ویدئو", "callback_data": f"preview:{script_id}"}]
                ]
            },
        )
    receipt = BotReply(
        "اصل صدا محفوظ است و نسخهٔ پردازش‌شده آماده شد.\n" + str(reply), reply.keyboard
    )
    receipt.__dict__.update(reply.__dict__)
    reply = receipt
    reply.audio_preview = preview.content
    return reply
