# Deterministic pipeline — real benchmark vs positive controls

**Every number here comes from an actual pipeline run**, fully in-repo — no
deliverome-internal dependency:

- **sequence + per-residue topology**: the committed DeepTMHMM prediction
  (`data/external/deeptmhmm_surfaceome_predictions/human_canonical_non_hla/predicted_topologies.3line`),
  the same topology source the main pipeline uses;
- **AlphaFold model**: fetched from AFDB via `tools.afdb_plddt` (the repo's own AF
  approach), cached under `data/cache/afdb_pdb/` (gitignored);
- **UniProt feature vetoes**: fetched live.

Reproduce: `uv run python scripts/benchmark_tag_sites_deterministic.py`.
Ground truth = the **internal-site** rows of `positive_controls.tsv` whose residue is
checkable and whose protein has a reliable AlphaFold ectodomain model.

## Results (deterministic path only)

| Gene | Acc | Control | pLDDT @ ctrl | RSA (win) | SS | topo | Candidate (pre-NMS) | Representative (emitted) | Path |
|---|---|---|---:|---:|:--:|:--:|:--:|---|---|
| **AXL** | P30530 | after P184 | 37.1 | 0.90 | C | O | yes (181–187) | **exact (184)** | disorder |
| **ITGB5** | P18084 | after A102 | 43.0 | 0.90 | C | O | yes (99–105) | near (103, 105) | disorder |
| **TFRC** | P02786 | after I290 | 95.9 | 0.88 | C | O | yes (289, 291) | near (291) | surface_loop |
| **ITGB1** | P05556 | after G101 | 56.4 | 0.85 | C | O | yes (101, 103) | near (103) | disorder |
| **TMEM123** | Q8N131 | after A33 | 51.6 | 0.68 | H | O | yes (30–36) | **miss** (27, 39 flank it) | disorder |

- **Candidate recall (gates identify the control site, ±3): 5/5.**
- **Representative recall (what the pipeline actually emits, post-NMS, ±3): 4/5.**

## Reading the two columns

The gates correctly flag **all five** control residues as valid tag sites (candidate
recall 5/5). The emitted set is then thinned by `select_representatives` (NMS,
min-gap 8, cap 20) so a long exposed loop yields a few spaced options rather than a
dense run. Four controls survive that thinning within ±3; **TMEM123 A33 does not** —
its disordered ectodomain (residues 27–140, all pLDDT<70) is offered representatives at
27 and 39 (both more solvent-exposed, 6 aa either side of A33), and the min-gap-8
spacing drops 33 in between. This is an NMS-spacing artifact, not a gate failure: A33
is in the candidate pool (30–36 all qualify). Tightening `min_gap` would surface it at
the cost of a denser emitted set; that knob is **not** tuned to pass this one control.

## What the real run shows

1. **Four of five controls sit in low-pLDDT regions** (AXL 37, ITGB5 43, TMEM123 52,
   ITGB1 56) — the **disorder** path's job, not surface_loop. Matches the control doc's
   structural notes: AXL "inter-domain linker", TMEM123 "unstructured ectodomain", ITGB5
   hybrid/beta-I loop.
2. **Only TFRC (pLDDT 95.9) is the ordered-surface-loop case** that Path 2b was built
   for — a folded loop with a buried anchor (I290 own-RSA 0.02) but exposed junction
   (window-RSA 0.88), snapped to V291. The class the incumbent low-pLDDT screen misses.
3. **The disorder-path fix that raised candidate recall to 5/5** (from the original
   one-midpoint-anchor-per-run): build runs on pLDDT+topology only; apply the 3D-feature
   veto to the *insertion point* not run membership (nearby features were fragmenting
   ITGB1's 98–105 run); and emit an exposed, feature-clear candidate **per residue**,
   ranked by exposure, letting NMS space them. A long disordered ectodomain has many
   valid sites, not one.

## Note on AF model version

Recovery is mildly sensitive to the AlphaFold model version: an earlier run against
deliverome-internal's cached models surfaced TMEM123 at 36 (a representative hit),
whereas the current AFDB model shifts that region's exposed peak to 39. The gates find
A33 either way; only whether NMS surfaces a within-±3 representative moves. Reported here
is the repo-native AFDB result.

## Out of scope for the deterministic path

- **TRPC5 (Q9UL62) and KCNH2/hERG (Q12809)** are multi-pass channels **outside the
  expressed-surfaceome reference set**, and AlphaFold is unreliable at their extracellular
  loops. These are **literature-only controls** — the deterministic pipeline is not
  expected to recover them, and any claim that it does must come from a run, not assertion.

## Honesty note

An earlier HTML "benchmark" in this branch was removed because its per-control verdicts and
structural numbers were **not** produced by runs. This table replaces it and is regenerable
end-to-end from the script above.

## All controls (2026-08-15) — breakdown by deterministic result type

Ran the deterministic pipeline on every control in `positive_controls.tsv`
(reproduce: `uv run python scripts/benchmark_tag_sites_all_controls.py`). Internal
controls only get a run — the pipeline designs internal loop + disordered sites,
not terminals.

| Result type | n | examples |
|---|---:|---|
| `disorder_exact` | 3 | AXL P184, SLC9A6 M53, SLC5A6 483 |
| `disorder_near` (±3) | 4 | ITGB1 G101→103, ITGB5 A102→103, SLC26A1 P155→153, ASIC1 D298→295 |
| `surface_loop_near` (±3) | 3 | TFRC I290→291, AQP1 T120→121, SLC19A1 P297→299 |
| `candidate_only` (gates find it; NMS-suppressed) | 5 | TMEM123 A33, SLC6A3 A192, EDNRB G57, SLC4A1 557, ASIC1 F147 |
| `miss` | 2 | SLC6A4 N211 (folded EL2 replacement, pLDDT 88), ANO1 396 (isoform-suspect) |
| `terminal_out_of_scope` | 9 | A1–A8 GPCRs + TFRC A24 C-terminus |
| `not_in_surfaceome_3line` | 7 | TRPC5, KCNH2, PMP22, VANGL1×2, KCNQ1, CFTR |

**Recall on the 17 runnable internal controls:** candidate (gates, ±3) **15/17**;
representative (emitted, post-NMS, ±3) **10/17**. The disorder path carries 7/10
representative hits. The two misses are informative: SLC6A4 N211 is a
confidently-folded (pLDDT 88) constrained EL2 replacement that neither the
disorder gate (needs pLDDT<70) nor the surface-loop RSA gate catches; ANO1 396 is
the isoform-numbering-suspect control (Q5XXA6 396=A, not the cited H396).
