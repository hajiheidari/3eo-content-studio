# Private automatic research: verified development setup

The active CPU model is official Qwen/Qwen2.5-14B-Instruct-GGUF Q4_K_M, served by llama.cpp
b12129 on 127.0.0.1:8081. All three GGUF shards and the CPU runtime are SHA-256 verified.
Pinned model revision: b466e1f8c07172155743e8e1307507d8a4f91fbd. Script constants and ignored
.local/model-manifest.json record every shard digest. Model license: Apache-2.0. No paid API.

## Reproduce
Python 3.12+/uv, ~9 GB model disk plus installation space, and sufficient memory required.
The development machine has 5 visible CPUs/~33 GiB RAM. Observed model RSS ~16 GiB;
production requirements are NOT inferred from this cloud machine. CPU inference is slow.

```sh
uv sync --frozen
uv run python scripts/prepare_local_model.py
bash scripts/start_local_model.sh
```

The preparation script downloads pinned official artifacts with TLS/checksum verification,
reuses verified files and refuses to overwrite a differing installed native runtime. Repeating
setup on a running healthy installation does not replace memory-mapped libraries. Model and
runtime files are ignored local artifacts, never committed. Network destinations are GitHub,
Hugging Face and its model CDNs; approved network access is now applied.

The model is CPU only, four threads, one slot, 8192 context and a 24 GiB virtual memory ceiling.
Check local GET http://127.0.0.1:8081/health (200), then in separate processes:

```sh
# Only against the selected development database; never migrate production here.
uv run alembic upgrade head
STUDIO_LOCAL_AI=1 uv run uvicorn studio.api:create_app --factory --host 127.0.0.1 --port 8000
STUDIO_TELEGRAM_ENABLED=1 uv run python -m studio.worker
```

Keep existing dedicated token, positive Telegram user allowlist and admin token bindings.
API and worker must share the same DB. Authenticated GET /research/health must report ready.
Do not run competing workers. Publication snapshots do not retain running processes: restart
model, API and worker in a restored task. Publishing the development snapshot is separate
from any production deployment, which remains unapproved.

## Conversational workflow
Send a supported source link; metadata retrieval is attempted without pretending to watch
inaccessible media. Send its description in the next message, or select authorized transcript
with its type button. Text can also start an independent idea. Use /start for the Persian menu
and «ایده جدید» to clear source context before a different standalone topic. No multi-line
commands are needed. Minimum 80/max 12000 characters, no silent truncation. Text is saved
before analysis, so failures return a retry button rather than losing it.

Local inference uses a schema-constrained demonstration plan (topic, input, action, comparison),
then title/research/scoring. Identical claims and repeated generic fields are rejected.
Description confidence is capped at 0.5. Evidence limitations come from actual stored input
availability, not invented model statements. Suggestions are hypotheses for founder review;
schema validity does not prove factual correctness or editorial quality.

## Real validation and limits
The founder's actual item 1 description ran through the live provider/API and was stored as
RESEARCHED. The final structured-plan run took 117.5 seconds, score 53, confidence 0.4. The
stored result was delivered through Telegram to the approved private user, with review buttons.
No founder approval was simulated. The two smaller models were rejected after weak outputs;
their unused files were removed. No transcript or watched-video claim was fabricated.

A native-library re-extraction during an early repeat-install check caused the first runtime
to stop. The installer was fixed and regression-tested to never rewrite intact mapped files;
repeated setup now passes while the model stays healthy.

The API model timeout is 420s; worker timeout 480s. The worker sends a receipt for long text
before processing. One sequential worker can delay other messages/reports during inference;
this is a development pilot, not a production scheduling SLA. Independent job workers,
broader quality evaluation and performance work remain. Live YouTube access is still blocked
by proxy 403; descriptions/authorized text remain the supported fallback. No automatic
publication, paid service, production deployment or Espadna changes occurred.
