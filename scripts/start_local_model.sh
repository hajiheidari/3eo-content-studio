#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
# Explicitly started, CPU only, bounded threads/context and one inference slot.
# 10 GiB virtual address-space ceiling for this development process only.
ulimit -v 10485760
exec .local/llama/llama-b12129/llama-server \
  --model .local/models/Qwen3-4B-Q4_K_M.gguf \
  --host 127.0.0.1 --port 8081 --ctx-size 8192 --threads 4 --threads-batch 4 \
  --parallel 1 --n-gpu-layers 0 --jinja
