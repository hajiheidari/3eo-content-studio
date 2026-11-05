#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
# Explicitly started, CPU only, bounded threads/context and one inference slot.
# 24 GiB virtual address-space ceiling for this development process only.
ulimit -v 25165824
exec .local/llama/llama-b12129/llama-server \
  --model .local/models/qwen2.5-14b-instruct-q4_k_m-00001-of-00003.gguf \
  --host 127.0.0.1 --port 8081 --ctx-size 8192 --threads 4 --threads-batch 4 \
  --parallel 1 --n-gpu-layers 0 --jinja
