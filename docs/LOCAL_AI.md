# Complete the private automatic research path

The application now binds the next plain-text message to the sender's selected source,
classifies it as description/transcript/user text, calls the research provider, validates and
stores the Persian result, and returns approval buttons. A standalone long text also works.
A title alone is not treated as a transcript. Pending text survives provider outages and
conversation context survives restarts. No publication occurs on approval.

## Actual prerequisite
A language model is not yet installed. Hugging Face downloads currently fail with proxy
403. The environment draft adds huggingface.co, *.hf.co (official model CDNs) and
cdn-lfs.huggingface.co while preserving prior domain rules. Review/save and publish the
**development environment** configuration to apply access. This is not server deployment.
No API key or paid provider is needed for this CPU option. No new mandatory model variable
has been added to the settings form.

## Reproducible free CPU option
Available development resources at inspection: 5 CPUs, ~33 GiB free RAM, ~60 GiB disk.
Use Qwen/Qwen3-4B-GGUF Q4_K_M, served privately by llama.cpp b12129. Binary and weights
are fetched from official project repositories over verified TLS; both require authoritative
SHA-256 verification. The CPU runtime has already been downloaded and its digest verified.
Actual model download, startup and Persian quality/latency acceptance remain unverified.
No automatic model download occurs on API import or when the bot receives a message.

From the project directory, explicitly run:

```sh
uv run python scripts/prepare_local_model.py
bash scripts/start_local_model.sh
```

The preparation script pins the selected model commit in ignored .local/model-manifest.json
and verifies its LFS SHA. It refuses corrupt/oversized artifacts. Keep model data out of Git.
The model process binds only 127.0.0.1:8081, uses CPU, four threads, one slot, 8192 context,
and a 10 GiB virtual memory ceiling. It is a development choice, not production sizing.
Check local `GET http://127.0.0.1:8081/health` for a 200 response before enabling the adapter.

Restart only this API with its existing secret bindings:

```sh
STUDIO_LOCAL_AI=1 uv run uvicorn studio.api:create_app --factory --host 127.0.0.1 --port 8000
```

Authenticated `GET /research/health` must report configured/ready true. Restart this project's
Telegram worker with its existing allowlist/token and explicit per-process enablement:

```sh
STUDIO_TELEGRAM_ENABLED=1 uv run python -m studio.worker
```

Do not start competing workers or migrate a production DB. Use the same dev database for API
and worker. Nothing here changes services, networking or schedules on the production server.
These processes are ephemeral; a snapshot does not preserve running processes.

## User experience and limits
Send a YouTube/Instagram link. Metadata is attempted automatically, but a blocked/inaccessible
video is never represented as watched. Select source-text type if needed, then send the
public description or authorized transcript in the next message. No multi-line command is
required. Text without a selected link becomes an independent text source. Minimum 80,
maximum 12000 characters; larger text is rejected rather than silently cut. For descriptions,
confidence is capped at 0.5 and an application-generated evidence limitation is always added.
Only explicit founder approval moves the item to IDEA_APPROVED.

Model errors leave the evidence saved and return a retry button, not invented analysis.
Telegram callback authorization is checked before acknowledgement; callbacks are acknowledged
before potentially slow model work. CPU inference can take minutes and one private worker
processes updates sequentially. The API timeout is 240s and worker client timeout 300s;
concurrent generation is limited to one slot. Unattended 05:00 delivery under concurrent
inference still needs a separate job worker before claiming production scheduling guarantees.

## Required live acceptance
After network access is applied: download/checksum model, start server, inspect ready endpoint,
run item 1's stored description through `POST /items/1/research` without a supplied research
body, inspect the actual Persian output for fidelity and limitations, then exercise Telegram
plain-text intake/reply and founder approval. Mocked provider tests alone do not establish
model readiness, quality or a complete autonomous agent. No live approval is simulated.
