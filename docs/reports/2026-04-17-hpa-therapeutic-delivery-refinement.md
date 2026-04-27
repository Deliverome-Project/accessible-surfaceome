# HPA integration — therapeutic-delivery refinement

**Date:** 2026-04-17 · **Status:** Implemented.
**Files touched:** [`build_hpa.py`](../../src/surface_proteome/candidates/build_hpa.py), [`build_candidate_universe.py`](../../src/surface_proteome/candidates/merge.py).
**Related:** [`2026-04-17-jensenlab-compartments-integration.md`](2026-04-17-jensenlab-compartments-integration.md) (companion source), [`2026-04-16-surface-proteome-annotation.md`](../plans/2026-04-16-surface-proteome-annotation.md) (M0 plan).

## Why this refinement exists

HPA's `subcellular_location.tsv` v25 carries ~13.6k gene-level subcellular calls spanning 49 distinct cellular compartments. The first-cut integration collapsed three coarse flags (PM, Extracellular, surface-GO) into one `hpa_surface_flag` gated on a gene-wide `Reliability` tier, then used that as a pool admission signal. A targeted Codex adversarial review — specifically scoped to *therapeutic delivery* relevance (ADC / CAR-T / mRNA-LNP, which requires extracellular accessibility on intact cells, not just "membrane-associated") — flagged five distinct issues with that treatment, all verified numerically against the raw file. This doc records the findings and the refined design we implemented.

## Codex findings — all verified against the raw file

| # | Finding | Verification on `subcellular_location.tsv` |
|---|---|---|
| 1 | Every non-empty `Extracellular location` value is literally the string `"Predicted to be secreted"`. | `value_counts()` on the column: **740/740** rows carry that exact string. It's not an IF observation — it's a SignalP-based sequence prediction HPA displays there. |
| 2 | Extracellular-only rows (non-empty `Extracellular location`, no PM anywhere, no Cell Junctions anywhere) — candidates for the flag-removal class. | **577 rows** on the raw HPA file (my first-pass number of 587 was computed against an intermediate snapshot; the correct count on `subcellular_location.tsv` is 577). |
| 3 | `hpa_has_surface_go` is *exactly* redundant with `hpa_has_plasma_membrane` in this release. | Crosstab: **0 disagreement cases** across 13,603 rows — the HPA `GO id` column carries GO:0005886 iff `Plasma membrane` appears in Main/Additional. |
| 4 | **220 rows** have PM *only* in the `Uncertain` per-tier column while gene-wide `Reliability` is `Supported` (138) or `Approved` (82). | Confirmed. Using gene-wide reliability as the flag gate overcalls PM confidence for these — the gene's stronger non-Uncertain localization is usually nuclear or cytosolic, not PM. |
| 5 | `Cell Junctions` coverage: **194 of 331** CJ rows fall outside the old pool; most (180) are at Approved-or-better confidence. | Confirmed. These include legitimate ADC-accessible epithelial junction proteins (cadherins, claudins, JAM family, occludin, desmosomal cadherins). |

## Design changes

### A. Drop extracellular-only from the flag

HPA's `Extracellular location` column is **not an IF observation**. It's populated exclusively (740/740) by `"Predicted to be secreted"` — a SignalP-based sequence prediction surfaced as a label. Secretion ≠ "accessible from outside an intact plasma membrane" (secreted proteins leave the cell; they're not the targeting surface ADCs bind to). Flagging these inflates the candidate universe with **577 false positives** for therapeutic delivery (rows with non-empty Extracellular location AND no PM evidence AND no Cell Junctions evidence at any tier).

**New treatment.** `hpa_has_extracellular` stays as raw provenance, but a separate derived state column `hpa_secreted_only = 1` marks rows where the *only* HPA signal is the secretion prediction. Those rows remain in the pool for provenance (so the downstream M2+ Claude agent pipeline can distinguish secreted from surface-anchored proteins when assembling the `topology` field in the per-gene `GeneAnnotation` — see M0 plan §"Provenance & anti-hallucination"), but never set `hpa_surface_flag`.

### B. Per-tier PM-specific reliability gating

Previously the flag gated on gene-wide `Reliability != "Uncertain"`. That's a gene-level tag computed across *all* a gene's localizations: a gene whose strongest localization is nuclear at `Supported` tier but whose PM call lives only in the `Uncertain` column would incorrectly flag as surface.

**New treatment.** Emit per-tier booleans `hpa_pm_in_{enhanced,supported,approved,uncertain}` derived from HPA's four per-tier columns. Derive `hpa_pm_accessible = 1` iff PM appears in Enhanced / Supported / Approved. The flag requires `hpa_pm_accessible OR hpa_junctional`. Removes the **220 overcalled rows** identified above (PM appears only in the Uncertain per-tier column while gene-wide `Reliability` is non-Uncertain — typically because the gene's strongest non-Uncertain location is nuclear or cytosolic, not PM).

A parallel set of per-tier booleans for Cell Junctions (`hpa_cj_in_{enhanced,…}`) supports the same logic for junction proteins (see C). Summary enums `hpa_pm_reliability` and `hpa_junction_reliability` report the highest tier where the respective location appears, for quick filtering downstream.

