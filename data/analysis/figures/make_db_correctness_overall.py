# /// script
# requires-python = ">=3.11"
# dependencies = [
#   "matplotlib>=3.9",
#   "pandas>=2.2",
#   "seaborn>=0.13",
#   "httpx>=0.27",
# ]
# ///
"""Reproduce ``db_correctness_overall.{pdf,png}`` from the public repo.

LLM-only overall accuracy on the 147-gene bench, grouped by model
(Haiku 4.5 / Sonnet 4.6 / Opus 4.8) with hatched bars for the
within-model prompt variants (naive / + IDs / + IDs + web /
+ IDs + PubMed). Color encodes the model (Claude-orange walk);
hatch encodes the prompt variant.

Visual styling matches the in-repo `_plotting_config` (Deliverome
categorical palette + Manrope-when-available). Inlined so the gist
runs standalone.

Standalone — ``uv run make_db_correctness_overall.py``.
"""
from __future__ import annotations

import io
from pathlib import Path

import httpx
import matplotlib.font_manager as fm
import matplotlib.pyplot as plt
import pandas as pd
import seaborn as sns

REPO = "Deliverome-Project/accessible-surfaceome"
BRANCH = "main"
BASE = f"https://raw.githubusercontent.com/{REPO}/{BRANCH}"
BENCH_TSV = f"{BASE}/data/eval/triage_benchmark_v1.tsv"
PREDS_TSV = f"{BASE}/data/processed/triage_bench/mainbench_canonical_v2.tsv"
# Per-replicate predictions (3 reps/cell) — drives the individual-replicate
# accuracy points + SEM error bars overlaid on each bar.
REPS_TSV = f"{BASE}/data/processed/triage_bench/mainbench_replicates_v2.tsv"

# Published reproduction gist (embedded into output PNG Source / PDF
# Subject metadata — mirrors save_figure in _plotting_config.py).
GIST_URL = "https://gist.github.com/beccajcarlson/9c765ed9673d7bd845c3ac091ad2204d"

# ──── Inline brand styling — sentinel: brand-style-v3 ────
# Mirrors src/accessible_surfaceome/audit/_plotting_config.py so the gist
# stays self-contained. Kept in sync via tests/test_figure_gists_styling.py.
BRAND_PALETTE = [
    "#BC3C4C",  # maroon-light
    "#3D6B60",  # teal-mid
    "#F4AA28",  # amber-bright
    "#8878C8",  # lavender-bright
    "#6E1428",  # maroon-dark
    "#7AAB9F",  # teal-light
]
BRAND_SEQUENTIAL = {
    "maroon":   ["#3E0A18", "#6E1428", "#922038", "#BC3C4C", "#F0A098", "#FDE8E6"],
    "teal":     ["#152E28", "#244840", "#3D6B60", "#4D8A80", "#7AAB9F", "#CCE8E4"],
    "amber":    ["#5A2608", "#8C4210", "#C07830", "#F4AA28", "#F4C070", "#FAECD4"],
    "lavender": ["#1E1450", "#3A2888", "#5848A8", "#8878C8", "#A090D4", "#E4E0F8"],
}
BRAND_CLAUDE_ORANGE = "#d87851"
BRAND_INK = "#1F1718"
BRAND_NEUTRAL = "#6F5D5A"
BRAND_GRID = "#E6DAD4"


def _register_brand_fonts() -> None:
    candidates = [
        Path(__file__).resolve().parents[3] / "assets" / "fonts",
        Path.cwd() / "assets" / "fonts",
    ]
    for fonts_dir in candidates:
        if fonts_dir.is_dir():
            for path in sorted(list(fonts_dir.glob("*.ttf")) + list(fonts_dir.glob("*.otf"))):
                try:
                    fm.fontManager.addfont(str(path))
                except Exception:  # noqa: BLE001
                    continue
            return


