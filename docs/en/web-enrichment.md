# Web enrichment and attribution

[🇫🇷 Français](../RECHERCHE-WEB.md) · [🇬🇧 English](web-enrichment.md)

Optional web research supplements an already published tool card without replacing the original source. The worker processes a bounded tool group, sharing successful searches/reads across bookmarks and quota retries. An unavailable search service leaves existing cards usable.

```sh
docker compose --profile automation run --rm worker python -m kararecall.worker research --tool TOOL_ID
```

`--refresh` explicitly reruns a group. Explicit UI commands can work with `WEB_RESEARCH_ENABLED=false`; that flag controls periodic research. A configured research key is required, inherited from the text key for the official DeepSeek endpoint or supplied through `DEEPSEEK_RESEARCH_API_KEY`.

## Request and reading contract

Send only the tool name and useful public candidate addresses, not private notes/transcripts/bookmark IDs. Bound one search and up to two reads per new tool, input sizes, timeout and retries. Reserve budget before each request and retain empty/ambiguous results with dates to avoid loops.

The NAS connects to the fixed configured search/fetch API, not directly to newly discovered sites. Candidate URLs must be public HTTP(S), without credentials, private/local destinations, signed tokens or truncated domains. API redirects are refused. Fetched pages/search results are untrusted content, not instructions.

Separate links merely listed in results from actually read pages. Traces preserve provider, requested URL, date, bounded excerpts and final URL when available. The reviewed DeepSeek Fetch response did not provide a final redirected URL, so do not imply it was verified. Empty/unavailable reading is a dated result, not proof that the site vanished. Confirm identity before attributing statements to a publisher; a matching name/domain alone does not resolve homonyms.

## Editorial notes and qualification

A French supplementary description uses only read passages and cites their URLs. Publisher-documentation notes require identity/passage review and retain a documentary status. They do not verify performance or overwrite source claims/manual corrections. Ambiguity should yield candidate links or abstention; contradictions remain visible. Existing proof references remain accessible.

The pilot needs a homonym, incomplete URL, unavailable page, repeated bookmarks for one tool and contradictory claims with the actual account. Synthetic tests cover caching, ambiguity and quota continuation, not real provider quality.

## Historical provider comparison

The French study recorded public tariffs on 5 November 2026, not a live price guarantee. For twenty distinct tools with one search/two pages each, its reference estimates were USD 0.045 for 60 successful DeepSeek Search/Fetch calls at USD 0.75/thousand; about USD 0.10 for twenty Brave searches before credits/reader costs; about 80 Firecrawl credits for short search plus basic scraping. LLM writing is additional and account quotas are shared. DeepSeek was the first pilot candidate because the user already had a key; Brave/Firecrawl remain comparison options for extraction needs.

Check actual account terms/rates before changing providers. [DeepSeek search contract](https://api-docs.deepseek.com/guides/search) · [Brave API](https://brave.com/search/api/) · [Firecrawl pricing](https://www.firecrawl.dev/pricing) · [Accounting](reliability.md#budget-ledger).
