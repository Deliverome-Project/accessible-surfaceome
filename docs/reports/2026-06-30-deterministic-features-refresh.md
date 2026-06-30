# Deterministic-features refresh — pubmed-triage + PR #86 v3 additions

**Date:** 2026-06-30
**Scope:** Compute DeepTMHMM topology (+ paralog ECD, ortholog ECD) for genes newly
added to the catalogue by (a) the PubMed triage rerun and (b) the PR #86 v3 rebuild,
then append them to the existing D1 topology/paralog/ortholog versions
**without** disturbing the genes already covered.

## Why

Two recent catalogue changes added genes that had never been through the topology
sweep, so their `deterministic_features` block is schema-incomplete (no DeepTMHMM
topology, no paralog/ortholog ECD):

1. **PubMed triage rerun** (`triage_run.run_id = genome_full_sonnet_pubmed_ncbi_v1`)
   — 177 genes with `predicted_verdict ∈ {yes, contextual}`.
2. **PR #86 v3 rebuild** (`candidate_universe_v3` 5,105 → 5,151) — net +46 genes
   (50 added, 4 removed).

All gene resolution is HGNC-ID-first per the repo's resolver contract; symbols are
only used to translate legacy symbol-keyed sources.

## Gap analysis (read-only, vs. public D1)

Coverage was checked against the live `topology_public` (active human_canonical
version `topo_2026_05_16`).

| Batch | New genes | Missing canonical topology | Notes |
|---|---|---|---|
| PubMed rerun | 177 | **54** | other 123 already in D1 |
| PR #86 v3 adds | 50 | **8** | other 42 already in D1; none overlap the PubMed batch |

The 8 PR #86 genes missing topology: **BLTP2, CFAP65, LTAP1, PIP4P1, SERTM2,
SIGMAR1, TMUB1, VEZT**.

Features that did **not** need recomputation:

- **SURFACE-Bind** — a fixed published dataset (~2,700 proteins from the
  SURFACE-Bind repo). Sparse coverage of the new genes is expected, not a gap.
- **Schweke homo-oligomer** — handled separately.

## What is being computed

A topology sweep (`scripts/run_topology_sweep.py`) per batch, run with
`--max-workers 1` (sequential batches — gentle memory footprint), producing for
each cohort `human_canonical | human_isoforms | mouse_ortholog | cyno_ortholog`:

- DeepTMHMM 1.0.24 topology (label, terminal orientation, ECD/ICD lengths,
  per-residue string)
- paralog ECD identity (Compara r112 paralogs, expanded into the candidate set so
  every paralog has topology for the ECD computation)
- mouse/cyno ortholog ECD identity

DeepTMHMM runs from the local academic-license install
(`DEEPTMHMM_ROOT=.../deliverome-internal/analyses/surface-proteome`). The sweep's
legacy-`.3line` reuse only consults the local prediction file, not D1, so the
paralog-expanded candidate set re-predicts many proteins that already have D1
topology; this is wasteful but harmless — see the upload contract below.

## D1 upload contract — append-only, no overwrites, no pointer flips

The upload appends into the **existing** versions; it never creates a new
partial-coverage version (which would shadow a full one via the
`_latest_topology_version_for_cohort` "most-recently-loaded" selector):

| Table | Target version | Write mode |
|---|---|---|
| `topology_public` (canonical, mouse, cyno) | `topo_2026_05_16` | `INSERT OR IGNORE` |
| `topology_public` (isoforms) | `topo_2026_05_25` | `INSERT OR IGNORE` |
| `compara_paralog` | `paralog_topo_2026_05_16` | `INSERT OR IGNORE` |
| `compara_ortholog_ecd` | `orthologecd_topo_2026_05_16_idfix` | `INSERT OR IGNORE` |

- **No row is overwritten** — `INSERT OR IGNORE` keeps D1's existing value on
  conflict; only genuinely-new accessions are added.
- **No version pointer flips** — the `topology_release` upsert's
  `ON CONFLICT DO UPDATE` does **not** touch `loaded_at`, so appending to
  `topo_2026_05_16` leaves its 2026-05-17 timestamp intact and `topo_2026_05_25`
  (2026-05-27) stays newest for the isoform cohort. Isoforms are uploaded into
  `topo_2026_05_25` specifically to avoid shrinking served isoform coverage.

Because the deterministic features are surfaced by the Worker LEFT JOINs, these
genes' pages pick up the new topology/ECD automatically once the rows land — no
re-annotation required.

## Status

- ☐ PubMed-177 sweep — running
- ☐ PR #86 8-gene sweep — queued (auto-launches when the first sweep frees RAM)
- ☐ Validation of both runs' JSONL
- ☐ Combined append-only D1 upload (after sign-off) + before/after coverage report

This document will be updated with final row counts once the upload completes.
