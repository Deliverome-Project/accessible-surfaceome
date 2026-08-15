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
| **AXL** | P30530 | after P184 | 33.2 | 0.89 | C | O | yes — **exact (184)** | disorder | 184 |
| **ITGB5** | P18084 | after A102 | 43.0 | 0.90 | C | O | yes — near (103, 105) | disorder | 103 (+1) |
| **TMEM123** | Q8N131 | after A33 | 50.6 | 0.74 | C | O | yes — near (36) | disorder | 36 (+3) |
| **TFRC** | P02786 | after I290 | 95.9 | 0.88 | C | O | yes — near (291) | surface_loop | 291 (+1) |
| **ITGB1** | P05556 | after G101 | 57.1 | 0.85 | C | O | yes — near (103) | disorder | 103 (+2) |

**Recovery: 5/5 within +/-3 residues (1 exact).**

## What the real run shows

1. **Four of five controls sit in low-pLDDT regions** (AXL 33, ITGB5 43, TMEM123 50,
   ITGB1 57) and are the **disorder** path's job — not the surface-loop path. This matches
   the positive-control doc's structural notes verbatim: AXL "extracellular inter-domain
   linker", TMEM123 "unstructured ectodomain", ITGB5 hybrid/beta-I loop.
2. **Only TFRC (pLDDT 95.9) is the ordered-surface-loop case** that Path 2b (`surface_loop`)
   was built for — a confidently folded loop with a buried anchor (I290 own-RSA 0.02) but an
   exposed junction (window-RSA 0.88), snapped to V291. This is the class the incumbent
   low-pLDDT screen structurally misses, and the reason Path 2b exists.
3. **ITGB1 was the initial miss, and diagnosing it fixed the disorder path.** G101 (pLDDT 57)
   fails the surface-loop reliability gate (>=70) and falls to the disorder path. The original
   disorder path (a) emitted one site per low-pLDDT run at its **midpoint** and (b) applied
   the 3D-feature veto **per residue during run-building**. Both hurt: the per-residue veto
   *fragmented* ITGB1's 98-105 run (only 101/103/105 clear 12 A, so no contiguous >=4 run
   formed), and the midpoint would have missed the edge-sited control anyway.

## The disorder-path fix (three parts)

- **Build runs on pLDDT + topology only.** A low-pLDDT extracellular run defines the
  disordered loop; nearby functional atoms must not fragment it.
- **Apply the 3D-feature veto to the insertion point, not run membership.** A disordered
  loop that mostly runs near features can still host a tag at an exposed sub-position that
  clears them (12 A).
- **Emit an exposed, feature-clear candidate per residue in the run, ranked by exposure,**
  and let `select_representatives` (NMS, min-gap 8, cap 20) space them across the loop. A
  long disordered ectodomain (TMEM123, ~110 aa of pLDDT<70) has many valid tag positions,
  not one; collapsing it to a single anchor was the bug. This recovers ITGB1 (->103) and
  TMEM123 (->36) without regressing AXL/ITGB5/TFRC.

## Out of scope for the deterministic path

- **TRPC5 (Q9UL62) and KCNH2/hERG (Q12809)** are multi-pass channels **outside the
  expressed-surfaceome reference set**, and AlphaFold is unreliable at their extracellular
  loops (hERG's S1-S2 loop is not a confidently-folded ordered loop). These are
  **literature-only controls** — the deterministic pipeline is not expected to recover them,
  and any claim that it does must come from an actual run, not assertion.

## Honesty note

An earlier HTML "benchmark" in this branch was removed because its per-control verdicts and
structural numbers were **not** produced by runs. This table replaces it and is regenerable
end-to-end from the script above.
