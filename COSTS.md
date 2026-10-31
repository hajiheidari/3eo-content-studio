# Cost estimate
No services purchased and no paid API calls made. Local development uses open-source
software. Incremental software license cost for the proposed stack is zero; existing
server capacity, backup storage and bandwidth are unknown. AI, transcription and rendering
costs cannot be estimated responsibly without provider/model, volume, duration and server
measurements. Keep paid adapters disabled until the founder approves a budget. Prefer
manual transcript/reviewed research and CPU rendering benchmarks first.


## AI controls implemented
The OpenAI adapter remains disabled. Selecting it requires an explicit model, dedicated key,
recorded budget approval and a daily reserved-request cap. Input bytes and output tokens are
bounded. Identical completed requests are reused; uncertain/duplicate calls are not blindly
resent. All implementation tests use mocked transport and incurred no paid API usage.

A request cap is not a currency budget: model pricing, actual input/output/reasoning tokens,
provider-side caching and usage outside this application affect invoices. No price, account
balance or free allowance is assumed. Choose the model and check its official current pricing
before setting provider project spend controls and enabling a live acceptance test. No model
is selected by default and no live usage budget has been approved in this chat.


The optional feed inbox requires no API key or paid model. Explicit admin collection performs
at most one request per source per hour after success, with a five-minute failure/crash cooldown.
It stores only bounded metadata per entry. It is disabled by default and has no scheduler or
retention job; network/storage/hosting use still needs monitoring before sustained operation.
