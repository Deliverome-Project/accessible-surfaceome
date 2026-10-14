# /// script
# requires-python = ">=3.11"
# dependencies = [
#   "matplotlib>=3.9",
#   "pandas>=2.2",
#   "seaborn>=0.13",
# ]
# ///
"""Reproduce ``db_correctness_overall.{pdf,png}`` from the bundled TSV.

LLM-only overall accuracy on the 147-gene bench, grouped by model
(Haiku 4.5 / Haiku 5.5 / Sonnet 4.6 / Sonnet 5 / Sonnet 5.5 / Opus 4.8 /
Opus 5 / Opus 5.5) with hatched bars for the within-model prompt variants
(naive / + IDs / + IDs + web / + IDs + PubMed / + IDs at low reasoning
effort). Groups are packed: a model gets only as many bar slots as it has
variants. Color encodes model generation (orange Claude 4.x, blue Claude 5,
teal Claude 5.5; darker = larger model); the two Sonnet 4.6 configurations
the production pipeline uses are lavender. Bar height is the mean of the
three per-replicate accuracies over answered calls; points are the
replicates and error bars are the SEM across replicates. Refused calls
(``refused`` = 1) are excluded and their rate is printed on the bar.

Visual styling matches the in-repo `_plotting_config` (Deliverome
categorical palette + Manrope-when-available). Inlined so the gist
runs standalone.

Standalone — ``uv run make_db_correctness_overall.py``.
"""
from __future__ import annotations

from math import comb
from pathlib import Path

import matplotlib.font_manager as fm
import matplotlib.pyplot as plt
import pandas as pd
import seaborn as sns
from matplotlib.patches import Patch

