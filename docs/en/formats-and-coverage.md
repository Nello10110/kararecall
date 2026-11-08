# Formats and actual coverage

[🇫🇷 Français](../FORMATS-ET-COUVERTURE.md) · [🇬🇧 English](formats-and-coverage.md)

Import, text acquisition, editorial generation and video analysis are distinct. All bookmark records are retained by default; unavailable or unsupported contents must not silently become an analyzed source.

## Karakeep contract

The official schema distinguishes `link`, `text`, `asset` and `unknown` bookmarks. Standalone assets declare `image` or `pdf`. Attachments have a separate enum: `linkHtmlContent`, `screenshot`, `pdf`, `assetScreenshot`, `bannerImage`, `fullPageArchive`, `video`, `bookmarkAsset`, `precrawledArchive`, `userUploaded`, `avatar`, `unknown`. Link fields can reference HTML, image, screenshot, PDF and video assets. [Reviewed schema revision](https://github.com/karakeep-app/karakeep/blob/a891444dae92a673df800185ae3ad1d7b0fef61d/packages/open-api/karakeep-openapi-spec.json) · [0.30 bookmark reference](https://docs.karakeep.com/v0.30.0/api/get-a-single-bookmark).

This schema does not establish the NAS version, accepted upload formats or available content for a particular host. Audio-only/office files absent from the supported contract remain inventoried and explicitly unsupported. A filename never causes execution of a tool.

## Processing matrix

| Input | Processing | Explicit limit |
|---|---|---|
| Site/article with text or HTML | Readable page evidence, search and configured French summary | Long-document coverage; source attribution |
| Separate Karakeep HTML asset | Bounded read, archived content and provenance hash | Error/retry state; no original-site crawl |
| Successfully crawled page missing inline content | Bounded readable-content API | Consistent chunks; no full-document summary from a title |
| Pending/failed/private page | Preserve metadata and later upstream updates | Unavailable principal content stays absent |
| Text note, with/without URL | Note evidence, search/export and configured summary | Personal note is distinct from publisher claims |
| Standalone PDF or PDF attached to a link | Original, Poppler page text, optional blank-page OCR | 20 MiB, page/time/memory limits and visible truncation |
| Scanned PDF | Bounded page previews plus configured vision | No invented text with OCR disabled |
| Protected/damaged PDF | Explicit extraction failure, old evidence retained | No password bypass; real encrypted samples still need qualification |
| JPEG/PNG/WebP/GIF image | Original and optional OCR from normalized JPEG | 20 megapixels/20 MiB; unreadable input reported |
| Animated GIF/WebP | First frame only | Frame counts/partial coverage; no motion analysis |
| TIFF/BMP/other image encoding | Import/original; explicit OCR failure if unsupported | Not advertised as successful recognition |
| Attached video from Instagram, YouTube or another host | Local media, optional embedded subtitles, configured ASR/vision | Size/duration caps, independent stages and sampled screen text |
| Instagram/YouTube link without an attached video | Karakeep text only | No transcription/full video analysis or direct host download |
| Banner/screenshot | Local normalized preview, no AI | A preview is not content analysis |
| Complete/pre-crawled archive, uploaded/unknown attachment | Inventoried reference | No automatic unpacking/execution; unextracted attachments remain visible |

Every source has a local or generic preview. `DOWNLOAD_MEDIA` controls acquisition; the generic cover remains available without it.

## UI and validation

**Administration → Couverture des contenus** shows counts by type and coverage; source filters apply before pagination. A source explains whether it has metadata only, available content, partial analysis, completed configured analysis or an unsupported format. Completed video analysis still means sampled screen reading within configured bounds, not exhaustive comprehension. Preserved old summaries do not turn new failures into success.

Synthetic tests cover 13 record families, inline/separate HTML, deduplication, search/export, auth, native/linked/scanned/corrupted PDFs, four image encodings, first-frame animation, audio/no-audio video, subtitles, quotas, retries and old evidence. Poppler/media dependencies run in Docker CI. Real NAS version/upload support, encrypted PDFs, private hosts, inference fidelity, memory and throughput remain pilot checks. [Pilot](pilot.md).
