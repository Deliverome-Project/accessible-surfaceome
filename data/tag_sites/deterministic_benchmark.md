# Deterministic pipeline — real benchmark vs positive controls

**Every number here comes from an actual pipeline run** on the real cached AlphaFold
models + real DeepTMHMM topology + real UniProt feature vetoes. Reproduce with
`scripts/benchmark_tag_sites_deterministic.py` (needs the deliverome-internal AF-model
cache checked out locally; TFRC also runs from the in-repo fixture
`tests/fixtures/AF-P02786.pdb.gz`).

Ground truth = the **internal-site** rows of `positive_controls.tsv` whose residue is
checkable and whose protein has a reliable AlphaFold ectodomain model.

## Results (deterministic path only)

| Gene | Acc | Control | pLDDT @ ctrl | RSA (window) | SS | topo | Recovered? | Path | Nearest picks |
|---|---|---|---:|---:|:--:|:--:|---|---|---|
| **AXL** | P30530 | after P184 | 33.2 | 0.89 | C | O | ✅ **exact (184)** | disorder | 184 |
| **ITGB5** | P18084 | after A102 | 43.0 | 0.90 | C | O | ✅ near (101, 105) | disorder | 101 (±1) |
| **TMEM123** | Q8N131 | after A33 | 50.6 | 0.74 | C | O | ✅ near (35) | disorder | 35 (±2) |
| **TFRC** | P02786 | after I290 | 95.9 | 0.88 | C | O | ✅ near (291) | surface_loop | 291 (±1) |
| **ITGB1** | P05556 | after G101 | 57.1 | 0.85 | C | O | ❌ **MISS** | — | 90, 128 |

**Recovery: 4/5 within ±3 residues (1 exact). 1 genuine miss (ITGB1 G101).**

## What the real run shows

1. **Four of five controls sit in low-pLDDT regions** (AXL 33, ITGB5 43, TMEM123 50,
   ITGB1 57) and are the **disorder** path's job — not the surface-loop path. This matches
   the positive-control doc's structural notes verbatim: AXL "extracellular inter-domain
   linker", TMEM123 "unstructured ectodomain", ITGB5 hybrid/β-I loop.
2. **Only TFRC (pLDDT 95.9) is the ordered-surface-loop case** that Path 2b (`surface_loop`)
   was built for — a confidently folded loop with a buried anchor (I290 own-RSA 0.02) but an
   exposed junction (window-RSA 0.88), snapped to V291. This is the class the incumbent
   low-pLDDT screen structurally misses, and the reason Path 2b exists.
3. **The ITGB1 miss is real and diagnosable.** G101 has pLDDT 57 → fails the surface-loop
   reliability gate (≥70), so it falls to the disorder path. But the disorder path nominates
   the **midpoint** of each contiguous low-pLDDT run, which lands at 90 — 11 residues from
   the edge-sited G101. Its equivalent ITGB5 A102 is recovered only because that run's
   midpoint happens to land at 101/105. **Fix candidate:** snap the disorder nomination to
   the most solvent-exposed residue of the run (as `surface_loop._exposed_anchor` already
   does), rather than the geometric midpoint — likely recovers ITGB1 and tightens the others.

## Out of scope for the deterministic path

- **TRPC5 (Q9UL62) and KCNH2/hERG (Q12809)** are multi-pass channels **outside the
  expressed-surfaceome reference set**, and AlphaFold is unreliable at their extracellular
  loops (hERG's S1–S2 loop is not a confidently-folded ordered loop). These are
  **literature-only controls** — the deterministic pipeline is not expected to recover them,
  and any claim that it does must come from an actual run, not assertion.

## Honesty note

An earlier HTML "benchmark" in this branch was removed because its per-control verdicts and
structural numbers were **not** produced by runs. This table replaces it and is regenerable
end-to-end from the script above.
