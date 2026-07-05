# Supplementary Figure 4 — Curator vs agent `TriageReason` confusion matrix

**147-gene SurfaceBench, Sonnet 4.6 + NCBI context.** For each gene
the curator hand-assigned a `ground_truth_reason` from the same closed
19-value `TriageReason` enum the triage agent emits. This matrix plots
curator (y) vs agent (x), one cell per (curator-reason, agent-reason)
pair, count + gene names overlaid. The diagonal is exact-reason
agreement; the off-diagonal cells split into within-bucket reassignments
(same Yes / Contextual / No bucket, different reason) and cross-bucket
flips (the cells that matter most for verdict accuracy).

Bucket separators are drawn after `stable_complex_partner` (yes →
contextual) and after `dual_localization` (contextual → no). Axis
labels are colored by bucket so the eye locks on the partitions.

**Headline**: 128/147 = **87.1 %** exact-reason agreement.

The **biggest single disagreement bucket** (3 of 19 disagreements) is
cytoplasmic kinases — BTK, JAK1, AKT2 — that the curator called
`cytoplasmic` (their steady-state biological compartment) and the
agent called `inner_leaflet_anchored` (the membrane-proximal SH2/PH
binding evidence the agent over-weights). No other systematic mis-tag
pattern emerges from the 19 disagreements.

## Reproducibility

```bash
uv run make_curator_vs_agent_reason.py
```

The script reads only the bundled `curator_vs_agent_reason.tsv`
next to it — no network fetch, no external joins. The TSV is one
row per `(gene × model × prompt_variant × replicate)` on the
147-gene bench, with `ground_truth_verdict` + `ground_truth_reason`
+ per-rep `is_match` denormalized in.

## Canonical generator (full 3-panel composite)

The in-repo figure at
[`data/analysis/figures/curator_vs_agent_reason.pdf`](https://raw.githubusercontent.com/Deliverome-Project/accessible-surfaceome/main/data/analysis/figures/curator_vs_agent_reason.pdf)
is a **3-panel composite** that adds:

- **Panel a** — bucket-strict accuracy across 10 model variants
  (Haiku 4.5 × 4 prompt variants + Sonnet 4.6 × 4 + Opus 4.8 × 2)
- **Panel b** — per-reason accuracy across 4 frontier configs
- **Panel c** — the confusion matrix this gist reproduces

The composite is produced by
[`scripts/curator_vs_agent_reason.py`](https://github.com/Deliverome-Project/accessible-surfaceome/blob/main/scripts/curator_vs_agent_reason.py)
in the project repo. This gist mirror ships the matrix alone since
that's the analytical core readers cite for Figure S4.

## Data lineage

- Bench truth: [`data/eval/triage_benchmark_v1.tsv`](https://github.com/Deliverome-Project/accessible-surfaceome/blob/main/data/eval/triage_benchmark_v1.tsv)
- Per-rep agent predictions: [`data/processed/triage_bench/mainbench_replicates_v2.tsv`](https://github.com/Deliverome-Project/accessible-surfaceome/blob/main/data/processed/triage_bench/mainbench_replicates_v2.tsv)
- Pre-joined per-figure TSV (bundled here): [`data/processed/figures/curator_vs_agent_reason.tsv`](https://github.com/Deliverome-Project/accessible-surfaceome/blob/main/data/processed/figures/curator_vs_agent_reason.tsv)
- Per-cell collapse rule documented at
  [`scripts/export_mainbench_to_tsv.py:_collapse_to_majority`](https://github.com/Deliverome-Project/accessible-surfaceome/blob/main/scripts/export_mainbench_to_tsv.py)
  — pick the majority verdict across reps, then the first replicate
  in that majority-verdict group provides the representative reason.
