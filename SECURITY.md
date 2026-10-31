# Security boundary
Foundation only; not approved for public exposure. All content endpoints require a bearer
admin token and fail closed when unset. Bind to loopback. A token grants administrator access;
per-user dashboard RBAC, rate limits and production authentication remain pending.
Only exact HTTPS YouTube/Instagram hosts and recognized paths are accepted. No submitted
URL is fetched, so redirects and DNS cannot trigger SSRF. Future fetch adapters must validate
resolved addresses, every redirect, time/byte limits and content types. Metadata is explicitly
user supplied until an adapter is implemented. No scraping, public media serving, upload,
publication or voice generation endpoints exist. Telegram handler permits only configured
users in private chats; it does not start a live bot. Research requires provenance and
limitations, but schema validation cannot establish truth; founder fact checking remains required.
Protect DB and token locally; never commit environment files. Dependency lock included;
container scanning and full security audit remain pending.
