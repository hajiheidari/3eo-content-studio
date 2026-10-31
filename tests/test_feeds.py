"""Public feeds are a bounded, untrusted inbox, independent from source research."""

import xml.etree.ElementTree as ET
from concurrent.futures import ThreadPoolExecutor

import httpx
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from studio.api import create_app
from studio.feeds import (
    MAX_BYTES,
    SOURCES,
    FeedClient,
    FeedCoolingDown,
    FeedResponse,
    FeedUnavailable,
    article_url,
    collect,
    parse_feed,
)
from studio.storage import Base, FeedEntry, FeedState, Item, database

URL = "https://developers.google.com/search/blog/2026/10/test-post"
SOURCE = "google-search-central"
RSS = f'''<rss version="2.0"><channel><item><title>Test &amp; SEO</title>
<link>{URL}?utm_source=feed#top</link><pubDate>Fri, 30 Oct 2026 12:00:00 GMT</pubDate>
<description>Not an authorized transcript</description></item></channel></rss>'''.encode()


def response_handler(request):
    assert str(request.url) == SOURCES[SOURCE]["url"]
    assert request.headers["accept-encoding"] == "identity"
    return httpx.Response(200, content=RSS, headers={"content-type": "text/xml", "etag": '"v1"'})


def test_rss_metadata_only_and_atom_are_deduplicated():
    entries, skipped = parse_feed(RSS)
    assert entries == [{"url": URL, "title": "Test & SEO",
                        "published_at": "Fri, 30 Oct 2026 12:00:00 GMT"}]
    assert skipped == 0
    atom = f'''<feed xmlns="http://www.w3.org/2005/Atom"><entry>
    <title type="html">&lt;b&gt;New post&lt;/b&gt;</title>
    <link rel="self" href="https://internal.invalid/"/><link href="{URL}"/>
    <updated>2026-10-31T12:00:00Z</updated></entry><entry><title>Duplicate</title>
    <link href="{URL}?tracking=1"/></entry><entry><title>Unsafe</title>
    <link href="http://127.0.0.1/"/></entry></feed>'''.encode()
    entries, skipped = parse_feed(atom)
    assert entries == [{"url": URL, "title": "New post", "published_at": "2026-10-31T12:00:00Z"}]
    assert skipped == 1


@pytest.mark.parametrize("payload", [
    b'<!DOCTYPE rss [<!ENTITY x "expanded">]><rss><channel/></rss>',
    b'<!DOCTYPE rss SYSTEM "http://127.0.0.1/"><rss><channel/></rss>',
    '<!DOCTYPE rss><rss><channel/></rss>'.encode('utf-16'),
    b'<rss><channel>', b'<html/>', b'<rss/>', b'x' * (MAX_BYTES + 1),
    b'<rss><channel>' + b'<a>' * 33 + b'</a>' * 33 + b'</channel></rss>',
    b'<rss><channel>' + b'<a/>' * 10000 + b'</channel></rss>',
    b'<rss><channel>' + b'<item/>' * 201 + b'</channel></rss>',
    b'<rss><channel><item><title>Bad</title><link>http://localhost/</link></item></channel></rss>',
])
def test_bad_xml_and_bounded_structure(payload):
    with pytest.raises((ValueError, ET.ParseError)):
        parse_feed(payload)


@pytest.mark.parametrize("url", [
    'http://developers.google.com/search/blog/2026/10/test',
    'https://developers.google.com.evil.test/search/blog/2026/10/test',
    'https://developers.google.com@127.0.0.1/search/blog/2026/10/test',
    'https://developers.google.com:443/search/blog/2026/10/test',
    'https://developers.google.com/search/blog/2026/10/../../admin',
    'https://developers.google.com/search/blog/2026/10/%2e%2e',
    'https://developers.google.com/search/blog/2026/10/test\n',
])
def test_only_publisher_article_links_are_accepted(url):
    with pytest.raises(ValueError):
        article_url(url)


