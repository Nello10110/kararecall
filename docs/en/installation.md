# Install KaraRecall on your NAS

[🇫🇷 Français](../INSTALLATION.md) · [🇬🇧 English](installation.md)

Start with a text/metadata import and AI disabled. You need Docker Compose v2, a reachable Karakeep URL and API key. A DeepSeek key is optional until you enable analysis. Run commands in your application directory on the NAS, for example through SSH. The same steps work with OrbStack on a Mac.

## 1. Get the application

```sh
git clone https://github.com/Nello10110/kararecall.git
cd kararecall
```

The repository is public. Without Git, download its ZIP and extract it, keeping hidden files such as `.env.example` and `.dockerignore`. Preserve an existing installation's `.env` and volume.

## 2. Create configuration

```sh
python3 scripts/setup_env.py --profile deepseek
```

Without Python on the NAS:

```sh
docker run --rm --user "$(id -u):$(id -g)" \
  --mount "type=bind,src=$PWD,dst=/app" --workdir /app \
  python:3.12-slim python scripts/setup_env.py --profile deepseek
```

The script creates `.env` with a random web password and disabled paid analysis. It refuses to overwrite an existing file. It does not print the generated password.

## 3. Edit existing settings

```dotenv
COMPOSE_PROFILES=automation
KARARECALL_BIND_ADDRESS=0.0.0.0
KARAKEEP_BASE_URL='https://karakeep.example.net'
KARAKEEP_API_KEY='REPLACE_WITH_YOUR_KEY'
SYNC_ENABLED=false
LLM_ENABLED=false
KARAKEEP_URL_FILTER=
KARAKEEP_TAG_FILTER=
```

Use a Karakeep address reachable from the container. `localhost` refers to the container itself. Empty filters include every bookmark type. The automation profile starts the worker; with synchronization disabled, it waits for manual import requests. Keep `KARARECALL_USERNAME` and `KARARECALL_PASSWORD` from the generated file. Keys and credentials stay in `.env`, outside Git.

Bind to `0.0.0.0` for your LAN, or `127.0.0.1` for a local-only trial. Use a VPN or HTTPS reverse proxy for remote access.

## 4. Start

```sh
docker compose up -d
docker compose ps
```

Public AMD64/ARM64 images are downloaded without compiling on the NAS. Check that web and worker run and that web becomes healthy. Open `http://NAS_IP:8765` and sign in. A new volume has an empty library.

## 5. Import history

Select **Activité → Importer tout l’historique**. Wait for completion, then open **Sources** or **Recherche**. Text already supplied by Karakeep is immediately searchable. Repeating an import updates the same bookmark ID without duplication. This import performs no AI calls or media downloads. Files without supplied text remain metadata-only until extraction is configured.

## 6. Enable DeepSeek and automatic processing

Stop the periodic worker for a one-source trial:

```sh
docker compose stop worker
```

Edit `.env`:

```dotenv
LLM_API_KEY='REPLACE_WITH_YOUR_DEEPSEEK_KEY'
LLM_ENABLED=true
SYNC_ENABLED=true
WORKER_BATCH_SIZE=1
```

Keep the profile's prepared endpoint/model settings and check their availability with your provider. Text and vision share the key when the vision override is empty. These stages can be billed. The default application accounting budget is USD 2/month.

For text-only processing, clear `VISION_MODEL` and set `DOWNLOAD_MEDIA=false`. Configure audio separately; a text/vision model is not automatically a speech recognition service.

```sh
docker compose run --rm --no-deps worker python -m kararecall.worker check &&
  docker compose run --rm --no-deps worker python -m kararecall.worker once
```

`check` probes access/model lists without inference; `once` runs configured stages. Review the resulting summary, evidence and errors in the UI. When satisfied:

```sh
docker compose up -d worker
```

The loop runs immediately and then every 15 minutes by default. Raise `WORKER_BATCH_SIZE` later if appropriate. Recreate the worker after changing `.env`; unchanged successful results are cached.

## Troubleshooting

| Symptom | Check |
|---|---|
| Cannot clone | GitHub network access, or use the ZIP method |
| `.env` already exists | Edit it rather than overwriting credentials |
| Page inaccessible | Correct NAS IP, bind address, firewall and `docker compose ps` |
| Port occupied | Change `KARARECALL_PORT`, recreate and use the new port |
| Import remains queued | Automation profile and running worker |
| Karakeep 401/403 | Container-reachable base URL and API key |
| AI error | Provider key, model availability, account credit and stage error |
| Quota/budget pause | Inspect counters and renewal periods; do not reset the ledger |
| Settings have no effect | Recreate services with `docker compose up -d` |

```sh
docker compose logs --tail=50 web worker
```

## Update and next steps

```sh
git pull --ff-only
docker compose --profile automation pull web worker
docker compose --profile automation up -d --no-deps web worker
```

Compare `.env.example` with your file while preserving private values. A custom Compose already using `latest` only needs image pull/redeployment. Keep the named volume `kararecall-storage`; `docker compose stop` stops services while retaining data. [Backup](homelab.md#backup-and-restore).

After an update, **Résumer / traduire** processes saved evidence, while **Relancer l’analyse complète** refreshes a source from Karakeep. Global commands use the durable worker queue and quotas. Optional periodic tool research uses `WEB_RESEARCH_ENABLED=true`; explicit research buttons do not require periodic research. [Import and models](import-and-deepseek.md) · [Digests](digests.md) · [Web controls](web-and-api.md).
