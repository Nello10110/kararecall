# Qualify the NAS installation

[🇫🇷 Français](../PILOTE.md) · [🇬🇧 English](pilot.md)

Separate installation checks, read-only Karakeep access, actual inference quality and operational measurements. Reports contain counts/timings rather than bookmark text or keys.

## Storage and first import

Follow [installation](installation.md), import history and run:

```sh
docker compose ps
docker compose exec -T web python scripts/verify_storage.py
```

Check coherent source counts, a searchable article and a note without a URL. For imported POC data, verify an old card and exact citation. Check authenticated playback/seeking through the actual VPN/proxy. Restore a backup into a separate new volume before considering backup/restore qualified.

## Read Karakeep and one attachment

```sh
docker compose --profile automation run --rm worker python scripts/pilot.py --probe-karakeep --probe-media
```

This GET-only probe reads all catalogue pages, deduplicates IDs and counts types/missing text. The media probe tries at most three originals and retains the first successful download only in temporary storage, with a cap of 20 MiB or the lower configured limit. It reports type, bytes and elapsed time; `absent`/`failed` are explicit. No catalogue publication or model request occurs.

## Representative inference

Start with `WORKER_BATCH_SIZE=1`. Check settings, note usage before/after and process one source. Then select around twenty varied real cases: article, note, image/PDF, silent video, proper names, briefly displayed text, ambiguity, multiple tools and missing media. Check raw evidence, faithful French summary, supported parameters, JSON output and timestamp accuracy. Record actual elapsed time and worker memory with the other NAS services running.

```sh
docker compose --profile automation run --rm worker python -m kararecall.worker usage
docker stats --no-stream "$(docker compose ps -q web)" "$(docker compose --profile automation ps -q worker)"
```

For web enrichment, test homonyms, truncated links, unavailable pages and conflicting claims. For MCP, test a remembered purpose, exact passage and absent information from the real assistant/voice client. Real SMTP/webhook acceptance and RSS reading need their configured services.

## Search measurement

Write twenty memory questions before inspecting results in a private `.pilot-questions.json`:

```json
[{"query":"The article about storing heat in winter", "source_id":"BOOKMARK_ID"}]
```

```sh
docker compose --profile automation run --rm \
  --volume "$PWD/.pilot-questions.json:/questions.json:ro" \
  worker python scripts/pilot.py --questions /questions.json
```

The report gives ranks in question order, top-one/top-three counts, median/max latency and peak process memory, excluding questions and IDs. Proposed target: correct source in the top three for at least 16/20 questions. Use the same holdout questions for any lexical/hybrid comparison.

## Coverage, batch cost and HTTP

```sh
docker compose exec -T web python scripts/pilot.py
docker compose exec -T web python scripts/pilot.py --http-url http://127.0.0.1:8765
docker compose exec -T web python scripts/pilot.py --usage-since 2026-11-08T12:00:00Z
```

The normal report includes observed coverage by family without private titles/URLs. HTTP measurement uses the service credentials and reads three routes three times each: compact catalogue, 24-source page and overview. It records sizes/timings, not response content, and refuses redirects. Replace the date example with the actual batch start, including timezone. The batch report reads SQLite without mutation and counts calls, uncertain reservations and configured accounting costs by stage. Missing measured usage does not imply zero billing. Compare initial catch-up and normal monthly work separately.

The worker also records last publication copy/publish timing. Measure search memory and both containers under real NAS load rather than selecting a new database from synthetic timings alone.

## Local reference results

A previous Mac experiment with 2,002 fictional sources/two tools measured median HTTP latencies of 5.3 ms for a 1.19 MB full catalogue, 0.8 ms for an 11.3 kB compact catalogue, 0.5 ms for a 14.3 kB source page and 181 ms for a 149 kB search response. Two publications took 0.29/0.48 seconds; measured process peak was 162 MiB. These were small synthetic media, not a NAS capacity guarantee.

```sh
PYTHONPYCACHEPREFIX=.build/pycache python3 scripts/benchmark_search.py
```

The newer 20-document fictional memory reference has no generated tool cards. Its current result is **15/20 top-one and top-three**, below the proposed 16/20 target; the five misses were not hidden by changing the dataset. The observed small-corpus Mac median was 2.4 ms. Reformulations lacking enough common words expose lexical limits. This justifies preparing a hybrid comparison, not declaring a production embedding choice or validating real memories. No semantic engine is enabled. [Long-term plan](long-term-operations.md).