REPO = "Deliverome-Project/accessible-surfaceome"
BRANCH = "main"
BASE = f"https://raw.githubusercontent.com/{REPO}/{BRANCH}"
# Single per-figure TSV: one row per (gene × model × prompt_variant ×
# replicate) with ``is_match`` (soft-credit) + ``ground_truth_verdict``
# denormalized in. Produced by ``scripts/build_figure_tsvs.py``. Gist
# bundles this TSV next to the script; the figure reads only from the
# sibling. No other data sources.
DATA_TSV = f"{BASE}/data/processed/figures/db_correctness_overall.tsv"

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
    static Manrope-{Regular,Medium,SemiBold,Bold}.ttf files in assets/fonts/."""
    _register_brand_fonts()
    sns.set_style("whitegrid")
    sns.set_context("notebook", font_scale=1.0)
    plt.rcParams.update({
        "savefig.dpi": 600,
        "savefig.bbox": "tight",
        "figure.facecolor": "none",
        "savefig.facecolor": "none",
        "font.family": ["Manrope", "DejaVu Sans"],
        "font.sans-serif": ["Manrope", "Outfit", "DejaVu Sans", "Liberation Sans", "Arial"],
        "font.weight": "semibold",
        "font.size": 16,
        "axes.labelsize": 18,
        "axes.labelweight": "semibold",
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
        "xtick.labelsize": 16,
        "ytick.labelsize": 16,
        "xtick.color": BRAND_INK,
        "ytick.color": BRAND_INK,
        "legend.frameon": False,
        "legend.fontsize": 16,
        "patch.edgecolor": "none",
        "patch.linewidth": 0.0,
    })


# Model display order + color: hue = generation (orange 4.x, blue 5, teal
# 5.5), light → dark = larger model.
MODEL_ORDER = [
    ("claude-haiku-4-5",  "Haiku 4.5",  "#f1c4ab"),
    ("claude-haiku-5-5",  "Haiku 5.5",  "#9fd3cf"),
    ("claude-sonnet-4-6", "Sonnet 4.6", BRAND_CLAUDE_ORANGE),
    ("claude-sonnet-5",   "Sonnet 5",   "#6b9cc4"),
    ("claude-sonnet-5-5", "Sonnet 5.5", "#3f9c96"),
    ("claude-opus-4-8",   "Opus 4.8",   "#a85b3f"),
    ("claude-opus-5",     "Opus 5",     "#2e5d7a"),
    ("claude-opus-5-5",   "Opus 5.5",   "#1f5f5b"),
]
# The configurations the production pipeline runs, recolored so they stand
# out from their generation.
PRODUCTION_COLOR = {
    ("claude-sonnet-4-6", "ncbi"):        "#7B6BB0",
    ("claude-sonnet-4-6", "pubmed_ncbi"): "#B3A6DA",
}
# Variant display order + matplotlib hatch pattern.
VARIANT_ORDER = [
    ("naive",           "naive",                 ""),
    ("ncbi",            "+ IDs",                 "//"),
    ("web_ncbi",        "+ IDs + web",           "xx"),
    ("pubmed_ncbi",     "+ IDs + PubMed",        ".."),
    ("ncbi_effort_low", "+ IDs, low effort",     "\\\\"),
]
COLOR_LEGEND = [
    ("Claude 4.x", BRAND_CLAUDE_ORANGE),
    ("Claude 5", "#2e5d7a"),
    ("Claude 5.5", "#3f9c96"),
    ("Production triage", "#7B6BB0"),
]
BAR_W = 0.22      # one bar slot, in axis units
GROUP_GAP = 0.30  # space between model groups


def _fetch_tsv(url: str) -> pd.DataFrame:
    # Bundled-only: the gist HEAD commit SHA is the SWHID for the
    # whole reproduction unit (script + data + README), so we must
    # never read a *different* TSV than what's bundled. Sibling-first
    # (gist case); fall back to the in-repo TSV path (dev case). No
    # network fetch — a missing sibling in a gist is a hard error.
    sibling = Path(__file__).parent / Path(url).name
    if sibling.is_file():
        return pd.read_csv(sibling, sep="\t")
    local = Path(__file__).resolve().parents[3] / url[len(BASE) + 1:]
    if local.is_file():
        return pd.read_csv(local, sep="\t")
    raise FileNotFoundError(
        f"TSV not found at sibling ({sibling.name}) or local ({local}). "
        f"In a gist, the bundled TSV must sit next to this script."
    )


def _per_rep_accuracy(reps_df):
    """Return {(model, variant): [acc_rep1, acc_rep2, ...]} — one overall
    bench-accuracy value per replicate over answered calls. The per-rep TSV
    already carries `is_match` (soft-credit), so accuracy is its mean within
    each (model, variant, replicate) group once refused calls are dropped."""
    out: dict[tuple[str, str], list[float]] = {}
    reps_df = reps_df.copy()
    reps_df["is_match"] = reps_df["is_match"].astype(int)
    if "refused" in reps_df:
        reps_df = reps_df[reps_df["refused"].fillna(0).astype(int) == 0]
    grouped = (
        reps_df.groupby(["model", "prompt_variant", "replicate"])["is_match"]
        .mean()
        .reset_index()
    )
    for (model, variant), g in grouped.groupby(["model", "prompt_variant"]):
        out[(model, variant)] = [v * 100 for v in g["is_match"].tolist()]
    return out


def _refusal_pct(reps_df):
    """{(model, variant): % of calls refused}."""
    if "refused" not in reps_df:
        return {}
    refused = reps_df["refused"].fillna(0).astype(int)
    return (refused.groupby([reps_df["model"], reps_df["prompt_variant"]]).mean() * 100).to_dict()


def _exact_mcnemar(a_correct, b_correct):
    """Exact two-sided McNemar test on paired correctness: returns
    (n_only_a, n_only_b, p). Same arithmetic as
    ``accessible_surfaceome.audit.paired_tests.exact_mcnemar``, inlined so
    this script stays standalone."""
    only_a = sum(1 for a, b in zip(a_correct, b_correct) if a and not b)
    only_b = sum(1 for a, b in zip(a_correct, b_correct) if b and not a)
    n = only_a + only_b
    if n == 0:
        return only_a, only_b, 1.0
    tail = sum(comb(n, k) for k in range(min(only_a, only_b) + 1)) / 2**n
    return only_a, only_b, min(1.0, 2 * tail)


# Paired comparisons the Results describe as not significantly different:
# added context (web search, pre-fetched PubMed abstracts) against identifiers
# alone, and Sonnet 5 against the production Sonnet 4.6, both with identifiers.
MCNEMAR_PAIRS = [
    (("claude-sonnet-4-6", "ncbi"), ("claude-sonnet-4-6", "web_ncbi")),
    (("claude-sonnet-4-6", "ncbi"), ("claude-sonnet-4-6", "pubmed_ncbi")),
    (("claude-haiku-4-5", "ncbi"), ("claude-haiku-4-5", "web_ncbi")),
    (("claude-haiku-4-5", "ncbi"), ("claude-haiku-4-5", "pubmed_ncbi")),
    (("claude-sonnet-4-6", "ncbi"), ("claude-sonnet-5", "ncbi")),
]


def mcnemar_rows(reps_df):
    """Exact McNemar test on paired per-protein correctness for each pair in
    ``MCNEMAR_PAIRS``.

    A protein counts as correct for a (model, context) when most of its
    answered replicates were; a protein is dropped from a pair if either side
    has no answered replicate.
    """
    df = reps_df.copy()
    df["is_match"] = df["is_match"].astype(int)
    if "refused" in df:
        df = df[df["refused"].fillna(0).astype(int) == 0]
    majority = (
        df.groupby(["model", "prompt_variant", "gene_symbol"])["is_match"].mean() > 0.5
    )
    out = []
    for a, b in MCNEMAR_PAIRS:
        a_ok, b_ok = majority.loc[a], majority.loc[b]
        genes = sorted(set(a_ok.index) & set(b_ok.index))
        only_a, only_b, p = _exact_mcnemar(
            [bool(a_ok[g]) for g in genes], [bool(b_ok[g]) for g in genes]
        )
        out.append({
            "a": "/".join(a), "b": "/".join(b), "n": len(genes),
            "only_a_correct": only_a, "only_b_correct": only_b, "p": p,
        })
    return out


def _print_mcnemar(reps_df) -> None:
    print("Exact McNemar test (paired per-protein correctness, majority of replicates):")
    for r in mcnemar_rows(reps_df):
        print(f"  {r['a']} vs {r['b']}: n={r['n']}  only first correct={r['only_a_correct']}"
              f"  only second correct={r['only_b_correct']}  p={r['p']:.3f}")


def main() -> None:
    _apply_brand_style()
    reps_df = _fetch_tsv(DATA_TSV)
    rep_acc = _per_rep_accuracy(reps_df)
    _print_mcnemar(reps_df)
    refusal_pct = _refusal_pct(reps_df)

    # Legends sit above the axes so the bars span the full width and each
    # bar-top "9X.X%" label fits inside its own bar without touching neighbors.
    fig, ax = plt.subplots(figsize=(18, 5.5))
    x, centers, labels = 0.0, [], []
    for model, m_label, color in MODEL_ORDER:
        present = [(v, h) for v, _, h in VARIANT_ORDER if rep_acc.get((model, v))]
        if not present:
            continue  # model not in the data
        xs = [x + i * BAR_W for i in range(len(present))]
        for xi, (variant, hatch) in zip(xs, present):
            reps = rep_acc[(model, variant)]
            # Bar height = MEAN of per-replicate accuracies so the bar, the
            # overlaid points, and the SEM error bar all share one center.
            mean_rep = sum(reps) / len(reps)
            ax.bar(
                xi, mean_rep, width=BAR_W, color=PRODUCTION_COLOR.get((model, variant), color),
                hatch=hatch, edgecolor=BRAND_INK, linewidth=0.8, zorder=3,
            )
            sem = 0.0
            if len(reps) >= 2:
                sd = (sum((v - mean_rep) ** 2 for v in reps) / (len(reps) - 1)) ** 0.5
                sem = sd / (len(reps) ** 0.5)
                ax.errorbar(
                    xi, mean_rep, yerr=sem, fmt="none",
                    ecolor=BRAND_INK, elinewidth=1.1, capsize=3, capthick=1.1,
                    zorder=4,
                )
            # Jitter the points slightly within the bar so coincident values
            # don't fully overlap.
            for j, rv in enumerate(reps):
                jitter = (j - (len(reps) - 1) / 2) * (BAR_W * 0.18)
                ax.scatter(
                    xi + jitter, rv, s=20, color=BRAND_INK,
                    edgecolor="white", linewidth=0.5, zorder=5, alpha=0.85,
                )
            # Clear the highest replicate dot / SEM cap, not just the bar.
            ax.annotate(
                f"{mean_rep:.1f}%", xy=(xi, max([*reps, mean_rep + sem])), xytext=(0, 5),
                textcoords="offset points", ha="center", va="bottom",
                fontsize=13.5, color=BRAND_INK,
            )
            pct = refusal_pct.get((model, variant), 0.0)
            if pct:
                ax.annotate(
                    f"{pct:.1f}% of calls refused", xy=(xi, mean_rep / 2),
                    ha="center", va="center", rotation=90, fontsize=13,
                    color="white", fontweight="bold", zorder=6,
                )
        centers.append(sum(xs) / len(xs))
        labels.append(m_label)
        x = xs[-1] + BAR_W + GROUP_GAP

    ax.set_xticks(centers)
    ax.set_xticklabels(labels)
    ax.set_ylabel("Overall accuracy on\n147-gene benchmark")
    ax.set_ylim(0, 106)
    ax.set_xlim(-BAR_W / 2 - 0.12, x - GROUP_GAP - BAR_W / 2 + 0.12)
    hatch_handles = [
        plt.Rectangle((0, 0), 1, 1, facecolor="white", edgecolor=BRAND_INK,
                      hatch=hatch, linewidth=0.8, label=variant_label)
        for _, variant_label, hatch in VARIANT_ORDER
    ]
    # Two legends above the axes: context (hatch) on the left, color on the
    # right, so the bars get the full width.
    hatch_legend = ax.legend(
        handles=hatch_handles, title="Context (hatch)", loc="lower left",
        bbox_to_anchor=(0.0, 1.04), ncol=len(hatch_handles), frameon=False,
        title_fontsize=16, fontsize=14, columnspacing=1.2, handlelength=2.0,
        alignment="left",
    )
    ax.add_artist(hatch_legend)
    ax.legend(
        handles=[Patch(facecolor=c, edgecolor=BRAND_INK, label=lab) for lab, c in COLOR_LEGEND],
        title="Color (darker = larger model)", loc="lower right",
        bbox_to_anchor=(1.0, 1.04), ncol=len(COLOR_LEGEND), frameon=False,
        title_fontsize=16, fontsize=14, columnspacing=1.2, handlelength=1.6,
        alignment="left",
    )
    sns.despine(ax=ax, top=True, right=True)

    fig.tight_layout()
    out_pdf = Path("db_correctness_overall.pdf")
    out_png = Path("db_correctness_overall.png")
    fig.savefig(out_pdf, bbox_inches="tight", metadata={"Subject": GIST_URL})
    fig.savefig(out_png, bbox_inches="tight", dpi=600, metadata={"Source": GIST_URL})
    print(f"Wrote {out_pdf} + {out_png}")


if __name__ == "__main__":
    main()
