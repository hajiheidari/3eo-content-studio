# Cost estimate
No services purchased and no paid API calls made. Local development uses open-source
software. Incremental software license cost for the proposed stack is zero; existing
server capacity, backup storage and bandwidth are unknown. AI, transcription and rendering
costs cannot be estimated responsibly without provider/model, volume, duration and server
measurements. Keep paid adapters disabled until the founder approves a budget. Prefer
manual transcript/reviewed research and CPU rendering benchmarks first.


Measured development option: local Qwen2.5-14B Q4_K_M (~9 GB weights), four CPU threads,
approximately 16 GiB observed RSS, 117.5 seconds for the sampled research call. No paid API
usage. Production suitability depends on the inspected server; do not assume it can host this
model alongside Espadna. Retired model artifacts were removed; the active model is retained
in ignored .local/. Higher throughput/provider spending still requires explicit approval.
