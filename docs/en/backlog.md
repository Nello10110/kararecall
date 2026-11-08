# KaraRecall backlog

[🇫🇷 Français](../BACKLOG.md) · [🇬🇧 English](backlog.md)

Status: release 0.5.1. This English roadmap mirrors the remaining qualification work in the French backlog. Completed implementation is grouped below; an unchecked real-world task is not completed merely because synthetic tests pass. The owner has started the NAS pilot and reported an initial analyzed bookmark. Planning volume remains about twenty videos/month, plus sites/articles/notes.

## Delivered foundation

- [x] Portable read-only Karakeep library, all bookmark types included by default, historical import without AI/downloads and ID-based deduplication.
- [x] Immutable evidence/provenance and media hashes, complete draft generations, atomic publication and preserved old citations.
- [x] Durable processing/cache contracts, explicit stage retry, independent extraction stages, silent/no-audio handling and honest partial states.
- [x] Configurable text/vision/ASR roles, DeepSeek profile, per-request output bounds, persistent usage reservations, UTC call quotas and configurable accounting budget.
- [x] Authenticated browser UI, lexical search, source/video/PDF evidence, French editorial titles/summaries/translations and portable Markdown/context exports.
- [x] Revision-safe review/merging, preserved history, durable manual/global commands, cancellation, pause and explicitly confirmed local clear without upstream changes.
- [x] Bounded optional tool web research with caching, candidate/reading distinction, attribution and dated traces.
- [x] Illustrated initial/weekly/monthly articles, automatic writing, configurable scheduling, email, private RSS, webhook and HTML/Markdown/PDF-through-browser output.
- [x] Embedded subtitle reuse, optional image-change sampling, long-document section summaries and explicit coverage.
- [x] Read-only stdio MCP with bounded source/evidence/context access and citation/absent-data tests.
- [x] Glass light/dark/mobile workspace, clear detail-page reading hierarchy, useful tool links and collapsed maintenance controls.
- [x] Public tested GHCR web/worker images for AMD64/ARM64, common commit pinning and guarded `latest` promotion.
- [x] Independent previews/generic covers, separate HTML/readable-content acquisition, linked PDF extraction, JPEG/PNG/WebP/GIF OCR and first-frame animation limits.
- [x] Content matrix and coverage administration/filters, explicit unsupported attachments and no inference spending on unsupported formats.
- [x] Read-only coverage, HTTP performance, batch accounting and historical-generation integrity tools; documented safe restore study.
- [x] Synthetic 2,002-source publication/pagination reference and 20-question lexical baseline: 15/20 top-three, with misses retained.
- [x] Repository package/dependency/deployment organization, bilingual documentation navigation and English guides.

## Real providers and NAS foundation

- [ ] Validate actual audio/vision/text contracts, unsupported parameters, timestamps and JSON; connection checks alone are insufficient.
- [ ] Read bookmarks and download at least one attachment through the actual Karakeep REST API, without upstream changes or direct Instagram access.
- [ ] Measure total bookmarks and missing page text on the real first import; qualify articles, notes and files as well as videos.
- [ ] Qualify twenty varied sources: silence, proper names, short on-screen text, ambiguity, multiple tools and absent media; measure fidelity, duration and RAM.
- [ ] Measure a real batch cost before large catch-up; separate historical import/processing from recurring monthly cost.
- [ ] Verify the NAS Compose deployment, private `.env`, UID/GID, network reachability, disk and resource behavior.
- [ ] Import private POC data directly into the volume, outside GitHub, and verify rebuild/original references.
- [ ] Verify the chosen LAN/VPN/HTTPS proxy with authentication, media access and partial video requests.
- [ ] Back up volume/configuration, restore into a genuinely new volume and test update/recovery.
- [ ] Measure worker load alongside the other NAS services.

## Content types and everyday use

- [ ] Confirm upload/bookmark/attachment types actually accepted by the installed Karakeep version; do not assume MP3/office support from filenames or a different version.
- [ ] Complete real qualification for encrypted PDFs, private sources/hosts, language fidelity, memory, timing and retries.
- [ ] Add other extractors only when the NAS inventory establishes useful currently unsupported formats.
- [ ] Qualify the matrix on the NAS, especially the reported sites and Instagram/YouTube items, and document observed format limits.
- [ ] Qualify web enrichment using the actual DeepSeek account, including homonyms and contradictions.
- [ ] Gather usage feedback, adjust navigation/filters and improve retry actions/error explanations.
- [ ] Qualify actual SMTP/webhook delivery and NAS RSS reading, then review the first digest presentations.
- [ ] Qualify natural/voice assistant requests and abstention when information is absent.
- [ ] Measure twenty independent real-memory questions; proposed target is 16/20 correct top-three results. The fictional reference does not validate the actual NAS library.
- [ ] Measure copy/rebuild and HTTP pagination on real NAS history.
- [ ] Measure representative search latency/RAM before choosing a new engine or server database.
- [ ] Qualify the new commands and translation fidelity with actual NAS models/content.
- [ ] Verify configuration states, provider checks and UI workflows on the NAS after updating both images.
- [ ] Qualify real external restoration before offering an in-app switch to an old generation.
- [ ] Validate image pull and coordinated service update through the NAS Dockhand setup.
- [ ] Confirm the formerly failing vision source resumes with the structured-output fix and inspect its recognized text/references.
- [ ] Confirm detail-page reading comfort and primary links on real NAS content after the UX update.
- [ ] Run the coverage/HTTP/accounting tools on the NAS and record memory, batch cost and external backup results.

## Conditional follow-up

A local Mac model service requires explicit endpoint/authentication and comparison on identical samples. Additional media extractors depend on observed supported inputs. Hybrid search requires the same holdout questions, rebuildable vectors, false-positive/abstention evaluation and a measured NAS resource budget. Long-audio segmentation needs bounded windows, offset reconciliation and resumable evidence identities. These are conditional extensions rather than claims of completed production support.

## Acceptance

Every imported source has a preview and an honest coverage state. Claims retain exact evidence, documentary URLs/traces are distinct from source claims, retries preserve earlier results and publishing is coherent. A usable Compose stack is not, by itself, an autonomous-operation sign-off. Actual provider quality, network/authenticated playback, cost, resources and external restoration must be demonstrated. [Pilot](pilot.md) · [Reliability](reliability.md) · [Format matrix](formats-and-coverage.md).
