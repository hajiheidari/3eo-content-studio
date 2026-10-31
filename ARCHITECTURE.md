# Architecture and M0 assessment

The production Ubuntu host is unavailable in this session: no host, SSH identity,
service inventory, or approved inspection route was supplied. No production commands
were run. Espadna Sim's containers, data, 08:00 Tehran job, and reverse proxy are untouched.
The original M0 cloud session reported Debian 13, Python 3.12, 5 visible CPUs, approximately
33 GiB available RAM and 60 GiB available disk. These are historical development measurements,
not current production resources. GPU availability is not assumed.

Use one Python application with FastAPI and SQLAlchemy. SQLite supports isolated local
work; PostgreSQL is the production target. Local 16.2 and hosted CI 17.11 integration have
passed; this does not establish production readiness. Alembic owns
schema changes. Avoid Redis until durable worker concurrency warrants it. Large media
will live outside the database. Research providers are interchangeable; default is unavailable,
never fabricated analysis. Submitted URLs are identifiers only. The opt-in YouTube metadata operation calls a fixed
official Google endpoint with a validated video ID; submitted URLs and redirects are never fetched.

Implemented schema: source_items (unique platform/content_id and optimistic version), audit_logs, daily_reports
(unique Tehran date). Transcript provenance and structured research are stored with their
source. Further normalized roles, scripts, storyboards, media, jobs, settings, quotas and
publication records are planned before their respective features. Migration 0002 adds atomic
mutation_receipts, worker_cursors (offsets/lease/cooldown), and a per-message telegram_outbox.
Migrations 0003–0004 add durable inline keyboards, cached source metadata and daily
api_usage request reservations. The full schema in the brief is a target, not implemented functionality.

Manual flow: authenticated link → normalized identifier → authorized transcript and
user-supplied metadata → validated reviewed research or injected provider → weighted score
→ explicit approval. Rejected items cannot progress. Reports snapshot up to five researched
ideas after 05:00 Tehran with one durable record per day. Report preparation is not delivery.

The opt-in worker prepares reports on the first tick at/after 05:00 Tehran and queues durable
private messages. Polling offsets, replay receipts and outbox recovery are implemented, tested
with mocked Telegram transport. Confirmed message IDs distinguish sent messages from uncertain
outcomes; uncertain sends are held for review rather than automatically resent. A dedicated
gateway credential asserts allowlisted Telegram identities. No worker is installed or running.

PostgreSQL 16.2 integration was verified in an isolated temporary local instance. Versioned
inline decisions bind approval to the reviewed revision, and callback acknowledgement is
separate from durable command/reply processing. The YouTube metadata adapter has a one-hour
cache and atomic Tehran-date request limits; it is disabled by default and tested with mocks.

Next: current-head CI and isolated live bot acceptance; Instagram metadata permissions;
isolated AI acceptance and provider project controls; producer and script approvals; media processing;
dashboard, operator reconciliation, monitoring and security hardening.

The optional OpenAI Responses adapter uses strict structured output and no tools. Migration
0005 adds research_attempts and source research provenance. A pre-HTTP durable claim prevents
concurrent/ambiguous duplicate generations; successful results are cached independently of
item/audit commit. Daily request reservations are shared by the application database. These
controls do not assert a dollar budget. Real model availability, quality, latency and billing
remain unverified. Requests are opt-in only; no live model was called during development.

Migration 0006 stores bounded lexical profiles derived from authorized transcripts and Persian
research. Writes maintain them in the same item transaction. Reads compare a bounded 200-row
page and return explicit coverage, never workflow mutations. Equality uses normalized text
digests; near matching uses word/shingle hash samples and a conservative heuristic threshold.
Old unindexed records are counted and require explicit backfill. Reports snapshot warnings
without excluding candidates. Status-filtered cursor lists support saved/approved review.
Semantic/cross-language matching and real-world accuracy evaluation remain out of scope.


## Public feeds
Migration 0007 isolates discovery metadata from source_items. A fixed reviewed source map
prevents user-controlled request origins. Only explicit admin collection is supported; no
background scheduler or Telegram gateway access. A durable conditional update claims each
source before HTTP and establishes a five-minute crash/failure cooldown. Successful HTTP 200
or conditional 304 establishes a one-hour cooldown. Owner fencing prevents a delayed previous
collector from committing after a takeover. ETag/Last-Modified validators and new entry rows
commit together. A failed download/parse retains the previous validators, inbox and last-success
stamp, with a sanitized status. URL hashes deduplicate entries after query/fragment removal;
first-seen title/date metadata remains unchanged on later fetches. Publisher dates are untrusted
strings, not scheduling input. The inbox has no foreign key into research or approval state.

Transport disallows redirects, environment proxies and compressed replies; bounds are 512 KiB,
10-second HTTP operation timeout, 20-second stream deadline, 200 entries, 10,000 XML nodes and
32 levels. UTF-8 only, DTD/entity declarations rejected before ElementTree parsing. RSS 2.0 and
Atom supported, HTML title markup stripped, canonical publisher article paths required. No
feed-supplied URL, enclosure, pagination link, stylesheet, body or transcript is downloaded.
A fixed source still needs a usable TLS/network route and upstream availability; this is not a
live-service acceptance claim. Feed retention, source configuration UI, scheduled collection,
article selection/promotion and Telegram inbox review remain future work.
