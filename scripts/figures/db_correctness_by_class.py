"""Figure 2 — per-class DB-vs-LLM accuracy on the 147-gene benchmark.

For 6 callers (5 DBs + Sonnet+NCBI), grouped bars showing overall
accuracy + per-verdict-bucket accuracy (yes / contextual / no).

DB cutoffs are the **trade-off-audit optimized** versions:

  * **UniProt — TM+signal**: admit any accession with a transmembrane
    domain, a signal peptide, OR a strict surface subcellular term.
  * **CSPA — HC-only**: admit only the high-confidence flag.
  * **GO CC / HPA / SURFY**: canonical baselines.

DATA SOURCE — reads ``data/processed/figures/db_correctness_by_class.tsv``
(built by ``scripts/build_figure_tsvs.py``). The model list comes from the
data, never a hardcode — this replaces the
``triage_bench_db_barplot.py::make_class_plot`` path that hardcoded
``opus-4-7`` and shipped empty bars when the data moved to Opus 4.8.

Run: ``uv run python scripts/db_correctness_by_class.py``
# Reproduction: https://gist.github.com/beccajcarlson/2bb4f7aac629535982c142bc2032e04d
"""
from __future__ import annotations

from pathlib import Path

import matplotlib.pyplot as plt
import pandas as pd
import seaborn as sns

from accessible_surfaceome.audit._plotting_config import save_figure, setup_plotting_style

REPO = Path(__file__).resolve().parents[1]
DATA_TSV = REPO / "data/processed/figures/db_correctness_by_class.tsv"
OUT_DIR = REPO / "data/analysis/figures"
GIST_URL = "https://gist.github.com/beccajcarlson/2bb4f7aac629535982c142bc2032e04d"

INK = "#1F1718"
NEUTRAL = "#6F5D5A"

# Deliverome categorical palette (matches _plotting_config.CATEGORICAL_PALETTE)
BRAND_PALETTE = [
    "#BC3C4C",  # maroon-light
    "#3D6B60",  # teal-mid
    "#F4AA28",  # amber-bright
    "#8878C8",  # lavender-bright
    "#6E1428",  # maroon-dark
    "#7AAB9F",  # teal-light
]
BRAND_CLAUDE_ORANGE = "#d87851"

DB_LABELS = ["UniProt", "GO CC", "HPA", "SURFY", "CSPA"]
DB_PALETTE = {
    "UniProt":         BRAND_PALETTE[0],
    "GO CC":           BRAND_PALETTE[1],
    "HPA":             BRAND_PALETTE[2],
    "SURFY":           BRAND_PALETTE[3],
    "CSPA":            BRAND_PALETTE[4],
    "Sonnet (+ IDs)": BRAND_CLAUDE_ORANGE,
}
COLUMNS = ["overall", "yes", "contextual", "no"]
COLUMN_LABEL = {
    "overall":    "overall\n(all 147 proteins)",
    "yes":        "yes",
    "contextual": "contextual\n(yes-vote = correct)",
    "no":         "no",
}


def _vote_correct(vote: str, truth: str) -> bool:
    if vote == truth:
        return True
    return vote in ("yes", "contextual") and truth in ("yes", "contextual")


