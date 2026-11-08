# Study for sustainable everyday use

[🇫🇷 Français](../ETUDE-EXPLOITATION.md) · [🇬🇧 English](operations-study.md)

This is the English edition of the project's initial operations study, with implementation status clarified by the current guides. Its price observations and engineering estimates date from **5 November 2026**; they are historical assumptions, not current quotes or validated production costs. The planning volume is about **twenty videos/month**, plus articles/notes, on a Docker-capable NAS with roughly 2–3 GiB available. A Mac can optionally host models.

## Proposed direction

Keep a small dedicated web application and sequential worker on the NAS. Use portable JSON/Markdown and a persistent private volume. Configure inference roles separately, initially through economical compatible APIs if transmitting content is acceptable; a Mac service remains an option for privacy/quality or a measured need. At this volume, modest estimated inference savings alone do not justify an always-on Mac dependency. AFFiNE/Wiki.js are optional export destinations rather than the primary application.

The POC demonstrated useful retrieval and evidence-linked tool cards, but it did not establish reliable unattended operation. The initial review found incomplete cache contracts, position-based evidence vulnerable to reprocessing, publication/coherence risks and unmeasured input coverage. The reliability foundation subsequently delivered immutable evidence, atomic generations, bounded stages, persistent quotas and review controls. Real provider/NAS qualification remains separate.

## Deployment choices

| Option | Benefits | Cost/limitation |
|---|---|---|
| NAS plus remote role APIs | Independent of the Mac, modest NAS RAM | Sends configured content to providers; account/endpoint quality needs testing |
| NAS plus Mac inference service | Local-network processing and hardware options | Mac availability, API adapter, maintenance and model RAM |
| Models directly on NAS | No Mac dependency | Not supplied or qualified for the available CPU/RAM |
| Existing wiki/workspace as UI | Reuses an existing tool | Evidence/media synchronization and administration still need custom integration |

ASR and vision are separate. Local faster-whisper/Apple Vision POC scripts are not a ready NAS HTTP service. whisper.cpp or another local service needs compatible routes, timing, authentication and measured resource use. The NAS still prepares media locally without AI.

## Historical cost model

The comparison assumed per video: one minute of audio; text synthesis with 5,000 input/1,000 output tokens; twelve images with 1,800 image tokens plus 150 prompt and 200 billed output tokens each. Web enrichment assumed one new tool, one search, two pages and another 12,000 input/1,000 output-token synthesis. Token assumptions are budgeting examples, not tokenizer measurements; reasoning, resolution, retries and different models change costs.

Reference rates were Groq Whisper turbo at USD 0.04/hour with a ten-second minimum, and a compact text/image model at USD 0.10/0.50 per million input/output tokens. Brave/Firecrawl calculations assumed stated credits remained available and excluded other account use. These original examples do not choose a provider for the current application.

| One-minute videos/month | Audio/vision/cards, no web | With Brave reference | With Firecrawl reference | Local audio/OCR plus cards/Brave |
|---:|---:|---:|---:|---:|
| 20 | USD 0.10 | USD 0.14 | USD 0.14 | USD 0.05 plus local compute |
| 100 | 0.52 | 0.69 | 0.69 | 0.27 plus compute |
| 500 | 2.60 | 3.45 | 22.45 | 1.35 plus compute |
| 2,000 | 10.41 | 18.81 | 47.81 | 10.40 plus compute |

At twenty videos, the example comprised roughly USD 0.013 audio, 0.020 synthesis, 0.071 vision and 0.034 web-page synthesis, before exclusions. Moving audio/OCR local saved only about USD 0.08/month under those assumptions. A provisional EUR 1–2/month consumption reserve was proposed for the pilot, not a provider minimum top-up. At 500 videos, planning envelopes were EUR 5–15 with light economical APIs or EUR 25–50 with paid extraction and retry margin. Taxes, currency conversion, hardware, storage, account minimums, multiple tools/video, long media and unrelated usage were excluded. No paid production benchmark or electrical measurement validated these amounts.

Use configured current tariffs and [batch measurements](pilot.md#coverage-batch-cost-and-http) instead of extrapolating the historical table. The application now implements reservations/output limits that were missing when the initial study was written.

## Storage and engineering effort

At an illustrative 15 MB/video, twenty monthly videos add about 3.6 GB/year before captures, versions and backups; 100/500/2,000 add 18/90/360 GB/year. Three full copies triple those figures before retention. Streamed hashing, cached immutable-file hashes, stable-source export reuse and HTTP pagination reduce avoidable work, but actual NAS history must be measured.

Initial human engineering estimates were 2–4 days for reliability/budgets, 1–3 for real-model pilot, 0.5–1.5 for NAS operation, then 2–4 web enrichment, 1–3 review/navigation, 1–2 MCP and 1–3 optional hybrid evaluation. They are comparative work estimates, not a promise of assistant completion time or a service quote. Current completion is tracked in the [backlog](backlog.md).

## Gate for autonomous use

Validate exact citations after reprocessing, compatible inference outputs, resource/cost limits, representative search quality, private network/authenticated playback, backup/new-volume restore and update rollback. An existing Compose file or successful synthetic test is insufficient to declare all production criteria met. [Reliability](reliability.md) · [Long-term operations](long-term-operations.md) · [Pilot](pilot.md).
