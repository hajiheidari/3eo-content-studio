import json
from concurrent.futures import ThreadPoolExecutor

import httpx
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session, sessionmaker

from studio.api import create_app
from studio.metadata import SourceMetadata, YouTubeMetadata, reserve_quota
from studio.storage import Base, Item, Usage

URL = "https://youtu.be/abcdefghijk"
PAYLOAD = {"items": [{"id": "abcdefghijk", "snippet": {
    "title": "Source title", "channelTitle": "Creator", "publishedAt": "2026-10-20T08:00:00Z"}}]}


def adapter(handler):
    return YouTubeMetadata("test-only-key", httpx.MockTransport(handler))


def test_official_metadata_uses_fixed_endpoint_and_normalized_id():
    def handler(request):
        assert request.url.host == "www.googleapis.com"
        assert request.url.path == "/youtube/v3/videos"
        assert request.url.params["id"] == "abcdefghijk"
        assert request.url.params["part"] == "snippet"
        assert "description" not in request.url.params["fields"]
        return httpx.Response(200, json=PAYLOAD)
    metadata = adapter(handler).fetch(URL + "?tracking=ignored")
    assert metadata.author == "Creator"
    assert metadata.published_at.tzinfo is not None


@pytest.mark.parametrize("url", ["https://www.instagram.com/p/abc/", "https://127.0.0.1/",
                                  "https://youtube.com.evil.test/watch?v=abcdefghijk"])
def test_unsupported_or_hostile_url_never_calls_network(url):
    def handler(request):
        pytest.fail("Unsupported URL reached HTTP transport")
    with pytest.raises(ValueError):
        adapter(handler).fetch(url)


@pytest.mark.parametrize("status,body,headers,error", [
    (302, "", {"location": "http://127.0.0.1/secrets"}, RuntimeError),
    (429, "quota exhausted", {}, RuntimeError),
    (500, "test-only-key", {}, RuntimeError),
    (200, "x" * 65537, {"content-type": "application/json"}, ValueError),
    (200, "not JSON", {"content-type": "application/json"}, ValueError),
    (200, json.dumps(PAYLOAD), {"content-type": "text/html"}, ValueError),
    (200, '{"items":[]}', {"content-type": "application/json"}, RuntimeError),
])
def test_metadata_rejects_redirects_errors_oversize_and_invalid_payload(status, body, headers, error):
    requests = []
    def handler(request):
        requests.append(request)
        return httpx.Response(status, content=body, headers=headers)
    with pytest.raises(error) as exc:
        adapter(handler).fetch(URL)
    assert len(requests) == 1
    assert "test-only-key" not in str(exc.value)


def test_metadata_source_id_must_match():
    wrong = {"items": [{"id": "zzzzzzzzzzz", "snippet": PAYLOAD["items"][0]["snippet"]}]}
    with pytest.raises(ValueError):
        adapter(lambda _: httpx.Response(200, json=wrong)).fetch(URL)


def test_metadata_timeout_does_not_expose_key():
    def handler(request):
        raise httpx.ReadTimeout("test-only-key", request=request)
    with pytest.raises(RuntimeError) as exc:
        adapter(handler).fetch(URL)
    assert "test-only-key" not in str(exc.value)


def test_metadata_date_requires_timezone():
    with pytest.raises(ValueError):
        SourceMetadata(content_id="abcdefghijk", title="Title", author="Creator",
                       published_at="2026-10-20T08:00:00")


def test_metadata_disabled_does_not_consume_quota(client, app):
    item = client.post("/items", json={"url": URL}).json()["id"]
    assert client.post(f"/items/{item}/metadata").status_code == 503
    with Session(app.state.engine) as session:
        assert list(session.scalars(select(Usage))) == []


def test_metadata_cache_quota_manual_override_and_locked_state(tmp_path):
    calls = []
    def handler(request):
        calls.append(request)
        return httpx.Response(200, json=PAYLOAD)
    app = create_app(f"sqlite:///{tmp_path}/metadata.db", token="test-only",
                     metadata_provider=adapter(handler), metadata_daily_limit=1)
    Base.metadata.create_all(app.state.engine)
    try:
        with TestClient(app, headers={"Authorization": "Bearer test-only"}) as client:
            item = client.post("/items", json={"url": URL}).json()["id"]
            first = client.post(f"/items/{item}/metadata")
            assert first.status_code == 200 and first.json()["cached"] is False
            assert client.post(f"/items/{item}/metadata").json()["cached"] is True
            assert len(calls) == 1
            client.put(f"/items/{item}/transcript", json={"text": "Authorized", "provenance": "Permission"})
            assert client.get(f"/items/{item}").json()["author"] == "Creator"
            client.put(f"/items/{item}/transcript", json={"text": "Authorized", "provenance": "Permission",
                                                        "author": "Manual author"})
            assert client.get(f"/items/{item}").json()["author"] == "Manual author"
            assert client.get(f"/items/{item}").json()["metadata"]["author"] == "Creator"
            other = client.post("/items", json={"url": "https://youtu.be/zzzzzzzzzzz"}).json()["id"]
            assert client.post(f"/items/{other}/metadata").status_code == 429
            assert len(calls) == 1
            with Session(app.state.engine) as session:
                old = session.get(Item, item)
                data = json.loads(old.source_metadata)
                data["fetched_at"] = 0
                old.source_metadata, old.status = json.dumps(data), "RESEARCHED"
                session.commit()
            assert client.post(f"/items/{item}/metadata").status_code == 409
    finally:
        app.state.engine.dispose()


def test_failed_fetch_consumes_reservation_but_never_partial_metadata(tmp_path):
    app = create_app(f"sqlite:///{tmp_path}/failure.db", token="test-only", metadata_daily_limit=1,
                     metadata_provider=adapter(lambda _: httpx.Response(200, json={"items": []})))
    Base.metadata.create_all(app.state.engine)
    try:
        with TestClient(app, headers={"Authorization": "Bearer test-only"}) as client:
            item = client.post("/items", json={"url": URL}).json()["id"]
            assert client.post(f"/items/{item}/metadata").status_code == 503
            assert client.get(f"/items/{item}").json()["metadata"] is None
            assert client.post(f"/items/{item}/metadata").status_code == 429
    finally:
        app.state.engine.dispose()


def test_quota_reservations_enforce_concurrent_limit(app):
    sessions = sessionmaker(app.state.engine)
    with ThreadPoolExecutor(max_workers=5) as pool:
        granted = list(pool.map(lambda _: reserve_quota(sessions, "2026-10-31", 3), range(10)))
    assert sum(granted) == 3
    with Session(app.state.engine) as session:
        assert session.get(Usage, "youtube:2026-10-31").count == 3
    assert reserve_quota(sessions, "2026-11-01", 3)
