import json

import pytest
from sqlalchemy import select
from sqlalchemy.orm import Session, sessionmaker
from test_scout_delivery import RESEARCH

from studio.similarity import ALGORITHM, backfill, compare, profile, tokens
from studio.storage import Item
from studio.telegram import TelegramGateway, idea_text

TEXT = (
    "Technical search analysis requires careful evidence collection before making reliable claims. "
    "Review crawl logs indexing coverage canonical signals internal links structured data rendering "
    "and performance measurements across multiple pages. Compare baseline results with controlled "
    "experiments record limitations separate observations from assumptions and explain practical "
    "changes without promising guaranteed rankings or inventing engagement metrics for source videos."
)
PERSIAN = (
    "برای بررسی فنی سایت ابتدا داده های خزش صفحه نمایه سازی لینک داخلی عنوان توضیح محتوا "
    "و سرعت بارگذاری را ثبت کنید سپس نتایج آزمایش کنترل شده محدودیت شواهد منبع فرضیه تغییر "
    "روش اندازه گیری خطا بازبینی و گزارش نهایی را با دقت مقایسه کنید"
)


def indexed(text=TEXT, research=None):
    return json.loads(profile(text, json.dumps(research) if research else None))


def post_item(client, code, text=TEXT):
    item = client.post("/items", json={"url": f"https://youtu.be/{code:011d}"}).json()["id"]
    assert client.put(f"/items/{item}/transcript", json={"text": text, "provenance": "test permission"}).status_code == 200
    return item


def gateway_update(text):
    return {"message": {"from": {"id": 123}, "chat": {"type": "private", "id": 123}, "text": text}}


def test_normalization_covers_persian_letters_digits_marks_spacing_and_case():
    assert tokens("كِتاب يک ۱۲٣ می‌شود SEO!") == tokens("کتاب یک 123 می شود seo")
    assert tokens("ＳＥＯ canonical") == tokens("seo CANONICAL")


def test_normalized_identical_text_matches():
    match = compare(indexed(TEXT), indexed(TEXT.upper().replace(".", "!")), "DISCOVERED", "DISCOVERED")
    assert match == {"basis": "transcript", "score": 1.0, "match": "same_normalized_text"}


def test_small_edit_is_advisory_near_match():
    changed = TEXT.replace("careful", "rigorous")
    match = compare(indexed(TEXT), indexed(changed), "DISCOVERED", "DISCOVERED")
    assert match["match"] == "high_lexical_overlap" and 0.8 <= match["score"] < 1


@pytest.mark.parametrize("other", [
    "A short unrelated generic SEO heading",
    " ".join(reversed(tokens(TEXT))),
    PERSIAN,
    TEXT + " " + " ".join(f"different{n}" for n in range(200)),
])
def test_generic_short_reordered_translated_and_excerpt_text_is_not_declared_duplicate(other):
    assert compare(indexed(TEXT), indexed(other), "DISCOVERED", "DISCOVERED") is None


def test_research_requires_more_than_same_title_and_ignores_pending_revision():
    research = RESEARCH | {"summary_fa": PERSIAN, "angle_fa": "آزمایش مستقل"}
    first = indexed("short", research)
    second = indexed("another short text", research)
    assert compare(first, second, "RESEARCHED", "SAVED")["basis"] == "research"
    assert compare(first, second, "MORE_RESEARCH", "RESEARCHED") is None
    assert compare(first, indexed("short", RESEARCH), "RESEARCHED", "RESEARCHED") is None


def test_profiles_are_bounded_and_do_not_duplicate_raw_transcript():
    data = indexed(" ".join(f"word{n}" for n in range(6000)))
    assert len(data["transcript"]["words"]) <= 128
    assert len(data["transcript"]["shingles"]) <= 256
    assert "word5999" not in json.dumps(data)
    assert len(json.dumps(data)) < 12000


def test_similarity_endpoint_profiles_refresh_and_never_mutate_status(client, app):
    first, second = post_item(client, 1), post_item(client, 2, TEXT.replace("careful", "rigorous"))
    before = client.get(f"/items/{second}").json()
    result = client.get(f"/items/{second}/similar").json()
    assert result["advisory_only"] and result["algorithm"] == ALGORITHM
    assert result["matches"][0]["id"] == first
    assert result["matches"][0]["basis"] == "transcript"
    assert result["source_version"] == before["version"]
    after = client.get(f"/items/{second}").json()
    assert after["version"] == before["version"] and after["status"] == "DISCOVERED"
    client.put(f"/items/{second}/transcript", json={"text": PERSIAN, "provenance": "permission"})
    assert client.get(f"/items/{second}/similar").json()["matches"] == []
    with Session(app.state.engine) as session:
        assert session.get(Item, first).similarity_profile is not None


def test_research_profile_refreshes_and_rejected_matches_remain_visible(client):
    first, second = post_item(client, 3, "short"), post_item(client, 4, "short")
    research = RESEARCH | {"summary_fa": PERSIAN}
    client.post(f"/items/{first}/research", json=research)
    client.post(f"/items/{second}/research", json=research)
    client.post(f"/items/{first}/transition", json={"status": "REJECTED"})
    match = client.get(f"/items/{second}/similar").json()["matches"][0]
    assert match["id"] == first and match["status"] == "REJECTED" and match["basis"] == "research"
    # A warning never rejects, merges or blocks a founder's deliberate approval.
    assert client.post(f"/items/{second}/transition", json={"status": "IDEA_APPROVED"}).status_code == 200


