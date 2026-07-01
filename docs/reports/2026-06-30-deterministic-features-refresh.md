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

Net topology coverage across v3: **5,135 / 5,135 resolvable proteins** (100%). 16 of the 5,151 v3 rows carry no UniProt accession (incl. RSC1A1 / withdrawn HGNC:10458) — no protein to predict on, a cohort-hygiene item rather than a features gap. See the verified final-coverage table below.

## Whole-cohort re-audit — COMPLETED

A re-audit of all 5,151 v3 genes flagged genes that have paralogs/orthologs but show
none in D1. The first-pass counts were **over-stated** and were corrected through two
rounds of verification (each cut the number substantially):

| Feature | First-pass flag | After served-table + private/public check | After 1:1-high-confidence filter (**real**) |
|---|---|---|---|
| Paralog | 119 | 11 | **11** |
| Ortholog | 739 | 731 | **372** |

Why the first pass was wrong:
- **Paralog (119 → 11):** the re-audit snapshot ran *before* the new-gene upload; the
  PubMed sweep's paralog-expansion had already computed pairs for 108 of them, which
  the upload then landed. Only 11 were truly missing.
- **Ortholog (739 → 372):** (a) the re-audit checked the *source* `compara_ortholog`
  table, not the served `compara_ortholog_ecd`, and only the public mirror; (b) its
  crude BioMart check counted *any* ortholog, but the served feature requires a
  **one2one high-confidence** ortholog — only 372 qualify. The other ~360 correctly
  have no qualifying ortholog.

**Root cause (verified):** not flaky pulls but **cohort drift**. All 372 already had
canonical topology, but the `compara_ortholog` *source* table (built May 2026 from an
older, narrower input) never covered them — the v3 optimized-DB-cutoff rebuild
(`ddb82202f`) admitted genes that topology re-ran over but the ortholog pull never saw.

**Recompute (done):** seeded the 372's orthologs into `compara_ortholog` (private +
public, 647 rows) → swept (`--skip-paralogs` to avoid wasteful paralog re-expansion of
genes that already had paralog data) → appended **633 ortholog-ECD rows** to
`orthologecd_topo_2026_05_16_idfix`. The 11 paralog misses got a dedicated sweep → **81
paralog pairs** appended to `paralog_topo_2026_05_16`. A final full-cohort verification
then caught a **third** blind spot (genes with a source ortholog row but no computed
ECD — private/public source drift); 7 of those 10 were closed by a follow-up seed+sweep.

The original 748-row flag list is preserved at
[`data/analysis/topology_reaudit/2026-06-30_paralog_ortholog_misses.tsv`](../../data/analysis/topology_reaudit/2026-06-30_paralog_ortholog_misses.tsv)
(now superseded by the verified counts above).

## Final coverage — verified across all 5,151 v3 genes (served public D1)

| Feature | Coverage | Notes |
|---|---|---|
| **Topology (canonical)** | **5,135 / 5,135** | 100% of resolvable proteins. 16 v3 rows have no UniProt acc (incl. RSC1A1 / withdrawn HGNC:10458) → no protein → no features. |
| **Ortholog ECD (1:1)** | **4,550 / 4,553** with a qualifying ortholog source | The 3 remaining (OR4X1, OR51L1, OR52N1) are olfactory receptors whose mouse ortholog has **no UniProt protein** → no sequence to run DeepTMHMM on → ECD genuinely uncomputable (data limit, not a bug). ~598 genes have no qualifying 1:1 ortholog (true-absent). |
| **Paralog ECD** | 4,464 genes with ≥1 paralog | All re-audit-verified misses closed. |
| **SURFACE-Bind** | 2,629 / 5,135 | Fixed published dataset — sparse by design. |
| **Schweke homo-oligomer** | 907 / 5,135 | Owned separately; sparse by design (homomers only). |

**Bottom line:** every v3 gene that *can* carry each deterministic feature now does.
Remaining absences are exactly two kinds — (1) **true biology** (no paralog / no 1:1
ortholog / not a homomer / not in SURFACE-Bind), and (2) **3 OR genes + RSC1A1** where
the upstream protein/ortholog has no UniProt entry to compute on. No bug- or
drift-driven gaps remain.
