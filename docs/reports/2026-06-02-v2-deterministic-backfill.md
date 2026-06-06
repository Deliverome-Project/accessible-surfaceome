# v2 deterministic-feature backfill — results

**Date:** 2026-06-02 · **Branch:** stacked on PR #47 (`claude/pedantic-mendel-d0be83`) · **PR #53**

## Why

When the genome-wide **v2** deep-dive runs, each record's deterministic features
(orthologs / paralogs / isoform topology / canonical "main" topology) are read
from D1. Those feature tables were swept for the **v1** triage scope, so v2
candidates outside it would render with blank blocks. This work completes the
feature tables for the full v2 candidate scope and adds an explicit
"checked, none found" sentinel so genuine absence is distinguishable from
not-yet-computed.

## Scope

The candidate-set union `build_topology_candidate_set.py` already defines —
DB-positive (`in_db_union=1`) **OR** v2 triage `yes`/`contextual`:
**6,431 rows → 6,418 distinct accessions** (`db_only` 2,182 + `triage_only` 858 +
`both` 3,391).

## What was missing vs. what actually needed compute

The raw "no D1 row" counts are upper bounds dominated by genuine absence
(single-isoform genes, genes with no one2one ortholog). Measured empirically:

| Cohort | Genes w/ no row | **New DeepTMHMM sequences** | Genuine-absence (flag only) |
|---|---|---|---|
| Canonical | 66 | 66 | 0 |
| Isoforms | 3,014 | ~141 (3% of missing have an alt isoform) | ~2,934 single-isoform |
| Orthologs | 1,360 | ~1,190 mouse+cyno (~50% have a one2one) | ~674 no one2one |
| Paralogs | 953 | 0 (ECD reuses each paralog's canonical row) | — |

**Total ≈ ~1,400 new DeepTMHMM sequences**, single-worker-friendly.

## What landed in D1 (both public + private, version-pinned)

Sweeps ran under isolated scratch `topology_version` labels (`v2bf_*`) to avoid
run-dir batch collisions, then the upload normalized each JSONL's embedded
version back to the **existing production versions** so rows extend them in
place (`INSERT OR IGNORE`) — never minting a new "latest" that would orphan the
~11k existing rows.

| Table | Version (existing, pinned) | New rows |
|---|---|---|
| `topology_public` canonical | `topo_2026_05_16` | +122 |
| `topology_public` isoforms | `topo_2026_05_25` | +88 |
| `topology_public` mouse_ortholog | `topo_2026_05_16` | +442 |
| `topology_public` cyno_ortholog | `topo_2026_05_16` | +456 |
| `compara_ortholog_ecd` | **`orthologecd_topo_2026_05_16_idfix`** | +898 |
| `compara_paralog` | `paralog_topo_2026_05_16` | +1,027 |

`ecd_pct_similarity` recomputed for the new close (≥80%) paralog pairs (1,177
written). **Orphan check passed** — every `_latest_*` version unchanged after the
write. Functional fetch confirmed: a backfilled gene now returns mouse/cyno
orthologs (`checked=True`), paralogs with topology, isoform topologies, and
canonical TM count.

## Code changes

- **Checked-none sentinel** — `Orthologs.checked`, `DeterministicFeatures.paralogs_checked` /
  `isoform_topologies_checked` (Pydantic + TS mirror), stamped by the loader so a
  checked-but-empty feature is distinguishable from a never-computed stub.
- **`compara_paralog.ecd_pct_similarity`** documented in both `.sql` schemas; the
  viewer TS `ParalogEntry` re-synced to carry #47's paralog topology fields
  (≥80% close-paralog promotion).
- **Coverage audit** — `audit/v2_deterministic_coverage.py` classifier + tested,
  `scripts/audit_v2_deterministic_coverage.py` writes the manifest.
- **Reproducible runbooks** — `scripts/run_v2_backfill_sweeps.sh` (resumable,
  `--skip-upload`, 2-worker) and `scripts/upload_v2_backfill_to_d1.sh`
  (version-normalize → upload; `DRYRUN`/`PUBLIC_ONLY`/`PRIVATE_ONLY` toggles).

## CI note

`scripts/check-py.sh` is red **only from pre-existing #47 issues** in files this
PR does not touch: 5 `ty` diagnostics (`cloud/surface_annotation.py`,
`tests/test_surface_annotation_publish.py`, `tools/pubmed_lookup.py`) and 4 ruff
errors (`data/analysis/figures/make_db_correctness_by_class.py`). This PR's new
code is ruff- + ty-clean and its tests pass (26). Those failures resolve on the
#47 base, not here.
