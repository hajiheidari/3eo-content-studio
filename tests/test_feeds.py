import httpx
import pytest
from fastapi.testclient import TestClient

from studio.api import create_app
from studio.feeds import FeedReader, feed_url, parse_feed
from studio.integrations import IntegrationError
from studio.storage import Base

ATOM = b"""<feed xmlns="http://www.w3.org/2005/Atom"><entry>
<title>Official search update</title><link href="https://developers.google.com/search/blog/test"/>
<author><name>Search team</name></author><published>2026-11-03</published>
<summary>Public educational excerpt</summary></entry></feed>"""


@pytest.mark.parametrize(
    "url",
    [
        "http://developers.google.com/feed",
        "https://developers.google.com.evil.test/feed",
        "https://127.0.0.1/feed",
        "https://developers.google.com:443/feed",
        "https://user@developers.google.com/feed",
        "https://developers.google.com/feed#fragment",
    ],
)
def test_feed_url_safety(url):
    with pytest.raises(ValueError):
        feed_url(url)


def test_atom_and_rss_parsing():
    entry = parse_feed(ATOM)[0]
    assert entry.author == "Search team" and entry.published_at == "2026-11-03"
    assert entry.excerpt == "Public educational excerpt"
    rss = b"<rss><channel><item><title>News</title><link>https://blog.google/test</link><description>Excerpt</description></item></channel></rss>"
    assert parse_feed(rss)[0].published_at is None


@pytest.mark.parametrize(
    "data",
    [b'<!DOCTYPE rss [<!ENTITY x "bomb">]><rss>&x;</rss>', b"<broken", b"<html/>", b"x" * 524289],
)
def test_unsafe_xml(data):
    with pytest.raises(IntegrationError):
        parse_feed(data)


def test_link_to_private_host_is_discarded():
    assert (
        parse_feed(
            ATOM.replace(
                b"https://developers.google.com/search/blog/test", b"http://127.0.0.1/admin"
            )
        )
        == []
    )


def test_feed_redirect_not_followed():
    calls = []

    def handler(request):
        calls.append(request)
        return httpx.Response(302, headers={"Location": "http://127.0.0.1"})

    reader = FeedReader(httpx.Client(transport=httpx.MockTransport(handler)))
    with pytest.raises(IntegrationError):
        reader.fetch("https://developers.google.com/feed")
    assert len(calls) == 1


def test_ingestion_is_idempotent_and_disabled_sources_do_not_fetch(tmp_path):
    calls = []

    def handler(request):
        calls.append(request)
        return httpx.Response(200, content=ATOM)

    app = create_app(
        f"sqlite:///{tmp_path}/feeds.db",
        token="test",
        feeds=FeedReader(httpx.Client(transport=httpx.MockTransport(handler))),
    )
    Base.metadata.create_all(app.state.engine)
    with TestClient(app, headers={"Authorization": "Bearer test"}) as client:
        body = {"name": "Google official", "url": "https://developers.google.com/feed"}
        source = client.post("/sources", json=body).json()["id"]
        assert client.post(f"/sources/{source}/refresh").json()["added"] == 1
        assert client.post(f"/sources/{source}/refresh").json()["added"] == 0
        item = client.get("/items").json()[0]
        assert item["status"] == "DISCOVERED"
        assert item["metadata_provenance"].startswith("Official public feed")
        assert item["research"] is None
        client.post("/sources", json={**body, "enabled": False})
        assert client.post(f"/sources/{source}/refresh").status_code == 409
        assert len(calls) == 2
    app.state.engine.dispose()
