# Reliability foundation: implementation and qualification

[🇫🇷 Français](../P0.md) · [🇬🇧 English](reliability.md)

This foundation makes publication, evidence, retries and spending explicit. Implemented mechanisms are distinct from qualification using real NAS accounts and models.

## Delivered mechanisms

- Immutable evidence IDs bind source content, recognition settings and original media hashes. Old references retain their original text and images.
- Complete drafts are validated before an atomic generation pointer update. Failure retains a coherent prior library.
- Durable job fingerprints include relevant source/model/provider/parameter contracts without secrets. Unchanged successes are reused; stages can be retried explicitly.
- ASR and vision progress independently; extraction success survives another stage's error. A partial synthesis is not silently advertised as complete.
- Authentication, allowed-origin/CSRF checks, revision checks and a shared volume lock protect import/review/control writes.
- JSON, Markdown and originals remain portable; derived SQLite does not replace evidence.

## Profiles and first checks

The default setup profile is DeepSeek text/vision with ASR unset. The alternative `--profile api` prepares the historical Groq/OpenAI example. Neither profile proves model availability/quality and both start with periodic processing/paid text generation disabled. Keys are configured privately and exact model contracts need one-source tests. [Import/models](import-and-deepseek.md).

```sh
docker compose up -d web
docker compose --profile automation run --rm worker python -m kararecall.worker check
docker compose exec -T web python scripts/verify_storage.py
```

After explicitly enabling the desired roles, stop any periodic worker before `once` or use the UI queue. A stage retry is explicit:

```sh
docker compose --profile automation run --rm worker python -m kararecall.worker retry --source BOOKMARK_ID --stage asr
```

Changing a key does not invalidate successful cached results. Old evidence remains available when a reprocessing request fails. A replaced local video's asset is blocked rather than overwriting media still referenced by old proofs; document replacements retain separate originals.

## Budget ledger

Defaults: USD 2/month, 50 calls/day, 400/month, USD 0.05 reserved per call, three automatic attempts. Accounting periods use UTC. Before a request, `data/usage.sqlite` durably reserves its cost. If a limit cannot accommodate the reservation, no request is sent. Known token usage/rates replace the reservation with calculated cost; ASR uses duration/rate with the selected profile's minimum. Unknown rates/usage, errors and uncertain requests keep their reservation after restart. Keys, prompts and response bodies are not logged there.

```sh
docker compose --profile automation run --rm worker python -m kararecall.worker usage
```

Important variables: `AI_MONTHLY_BUDGET_USD`, `AI_CALL_RESERVE_USD`, `AI_MAX_CALLS_PER_DAY`, `AI_MAX_CALLS_PER_MONTH`, `WORKER_MAX_ATTEMPTS`, `LLM_MAX_OUTPUT_TOKENS`, `VISION_MAX_OUTPUT_TOKENS`, text/vision `*_USD_PER_MILLION` rates and `ASR_USD_PER_HOUR`. A zero rate means unknown, not free. If calculated usage exceeds the per-call reserve, further monthly requests are suspended pending explicit review of rates/limits. This ledger is an estimate/control, not a provider billing guarantee or a replacement for account spending caps.

## Storage and tests

Generation migration preserves citations, and `python3 -m kararecall build` publishes a fresh generation rather than editing a selected one. Legacy macOS scripts refuse to mutate already-published libraries. Keep media/recognition artifacts and hashes together. [Backup/new-volume restore](homelab.md#backup-and-restore).

Synthetic tests cover generation failure, re-transcription/model change, missing references, stage cache/retries, accounting persistence, authenticated APIs, review conflicts, media limits, document extraction, MCP and digest state. Container checks verify their own build/start/search/export/video/digest and backup/restore workflow, then remove their own resources. They do not qualify the configured external endpoints, real content fidelity or NAS hardware. [Pilot](pilot.md) · [Backlog](backlog.md).
