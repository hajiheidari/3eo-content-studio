"""Complete, lossless Telegram review of an immutable script revision."""


def split_telegram(text, limit=3500):
    parts, current, units = [], [], 0
    for char in text:
        width = 2 if ord(char) > 0xFFFF else 1
        if units + width > limit:
            parts.append("".join(current))
            current, units = [], 0
        current.append(char)
        units += width
    if current:
        parts.append("".join(current))
    return parts


def script_review(script):
    content = script["content"]
    lines = [
        f"سناریو #{script['id']} — نسخهٔ {script['revision']} — ایدهٔ #{script['item_id']}",
        f"{content['title_fa']} | {content['duration_seconds']} ثانیه (زمان پیشنهادی)",
        "\nسه هوک پیشنهادی:",
    ]
    lines += [f"{n}. {hook}" for n, hook in enumerate(content["hooks_fa"], 1)]
    lines += ["\nمتن روایت با صدای خودت:", content["narration_fa"], "\nاستوری‌بورد ویدئو (تصویر شماتیک را سیستم می‌سازد):"]
    for shot in content["storyboard"]:
        visual = "ضبط صفحه" if shot["visual_type"] == "screen_recording" else "موشن گرافیک"
        lines.append(
            f"{shot['start_seconds']}–{shot['end_seconds']} ثانیه | {visual}\n"
            f"تصویر: {shot['visual_instruction_fa']}\nمتن روی تصویر: {shot['on_screen_fa']}"
        )
    lines += [
        "\nپیش از ضبط راستی‌آزمایی کن:",
        *[f"• {p}" for p in content["fact_check_fa"]],
        "\nمحدودیت شواهد منبع:",
        *content["source_limitations"],
        "\nدعوت به اقدام:",
        content["cta_fa"],
        "\nکپشن پیشنهادی:",
        content["caption_fa"],
        " ".join(content["hashtags"]),
        "\nمنابع:",
        *content["source_references"],
        "\nسناریو را تأیید کن و فقط متن روایت را با صدای خودت ضبط کن؛ تصویر و تدوین با سیستم است. ضبط صفحه لازم نیست. هیچ انتشار یا تولید صدایی انجام نشده است.",
    ]
    parts = split_telegram("\n".join(lines))
    keyboard = {
        "inline_keyboard": [
            [
                {
                    "text": "تأیید همین نسخهٔ سناریو",
                    "callback_data": f"scriptapprove:{script['id']}:{script['content_hash'][:16]}",
                },
                {"text": "درخواست اصلاح", "callback_data": f"scriptrevise:{script['id']}"},
            ]
        ]
    }
    return parts, keyboard
