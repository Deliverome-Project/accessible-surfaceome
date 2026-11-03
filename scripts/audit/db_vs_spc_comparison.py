"""Single-DB vs SurfaceGenie SPC performance on the triage benchmark (v1).

Reproduces the table in ``docs/evals/db_comparison_uniprot_surfy_spc.md``. Scores each
individual surface-annotation database and the SurfaceGenie **SPC** consensus (0-4) on the
curated triage benchmark, as a clean head-to-head classifier comparison.

Scoring convention (deliberately different from the paper's Figure-2 DB barplot):
  * Positives / negatives are ``ground_truth_verdict`` with ``contextual`` DROPPED, so every
    predictor is scored on the SAME binary yes-vs-no set (116 proteins: 68 yes / 48 no on the
    current benchmark). The paper figure instead keeps all 147, counts ``contextual`` as a
    correct surface call, and is coverage-aware (a source is not penalised where it abstains).
    That convention is better for "how good is each DB where it has an opinion"; this one is
    better for "is SPC a better classifier than the DBs head-to-head", which is the question
    the note answers. The two tables are therefore NOT directly comparable by construction.
  * Baseline DB flags (UniProt/GO/SURFY/CSPA/HPA) come from ``mainbench_canonical_v2.tsv``,
    which carries the true per-protein flag for all 116 (full coverage).
  * The **optimized** UniProt cutoff (TM-or-signal-or-strict-location) comes from
    ``db_optimized_cutoffs.tsv``; a benchmark protein absent from that file did not pass the
    optimized rule, so its optimized flag is 0. (All benchmark proteins absent from the file
    are ``no``/``contextual`` — never ``yes`` — so 0 is the correct call, not an artifact.)
  * SPC (0-4) is the per-accession SurfaceGenie score from
    ``data/external/surfacegenie/SPC_by_Source_sprot.csv`` (Waas et al. 2020, Bioinformatics
    36:3447); every benchmark accession is covered.

Run: ``uv run python scripts/audit/db_vs_spc_comparison.py``
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
BENCH_TSV = ROOT / "data/eval/triage_benchmark_v1.tsv"
MAINBENCH_TSV = ROOT / "data/processed/triage_bench/mainbench_canonical_v2.tsv"
DB_OPT_TSV = ROOT / "data/processed/triage_bench/db_optimized_cutoffs.tsv"
SPC_CSV = ROOT / "data/external/surfacegenie/SPC_by_Source_sprot.csv"

BASELINE_FLAGS = {
    "UniProt (baseline)": "uniprot_surface_flag",
    "SURFY": "surfy_surface_flag",
    "GO-CC": "go_surface_flag",
    "CSPA": "cspa_surface_flag",
    "HPA": "hpa_surface_flag",
}


def _base_acc(series: pd.Series) -> pd.Series:
    """Strip UniProt isoform suffix so joins key on the stable accession."""
    return series.astype(str).str.split("-").str[0]


def _metrics(pred: np.ndarray, y: np.ndarray) -> tuple[float, float, float, float, float]:
    pred = np.asarray(pred, float)
    y = np.asarray(y, float)
    tp = ((pred == 1) & (y == 1)).sum()
    tn = ((pred == 0) & (y == 0)).sum()
    fp = ((pred == 1) & (y == 0)).sum()
    fn = ((pred == 0) & (y == 1)).sum()
    acc = (tp + tn) / len(y)
    tpr = tp / (tp + fn) if tp + fn else 0.0
    tnr = tn / (tn + fp) if tn + fp else 0.0
    prec = tp / (tp + fp) if tp + fp else 0.0
    f1 = 2 * prec * tpr / (prec + tpr) if prec + tpr else 0.0
    return acc, (tpr + tnr) / 2, prec, tpr, f1


def _auroc(score: np.ndarray, label: np.ndarray) -> float:
    """AUROC = the Mann-Whitney statistic (prevalence-independent, ties averaged)."""
    score = np.asarray(score, float)
    label = np.asarray(label, int)
    order = np.argsort(score)
    ranks = np.empty(len(score))
    ranks[order] = np.arange(1, len(score) + 1)
    df = pd.DataFrame({"s": score, "r": ranks})
    df["r"] = df.groupby("s")["r"].transform("mean")
    npos = label.sum()
    nneg = len(label) - npos
    return (df["r"].to_numpy()[label == 1].sum() - npos * (npos + 1) / 2) / (npos * nneg)


def build_table() -> pd.DataFrame:
    bench = pd.read_csv(BENCH_TSV, sep="\t")
    mainbench = pd.read_csv(MAINBENCH_TSV, sep="\t")
    db_opt = pd.read_csv(DB_OPT_TSV, sep="\t")
    spc = pd.read_csv(SPC_CSV)

    bench["acc"] = _base_acc(bench["uniprot_acc"])
    mainbench["acc"] = _base_acc(mainbench["uniprot_acc"])
    db_opt["acc"] = _base_acc(db_opt["accession"])
    spc["acc"] = _base_acc(spc["Accession"])

    b = bench[bench["ground_truth_verdict"].isin(["yes", "no"])].copy()
    b["y"] = (b["ground_truth_verdict"] == "yes").astype(int)
    b = b.set_index("acc")
    y = b["y"].to_numpy()

    mb = mainbench.drop_duplicates("acc").set_index("acc")
    opt = db_opt.drop_duplicates("acc").set_index("acc")
    sp = spc.drop_duplicates("acc").set_index("acc")

    rows = []

    def flag(table: pd.DataFrame, col: str) -> np.ndarray:
        return np.array([int(table[col].get(a, 0)) if a in table.index else 0 for a in b.index])

    rows.append(("UniProt (optimized)", *_metrics(flag(opt, "uniprot_optimized"), y)))
    for name, col in BASELINE_FLAGS.items():
        rows.append((name, *_metrics(flag(mb, col), y)))

    spc_val = pd.Series(
        [sp["SPC"].get(a, 0) if a in sp.index else 0 for a in b.index], dtype=float
    )
    for k in (1, 2, 3, 4):
        rows.append((f"SPC >= {k}", *_metrics((spc_val >= k).astype(int).to_numpy(), y)))
    rows.append(("SPC graded (AUROC)", np.nan, _auroc(spc_val.to_numpy(), y), np.nan, np.nan, np.nan))

    tab = pd.DataFrame(
        rows, columns=["predictor", "accuracy", "balanced_acc", "precision", "recall", "f1"]
    )
    tab.attrs["n_yes"] = int(y.sum())
    tab.attrs["n_no"] = int(len(y) - y.sum())
    return tab


def main() -> None:
    tab = build_table()
    n_yes, n_no = tab.attrs["n_yes"], tab.attrs["n_no"]
    print(f"Triage benchmark v1, drop-contextual: n={n_yes + n_no} ({n_yes} yes / {n_no} no)\n")
    header = f"| {'predictor':22s} | acc | bal | prec | rec | F1 |"
    print(header)
    print("|" + "---|" * 6)
    for _, r in tab.iterrows():
        def fmt(x: float) -> str:
            return "-" if pd.isna(x) else f"{x:.3f}"

        print(
            f"| {r['predictor']:22s} | {fmt(r['accuracy'])} | {fmt(r['balanced_acc'])} "
            f"| {fmt(r['precision'])} | {fmt(r['recall'])} | {fmt(r['f1'])} |"
        )


if __name__ == "__main__":
    main()