def _apply_brand_style() -> None:
    """Inline equivalent of `setup_plotting_style`. Sentinel: brand-style-v3.
    v2: bumped sizes ~25% + explicit medium weight (avoids ExtraLight default
    that matplotlib picks from the Manrope variable file). Companion to the
    static Manrope-{regular,medium,semibold,bold}.otf files in assets/fonts/."""
    _register_brand_fonts()
    sns.set_style("whitegrid")
    sns.set_context("notebook", font_scale=1.0)
    plt.rcParams.update({
        "savefig.dpi": 300,
        "savefig.bbox": "tight",
        "figure.facecolor": "none",
        "savefig.facecolor": "none",
        "font.family": "sans-serif",
        "font.sans-serif": ["Manrope", "Outfit", "DejaVu Sans", "Liberation Sans", "Arial"],
        "font.weight": "medium",
        "font.size": 21,
        "axes.labelsize": 25,
        "axes.labelweight": "medium",
        "axes.titlesize": 0,
        "axes.titlepad": 0,
        "axes.spines.top": False,
        "axes.spines.right": False,
        "axes.grid": True,
        "axes.axisbelow": True,
        "axes.edgecolor": BRAND_GRID,
        "axes.labelcolor": BRAND_INK,
        "axes.facecolor": "none",
        "text.color": BRAND_INK,
        "grid.alpha": 0.35,
        "grid.linestyle": "-",
        "grid.linewidth": 0.7,
        "grid.color": BRAND_GRID,
        "xtick.labelsize": 20,
        "ytick.labelsize": 20,
        "xtick.color": BRAND_INK,
        "ytick.color": BRAND_INK,
        "legend.frameon": False,
        "legend.fontsize": 20,
        "patch.edgecolor": "none",
        "patch.linewidth": 0.0,
    })


# Model display order + Claude-orange palette (light → dark = larger model).
MODEL_ORDER = [
    ("claude-haiku-4-5",  "Haiku 4.5",  "#f1c4ab"),
    ("claude-sonnet-4-6", "Sonnet 4.6", BRAND_CLAUDE_ORANGE),
    ("claude-opus-4-8",   "Opus 4.8",   "#a85b3f"),
]

# Variant display order + matplotlib hatch pattern.
VARIANT_ORDER = [
    ("naive",        "naive",           ""),
    ("ncbi",         "+ IDs",          "//"),
    ("web_ncbi",     "+ IDs + web",    "xx"),
    ("pubmed_ncbi",  "+ IDs + PubMed", ".."),
]


def _fetch_tsv(url: str) -> pd.DataFrame:
    local = Path(__file__).resolve().parents[3] / url[len(BASE) + 1:]
    if local.is_file():
        return pd.read_csv(local, sep="\t")
    r = httpx.get(url, timeout=30)
    r.raise_for_status()
    return pd.read_csv(io.StringIO(r.text), sep="\t")


def _verdict_match(pred: str | None, truth: str | None) -> bool:
    if pred is None or truth is None:
        return False
    if pred == truth:
        return True
    return pred in ("yes", "contextual") and truth in ("yes", "contextual")


def _per_rep_accuracy(reps_df):
    """Return {(model, variant): [acc_rep1, acc_rep2, ...]} — one overall
    bench-accuracy value per replicate. The per-rep TSV already carries
    `is_match` (soft-credit), so accuracy is just its mean within each
    (model, variant, replicate) group."""
    out: dict[tuple[str, str], list[float]] = {}
    reps_df = reps_df.copy()
    reps_df["is_match"] = reps_df["is_match"].astype(int)
    grouped = (
        reps_df.groupby(["model", "prompt_variant", "replicate"])["is_match"]
        .mean()
        .reset_index()
    )
    for (model, variant), g in grouped.groupby(["model", "prompt_variant"]):
        out[(model, variant)] = [v * 100 for v in g["is_match"].tolist()]
    return out


