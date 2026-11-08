# Long-term operations

[🇫🇷 Français](../EXPLOITATION-LONG-TERME.md) · [🇬🇧 English](long-term-operations.md)

The starting volume is around twenty videos/month, plus articles and notes. The NAS stores the library and serves the UI; pilot measurements determine which processing to expand.

## Retention and source changes

Keep imported content when a bookmark disappears from Karakeep: its absence might reflect changed permissions/scope rather than deletion. Never delete local proofs or change the upstream bookmark automatically. PDF/image asset changes retain separate originals and archived citations. Replacing a local video is blocked until evidence/playback can bind each old and new version to the correct media hash.

Download caps and disk reserve protect new originals, not total volume growth. Generation copies and caches consume storage too. Retain referenced originals, raw proofs, reading traces, editorial revisions and a verified external backup. Generations currently remain retained; any future purge needs a prior inventory and tested restore, preserving cited files. Hard links share unchanged large files on compatible volumes.

## Long media

Current defaults are 100 MiB/five minutes for video, with a separate 24 MiB prepared-WAV limit. Raise limits only after measuring need. A future audio segmentation feature should use bounded overlapping windows, media hash, window bounds and model configuration in cache keys, validated offsets onto the media clock, overlap deduplication and explicit partial coverage when windows remain pending. Bound total duration, bytes, windows and calls. Test targeted screen reading before increasing image counts. This segmentation is a design direction, not a delivered extractor.

## Search and exports

Use lexical search as the pilot baseline. The fictional reference currently yields 15/20 correct top-three results; real memory questions are still required. If results are below the proposed 16/20 target, compare lexical/hybrid on the same holdout questions, including false positives, abstention, latency and RAM. Future vectors must be reconstructible from portable text/evidence IDs. A separate server database is justified only by measured NAS limits, not the number of containers.

KaraRecall remains the source catalogue. AFFiNE can receive a selected Markdown card; verify title/URL/relative-link behavior in the installed version. Wiki.js can use a separate Markdown/Git destination if synchronization becomes useful. Private evidence requires authorized destinations and equivalent access controls. No automatic connector is included. [AFFiNE adapter reference](https://docs.affine.pro/blocksuite-wip/store/transformer-and-adapter) · [Wiki.js Git storage](https://docs.requarks.io/s/en/storage/git).

Public GHCR web/worker images support AMD64/ARM64, `latest` and common commit pinning. Private data never needs GitHub. [Image guide](docker-images.md).

## Maintenance

Before updating, record installed versions, back up volume/configuration, restore into a new volume and verify integrity. Check an old card, citation and video seek after update. Retain the previous image tag and tested volume for recovery. Repeat after schema changes and at least quarterly in normal operation.

Migration tests must preserve old citations and reject incoherent publication. Review dependency/model changes with a one-source quality/cost comparison before replaying a queue. Old evidence remains tied to the settings that created it. [Restore study](recovery-and-generations.md) · [Pilot](pilot.md).
