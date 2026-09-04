"""Sonnet vs best single DB vs ≥k DB ensembles — overall accuracy on the 147-gene bench.

Six-bar comparison:
  * Sonnet (+ NCBI)        — the LLM, canonical NCBI-resolver variant
  * UniProt (TM+signal)    — best single DB under its optimized cutoff
  * ≥2 / ≥3 / ≥4 / ≥5 DB   — ensemble: "yes" iff at least k of the 5
                              surface DBs (each under its optimized
                              cutoff) vote yes

Overall correctness only — per-bucket breakdown lives in the sibling
`db_correctness_by_class` canonical figure.

# Reproduction:
#   Public gist (reader-side standalone, PyPA inline-script-metadata deps):
#   https://gist.github.com/beccajcarlson/0104308c239fe49d91d82a1007632b27
#   Reader-side mirror script:
#   data/analysis/figures/make_ensemble_vs_best_db_vs_sonnet.py.

Run:
    uv run python scripts/ensemble_vs_best_db_vs_sonnet.py
"""
from __future__ import annotations

from pathlib import Path

import matplotlib.pyplot as plt
import pandas as pd
import seaborn as sns

from accessible_surfaceome.audit._plotting_config import (
    CATEGORICAL_PALETTE,
    COLORS,
    save_figure,
    setup_plotting_style,
)

ROOT = Path(__file__).resolve().parents[1]
DATA_TSV = ROOT / "data/processed/figures/ensemble_vs_best_db_vs_sonnet.tsv"
OUT_DIR = ROOT / "data/analysis/figures"  # promoted to canonical figures dir

DB_LABELS = ["UniProt", "GO CC", "HPA", "SURFY", "CSPA"]
CLAUDE_ORANGE = "#d87851"

# Sequential teal ramp for the ≥k ensembles, light → dark = permissive → strict.
# Pulled from BRAND_SEQUENTIAL teal so the ensemble bars cluster visually.
ENSEMBLE_PALETTE = {
    2: "#7AAB9F",  # teal-light
    3: "#4D8A80",
    4: "#3D6B60",
    5: "#244840",  # teal-deep
}


def _vote_correct(vote: str, truth: str) -> bool:
    if vote == truth:
        return True
    return vote in ("yes", "contextual") and truth in ("yes", "contextual")


def main() -> None:
    # Single per-figure TSV — all inputs denormalized by build_figure_tsvs.py.
    data = pd.read_csv(DATA_TSV, sep="\t")

    # Per-gene tables — per-DB flags + truth + acc are constant across rows
    # for the same gene (independent of model/variant/replicate).
    gene_first = data.groupby("gene_symbol", sort=False).first()
    truth_by_gene = gene_first["ground_truth_verdict"].to_dict()

    def db_votes_for(gene: str) -> dict[str, bool]:
        out = {label: False for label in DB_LABELS}
        if gene not in gene_first.index:
            return out
        row = gene_first.loc[gene]
        out["UniProt"] = row["uniprot_optimized"] == 1
        out["CSPA"]    = row["cspa_optimized"]    == 1
        out["GO CC"]   = row["go_surface_flag"]   == 1
        out["HPA"]     = row["hpa_surface_flag"]  == 1
        out["SURFY"]   = row["surfy_surface_flag"] == 1
        return out

    sonnet_ncbi = (
        data[(data["model"] == "claude-sonnet-4-6") & (data["prompt_variant"] == "ncbi")]
        .groupby("gene_symbol", sort=False)["predicted_verdict"].first().to_dict()
    )

    callers: list[tuple[str, callable, str]] = [
        ("Sonnet (+ NCBI)",      lambda g: sonnet_ncbi.get(g) or "no",                              CLAUDE_ORANGE),
        ("UniProt\n(TM+signal)", lambda g: "yes" if db_votes_for(g).get("UniProt") else "no",
                                                                                                    CATEGORICAL_PALETTE[0]),
    ]
    for k in (2, 3, 4, 5):
        callers.append((
            f"≥{k} DB",
            (lambda g, k=k: "yes" if sum(db_votes_for(g).values()) >= k else "no"),
            ENSEMBLE_PALETTE[k],
        ))

    genes = list(truth_by_gene)
    rows = []
    for label, vote_fn, color in callers:
        n_correct = sum(_vote_correct(vote_fn(g), truth_by_gene[g]) for g in genes)
        rows.append({
            "caller": label, "accuracy": n_correct / len(genes),
            "n_correct": n_correct, "n_total": len(genes), "color": color,
        })
    df = pd.DataFrame(rows)
    print("\nOverall accuracy on 147-gene bench:")
    for _, row in df.iterrows():
        print(f"  {row['caller'].replace(chr(10), ' '):20s}  "
              f"{row['accuracy']*100:5.1f}%  ({row['n_correct']}/{row['n_total']})")

    setup_plotting_style(style="whitegrid", context="notebook", font_scale=1.0)
    # Brand-style-v3 font sizes — matches the gist mirror.
    # See CLAUDE.md "Canonical generator vs gist mirror".
    plt.rcParams.update({
        "font.size": 20, "axes.labelsize": 20, "axes.titlesize": 0,
        "xtick.labelsize": 20, "ytick.labelsize": 20, "legend.fontsize": 20,
    })
    fig, ax = plt.subplots(figsize=(10, 5.5))
    bars = ax.bar(
        df["caller"], df["accuracy"] * 100,
        color=df["color"], edgecolor="none", width=0.6,
    )
    for bar, row in zip(bars, df.to_dict("records"), strict=True):
        ax.text(
            bar.get_x() + bar.get_width() / 2,
            bar.get_height() + 1.2,
            f"{row['accuracy']*100:.1f}%",
            ha="center", va="bottom",
            fontsize=17, fontweight="bold", color=COLORS["dark"],
        )
        ax.text(
            bar.get_x() + bar.get_width() / 2,
            bar.get_height() / 2,
            f"{row['n_correct']}/{row['n_total']}",
            ha="center", va="center",
            fontsize=12, color="white", fontweight="bold",
        )

    ax.set_ylabel("Overall accuracy on\n147-gene bench (%)", fontsize=19)
    ax.set_ylim(0, 105)
    ax.tick_params(axis="x", labelsize=13)
    ax.tick_params(axis="y", labelsize=13)

    sns.despine(ax=ax, top=True, right=True)
    fig.tight_layout()
    save_figure(
        fig, filename="ensemble_vs_best_db_vs_sonnet",
        output_dir=str(OUT_DIR), formats=["pdf", "png"],
        gist_url="https://gist.github.com/beccajcarlson/0104308c239fe49d91d82a1007632b27",
    )
    plt.close(fig)


if __name__ == "__main__":
    main()