def main() -> None:
    _apply_brand_style()
    preds = _fetch_tsv(PREDS_TSV)
    truth = _fetch_tsv(BENCH_TSV).set_index("gene_symbol")["ground_truth_verdict"]
    preds["truth_verdict"] = preds["gene_symbol"].map(truth)
    preds = preds.dropna(subset=["truth_verdict"])
    preds["correct"] = [
        _verdict_match(p, t)
        for p, t in zip(preds["predicted_verdict"], preds["truth_verdict"], strict=True)
    ]

    # Per-replicate accuracies for the points + SEM overlay (3 reps/cell).
    rep_acc = _per_rep_accuracy(_fetch_tsv(REPS_TSV))

    # Wider figure (was 12) so the 4-bar Haiku / Sonnet / Opus clusters'
    # bar-top "9X.X%" labels (one per prompt variant) sit with breathing
    # room instead of touching neighbours.
    fig, ax = plt.subplots(figsize=(16, 5.5))
    n_models = len(MODEL_ORDER)
    n_variants = len(VARIANT_ORDER)
    bar_w = 0.78 / n_variants

    for mi, (model, _, color) in enumerate(MODEL_ORDER):
        for vi, (variant, _, hatch) in enumerate(VARIANT_ORDER):
            reps = rep_acc.get((model, variant), [])
            if not reps:
                continue  # e.g. opus-4-8 was only run on naive + ncbi
            # Bar height = MEAN of per-replicate accuracies (not the majority-
            # vote accuracy) so the bar, the overlaid points, and the SEM error
            # bar all share one center. This is the average single-run accuracy
            # ± run-to-run SEM, with each replicate's accuracy shown as a point.
            mean_rep = sum(reps) / len(reps)
            x = mi + (vi - (n_variants - 1) / 2) * bar_w
            ax.bar(
                x, mean_rep, width=bar_w, color=color, hatch=hatch,
                edgecolor=BRAND_INK, linewidth=0.8, zorder=3,
            )
            if len(reps) >= 2:
                sd = (sum((v - mean_rep) ** 2 for v in reps) / (len(reps) - 1)) ** 0.5
                sem = sd / (len(reps) ** 0.5)
                ax.errorbar(
                    x, mean_rep, yerr=sem, fmt="none",
                    ecolor=BRAND_INK, elinewidth=1.1, capsize=3, capthick=1.1,
                    zorder=4,
                )
            # Jitter the points slightly within the bar so coincident values
            # don't fully overlap.
            for j, rv in enumerate(reps):
                jitter = (j - (len(reps) - 1) / 2) * (bar_w * 0.18)
                ax.scatter(
                    x + jitter, rv, s=20, color=BRAND_INK,
                    edgecolor="white", linewidth=0.5, zorder=5, alpha=0.85,
                )
            ax.text(
                x, mean_rep + 2.6, f"{mean_rep:.1f}%",
                ha="center", va="bottom", fontsize=14, color=BRAND_INK,
            )

    ax.set_xticks(range(n_models))
    ax.set_xticklabels([m_label for _, m_label, _ in MODEL_ORDER], fontsize=19)
    ax.set_ylabel("Overall accuracy on\n147-gene benchmark", fontsize=17)
    ax.set_ylim(0, 105)
    legend_handles = [
        plt.Rectangle((0, 0), 1, 1, facecolor="white", edgecolor=BRAND_INK,
                      hatch=hatch, linewidth=0.8, label=variant_label)
        for _, variant_label, hatch in VARIANT_ORDER
    ]
    ax.legend(
        handles=legend_handles, title="Variant (hatch)",
        loc="center left", bbox_to_anchor=(1.01, 0.5),
        frameon=False, fontsize=16, title_fontsize=19,
    )
    sns.despine(ax=ax, top=True, right=True)

    fig.tight_layout()
    out_pdf = Path("db_correctness_overall.pdf")
    out_png = Path("db_correctness_overall.png")
    fig.savefig(out_pdf, bbox_inches="tight", metadata={"Subject": GIST_URL})
    fig.savefig(out_png, bbox_inches="tight", dpi=300, metadata={"Source": GIST_URL})
    print(f"Wrote {out_pdf} + {out_png}")


if __name__ == "__main__":
    main()
