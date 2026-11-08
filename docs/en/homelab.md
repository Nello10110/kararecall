# Homelab deployment

[🇫🇷 Français](../HOMELAB.md) · [🇬🇧 English](homelab.md)

Use the [installation guide](installation.md) for the first import. This reference covers configuration, operations and private storage. The web service receives neither Karakeep nor AI API keys; Compose passes each service only its required variables.

## Configuration

Create `.env` with `python3 scripts/setup_env.py --profile deepseek`, or copy the root `.env.example` and replace its example password. Preserve existing private settings.

| Setting | Purpose and default |
|---|---|
| `KARARECALL_USERNAME`, `KARARECALL_PASSWORD` | Shared web credentials; example passwords are rejected |
| `KARARECALL_BIND_ADDRESS`, `KARARECALL_PORT` | Host listening address/port, default `127.0.0.1:8765` |
| `KARARECALL_VOLUME_NAME` | Persistent volume, default `kararecall-storage` |
| `KARARECALL_IMAGE_TAG` | Shared published image tag, default `latest` |
| `PUID`, `PGID` | Local build UID/GID only; published images use 10001:10001 |
| `COMPOSE_PROFILES=automation` | Starts the worker with the normal Compose command |
| `SYNC_ENABLED` | Periodic import/processing; false by default |
| `KARAKEEP_BASE_URL`, `KARAKEEP_API_KEY` | Read-only API connection; `/api/v1` is added when needed |
| `KARAKEEP_URL_FILTER`, `KARAKEEP_TAG_FILTER` | Optional filters; empty means all bookmarks |
| `SYNC_INTERVAL_SECONDS`, `WORKER_BATCH_SIZE` | Default 900 seconds and three processing jobs per cycle |
| `DOWNLOAD_MEDIA` | Download configured media/documents; true by default |
| `STORAGE_MIN_FREE_MB` | Reserve during downloads; default 256 MiB |
| `REUSE_SUBTITLES` | Reuse suitable embedded text subtitles before ASR; false by default |
| `MEDIA_MAX_MB`, `MEDIA_MAX_SECONDS` | Default 100 MiB and 300 seconds |
| `PDF_MAX_PAGES` | Default 25 pages, maximum 100 |
| `PDF_OCR_ENABLED`, `PDF_OCR_MAX_PAGES` | Optional scanned-page recognition; false, default cap three pages, maximum ten |
| `IMAGE_OCR_ENABLED` | Optional standalone image recognition; false |
| `HTTP_TIMEOUT_SECONDS` | Per-request network timeout, default 120 seconds |
| `LLM_ENABLED` | Text summaries/tool cards; false |
| `LLM_BASE_URL`, `LLM_API_KEY`, `LLM_MODEL` | OpenAI-compatible text endpoint, key and model |
| `LLM_MAX_INPUT_CHARS` | Default 24,000 characters of evidence per synthesis |
| `LLM_DOCUMENT_SECTIONS` | Optional intermediate summaries for long documents; default zero, maximum ten |
| `ASR_BASE_URL`, `ASR_API_KEY`, `ASR_MODEL` | Audio transcription endpoint/key/model |
| `VISION_BASE_URL`, `VISION_API_KEY`, `VISION_MODEL` | Image-reading service; empty URL/key inherit the text role |
| `VISION_INTERVAL_SECONDS`, `VISION_MAX_FRAMES` | Default minimum five seconds and maximum 12 images |
| `VISION_SAMPLE_MODE` | `regular`, or `changes` to select visual changes within the same image cap |
| `LLM_THINKING`, `VISION_THINKING` | Optional provider `thinking.type`; DeepSeek profile uses `disabled` |
| `AI_TOKEN_LIMIT_PARAM` | Provider-compatible output limit field: `max_tokens` or `max_completion_tokens` |

Use exact model names supported by your server. A text endpoint is not an audio API. ASR requires compatible multipart WAV requests and `verbose_json`; text-only audio output gets whole-media timing rather than invented word timestamps. Vision must support base64 `image_url` input. Local services must be reachable from the NAS; the model's RAM is consumed on its server. If that machine is off, stored results and the web interface remain usable.

