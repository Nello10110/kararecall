# Web interface and API

[🇫🇷 Français](../WEB.md) · [🇬🇧 English](web-and-api.md)

The standard-library HTTP server runs from `kararecall/web_server.py`; no frontend compilation is required. For a local development session:

```sh
python3 -m kararecall.web_server --open-browser
```

The default address is `127.0.0.1:8765`. Existing `.env` configuration is loaded from the project root. Network listening requires configured web credentials. The macOS launcher is under `scripts/macos/`. Docker uses the same server with mandatory configured authentication.

## Screens and reading

- **Tableau de bord:** real counts, recent bookmarks, quotas and alerts.
- **Recherche:** local lexical search across tools and sources; no model call.
- **Mes outils:** useful description and explicit destination links first, then usage, operation, limitations and evidence. Automatic cards remain marked for review. Editing, merging and web enrichment are in a collapsed maintenance section at the bottom.
- **Sources:** paginated bookmarks, source type/state/coverage filters, media or document reading, separate evidence tabs and original-text access.
- **Activité:** durable commands, history import, progress, cancellation, individual stages and retries. A successful transcript may coexist with failed vision.
- **Veille:** illustrated articles first, then optional editorial/delivery controls.
- **Administration:** connections/health, content coverage, accounting, storage/backup observation and automation.

Titles are limited to 80 characters and editorial source summaries to one sentence/180 characters. Editorial text remains French. The original caption is not used as an unbounded display title. Translation is stored separately from original evidence. Hashtags and promotion are removed from editorial views rather than erased from raw proof. Original evidence and earlier revisions remain accessible.

## Authentication and file access

HTTP Basic protects pages, APIs and media together. Administrative writes also require an allowed origin, JSON and `X-KaraRecall-CSRF`, obtained from `/api/control`. Arbitrary `.env`, raw API responses, model files and scripts are not served. Media is restricted to listed catalogue assets. `HEAD` and byte `Range` support video seeking; reverse proxies must preserve these and HTTP 206/Authorization.

A request uses one coherent generation. The catalogue reloads when publication changes. Editorial writes share the worker lock and reject stale revisions. There is one shared application account, without roles or multi-user access control.

## Reading routes

| Route | Result |
|---|---|
| `/api/health` | HTTP server health |
| `/api/control` | CSRF token and durable command/import status |
| `/api/catalog` | Catalogue, counters and public worker state |
| `/api/catalog?compact=1` | Startup projection with recent/linked sources |
| `/api/sources` | Paginated summaries, default 24, maximum 100 |
| `/api/sources/ID` | Source and evidence |
| `/api/sources/ID/thumbnail` | Authenticated local preview or generic cover |
| `/api/search?q=…&scope=all` | Search; scope also accepts `tools` or `sources` |
| `/api/tools/ID` | Tool card and source summaries |
| `/api/research/ID` | Existing tool web-research trace |
| `/api/editorial/ID` | Latest editorial revision with previous content |
| `/api/context/ID` | Tool context Markdown |
| `/api/overview`, `/api/administration` | Read-only operational views |
| `/api/administration/diagnostic` | Downloadable counters/operational metadata without private content |
| `/download/catalog.json` | Explicit private catalogue export, not a complete backup |
| `/download/tool/ID.md`, `/download/source/ID.md` | Markdown exports |
| `/download/document/ID/ASSET_ID` | Authorized original attached to current/archived evidence |
| `/assets/…` | Allowed catalogue media/images |

Source query parameters include `limit`, `offset`, `q`, `type=all|article|video|note|file`, `sort=recent|oldest` and `stage=all|failed|paused|pending|summarized|complete|partial`. Filters apply before pagination. Historical `complete`/`partial` stage filters concern videos. The separate `support=metadata|content|partial|analyzed|unsupported` filter reports actual content coverage. State is preserved in source URLs.

## Commands

`POST /api/import-history` receives `{}` and persists a whole-catalogue import without AI/downloads. It ignores periodic URL/tag filters and remains available when synchronization is disabled.