def test_transport_fixed_url_and_conditional_cache():
    calls = []
    def handler(request):
        calls.append(request)
        if len(calls) == 1:
            return response_handler(request)
        assert request.headers['if-none-match'] == '"v1"'
        return httpx.Response(304)
    client = FeedClient(httpx.MockTransport(handler))
    first = client.fetch(SOURCE)
    assert first.entries[0]['url'] == URL and first.etag == '"v1"'
    assert client.fetch(SOURCE, first.etag).not_modified
    assert len(calls) == 2  # Entry links are never requested.


@pytest.mark.parametrize("kind", ['redirect', 'large', 'compressed', 'html', 'bad', 'timeout', '304'])
def test_transport_fails_closed(kind):
    calls = []
    def handler(request):
        calls.append(request)
        if kind == 'timeout':
            raise httpx.ReadTimeout('secret upstream detail')
        if kind == 'redirect':
            return httpx.Response(302, headers={'location': 'http://127.0.0.1/'})
        if kind == '304':
            return httpx.Response(304)
        return httpx.Response(200, content=b'x' * (MAX_BYTES + 1) if kind == 'large' else b'<html/>',
                              headers={'content-type': 'text/html' if kind == 'html' else 'text/xml',
                                       'content-encoding': 'br' if kind == 'compressed' else 'identity'})
    with pytest.raises(FeedUnavailable, match='^Feed unavailable or invalid$'):
        FeedClient(httpx.MockTransport(handler)).fetch(SOURCE)
    assert len(calls) == 1


@pytest.fixture
def feed_db(tmp_path):
    engine, sessions = database(f'sqlite:///{tmp_path}/feeds.db')
    Base.metadata.create_all(engine)
    yield sessions
    engine.dispose()


def test_persistent_cache_dedup_and_cooldown(feed_db):
    client = FeedClient(httpx.MockTransport(response_handler))
    assert collect(feed_db, SOURCE, client, now=1000)['added'] == 1
    with pytest.raises(FeedCoolingDown):
        collect(feed_db, SOURCE, client, now=1001)
    assert collect(feed_db, SOURCE, client, now=4600)['added'] == 0
    with feed_db() as session:
        assert session.scalar(select(func.count()).select_from(FeedEntry)) == 1
        assert session.scalar(select(func.count()).select_from(Item)) == 0
        state = session.get(FeedState, SOURCE)
        assert state.etag == '"v1"' and state.success_at == 4600


def test_claim_is_atomic_and_old_worker_is_fenced(feed_db):
    calls = []
    class Client:
        def fetch(self, *args):
            calls.append(1)
            return FeedResponse([])
    def attempt(_):
        try:
            collect(feed_db, SOURCE, Client(), now=1000)
            return True
        except FeedCoolingDown:
            return False
    with ThreadPoolExecutor(max_workers=5) as pool:
        assert sum(pool.map(attempt, range(10))) == 1
    assert len(calls) == 1
    class Superseded:
        def fetch(self, *args):
            collect(feed_db, SOURCE, Client(), now=5000)
            return FeedResponse(parse_feed(RSS)[0])
    with pytest.raises(FeedCoolingDown):
        collect(feed_db, SOURCE, Superseded(), now=4600)
    with feed_db() as session:
        assert session.scalar(select(func.count()).select_from(FeedEntry)) == 0
        assert session.get(FeedState, SOURCE).success_at == 5000


def test_failure_preserves_cache_and_requires_cooldown(feed_db):
    collect(feed_db, SOURCE, FeedClient(httpx.MockTransport(response_handler)), now=1000)
    class Failed:
        def fetch(self, *args):
            raise FeedUnavailable('Feed unavailable or invalid')
    with pytest.raises(FeedUnavailable):
        collect(feed_db, SOURCE, Failed(), now=4600)
    with pytest.raises(FeedCoolingDown):
        collect(feed_db, SOURCE, Failed(), now=4601)
    with feed_db() as session:
        state = session.get(FeedState, SOURCE)
        assert state.success_at == 1000 and state.etag == '"v1"'
        assert state.error == 'unavailable_or_invalid' and state.owner is None