def main() -> None:
    setup_plotting_style(style="whitegrid", context="notebook", font_scale=1.0)
    # Match the gist mirror's layout fingerprint (tests/test_figure_canonical_mirror_sync).
    plt.rcParams.update({
        "axes.labelsize": 20, "xtick.labelsize": 20, "ytick.labelsize": 20,
        "legend.fontsize": 20, "axes.titlesize": 0, "font.size": 20,
    })

    data = pd.read_csv(DATA_TSV, sep="\t")

    # Derive per-gene tables — per-DB flags + truth are identical across
    # reps of the same gene; take the first row per gene.
    gene_first = data.groupby("gene_symbol", sort=False).first()
    truth_by_gene = gene_first["ground_truth_verdict"].to_dict()

    db_flags = gene_first[[
        "uniprot_optimized", "cspa_optimized",
        "go_surface_flag", "hpa_surface_flag", "surfy_surface_flag",
    ]]

    def _vote(gene: str, source: str) -> str:
        if gene not in db_flags.index:
            return "no"
        row = db_flags.loc[gene]
        if source == "UniProt":
            return "yes" if row["uniprot_optimized"] == 1 else "no"
        if source == "CSPA":
            return "yes" if row["cspa_optimized"] == 1 else "no"
        flag_col = {
            "GO CC":  "go_surface_flag",
            "HPA":    "hpa_surface_flag",
            "SURFY":  "surfy_surface_flag",
        }[source]
        return "yes" if row[flag_col] == 1 else "no"

    # Sonnet/ncbi per-cell predicted_verdict: first row per gene in that cell.
    # Model + variant come from the data — no hardcoded model name.
    sonnet_rows = data[data["prompt_variant"] == "ncbi"].copy()
    # Pick the model that appears in the data for the ncbi variant.
    # Prefer claude-sonnet-4-6 if present; otherwise take whatever is there.
    ncbi_models = sonnet_rows["model"].unique().tolist()
    preferred = [m for m in ncbi_models if "sonnet" in m]
    ncbi_model = preferred[0] if preferred else (ncbi_models[0] if ncbi_models else None)
    sonnet_label = "Sonnet (+ IDs)"
    if ncbi_model is not None:
        sonnet_ncbi = (
            sonnet_rows[sonnet_rows["model"] == ncbi_model]
            .groupby("gene_symbol", sort=False)["predicted_verdict"]
            .first()
            .to_dict()
        )
    else:
        sonnet_ncbi = {}

    def _overall_acc(caller_label: str) -> float:
        if caller_label == sonnet_label:
            def vote_fn(g: str) -> str:
                return sonnet_ncbi.get(g) or "no"
        else:
            def vote_fn(g: str, lbl: str = caller_label) -> str:
                return _vote(g, lbl)
        genes = list(truth_by_gene)
        n_correct = sum(_vote_correct(vote_fn(g), truth_by_gene[g]) for g in genes)
        return n_correct / len(genes)

    db_labels_sorted = sorted(DB_LABELS, key=lambda lbl: -_overall_acc(lbl))
    callers_in_plot = [sonnet_label, *db_labels_sorted]

    # Sonnet per-bucket MEAN-of-replicate fraction so the bar height
    # lines up with the overlaid per-rep points + SEM.
    sonnet_rep_frac: dict[str, float] = {}
    try:
        _s = sonnet_rows[sonnet_rows["model"] == ncbi_model].copy() if ncbi_model else pd.DataFrame()
        if len(_s):
            _s["is_match"] = _s["is_match"].astype(int)
            _s["truth"] = _s["gene_symbol"].map(truth_by_gene)
            _rep_ids = sorted(_s["replicate"].unique())
            for bucket in COLUMNS:
                sub = _s if bucket == "overall" else _s[_s["truth"] == bucket]
                per_rep = [
                    sub[sub["replicate"] == rid]["is_match"].mean()
                    for rid in _rep_ids if len(sub[sub["replicate"] == rid])
                ]
                if per_rep:
                    sonnet_rep_frac[bucket] = sum(per_rep) / len(per_rep)
    except Exception:  # noqa: BLE001
        sonnet_rep_frac = {}

    rows = []
    for caller_label in callers_in_plot:
        if caller_label == sonnet_label:
            def vote_fn(g: str) -> str:
                return sonnet_ncbi.get(g) or "no"
        else:
            def vote_fn(g: str, lbl: str = caller_label) -> str:
                return _vote(g, lbl)
        for bucket in COLUMNS:
            genes = (
                list(truth_by_gene)
                if bucket == "overall"
                else [g for g, t in truth_by_gene.items() if t == bucket]
            )
            if not genes:
                continue
            n_correct = sum(_vote_correct(vote_fn(g), truth_by_gene[g]) for g in genes)
            frac = n_correct / len(genes)
            if caller_label == sonnet_label and bucket in sonnet_rep_frac:
                frac = sonnet_rep_frac[bucket]
            rows.append({
                "caller": caller_label,
                "bucket": bucket,
                "bucket_label": COLUMN_LABEL[bucket],
                "n_correct": n_correct,
                "n_total": len(genes),
                "fraction": frac,
            })
    df = pd.DataFrame(rows)

    overall = {row["caller"]: row["fraction"]
               for row in rows if row["bucket"] == "overall"}
    totals = {row["bucket"]: row["n_total"]
              for row in rows if row["caller"] == sonnet_label and row["bucket"] != "overall"}

    fig, ax = plt.subplots(figsize=(11, 5.5))
    palette = [DB_PALETTE[c] for c in callers_in_plot]
    sns.barplot(
        data=df,
        x="bucket_label", y="fraction",
        hue="caller",
        order=[COLUMN_LABEL[c] for c in COLUMNS],
        hue_order=callers_in_plot,
        palette=palette,
        edgecolor="none", saturation=1.0,
        ax=ax,
    )

    # Insert a small visible gap between the single LLM bar and the
    # 5-DB cluster within each column group.
    n_col = len(COLUMNS)
    n_callers = len(callers_in_plot)
    bar_width = ax.patches[0].get_width()
    gap = bar_width * 0.6
    for caller_idx in range(1, n_callers):
        for j in range(n_col):
            patch = ax.patches[caller_idx * n_col + j]
            patch.set_x(patch.get_x() + gap)

    # Per-bar percentage annotations.
    for i, caller in enumerate(callers_in_plot):
        for j, bucket in enumerate(COLUMNS):
            patch = ax.patches[i * n_col + j]
            frac = df[(df["caller"] == caller) & (df["bucket"] == bucket)].iloc[0]["fraction"]
            ax.text(
                patch.get_x() + patch.get_width() / 2,
                patch.get_height() + 0.01,
                f"{frac:.0%}",
                ha="center", va="bottom",
                fontsize=11, color=INK,
            )

    # Overlay individual-replicate accuracy + SEM on the Sonnet bars.
    try:
        if ncbi_model is not None:
            srep = sonnet_rows[sonnet_rows["model"] == ncbi_model].copy()
            srep["is_match"] = srep["is_match"].astype(int)
            srep["truth"] = srep["gene_symbol"].map(truth_by_gene)
            rep_ids = sorted(srep["replicate"].unique())
            for j, bucket in enumerate(COLUMNS):
                patch = ax.patches[0 * n_col + j]
                xc = patch.get_x() + patch.get_width() / 2
                sub = srep if bucket == "overall" else srep[srep["truth"] == bucket]
                accs = []
                for rid in rep_ids:
                    cell = sub[sub["replicate"] == rid]
                    if len(cell):
                        accs.append(cell["is_match"].mean())
                if len(accs) >= 2:
                    m = sum(accs) / len(accs)
                    sd = (sum((v - m) ** 2 for v in accs) / (len(accs) - 1)) ** 0.5
                    sem = sd / (len(accs) ** 0.5)
                    ax.errorbar(xc, m, yerr=sem, fmt="none", ecolor=INK,
                                elinewidth=1.0, capsize=2.5, capthick=1.0, zorder=5)
                    for k, av in enumerate(accs):
                        jitter = (k - (len(accs) - 1) / 2) * (patch.get_width() * 0.22)
                        ax.scatter(xc + jitter, av, s=14, color=INK,
                                   edgecolor="white", linewidth=0.4, zorder=6, alpha=0.9)
    except Exception:  # noqa: BLE001
        pass

    ax.set_xlabel("")
    ax.set_ylabel("Fraction correctly\nclassified")
    ax.set_ylim(0, 1.14)
    ax.yaxis.set_major_locator(plt.MaxNLocator(6))

    handles, _ = ax.get_legend_handles_labels()
    legend_labels = [f"{lbl}  ({overall[lbl]:.0%})" for lbl in callers_in_plot]
    ax.legend(
        handles, legend_labels,
        title="Caller (overall acc.)",
        loc="upper left", bbox_to_anchor=(1.02, 1.0),
        frameon=False, borderaxespad=0.0,
    )

    subtitle_parts = [f"n(overall) = {sum(totals.values())}"]
    subtitle_parts += [f"n({v}) = {totals[v]}" for v in ["yes", "contextual", "no"]]
    ax.text(
        0.5, -0.34, "  ·  ".join(subtitle_parts),
        transform=ax.transAxes, ha="center", va="top",
        fontsize=13, color=NEUTRAL,
    )
    sns.despine(ax=ax, top=True, right=True)

    save_figure(fig, "db_correctness_by_class", OUT_DIR, gist_url=GIST_URL)
    n_uniprot_opt = int(db_flags["uniprot_optimized"].sum())
    n_cspa_opt    = int(db_flags["cspa_optimized"].sum())
    print(f"Wrote db_correctness_by_class.{{pdf,png}}  ({len(df)} (caller, bucket) cells; "
          f"UniProt TM+signal n={n_uniprot_opt:,}, CSPA HC-only n={n_cspa_opt:,})")


if __name__ == "__main__":
    main()