def test_report_snapshots_warning_without_excluding_ideas(client, monkeypatch):
    first, second = post_item(client, 5), post_item(client, 6)
    for item in (first, second):
        client.post(f"/items/{item}/research", json=RESEARCH)
    monkeypatch.setattr("studio.api.report_day", lambda _: "2026-10-31")
    report = client.post("/reports/prepare").json()
    assert len(report["ideas"]) == 2
    assert all(i["similarity"]["matches"] for i in report["ideas"])
    assert "هشدار بازبینی" in idea_text(report["ideas"][0])
    client.post(f"/items/{first}/transition", json={"status": "REJECTED"})
    assert client.post("/reports/prepare").json()["ideas"] == report["ideas"]


def test_legacy_index_backfill_is_explicit_and_bounded(client, app):
    with Session(app.state.engine) as session:
        session.add_all([Item(platform="youtube", content_id=f"{n:011d}",
                              url=f"https://youtu.be/{n:011d}", transcript=TEXT) for n in range(10, 13)])
        session.commit()
    current = post_item(client, 20)
    initial = client.get(f"/items/{current}/similar").json()
    assert initial["unindexed_count"] == 3 and initial["matches"] == []
    sessions = sessionmaker(app.state.engine, expire_on_commit=False)
    result = backfill(sessions, limit=2, batch_size=1)
    assert result["indexed"] == 2 and result["conflicts"] == 0
    updated = client.get(f"/items/{current}/similar").json()
    assert len(updated["matches"]) == 2 and updated["unindexed_count"] == 1
    assert backfill(sessions)["indexed"] == 1
    assert backfill(sessions)["indexed"] == 0
    with sessions() as session:
        assert all(i.status == "DISCOVERED" for i in session.scalars(select(Item)))


def test_similarity_scan_has_coverage_cursor_and_can_reach_old_records(client, app):
    profile_data = profile(TEXT, None)
    with Session(app.state.engine) as session:
        session.add_all([Item(platform="youtube", content_id=f"{n:011d}",
                              url=f"https://youtu.be/{n:011d}", transcript=TEXT,
                              similarity_profile=profile_data) for n in range(30, 232)])
        session.commit()
    current = post_item(client, 999)
    first = client.get(f"/items/{current}/similar").json()
    assert first["scanned"] == 200 and first["more_to_scan"] is True
    second = client.get(f"/items/{current}/similar", params={"before_id": first["next_before_id"]}).json()
    assert second["scanned"] == 2 and second["more_to_scan"] is False
    assert all(m["id"] < first["next_before_id"] for m in second["matches"])


@pytest.mark.parametrize("route", ["/items/999/similar", "/items?status=EXPORTED", "/items?limit=101",
                                   "/items/1/similar?limit=11", "/items?before_id=0"])
def test_invalid_filter_and_missing_item_requests_are_rejected(client, route):
    assert client.get(route).status_code in {404, 422}


def test_saved_approved_and_similarity_commands(client):
    first, second = post_item(client, 301), post_item(client, 302)
    for item in (first, second):
        client.post(f"/items/{item}/research", json=RESEARCH)
    client.post(f"/items/{first}/transition", json={"status": "SAVED"})
    client.post(f"/items/{second}/transition", json={"status": "IDEA_APPROVED"})
    bot = TelegramGateway({123}, client)
    saved = bot.handle(gateway_update("/saved"))
    approved = bot.handle(gateway_update("/approved"))
    assert f"{first}: SAVED" in saved and f"{second}:" not in saved
    assert f"{second}: IDEA_APPROVED" in approved and f"{first}:" not in approved
    assert f"/idea {first}" in bot.handle(gateway_update(f"/similar {second}"))
    assert "هشدار بازبینی" in bot.handle(gateway_update(f"/idea {second}"))


def test_list_cursor_is_stable_and_telegram_has_next_page(client, app):
    with Session(app.state.engine) as session:
        session.add_all([Item(platform="youtube", content_id=f"{n:011d}",
                              url=f"https://youtu.be/{n:011d}", status="SAVED") for n in range(400, 425)])
        session.commit()
    first = client.get("/items", params={"status": "SAVED", "limit": 20}).json()
    second = client.get("/items", params={"status": "SAVED", "limit": 20, "before_id": first[-1]["id"]}).json()
    assert len(first) == 20 and len(second) == 5
    assert not ({i["id"] for i in first} & {i["id"] for i in second})
    bot = TelegramGateway({123}, client)
    assert f"/saved {first[-1]['id']}" in bot.handle(gateway_update("/saved"))
    assert "ادامه:" not in bot.handle(gateway_update(f"/saved {first[-1]['id']}"))


def test_similarity_endpoints_require_auth(client):
    item = post_item(client, 777)
    assert client.get(f"/items/{item}/similar", headers={"Authorization": "Bearer wrong"}).status_code == 401
