# Previous publications and recovery

[🇫🇷 Français](../RESTAURATION-ET-GENERATIONS.md) · [🇬🇧 English](recovery-and-generations.md)

Published generations are immutable. `data/current.json` selects one coherent publication containing sources, evidence, media and cards. Accounting, pending commands, caches, digests and configuration have separate lifecycles. A local historical generation is not proof of an external backup.

## Read-only inventory and integrity checks

```sh
docker compose exec -T web python -m kararecall.recovery
docker compose exec -T web python -m kararecall.recovery --generation GENERATION_HEX_ID
```

Use an exact generation ID returned by the first command. Verification checks the catalogue, citations, originals, evidence images, supplementary page snapshots and preview hashes. It never switches the publication pointer or resets budgets. Invalid paths, missing generations or inconsistent files fail explicitly. A valid generation still does not prove an archive was copied off the NAS.

## Supported restore procedure

Restore a coherent volume backup into a **new volume**, retaining the private configuration and common image tag. Run `scripts/verify_storage.py` there, then check an old card, citation, article and video seek before changing the production volume selection. Keep the previous production volume for reversal. [Commands](homelab.md#backup-and-restore).

After restoring an old ledger, reconcile provider spending since its snapshot. Old storage does not undo real charges. Keep digest sending suspended until reconciling editions already delivered; an old backup may not know a message was sent.

## Study of an in-app generation restore

A pointer change alone is insufficient: the worker could replay newer state, pending commands/deliveries could resume, or old media might be missing. A future restore workflow must:

1. Acquire the worker lock, suspend automation and show before/after counts.
2. Verify integrity/schema compatibility and prepare a **new** generation based on the selected one.
3. Preserve current usage and delivery ledgers, set aside unfinished commands and reconcile job fingerprints.
4. Publish atomically, record the selection and retain the former current generation for reversal.
5. Require an explicit resume after evidence/media verification.

This restore button is not delivered as an operational capability. Read-only inventory/verification and the new-volume procedure are available.

## External backup observation

A future attestation must come from the actual archive copy/restore process: date, authorized destination, archive hash, image version and a successful independent-volume restoration. Without that evidence, Administration correctly reports **Backup not observed**. NAS storage and external restoration remain real deployment qualification tasks.
