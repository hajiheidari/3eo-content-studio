"""Compact Persian Telegram report formatting."""


def format_report(day, ideas):
    # One compact message avoids partial multi-message delivery and caps Telegram UTF-16 length.
    lines = [f"گزارش ایده‌های 3EO — {day}"]
    for idea in ideas[:5]:
        r = idea["research"]
        lines.append(
            f"\n#{idea['id']} {r['title_fa'][:40]}\n{idea['url']}\n"
            f"سازنده: {(idea.get('author') or 'نامشخص')[:20]} | تاریخ: {(idea.get('published_at') or 'نامشخص')[:20]}\n"
            f"امتیاز: {idea['score']} | اطمینان: {r.get('confidence') if r.get('confidence') is not None else 'ثبت نشده'}\nخلاصه: {r['summary_fa'][:45]}\n"
            f"اهمیت: {(r.get('why_it_matters_fa') or 'ثبت نشده')[:30]}\n"
            f"ارتباط با 3EO: {(r.get('tool_connection_fa') or 'ثبت نشده')[:30]}\n"
            f"قالب: {(r.get('recommended_format_fa') or 'ثبت نشده')[:20]}\n"
            f"زاویه: {r['angle_fa'][:45]}\nمحدودیت: {'؛ '.join(r['limitations'])[:50]}\n"
            f"/approve {idea['id']} /reject {idea['id']} /save {idea['id']} /research {idea['id']}"
        )
    if not ideas:
        lines.append("ایده پژوهش‌شده‌ای آماده نیست؛ لینک یا متن مجاز ارسال کنید.")
    text = "\n".join(lines)
    # Hard bound, including astral Unicode characters.
    return text.encode("utf-16-le")[:7800].decode("utf-16-le", errors="ignore")


def report_keyboard(ideas):
    return {
        "inline_keyboard": [
            [
                {"text": f"{idea['id']} تأیید", "callback_data": f"approve:{idea['id']}"},
                {"text": "رد", "callback_data": f"reject:{idea['id']}"},
                {"text": "ذخیره", "callback_data": f"save:{idea['id']}"},
                {"text": "پژوهش بیشتر", "callback_data": f"research:{idea['id']}"},
            ]
            for idea in ideas[:5]
        ]
    }