### C. Admit `Cell Junctions` to the pool

ADC-accessible epithelial junction proteins (E-cadherin / CDH1, claudins, JAM family, occludin, desmosomal cadherins) have legitimate, antibody-accessible extracellular domains on intact cells. They're *not* purely inner-leaflet or cytoplasmic. With the old pool rule (PM / Extracellular / surface-GO), 194 of 331 Cell Junctions rows were excluded. Admitting CJ to the pool (and to the flag, per-tier-gated at Enhanced/Supported/Approved) adds **175 new flagged rows** (CJ-at-Enhanced/Supported/Approved with no PM-at-Enhanced/Supported/Approved), plus 163 pool admissions that were CJ-at-Enhanced/Supported/Approved with no PM and no Extracellular signal.

**New treatment.** `hpa_junctional = 1` iff CJ appears in Enhanced / Supported / Approved. Pool admits any row with PM OR CJ evidence at any tier, OR the secretion prediction (provenance only).

**Focal adhesion sites is NOT admitted**, per Codex's recommendation and the biology — focal adhesions are inner-leaflet scaffolds (paxillin, vinculin, talin), not extracellularly accessible on intact cells. 91 of 148 focal-adhesion rows remain outside the pool.

### D. Drop the redundant `hpa_has_surface_go` boolean

