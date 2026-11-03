"""Public official feeds only; no linked-article fetching or transcript claims."""

import hashlib
from dataclasses import dataclass
from urllib.parse import urlsplit

import httpx
from defusedxml import ElementTree
from defusedxml.common import DefusedXmlException

from .integrations import IntegrationError

FEED_HOSTS = frozenset({"developers.google.com", "status.search.google.com", "blog.google"})
ATOM = "{http://www.w3.org/2005/Atom}"


def feed_url(value):
    try:
        parsed = urlsplit(value)
        if (
            len(value) > 2048
            or parsed.scheme != "https"
            or parsed.hostname not in FEED_HOSTS
            or parsed.username
            or parsed.password
            or parsed.netloc.lower() != (parsed.hostname or "")
            or parsed.fragment
            or any(c.isspace() for c in value)
        ):
            raise ValueError
    except ValueError:
        raise ValueError("An HTTPS URL on a supported official feed host is required") from None
    return value


@dataclass
class FeedEntry:
    content_id: str
    title: str
    url: str
    excerpt: str
    published_at: str | None
    author: str | None


def parse_feed(data: bytes):
    if len(data) > 524288:
        raise IntegrationError("Feed exceeded size limit")
    try:
        root = ElementTree.fromstring(data, forbid_dtd=True)
    except (ElementTree.ParseError, DefusedXmlException):
        raise IntegrationError("Unsafe or malformed feed") from None
    if root.tag == f"{ATOM}feed":
        nodes, atom = root.findall(f"{ATOM}entry"), True
    elif root.tag == "rss":
        nodes, atom = root.findall("channel/item"), False
    else:
        raise IntegrationError("Unsupported feed format")
    entries = []
    for node in nodes[:50]:

        def text(tag):
            element = node.find(f"{ATOM}{tag}" if atom else tag)
            return "".join(element.itertext()).strip() if element is not None else ""

        if atom:
            links = [
                e.get("href", "")
                for e in node.findall(f"{ATOM}link")
                if e.get("rel", "alternate") == "alternate"
            ]
            url = links[0] if links else ""
        else:
            url = text("link")
        try:
            feed_url(url)
        except ValueError:
            continue
        title = text("title")[:1000]
        if not title:
            continue
        entries.append(
            FeedEntry(
                content_id=hashlib.sha256(url.encode()).hexdigest(),
                title=title,
                url=url,
                excerpt=(text("summary") or text("content") if atom else text("description"))[
                    :10000
                ],
                published_at=(text("published") or text("updated") if atom else text("pubDate"))[
                    :100
                ]
                or None,
                author=(text("author") if not atom else text("author"))[:200] or None,
            )
        )
    return entries


class FeedReader:
    def __init__(self, client=None):
        self.client = client

    def fetch(self, url):
        feed_url(url)

        def request(client):
            try:
                with client.stream("GET", url, follow_redirects=False) as response:
                    if response.status_code != 200:
                        raise IntegrationError(f"Feed unavailable (HTTP {response.status_code})")
                    data = bytearray()
                    for chunk in response.iter_bytes(chunk_size=65536):
                        data.extend(chunk)
                        if len(data) > 524288:
                            raise IntegrationError("Feed exceeded size limit")
                    return parse_feed(bytes(data))
            except httpx.HTTPError:
                raise IntegrationError("Feed could not be read") from None

        if self.client:
            return request(self.client)
        with httpx.Client(timeout=10) as client:
            return request(client)