def test_api_disabled_authorization_inbox_and_pagination(tmp_path, monkeypatch):
    calls = []
    def handler(request):
        calls.append(1)
        return response_handler(request)
    app = create_app(f'sqlite:///{tmp_path}/api.db', token='admin-test',
                     telegram_token='gateway-test', allowed_users={123},
                     feed_client=FeedClient(httpx.MockTransport(handler)))
    Base.metadata.create_all(app.state.engine)
    try:
        with TestClient(app, headers={'Authorization': 'Bearer admin-test'}) as client:
            endpoint = f'/discovery/sources/{SOURCE}/collect'
            assert client.get('/discovery/sources').json()['enabled'] is False
            assert client.post(endpoint).status_code == 409
            monkeypatch.setenv('STUDIO_FEEDS_ENABLED', '1')
            unauthorized = {'Authorization': 'Bearer wrong'}
            gateway = {'Authorization': 'Bearer gateway-test', 'X-Studio-Telegram-User': '123'}
            assert client.post(endpoint, headers=unauthorized).status_code == 401
            assert client.post(endpoint, headers=gateway).status_code == 403
            assert client.get('/discovery/entries', headers=gateway).status_code == 403
            assert client.post('/discovery/sources/unknown/collect').status_code == 404
            assert calls == []
            assert client.post(endpoint).json()['added'] == 1
            assert client.post(endpoint).status_code == 409
            entries = client.get('/discovery/entries').json()
            assert entries['entries'][0]['verified'] is False
            assert entries['entries'][0]['provenance'] == 'publisher_feed_metadata_only'
            assert client.get('/items').json() == []
            assert client.get('/discovery/entries?limit=101').status_code == 422
            assert client.get('/discovery/entries?source=unknown').status_code == 404
            with Session(app.state.engine) as session:
                session.add(FeedEntry(key='0'*64, source=SOURCE, url=URL+'-other', title='Another',
                                      discovered_at=1000))
                session.commit()
            page = client.get('/discovery/entries?limit=1').json()
            assert page['next_after_key'] == '0'*64
            next_page = client.get('/discovery/entries', params={'after_key': page['next_after_key']}).json()
            assert len(next_page['entries']) == 1 and next_page['next_after_key'] is None
            assert len(calls) == 1
    finally:
        app.state.engine.dispose()


def test_streaming_deadline_and_invalid_validators(monkeypatch):
    import studio.feeds as feeds

    class SlowStream(httpx.SyncByteStream):
        def __iter__(self):
            yield b' ' * 8192
            yield RSS
    times = iter([0, 1, 21])
    monkeypatch.setattr(feeds.time, 'monotonic', lambda: next(times))
    transport = httpx.MockTransport(lambda r: httpx.Response(
        200, stream=SlowStream(), headers={'content-type': 'text/xml'}))
    with pytest.raises(FeedUnavailable):
        FeedClient(transport).fetch(SOURCE)
    monkeypatch.undo()
    def bad_cache(request):
        assert 'if-none-match' not in request.headers
        return httpx.Response(304)
    with pytest.raises(FeedUnavailable):
        FeedClient(httpx.MockTransport(bad_cache)).fetch(SOURCE, etag='bad\nheader')


def test_api_failure_is_sanitized_and_observable(tmp_path, monkeypatch):
    def failure(request):
        raise httpx.ConnectError('sensitive upstream detail')
    monkeypatch.setenv('STUDIO_FEEDS_ENABLED', '1')
    app = create_app(f'sqlite:///{tmp_path}/failed.db', token='admin-test',
                     feed_client=FeedClient(httpx.MockTransport(failure)))
    Base.metadata.create_all(app.state.engine)
    try:
        with TestClient(app, headers={'Authorization': 'Bearer admin-test'}) as client:
            response = client.post(f'/discovery/sources/{SOURCE}/collect')
            assert response.status_code == 502 and 'sensitive' not in response.text
            state = client.get('/discovery/sources').json()['sources'][0]
            assert state['status'] == 'failed' and state['error'] == 'unavailable_or_invalid'
            assert state['success_at'] is None
            assert client.get('/discovery/entries').json()['entries'] == []
    finally:
        app.state.engine.dispose()
