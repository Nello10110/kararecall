# Automatic weekly and monthly digests

[🇫🇷 Français](../VEILLE.md) · [🇬🇧 English](digests.md)

KaraRecall writes illustrated articles from saved bookmarks and evidence. Each discovery gets a title and two or three short paragraphs about its subject, usefulness and operation where the sources support them. Paragraphs retain references. Available video/page images illustrate articles without becoming new evidence for unsupported claims.

An initial edition selects historical discoveries, even when they were saved months ago. Later editions cover the completed week/month. Writing, selection for distribution and send requests are automatic by default; manual editing remains optional. Actual sending still requires channel configuration and `DIGEST_SEND_ENABLED`.

## Initial setup

The worker needs Karakeep and text-model access. Digest writing shares the normal model, budget and quotas. Completed articles are cached; count an additional writing call per newly drafted article.

```dotenv
COMPOSE_PROFILES=automation
SYNC_ENABLED=true
LLM_ENABLED=true
DIGEST_ENABLED=true
DIGEST_WRITE_ARTICLES=true
DIGEST_INITIAL_HISTORY=true
DIGEST_INITIAL_MAX_ITEMS=6
DIGEST_AUTO_APPROVE=true
DIGEST_AUTO_SEND=true
DIGEST_WEEKLY=true
DIGEST_MONTHLY=true
DIGEST_TIMEZONE=Europe/Paris
DIGEST_TIME=08:00
DIGEST_WEEKDAY=0
DIGEST_MONTHDAY=1
DIGEST_SCOPE=added
DIGEST_WEEKLY_MAX_ITEMS=12
DIGEST_MONTHLY_MAX_ITEMS=24
KARARECALL_PUBLIC_URL=http://NAS_IP:8765
```

Monday is zero; monthly days are 1–28. Between imports, the worker checks due periods approximately every 30 seconds and deduplicates editions by interval. The initial edition is prepared once a nonempty catalogue exists. `analyzed` scope selects processed sources; `viewed` requires `DIGEST_TRACK_VIEWS=true` and tracks opens only after activation. Historical selection uses bookmark creation dates. Selection limits retain recent discoveries and previously presented items are recognized as additions rather than duplicated claims.

Missing model configuration is reported as waiting. Invalid references are rejected. An interruption/quota preserves completed articles and postpones the rest rather than destroying older editions or stopping collection. Editorial output is currently French, even when following this English guide.

## Email delivery

```dotenv
DIGEST_SEND_ENABLED=true
DIGEST_CHANNELS=email
DIGEST_SMTP_HOST=smtp.example.net
DIGEST_SMTP_PORT=587
DIGEST_SMTP_TLS=starttls
DIGEST_SMTP_USERNAME=your-login
DIGEST_SMTP_PASSWORD=your-secret
DIGEST_EMAIL_FROM=discoveries@example.net
DIGEST_EMAIL_TO=recipient@example.net
```

The configured worker sends ready/approved editions as plain text and HTML, with inline images. Existing references do not certify faithful model prose. Up to twenty comma-separated recipients are supported; each receives a separate message. For implicit TLS, select `ssl` and the relay's port, typically 465. `DIGEST_AUTO_APPROVE=false` enables the optional manual **Valider pour diffusion** workflow.

The **Veille** page shows articles, references and delivery state. Standalone HTML can be printed to PDF in the browser. Markdown preserves text and references. Private RSS contains editions selected for distribution and requires application authentication.

## Webhook and other formats

```dotenv
DIGEST_CHANNELS=webhook
DIGEST_WEBHOOK_URL=https://your-service.example/webhook/discoveries
DIGEST_WEBHOOK_TOKEN=
```

Use `email,webhook` for both channels. Webhook JSON includes `id`, `title`, `start`, `end`, `markdown` and `html`, with a deterministic idempotency key and optional Bearer token. Use HTTPS; loopback HTTP is allowed for tests. Redirects are refused. A service requiring its own message format needs a transformation in your automation.

Relay acceptance and uncertain delivery are separate states. A failure after sending starts does not automatically resend: check the relay/destination to avoid duplicates. Receipts retain a hashed destination identity; raw addresses/secrets remain in private configuration.

## Storage and commands

The shared named volume is mounted at `/workspace`. Editions, copied images, views, revisions and receipts live in `data/digests/` and are included in backups of `data/`. Container recreation retains them while the volume name stays unchanged. Recreate the worker after `.env` changes.

```sh
docker compose --profile automation run --rm worker python -m kararecall.worker digest-generate --kind weekly --anchor 2026-11-02
docker compose --profile automation run --rm worker python -m kararecall.worker digest-run
```

The first command prepares a chosen edition; `--kind initial` uses history. The second checks schedules, pending writing and configured automatic sends. Synthetic tests use simulated transports. The actual NAS SMTP relay, webhook and RSS reader still need qualification. [Backup](homelab.md#backup-and-restore) · [API](web-and-api.md#digest-api).
