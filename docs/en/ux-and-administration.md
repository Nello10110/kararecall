# Everyday use and administration

[🇫🇷 Français](../UX-ET-ADMINISTRATION.md) · [🇬🇧 English](ux-and-administration.md)

The application helps a user recover a discovery, understand its value and return to evidence. Administration should explain what ran, what failed, what was spent and what is still unavailable without requiring knowledge of internal JSON files.

## Screen responsibilities

| Screen | Main job |
|---|---|
| Dashboard | Recent discoveries, real library counts and actionable alerts |
| Search | One lexical entry point, tools/source scope and cited results |
| Tools | Description, purpose, operation, limitations and useful links |
| Sources | Saved content, original references, media and evidence |
| Activity | Imports, processing commands, progress, cancellation and retry |
| Digests | Readable articles, references and optional delivery controls |
| Administration | Connections, versions, coverage, spending, storage and automation |

Navigation retains historical detail/proof routes. Source filters and sort can be shared through URLs. Tool review/search filters help distinguish edited/reviewed cards from automatic drafts. Mobile navigation, dark/light themes, keyboard focus and native disclosure elements belong to the glass UI system.

## Detail-page hierarchy

Tool pages lead with the name, useful description and the best explicit available destination. Links are not invented or labeled official merely because a domain looks plausible. Original publication/social/failed/credential URLs are excluded from the primary destination. A previously read homepage can still be the primary link. Unchecked links remain labeled unchecked.

Usefulness, operation and limitations precede provenance. Repeated citations are grouped without losing passage destinations. A boilerplate subtitle saying a tool was mentioned in a video gives way to useful sourced content. Full descriptions and source context remain accessible. Editing, merging and research move into the collapsed **Gérer cette fiche** section at the bottom; exports use a native menu.

Sources prioritize reading media/documents beside the evidence. **Gérer cette source** holds processing controls and detailed status. Compact failure/pause notices open the relevant detail. Non-video sources do not show irrelevant audio stages. Digests prioritize article reading before editing/delivery.

## Information actually observed

The dashboard distinguishes source count, summaries, tools requiring review and videos with extraction results. The administrator sees worker heartbeat, last completed run, mismatched web/worker versions, periodic synchronization, configured model roles, download/extraction limits and dated connectivity checks. “Configured” is not “tested”; model-list probes are not inference validation.

Accounting distinguishes daily/monthly call limits and monthly dollar reservation, with UTC periods and uncertain calls retained. Storage reports volume free space and selected publication. **Backup not observed** remains the correct state until a real external copy/restore is observed. Catalogue JSON export is not a full backup. Coverage counts separate metadata, usable content, partial/completed configured analysis and unsupported formats, with actual limitations.

## Controls and boundaries

Pause affects future automatic passes; manual jobs remain possible. Cancellation stops later targets, not an already running external request. Clearing requires explicit `VIDER` confirmation, preserves old generations/budgets/digests and leaves Karakeep untouched. Writes retain authentication, origin/CSRF checks, shared locking and revision conflict protection.

The application does not edit secrets in the UI. Change private `.env`/Dockhand values and recreate the worker. Review and automatic outputs retain citations; user-reviewed content survives later machine processing.

## Validation and remaining work

Synthetic HTTP and rendering tests cover counts, auth, controls, coverage filters and error cases. Earlier local desktop/mobile detail reviews covered the light/dark themes and reading hierarchy on a private copy, not the NAS. Real content ergonomics, provider behavior, translations, video playback through the actual reverse proxy and backup restoration still require feedback. A generation restore button is deliberately not presented as operational before its safety/state reconciliation is implemented. [Web/API](web-and-api.md) · [Recovery study](recovery-and-generations.md) · [Backlog](backlog.md).
