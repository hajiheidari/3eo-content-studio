# Security boundary
Foundation only; not approved for public exposure. All content endpoints require an authorized bearer
admin or dedicated gateway token and fail closed when unset. Bind to loopback. A token grants administrator access;
per-user dashboard RBAC, rate limits and production authentication remain pending.
Only exact HTTPS YouTube/Instagram hosts and recognized paths are accepted. No submitted
URL is fetched, so redirects and DNS cannot trigger SSRF. Future fetch adapters must validate
resolved addresses, every redirect, time/byte limits and content types. Metadata remains manual unless the dedicated YouTube adapter is explicitly configured.
That adapter accepts only validated YouTube IDs, calls one fixed official Google endpoint,
refuses redirects/compressed responses, caps time/bytes and reserves daily requests atomically.
No API key is required for the manual path. Never log metadata HTTP exception URLs (keys are
query parameters); only sanitized failures are returned. No scraping, public media serving, upload,
publication or voice generation endpoints exist. Telegram handler permits only configured
users in private chats. The API does not start a bot; polling/sending requires explicitly
configured opt-in foreground worker startup. A separate gateway token can assert allowlisted
Telegram identities and must never be reused as an admin token or shared with end users.
Secrets and HTTP exception URLs are not logged by the worker. Research requires provenance and
limitations, but schema validation cannot establish truth; founder fact checking remains required.
Protect DB and token locally; never commit environment files. Dependency lock included;
container scanning and full security audit remain pending.

Inline callback actions require the approved sender in their exact private chat and include
an expected item version. Replaying the same update returns its existing mutation receipt;
using an old button for a changed idea fails with 409. Old unversioned report snapshots do not
create new keyboards. Callback acknowledgements never authorize or repeat mutations.


The optional AI adapter defaults off and requires a dedicated key, explicit compatible model,
budget approval flag and daily cap. It calls one fixed OpenAI endpoint without tools, redirects,
proxy-environment inheritance or automatic retries. Untrusted transcript content is supplied
separately from instructions. This reduces instruction confusion but does not prove generated
claims true; all drafts remain labeled and require founder review. Invalid/refused/incomplete
responses do not mutate the source research or advance approval.

Attempt claims commit before generation and conservative unknown outcomes are held for review.
Cached research is private application data. The transcript is not copied into the operational
ledger, but validated draft output is retained there for crash-safe reuse. Admin operational
responses omit both transcript and draft. No secret, authorization header or raw provider error
is logged or returned. store:false is configured; provider data-retention policies must still be
reviewed before any real transcript is transmitted. Ordinary tests clear live provider settings
and keys and use mocked transport. No external AI request occurred in development.
