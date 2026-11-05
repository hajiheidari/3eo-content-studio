# Validation
From this checkout, with only a development DATABASE_URL:

```sh
uv sync --frozen
STUDIO_LOCAL_AI=0 STUDIO_OLLAMA_MODEL= uv run pytest -q
uv run ruff check src tests scripts migrations
uv run alembic upgrade head
uv run alembic check
```

97 tests pass. Coverage includes URL/SSRF validation, canonical/advisory duplicates,
transcript/evidence gating, research validation, source-context isolation, plain-text intake,
standalone text, new-idea reset, provider failures, concrete demonstration plan, scoring,
optimistic approval writes/audits, safe metadata/feeds and response caps, Telegram sender
checks/callbacks, Tehran timing, durable update/report state, uncertain delivery handling,
rate-limit retries, populated DB upgrade, model checksums and non-overwriting runtime reuse.
External APIs/model generation are mocked in this suite; tests do not call paid services.
One upstream Starlette/httpx TestClient deprecation warning remains.

## Actual development acceptance
- Real loopback HTTP server: schema health, persisted link, transcript gate and auth passed.
- Dedicated Telegram getMe and founder-submitted YouTube URL/reply passed.
- Official CPU runtime and all three Qwen2.5-14B GGUF shards matched pinned SHA-256.
- Local model/API readiness passed. Repeating installation while the model ran kept it healthy.
- Item 1's stored public description generated actual research without a supplied answer:
  HTTP 200, RESEARCHED, 117.5 seconds, score 53/confidence 0.4.
- The actual persisted draft and approval keyboard were delivered to the allowlisted user.
  No founder approval or publication was simulated.

Smaller models were rejected after weak drafts; they were not presented as accepted content.
The final plan is structured as topic/input/action/comparison; it remains a founder-reviewed
hypothesis. Live YouTube metadata failed at the proxy with 403, so no watched-video or full
transcript claim is made. PostgreSQL, unattended scheduling under load, broad editorial
quality and the full script/media/render/export workflow remain unvalidated or unimplemented.


Approval incident regressions: expired Telegram callback acknowledgement must not suppress
the business action; repeated approval must create one audit transition and a clear response.
Live reconciliation after the founder's chat confirmation verified IDEA_APPROVED and actual
Telegram confirmation delivery. No synthetic callback or publication was claimed.


Producer tests now cover approved-only generation, failed-model state restoration, concurrent
duplicate reservation, interruption lease recovery, frozen revisions, wrong/stale hash approval,
script-stage bypass prevention, Telegram revision notes and full Unicode multipart review.
Live item 1 generated a stored 55-second script draft with three hooks and five scenes; its
review/approval keyboard was delivered. Generation took 384.3s after a timeout-driven reduction
in output verbosity. No actual script approval, recording, rendering or export is claimed.
