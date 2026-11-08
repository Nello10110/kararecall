# All bookmarks and the DeepSeek profile

[🇫🇷 Français](../IMPORT-ET-DEEPSEEK.md) · [🇬🇧 English](import-and-deepseek.md)

This guide replaces the original Instagram-only scope. Normal collection includes all pages of Karakeep bookmarks with `includeContent=true`, without filtering archived or starred entries. Raw JSON, tags, notes and flags are retained. IDs prevent duplicate imports.

## Content used

Sites contribute titles, descriptions, supplied page text/HTML and personal notes. Notes may have no URL; no original link is invented. PDFs/images use supplied text or configured local extraction. Video analysis uses attachments supplied by Karakeep, never a new download directly from Instagram. Unknown formats remain explicit metadata-only/unsupported cases. HTML scripts and styles are excluded from readable text, while raw responses remain evidence of what was received.

Captions, page text, personal notes, audio and OCR remain separate. Karakeep's unverified generated summary is not proof of video contents. The text model can create a short reading summary even when no tool is identified. Tool cards require explicitly named tools and valid citations. Summaries, keywords and source text enrich lexical search; a title alone is not an analyzed article.

## Historical import

1. Configure Karakeep and start web plus worker with the automation profile. Keep `SYNC_ENABLED=false` initially.
2. Select **Activité → Importer tout l’historique**. The durable request reads the full catalogue without AI or downloads.
3. Check source counts and representative articles/notes, then configure analysis separately.

```sh
docker compose --profile automation run --rm worker python -m kararecall.worker import-history
```

The UI and CLI use the same import mechanism. Periodic processing remains bounded by batch size and quotas. [Installation](installation.md) · [Format coverage](formats-and-coverage.md).

## DeepSeek settings

```sh
python3 scripts/setup_env.py --profile deepseek
```

| Setting | Prepared profile value |
|---|---|
| `LLM_BASE_URL`, `VISION_BASE_URL` | `https://api.deepseek.com` |
| `LLM_MODEL`, `VISION_MODEL` | `deepseek-flash` |
| `LLM_API_KEY` | Your key; vision inherits it if its override is empty |
| `AI_TOKEN_LIMIT_PARAM` | `max_tokens` |
| `LLM_THINKING`, `VISION_THINKING` | `disabled` |
| Reasoning effort overrides | Empty |
| ASR endpoint, model and key | Empty; audio is not configured |
| Text/vision input/output accounting rates | Conservative configured reference: USD 0.30/1.20 per million tokens |

The script performs no network requests and refuses to replace `.env`. It leaves synchronization and text generation disabled. A configured vision model can run independently of `LLM_ENABLED`; clear `VISION_MODEL` for a text-only trial. The historical `--profile api` alternative is still available. Model availability and actual rates must be checked against the chosen account; these profile values do not certify successful inference.

ASR uses a separate `audio/transcriptions` contract with `verbose_json`. No compatible DeepSeek audio service was established in the project's reviewed references. Keep ASR off until selecting a local Whisper service or another compatible API. The vision role does not recognize spoken words. [Role contracts](architecture.md#ai-role-contracts).

## Budgets and privacy

All roles share persistent limits and usage accounting. Default limits are 50 daily calls, 400 monthly calls and USD 2/month, using UTC periods. Quotas can pause processing even when estimated dollar usage is low. Keep provider-side spending limits as well. Secrets stay in the worker environment; the web service does not receive them. [Reliability and accounting](reliability.md).

## Invalid vision JSON and retries

Official DeepSeek Chat Completions requests use `response_format: json_object`. OCR requests demand a JSON object with a string `text` field. An empty/whitespace-only response or invalid structured answer can trigger **one additional request**, through the same ledger. Truncation, refusal and HTTP failures are not retried by this rule. The OCR contract version participates in cache keys; audio caches remain separate. Old valid evidence survives failures.

Update **both** images, then use **Réessayer l’analyse de l’écran** for a targeted retry. This invalidates the vision stage only and reuses valid other extractions. Do not clear the library or reset quotas to repair output formatting. If the provider reports truncation, inspect its thinking setting and configured output cap before changing limits. Simulated tests cover blank and invalid responses; the configured NAS provider still requires a real pilot. [DeepSeek JSON output reference](https://api-docs.deepseek.com/guides/json_mode).
