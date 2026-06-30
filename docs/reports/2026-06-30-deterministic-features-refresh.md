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

## Status — new-gene work complete + published

- ☑ PubMed-177 sweep — topology (54/54 previously-missing now have it), 1,339 paralog pairs, 632 ortholog-ECD rows
- ☑ PR #86 8-gene sweep — full parity: topology + isoforms + 22 paralog pairs + 14 ortholog-ECD rows (orthologs seeded into private `compara_ortholog` first)
- ☑ Combined append-only D1 upload (private + public), `INSERT OR IGNORE` into existing versions:
  - topology canonical+mouse+cyno → `topo_2026_05_16` · isoforms → `topo_2026_05_25`
  - paralog ECD → `paralog_topo_2026_05_16` · ortholog ECD → `orthologecd_topo_2026_05_16_idfix`
- ☑ Post-upload coverage: pubmed-177 canonical topology **177/177**, v3add-8 **8/8**

Net topology coverage across v3: **5,150 / 5,151** (the one holdout, RSC1A1 / HGNC:10458, is a withdrawn HGNC ID with no resolvable protein — a cohort-hygiene item, not a features gap).

## Whole-cohort re-audit — follow-up (NOT yet recomputed)

A re-audit of all 5,151 v3 genes (BioMart-checked every gene with no paralog/ortholog
row in D1) found **bug-driven misses** from the May sweep — genes that *do* have
paralogs/orthologs but show none in D1, mostly because the May `compara_ortholog`
table predated the current v3 cohort:

| Feature | No data in D1 | True-absent | **Bug-driven miss** |
|---|---|---|---|
| Paralog | 791 | 672 | **119** |
| Ortholog (1:1) | 963 | 224 | **739** |

The 748 unique miss genes (119 paralog, 739 ortholog, 110 both) are listed in
[`data/analysis/topology_reaudit/2026-06-30_paralog_ortholog_misses.tsv`](../../data/analysis/topology_reaudit/2026-06-30_paralog_ortholog_misses.tsv).

**Recompute plan (deferred, ~1.5–2.5 h at 1 worker):** build a candidate set for the
~800 miss genes → pull + seed their orthologs into `compara_ortholog` (private +
public, ~1,400 rows) → run the sweep (topology mostly cached; ~1,400 ortholog +
paralog-expansion proteins predicted fresh) → append paralog + ortholog ECD to the
existing D1 versions. After this, paralog/ortholog absence will exist only where
BioMart confirms there genuinely are none.

Also deferred to the same batch: seeding the 8 v3add genes' orthologs into the
**public** `compara_ortholog` mirror (private was seeded to enable their ECD).
