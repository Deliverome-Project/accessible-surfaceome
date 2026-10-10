"""Sonnet vs best single DB vs k+ DB ensembles — overall accuracy on the 147-gene bench.

Seven-bar comparison:
  * Sonnet (+ IDs)         — the Claude Sonnet 4.6 triage agent on its
                             canonical NCBI-resolver ("gene identifiers")
                             prompt variant. Bar = MEAN of the three
                             per-replicate accuracies, with SEM error bar
                             and the individual replicates as dots.
  * UniProt (TM+signal)    — best single DB under its optimized cutoff
  * 1+ / 2+ / 3+ / 4+ / 5+ DB — ensemble: "yes" iff at least k of the 5
                             surface DBs (UniProt, GO CC, HPA, SURFY, CSPA,
                             each under its optimized cutoff) vote yes.
                             k=1 is the union (any DB), the most permissive
                             setting; k=5 is the strict intersection.

Accuracy uses the project's soft-credit rule: yes ≡ contextual on the
positive side; ``no`` matches ``no`` only. DB / ensemble bars are
deterministic (one value each, no replicates).

Overall correctness only — per-bucket breakdown lives in the sibling
`db_correctness_by_class` canonical figure.

Reads only the per-figure TSV
``data/processed/figures/ensemble_vs_best_db_vs_sonnet.tsv`` (built by
``scripts/build_figure_tsvs.py``).

# Reproduction:
#   Public gist (reader-side standalone, PyPA inline-script-metadata deps):
#   https://gist.github.com/beccajcarlson/0104308c239fe49d91d82a1007632b27
#   Reader-side mirror script:
#   data/analysis/figures/make_ensemble_vs_best_db_vs_sonnet.py.

Run:
    uv run python scripts/figures/ensemble_vs_best_db_vs_sonnet.py
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

ROOT = Path(__file__).resolve().parents[2]
DATA_TSV = ROOT / "data/processed/figures/ensemble_vs_best_db_vs_sonnet.tsv"
OUT_DIR = ROOT / "data/analysis/figures"  # promoted to canonical figures dir

DB_LABELS = ["UniProt", "GO CC", "HPA", "SURFY", "CSPA"]
CLAUDE_ORANGE = "#d87851"

# Sequential teal ramp for the ≥k ensembles, light → dark = permissive → strict.
# Pulled from BRAND_SEQUENTIAL teal so the ensemble bars cluster visually.
ENSEMBLE_PALETTE = {
    1: "#A9C7BF",  # teal-lightest — the union (any DB)
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

    # Sonnet bar = MEAN of the per-replicate accuracies (``is_match`` is the
    # soft-credit match per row), so bar, replicate dots and SEM share one
    # center. Matches the manuscript legend ("mean of three replicates").
    _sonnet_rows = data[
        (data["model"] == "claude-sonnet-4-6") & (data["prompt_variant"] == "ncbi")
    ]
    sonnet_rep_accs = (
        _sonnet_rows.assign(is_match=_sonnet_rows["is_match"].astype(int))
        .groupby("replicate")["is_match"].mean().tolist()
    )

    callers: list[tuple[str, callable, str]] = [
        ("UniProt\n(TM+signal)", lambda g: "yes" if db_votes_for(g).get("UniProt") else "no",
                                                                                                    CATEGORICAL_PALETTE[0]),
    ]
    # "k+ DB" rather than "≥k DB" — static Manrope OTFs lack the ≥ glyph
    # and matplotlib silently drops it; ASCII "+" stays robust.
    for k in (1, 2, 3, 4, 5):
        callers.append((
            f"{k}+ DB",
            (lambda g, k=k: "yes" if sum(db_votes_for(g).values()) >= k else "no"),
            ENSEMBLE_PALETTE[k],
        ))

    genes = list(truth_by_gene)
    sonnet_acc = sum(sonnet_rep_accs) / len(sonnet_rep_accs)
    rows = [{
        # Inner count label = rounded mean correct per single run.
        "caller": "Sonnet (+ IDs)", "accuracy": sonnet_acc,
        "n_correct": round(sonnet_acc * len(genes)), "n_total": len(genes),
        "color": CLAUDE_ORANGE,
    }]
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
    fig, ax = plt.subplots(figsize=(13, 6))
    bars = ax.bar(
        df["caller"], df["accuracy"] * 100,
        color=df["color"], edgecolor="none", width=0.6,
    )
    # Lift the Sonnet % label clear of its replicate dots + SEM cap.
    _reps = [v * 100 for v in sonnet_rep_accs]
    sonnet_top = 0.0
    if len(_reps) >= 2:
        _m = sum(_reps) / len(_reps)
        _sem = ((sum((v - _m) ** 2 for v in _reps) / (len(_reps) - 1)) ** 0.5) / len(_reps) ** 0.5
        sonnet_top = max(max(_reps), _m + _sem)
    for i, (bar, row) in enumerate(zip(bars, df.to_dict("records"), strict=True)):
        ax.text(
            bar.get_x() + bar.get_width() / 2,
            max(bar.get_height(), sonnet_top if i == 0 else 0.0) + 1.2,
            f"{row['accuracy']*100:.1f}%",
            ha="center", va="bottom",
            fontsize=20, fontweight="bold", color=COLORS["dark"],
        )
        ax.text(
            bar.get_x() + bar.get_width() / 2,
            bar.get_height() / 2,
            f"{row['n_correct']}/{row['n_total']}",
            ha="center", va="center",
            fontsize=15, color="white", fontweight="bold",
        )

    # Individual-replicate accuracies + SEM on the Sonnet bar only (bar
    # height is their mean, so all three share one center).
    rep_accs = [v * 100 for v in sonnet_rep_accs]
    if len(rep_accs) >= 2:
        sonnet_bar = bars[0]
        xc = sonnet_bar.get_x() + sonnet_bar.get_width() / 2
        m = sum(rep_accs) / len(rep_accs)
        sd = (sum((v - m) ** 2 for v in rep_accs) / (len(rep_accs) - 1)) ** 0.5
        sem = sd / (len(rep_accs) ** 0.5)
        ax.errorbar(xc, m, yerr=sem, fmt="none", ecolor=COLORS["dark"],
                    elinewidth=1.2, capsize=4, capthick=1.2, zorder=4)
        for j, rv in enumerate(rep_accs):
            jitter = (j - (len(rep_accs) - 1) / 2) * (sonnet_bar.get_width() * 0.16)
            ax.scatter(xc + jitter, rv, s=24, color=COLORS["dark"],
                       edgecolor="white", linewidth=0.5, zorder=5, alpha=0.9)

    ax.set_ylabel("Overall accuracy on\n147-gene bench (%)", fontsize=19)
    ax.set_ylim(0, 105)
    ax.tick_params(axis="x", labelsize=17)
    ax.tick_params(axis="y", labelsize=14)

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