Confirmed 0 disagreement with `hpa_has_plasma_membrane` in v25. `hpa_go_ids` (the raw GO ID string from HPA's `GO id` column) stays as provenance; only the derived redundant boolean is removed.

### E. Richer provenance: split into tracked states for the downstream LLM pipeline

The merge architecture mandates a single `<source>_surface_flag` per source (required by `FLAG_COLUMNS` + `n_sources_surface` + pairwise Jaccard). But the downstream Claude agent needs the *categorical* distinctions Codex correctly called out. So we keep one flag **and** emit richer provenance columns in the M1 snapshot:

| Column | Semantics | Contributes to flag? |
|---|---|---|
| `hpa_pm_accessible` | PM at Enhanced / Supported / Approved | **yes** |
| `hpa_junctional` | Cell Junctions at Enhanced / Supported / Approved | **yes** |
| `hpa_secreted_only` | `Extracellular location` non-empty AND no PM/CJ evidence at any tier | no |
| `hpa_trafficking_associated` | Vesicles / Endosomes / Lysosomes in Main/Additional | no (provenance only; see below) |
| `hpa_pm_in_{enhanced,supported,approved,uncertain}` | per-tier PM raw booleans | constituents of `hpa_pm_accessible` |
| `hpa_cj_in_{enhanced,supported,approved,uncertain}` | per-tier CJ raw booleans | constituents of `hpa_junctional` |
| `hpa_pm_reliability` | "enhanced" / "supported" / "approved" / "uncertain" / "" — highest tier where PM appears | provenance |
| `hpa_junction_reliability` | same for CJ | provenance |

**`hpa_trafficking_associated`** is the intentional half-measure for the ABCB9 class of false positives. Vesicles / endosomes / lysosomes proteins may legitimately cycle to the plasma membrane in specific contexts (GLUT4 on insulin stimulation; LAMP1 on activated T cells), so this info matters downstream. But admitting a row to the pool *solely* on trafficking-compartment evidence is exactly the ABCB9 failure mode — ABCB9 is lysosomal, flagged as surface by SURFY, and the whole project exists in part to catch errors like that. So: when PM or CJ evidence also exists on the row, the trafficking flag rides alongside for the Claude agent to consider; when a row has *only* trafficking-compartment evidence with no PM/CJ, it never enters the pool.

## Pre-publish drift assertion

The pre-publish assertion in [`build_candidate_universe.py:963-1033`](../../src/surface_proteome/candidates/merge.py:963) re-derives `hpa_surface_flag` from the raw per-tier columns:

```
hpa_surface_flag = (hpa_pm_accessible == 1 OR hpa_junctional == 1)
                   AND hpa_split_mapping_ambiguous == 0
```

and raises if the emitted flag disagrees. That keeps the `flag_rules` block in `candidate_universe_traceability.json` from silently desyncing from the loader if either side is changed in isolation.

## Numbers — before and after

All counts below use **unique UniProt primary accession** as the denominator after the HPA snapshot builder maps ENSG → UP. `hpa_human_snapshot.tsv` emits one row per `(UniProt primary, ENSG)` pair so the raw row count is slightly higher than the unique-primary count (3,008 rows vs. 3,004 unique primaries in the v25 committed snapshot; the 4 extra rows come from ENSGs that map to the same primary). After the merge in `candidate_universe.tsv` the accessions are unique.

| Metric | Pre-Codex-review design | Post-refinement (committed) |
|---|---:|---:|
| HPA unique primaries in pool | 2,813 | **3,004** (+191 from CJ admission) |
| HPA surface-flagged (unique primaries) | 2,631 | **2,077** |
| HPA-old5 overlap (of flagged primaries) | 49.1% | **58.3%** (1,211 / 2,077) |
| Candidate universe rows | 8,680 | 8,770 |
| `n_sources_surface == 0` | 1,486 | 2,125 (absorbs the former flag=1, now flag=0 rows) |
| `n_with_all_7_sources` | 50 | 50 |
| `n_with_all_6_db_sources` | 54 | 54 |

**Flag-count decomposition** relative to the pre-Codex-review design, computed directly against the raw HPA v25 `subcellular_location.tsv` (ENSG-level, pre-mapping to UniProt):

- **Removed**: 577 extracellular-only rows + 220 PM-only-in-Uncertain overcalls — these stopped setting `hpa_surface_flag` under the per-tier gating rule.
- **Added**: 175 rows with Cell Junctions at Enhanced/Supported/Approved tier AND no PM at the same tier — net new flag contributions from the CJ admission.
- **Post-mapping collapse** (ENSG → UP) can merge some of these into existing primaries, and split-mapping-ambiguous rows have their flag zero'd at the merge, so the post-merge delta is bounded but not exactly ±(577+220) − 175. The committed delta is 2,631 → 2,077 = **−554**, close to the naive 622 reduction minus overlap effects.

HPA-old5 overlap going **up** is the expected sign: we removed secreted-only false positives (which were HPA-only by construction) and replaced them with junctional proteins (which usually co-occur with UniProt / GO evidence since junction proteins are textbook surface markers). Exact decomposition numbers are reproducible from the raw HPA file with a short pandas script; see the full audit summary in [`hpa_build_summary.json`](../../data/processed/hpa/hpa_build_summary.json).

## Spot-check panel (EGFR + HLA + CD markers + IGHM)

| Accession | Gene | `hpa_surface_flag` | `hpa_pm_accessible` | `hpa_junctional` | `hpa_pm_reliability` | n_sources |
|---|---|---:|---:|---:|---|---:|
| P00533 | EGFR | 1 | 1 | 1 | supported | 7/7 |
| P04439 | HLA-A | 1 | 1 | 0 | supported | 6/7 |
| P11836 | MS4A1 (CD20) | 1 | 1 | 0 | supported | 6/7 |
| P15391 | CD19 | — (no HPA row) | — | — | — | 6/7 |
| P01889 | HLA-B | — (no HPA row) | — | — | — | 5/7 |
| P10321 | HLA-C | — (no HPA row) | — | — | — | 5/7 |
| P01871 | IGHM | — (no HPA row) | — | — | — | 4/7 |
| P01909 | HLA-DQA1 | — (no HPA row) | — | — | — | 4/7 |
| P01911 | HLA-DRB1 | — (no HPA row) | — | — | — | 4/7 |

EGFR correctly lights up both `pm_accessible` and `junctional` — EGFR does localize to cell junctions in epithelia. CD20 (MS4A1) keeps its flag via `pm_accessible` at Supported. HLA-A also passes. The HLA-B/C/DQA1/DRB1/CD19/IGHM proteins without HPA rows are HPA coverage gaps (HPA doesn't annotate every individual HLA allele or immunoglobulin class switch variant), consistent with the pre-refinement state.

## Deferred / follow-up

- **Full HPA dump (`proteinatlas.tsv.zip`)** — deferred per the M0 plan. That file adds tissue specificity, cancer atlas, scRNA, and HPA's curated Secretome / Predicted-membrane / Predicted-secreted class memberships. Codex specifically called out that tissue specificity is **non-optional** for delivery-modality ranking at M3/M4 (not a nice-to-have). Update the M0 plan to record this.
- **Compartment-specific flag variants for the downstream LLM pipeline.** `hpa_pm_accessible` / `hpa_junctional` / `hpa_secreted_only` / `hpa_trafficking_associated` are all emitted in `candidate_universe.tsv` so the Claude agent can condition on the specific class. The current `hpa_surface_flag` collapses `pm_accessible OR junctional` into one bit for the merge-level agreement counters, which is correct for the universe-assembly contract. If the blog-post analysis wants "pure PM vs. junction-only" numbers, those are computable directly from the emitted columns without changing the flag.
- **Sensitivity: require Enhanced or Supported only.** Codex argued against tightening (Approved accounts for 1,078 of the 1,905 `hpa_pm_accessible` calls). If the downstream audit surfaces Approved-tier false positives, this becomes a follow-up knob; not changing it today.

## Implementation references

- Pool/flag logic: [`build_hpa.py`](../../src/surface_proteome/candidates/build_hpa.py) — specifically [`_derive_per_tier`](../../src/surface_proteome/candidates/build_hpa.py) for per-tier booleans, the state-column block after it, and the pool filter.
- Merge-side consumption: [`_load_hpa`](../../src/surface_proteome/candidates/merge.py) — group-by collapse with per-tier `max` (OR) reducer plus post-collapse re-derivation of the tier enums so they stay consistent with the booleans.
- Pre-publish assertion: [`build_candidate_universe.py:963-1033`](../../src/surface_proteome/candidates/merge.py:963).
- Manifest `flag_rules` text: [`candidate_universe_traceability.json`](../../data/processed/candidate_universe/candidate_universe_traceability.json).