Use single quotes for `.env` values containing `$` or `#`. Avoid inline comments when also using the Python CLI loader. Keep credentials in key fields rather than URLs. Recreate services after changing environment settings.

## Import and extraction

The historical import ignores optional filters, includes archived/starred and ordinary bookmarks, deduplicates IDs and downloads no media. Periodic processing selects a bounded batch after importing catalogue changes. Missing bookmarks are retained locally rather than deleted.

When subtitle reuse is enabled, valid text tracks retain their provenance/timestamps and can avoid ASR. Unsupported/malformed tracks do not prevent the configured audio fallback. Vision changes sampling does not increase its configured number of sends.

PDF originals are limited to 20 MiB or the lower media cap. Poppler reads native text with CPU, memory, time and output bounds; optional PDF OCR sends only bounded JPEG previews of blank-text pages. Partially populated text layers are not automatically repaired. Image OCR accepts JPEG, PNG, WebP and GIF up to 20 megapixels. Animated GIF/WebP recognition reads the first frame only and reports partial coverage. Long-document section summaries add bounded paid calls and report represented characters. [Format matrix](formats-and-coverage.md).

## Start, diagnose and retry

```sh
docker compose up -d
docker compose ps
docker compose logs --tail=50 web worker
docker compose --profile automation run --rm worker python -m kararecall.worker check
```

`check` performs read-only access/model-list checks, not inference. For a manual processing cycle:

```sh
docker compose --profile automation stop worker
docker compose --profile automation run --rm worker python -m kararecall.worker once
docker compose up -d
```

A shared volume lock prevents competing writers. Three automatic attempts are allowed by default; explicit retries select a source/stage:

```sh
docker compose --profile automation run --rm worker python -m kararecall.worker retry --source BOOKMARK_ID --stage document
```

Stages include `asr`, `vision`, `document`, `llm` and `all`. `done` means configured steps finished, not exhaustive video understanding. Independent extractions survive another stage's failure; synthesis waits on failed prerequisites. Activity shows stale worker status, low free space, errors and quota pauses.

## Network

Use a LAN/VPN or HTTPS reverse proxy for remote access. Preserve authentication and video `Range`/`HEAD` handling, including HTTP 206. Protect pages, APIs and media together. The application uses one shared account and does not provide role-based multi-user access.

## Backup and restore

Back up **the volume and `.env`**, separately from Git. The volume contains private `data/` and `vault/`, including the selected generation, previous generations, caches, digests and usage ledger. Stop writes for a coherent snapshot:

```sh
umask 077
docker compose --profile automation stop
docker compose run --rm --no-deps -T web tar -C /workspace -czf - data vault > kararecall-backup.tar.gz
cp -p .env .env.backup
docker compose up -d
```

Use a **new, unused volume name** and separate project to test restoration:

```sh
KARARECALL_VOLUME_NAME=kararecall-restore-test docker compose -p kararecall-restore run --rm --no-deps -T web tar -C /workspace -xzf - < kararecall-backup.tar.gz
KARARECALL_VOLUME_NAME=kararecall-restore-test docker compose -p kararecall-restore run --rm --no-deps -T web python scripts/verify_storage.py
```

To import the private historical POC, transfer a `data/`/`vault/` archive over your private network; exclude local model downloads while retaining evidence and required originals. Stop production before selecting a validated restored volume. Keep the previous volume until verification is complete. Changing UID/GID does not automatically change existing file ownership.

Do not run `docker compose down -v` on the real installation: it deletes the data volume. A local generation is not an external backup. Restoring an old usage/delivery ledger requires reconciliation with actual provider charges and messages already sent. [Recovery plan](recovery-and-generations.md).

## Update and rename migration

Pull/redeploy both images using the [Docker guide](docker-images.md), preserving `.env`, the storage volume and proxy configuration. For installations with older project names, explicitly retain the original volume name while changing service/container names; changing the volume selects a different library. Recheck old citations, source playback and exported documents after migration. [Pilot measurements](pilot.md).