`POST /api/tools/ID/edit` requires the current revision, and the other card's revision for merges. It preserves history and citations; reviewed/edited cards survive later machine processing. Old merged routes remain usable.

`POST /api/actions` accepts `kind=llm|refresh|research|clear|check`. Optional `source_id` selects one source for editorial generation; without it, `llm` snapshots all current sources. `refresh` requires a source and accepts `stage=all|asr|vision|document|llm`. Research can select `tool_id`. Active duplicate commands are not queued twice. The worker processes persistent targets sequentially and resumes after restart/quota.

- **Résumer / traduire:** use saved evidence without Karakeep/media requests. A missing article cannot be synthesized from its title alone.
- **Relancer l’analyse complète:** reread the source from Karakeep and retry configured stages; explicit forced stages may make new paid calls.
- **Réessayer l’analyse de l’écran:** refresh only vision while retaining other valid extractions.
- **Enrichir la description sur le web:** explicit search/fetch and evidence-backed French editorial addition. It may run with periodic research disabled.
- **Vider la bibliothèque locale:** requires `confirmation: "VIDER"`. Publishes an empty library, cancels queued work and suspends synchronization. Karakeep, old generations, digests and accounting remain. It does not free their disk space or reset spending.
- **Vérifier les connexions:** read-only worker probes, without inference; this is not a model-quality test.

`POST /api/actions/ID/cancel` cancels later targets; an already running operation may finish. `POST /api/automation` with `paused: true|false` suspends/resumes future periodic passes without changing `.env` quotas or credentials. Manual commands remain possible. A prior explicit administrative pause survives historical import; only the pause created by clearing the library is automatically lifted by the next import.

## Previews and partial sources

Thumbnails prefer normalized Karakeep images or a local video frame, then valid evidence images and finally an explicit generic SVG cover. Reading a thumbnail calls no external site/model. Worker acquisition requires `DOWNLOAD_MEDIA=true`, tries at most three 8 MiB images and normalizes rasters with a pixel bound. Preview failure cannot block analysis; missing previews can retry after six hours. Generations/backups preserve previews.

Site text comes from inline text/HTML, a separate Karakeep HTML asset, or the readable-content API after a successful Karakeep crawl. At most 32 content chunks/8 MiB are read; repeated cursors or changing content versions are rejected. Raw responses/hashes accompany evidence. This extra page acquisition does not make local video processing depend on a readable host page. A metadata-only summary is labeled as such.

French speech is displayed as soon as available even when vision is paused and no editorial summary exists. Stored audio language/valid old extraction metadata can be read without rewriting a generation. Original foreign text remains visible through the original-evidence toggle; a missing translation produces a clear notice rather than fake empty passages. Quota messages distinguish daily renewal at UTC midnight, monthly call caps and insufficient budget reservation.

## Digest API

Authenticated GET routes: `/api/digests`, `/api/digests/ID`, `/api/digests/ID/article.html`, `/api/digests/ID/article.md`, `/api/digests/feed.xml` and `/api/digests/assets/HASH.jpg` (PNG also supported). CSRF-protected POST routes: `/api/digests/generate`, `/api/digests/ID/edit`, `/api/digests/ID/approve`, `/api/digests/ID/send`, `/api/digests/view`. Revisions prevent stale edits; deterministic period/channel/destination keys deduplicate editions and sends. Uncertain delivery needs operator verification. [Digest configuration](digests.md).

## Frontend organization and coverage

`web/app.js` handles routing and source/evidence views; `workspace.js` consultation/administration; `details.js` shared detail components; `digests.js` digest views. Base styles and glass/detail layers remain local under a strict CSP. Native disclosures/menus support keyboard use, visible focus and responsive layouts. Reading a detail page adds no model call.

`coverage_state` contains a known content family, state, French label and observed limitations. The Administration coverage view aggregates it without publishing source IDs, titles or domains. A summary does not certify completeness. GIF/WebP animation analysis reads one frame; unknown/archive attachments remain explicit limitations. [Formats](formats-and-coverage.md) · [UX review](ux-and-administration.md).
