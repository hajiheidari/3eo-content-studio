# Security boundary
Foundation only; not approved for public exposure. All content endpoints require a bearer
admin token and fail closed when unset. Bind to loopback. A token grants administrator access;
per-user dashboard RBAC, rate limits and production authentication remain pending.
Only exact HTTPS YouTube/Instagram hosts and recognized paths are accepted. No arbitrary submitted
URL is fetched: explicit YouTube oEmbed uses a fixed endpoint and canonical video ID; official
feeds accept three fixed public hosts. HTTP adapters reject redirects and cap response sizes.
XML parsing forbids DTD/entities. Unconfigured metadata stays unknown; feed content and model
input remain untrusted. Future expanded fetch hosts must preserve SSRF controls. No scraping, public media serving, upload,
publication or voice generation endpoints exist. Telegram handling permits only configured
users in private chats. The worker starts only with explicit enablement and dedicated credentials.
No live bot was started during implementation. Token-bearing request URLs are excluded from
application errors; avoid enabling low-level HTTP debug logs. Research requires provenance and
limitations, but schema validation cannot establish truth; founder fact checking remains required.
Protect DB and token locally; never commit environment files. Dependency lock included;
container scanning and full security audit remain pending.
