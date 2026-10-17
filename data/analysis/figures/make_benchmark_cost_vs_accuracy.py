# /// script
# requires-python = ">=3.11"
# dependencies = [
#   "matplotlib>=3.9",
#   "pandas>=2.2",
#   "seaborn>=0.13",
# ]
# ///
"""Reproduce ``benchmark_cost_vs_accuracy.{pdf,png}`` from the public repo.

Reads the bundled ``benchmark_cost_vs_accuracy.tsv`` (the sibling file in
the gist; falls back to the in-repo copy under ``data/processed/figures/``),
then renders the 18-cell cost/accuracy frontier: Haiku 4.5 and Sonnet 4.6
each × {naive, + IDs, + IDs + PubMed, + IDs + web}, Sonnet 5 × {+ IDs},
Opus 4.8 × {naive, + IDs}, Opus 5 × {+ IDs}, Haiku 5.5 and Sonnet 5.5 each ×
{naive, + IDs}, and Opus 5.5 × {+ IDs, + IDs at low reasoning effort}.
Accuracy is the mean over 3 replicates on the 147-gene bench, over answered
calls: refused calls (``refused`` = 1) are excluded and the cell's refusal
rate is printed in its label. Color encodes model generation (orange Claude
4.x, blue Claude 5, teal Claude 5.5). The two lavender points are the
Sonnet 4.6 configurations the production pipeline runs: + IDs for the
genome-wide triage sweep, and + IDs + PubMed for the rescue lanes.

Visual styling matches the in-repo `_plotting_config` (Deliverome
categorical palette + Manrope-when-available). Inlined so the gist
runs standalone.

Standalone — ``uv run make_benchmark_cost_vs_accuracy.py`` is all
you need.
"""
from __future__ import annotations

import colorsys
from pathlib import Path

import matplotlib.font_manager as fm
import matplotlib.pyplot as plt
import pandas as pd
import seaborn as sns
from matplotlib.colors import to_hex, to_rgb
from matplotlib.lines import Line2D

# Data source. BASE is used only to name the TSV and to map it to its
# in-repo path; the script never downloads it (see _fetch_tsv). Upstream,
# per-replicate predictions are exported from public D1 by
# `scripts/tsv-export/export_mainbench_to_tsv.py` into
# `data/processed/triage_bench/mainbench_replicates_v2.tsv`, which
# `scripts/build_figure_tsvs.py` turns into the per-figure TSV below.
REPO = "Deliverome-Project/accessible-surfaceome"
BRANCH = "main"  # pin to a commit SHA at publication for immutable citation
BASE = f"https://raw.githubusercontent.com/{REPO}/{BRANCH}"
# Single per-figure TSV: one row per (gene × model × prompt_variant ×
# replicate) with per-rep tokens, ``is_match`` (soft-credit), and
# ``ground_truth_verdict`` all denormalized in. Produced by
# ``scripts/build_figure_tsvs.py``. Gist bundles this TSV next to the
# script; the figure reads only from the sibling, no other URLs.
DATA_TSV = f"{BASE}/data/processed/figures/benchmark_cost_vs_accuracy.tsv"

# Published reproduction gist (embedded into output PNG Source / PDF
# Subject metadata — mirrors save_figure in _plotting_config.py).
GIST_URL = "https://gist.github.com/beccajcarlson/d7f764d2de288ae31cf44173bc396d41"

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
PRODUCTION_COLOR = "#7B6BB0"
PRODUCTION_LIGHT = "#B3A6DA"
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
        "font.size": 10.5,
        "axes.labelsize": 12,
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
        "xtick.labelsize": 10.5,
        "ytick.labelsize": 10.5,
        "xtick.color": BRAND_INK,
        "ytick.color": BRAND_INK,
        "legend.frameon": False,
        "legend.fontsize": 10.5,
        "patch.edgecolor": "none",
        "patch.linewidth": 0.0,
    })


# Per-million-token prices used for the figure: in = input, out = output,
# cr = cache read, cw = cache write. Verified 2026-10-11 against
# https://platform.claude.com/docs/en/about-claude/pricing.
#
# Two corrections landed here together, for different reasons:
#  * Opus 4.8 was carrying 15/75/1.50/18.75 — an exact four-way match for the
#    retired Opus 4.1 row. It was copied forward from a claude-opus-4-7 entry
#    that had the same problem. No Opus since 4.5 has been priced above 5/25.
#  * Sonnet 5 was deliberately entered at Sonnet 4.6's rate, because that was
#    the increase Anthropic had scheduled for 2026-09-01. The increase was
#    cancelled and the 2/10 launch price became the standard price, so the
#    legend sentence that explained the choice is gone too.
_PRICE = {
    "claude-haiku-4-5":  {"in": 1.00, "out": 5.00,  "cr": 0.10, "cw": 1.25},
    "claude-sonnet-4-6": {"in": 3.00, "out": 15.00, "cr": 0.30, "cw": 3.75},
    "claude-sonnet-5":   {"in": 2.00, "out": 10.00, "cr": 0.20, "cw": 2.50},
    "claude-opus-4-8":   {"in": 5.00, "out": 25.00, "cr": 0.50, "cw": 6.25},
    "claude-opus-5":     {"in": 5.00, "out": 25.00, "cr": 0.50, "cw": 6.25},
    # Claude 5.5 family, verified 2026-10-12. Cache write is 1.25x input;
    # Haiku 5.5's cache-read rate is not listed separately and is taken as
    # 0.1x input, the rate every other tier uses. Haiku 5.5's prices hold for
    # prompts up to 100K tokens, far above any triage call.
    "claude-opus-5-5":   {"in": 4.00, "out": 20.00, "cr": 0.20, "cw": 5.00},
    "claude-sonnet-5-5": {"in": 2.00, "out": 10.00, "cr": 0.20, "cw": 2.50},
    "claude-haiku-5-5":  {"in": 0.10, "out": 0.50,  "cr": 0.01, "cw": 0.125},
}
WEB_SEARCH_USD_PER_QUERY = 0.01
WHOLE_GENOME_N = 19_324  # protein-coding human genes with a valid HGNC + UniProt mapping

# Per-cell label + color. Hue = model generation, shade = model size and
# context (light → dark): orange Claude 4.x, blue Claude 5, teal Claude 5.5.
# The two production configurations (Sonnet 4.6 + IDs, + IDs + PubMed) are
# lavender instead, so they stand out from their own generation.
CELL_LABEL = {
    ("claude-haiku-4-5",  "naive"):       "Haiku 4.5 (naive)",
    ("claude-haiku-4-5",  "ncbi"):        "Haiku 4.5 (+ IDs)",
    ("claude-haiku-4-5",  "pubmed_ncbi"): "Haiku 4.5 (+ IDs + PubMed)",
    ("claude-haiku-4-5",  "web_ncbi"):    "Haiku 4.5 (+ IDs + web)",
    ("claude-sonnet-4-6", "naive"):       "Sonnet 4.6 (naive)",
    ("claude-sonnet-4-6", "ncbi"):        "Sonnet 4.6 (+ IDs)",
    ("claude-sonnet-4-6", "pubmed_ncbi"): "Sonnet 4.6 (+ IDs + PubMed)",
    ("claude-sonnet-4-6", "web_ncbi"):    "Sonnet 4.6 (+ IDs + web)",
    ("claude-sonnet-5",   "ncbi"):        "Sonnet 5 (+ IDs)",
    ("claude-opus-4-8",   "naive"):       "Opus 4.8 (naive)",
    ("claude-opus-4-8",   "ncbi"):        "Opus 4.8 (+ IDs)",
    ("claude-opus-5",     "ncbi"):        "Opus 5 (+ IDs)",
    ("claude-haiku-5-5",  "naive"):       "Haiku 5.5 (naive)",
    ("claude-haiku-5-5",  "ncbi"):        "Haiku 5.5 (+ IDs)",
    ("claude-sonnet-5-5", "naive"):       "Sonnet 5.5 (naive)",
    ("claude-sonnet-5-5", "ncbi"):        "Sonnet 5.5 (+ IDs)",
    ("claude-opus-5-5",   "ncbi"):        "Opus 5.5 (+ IDs)",
    # Two lines: the label also carries the refusal rate.
    ("claude-opus-5-5",   "ncbi_effort_low"): "Opus 5.5 (+ IDs,\nlow effort)",
}
CELL_COLOR = {
    ("claude-haiku-4-5",  "naive"):       "#f7d8c4",
    ("claude-haiku-4-5",  "ncbi"):        "#f1c4ab",
    ("claude-haiku-4-5",  "pubmed_ncbi"): "#eab695",
    ("claude-haiku-4-5",  "web_ncbi"):    "#ec9e7d",
    ("claude-sonnet-4-6", "naive"):       "#e3a07d",
    ("claude-sonnet-4-6", "ncbi"):        PRODUCTION_COLOR,
    ("claude-sonnet-4-6", "pubmed_ncbi"): PRODUCTION_LIGHT,
    ("claude-sonnet-4-6", "web_ncbi"):    "#c46139",
    ("claude-sonnet-5",   "ncbi"):        "#6b9cc4",
    ("claude-opus-4-8",   "naive"):       "#b66547",
    ("claude-opus-4-8",   "ncbi"):        "#a85b3f",
    ("claude-opus-5",     "ncbi"):        "#2e5d7a",
    ("claude-haiku-5-5",  "naive"):       "#d3eeeb",
    ("claude-haiku-5-5",  "ncbi"):        "#9fd3cf",
    ("claude-sonnet-5-5", "naive"):       "#8fcac5",
    ("claude-sonnet-5-5", "ncbi"):        "#3f9c96",
    ("claude-opus-5-5",   "ncbi"):        "#1f5f5b",
    ("claude-opus-5-5",   "ncbi_effort_low"): "#2d7a74",
}
# Legend: one swatch per generation plus the production configurations.
GENERATION_LEGEND = [
    ("Claude 4.x (Haiku 4.5, Sonnet 4.6, Opus 4.8)", BRAND_CLAUDE_ORANGE),
    ("Claude 5 (Sonnet 5, Opus 5)", "#2e5d7a"),
    ("Claude 5.5 (Haiku, Sonnet, Opus)", "#3f9c96"),
    ("Production triage (Sonnet 4.6)", PRODUCTION_COLOR),
]

# Per-cell label offsets (points) — mirrors
# scripts/figures/benchmark_cost_vs_accuracy.py. Labels are vertically
# centered on the anchor; dx < 0 right-aligns them to the left of the point.
# Offsets >= 18 pt get a leader line. Checked so no label touches a dot,
# another label or a leader line — re-tune if cells move.
CELL_LABEL_OFFSET = {
    ("claude-haiku-4-5",  "naive"):       (10,   0),
    # Below-right: the + IDs + PubMed point sits level with it to the right.
    ("claude-haiku-4-5",  "ncbi"):        (10, -13),
    ("claude-haiku-4-5",  "pubmed_ncbi"): (10,   0),
    ("claude-haiku-4-5",  "web_ncbi"):    (-10,  0),
    # Sonnet 4.6 naive / + IDs sit close together: both labels go LEFT into
    # the empty gap toward Haiku.
    ("claude-sonnet-4-6", "naive"):       (-10,  0),
    ("claude-sonnet-4-6", "ncbi"):        (-14,  9),
    # + IDs + PubMed is boxed in by Sonnet 5.5 (+ IDs) to its upper left and
    # Opus 4.8 (+ IDs) to its right: its label goes straight up on a leader,
    # into the empty band along the top of the axes.
    ("claude-sonnet-4-6", "pubmed_ncbi"): (2,   40),
    ("claude-sonnet-4-6", "web_ncbi"):    (10,   9),
    # Sonnet 5 (+ IDs) and Opus 4.8 (naive) labels go left, clearing the
    # space right of the Opus points for the Opus 5.5 labels.
    ("claude-sonnet-5",   "ncbi"):        (-12,  0),
    ("claude-opus-4-8",   "naive"):       (-12,  7),
    ("claude-opus-4-8",   "ncbi"):        (10,   0),
    ("claude-opus-5",     "ncbi"):        (10,  10),
    ("claude-haiku-5-5",  "naive"):       (10,   0),
    ("claude-haiku-5-5",  "ncbi"):        (10,   0),
    # Sonnet 5.5 sits on top of Sonnet 4.6 in cost: naive goes left between
    # the two Sonnet 4.6 labels, + IDs goes up-left on a leader.
    ("claude-sonnet-5-5", "naive"):       (-12,  0),
    ("claude-sonnet-5-5", "ncbi"):        (-16, 18),
    # The two Opus 5.5 labels carry refusal rates, so they are long: + IDs
    # goes down-left on a leader, low effort down-right below Opus 5.
    ("claude-opus-5-5",   "ncbi"):        (-14, -22),
    ("claude-opus-5-5",   "ncbi_effort_low"): (80, -45),
}


def _fetch_tsv(url: str) -> pd.DataFrame:
    """Bundled-only: the gist HEAD commit SHA is the SWHID for the
    whole reproduction unit (script + data + README), so we must
    never read a *different* TSV than what's bundled. Sibling-first
    (gist case); fall back to the in-repo TSV path (dev case). No
    network fetch — a missing sibling in a gist is a hard error."""
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


def _whole_genome_cost(group: pd.DataFrame) -> float:
    """Per-cell cost extrapolated to one pass over the 19,324-gene catalog.

    Per-rep TSV: each row IS one replicate (gene × model × variant × rep),
    so token columns already carry per-replicate counts. Cost is per single
    triage pass — average the per-rep counts across the cell's
    (gene, replicate) rows. ``n`` here is gene-count (rows ÷ reps per gene
    ≈ unique genes), used only in the system-prompt amortization: the
    shared system prompt is charged once at the cache-write rate and
    reused ``n - 1`` times at the cache-read rate. Cells with no recorded
    cache tokens treat the first 2,000 prompt tokens as that system
    prompt. Each web search adds WEB_SEARCH_USD_PER_QUERY."""
    model = group["model"].iloc[0]
    pricing = _PRICE[model]
    n = group["gene_symbol"].nunique()
    pt = group["prompt_tokens"].mean()
    cr = group["cache_read_tokens"].mean()
    cw = group["cache_creation_tokens"].mean()
    ot = group["completion_tokens"].mean()
    ws = group["n_web_searches"].mean()

    if cr > 0 or cw > 0:
        sys_size = max(cr, cw)
        user_size = pt
    else:
        sys_size = min(2000.0, pt)
        user_size = max(0.0, pt - sys_size)

    sys_per_cell = (
        sys_size * pricing["cw"] + (n - 1) * sys_size * pricing["cr"]
    ) / n / 1_000_000
    user_per_cell = user_size * pricing["in"] / 1_000_000
    out_per_cell  = ot       * pricing["out"] / 1_000_000
    web_per_cell  = ws       * WEB_SEARCH_USD_PER_QUERY
    return (sys_per_cell + user_per_cell + out_per_cell + web_per_cell) * WHOLE_GENOME_N


def _label(model: str, variant: str, refusal_pct: float) -> str:
    """Cell label, with the refusal rate folded into the parenthetical."""
    label = CELL_LABEL[(model, variant)]
    if refusal_pct:
        label = f"{label[:-1]}, {refusal_pct:.1f}% refused)"
    return label


def _text_color(hex_color: str) -> str:
    """The point's hue, darkened so labels for pale points stay legible."""
    h, lightness, sat = colorsys.rgb_to_hls(*to_rgb(hex_color))
    return to_hex(colorsys.hls_to_rgb(h, min(lightness, 0.38), max(sat, 0.45)))


def main() -> None:
    _apply_brand_style()
    # Single bundled per-rep TSV with truth + is_match denormalized.
    reps_df = _fetch_tsv(DATA_TSV)
    reps_df["is_match"] = reps_df["is_match"].astype(int)
    # Refused calls carry no verdict; report their rate and score the cell on
    # the calls the model answered.
    refused = reps_df.get("refused", pd.Series(0, index=reps_df.index)).fillna(0).astype(int)
    refusal_pct = (refused.groupby([reps_df["model"], reps_df["prompt_variant"]]).mean() * 100).to_dict()
    reps_df = reps_df[refused == 0]
    # Mean-of-replicate accuracy per (model, variant) — matches the 3
    # bar figures. Equivalent to mean-of-cells-of-mean-of-reps.
    rep_mean_acc = (
        reps_df.groupby(["model", "prompt_variant", "replicate"])["is_match"]
        .mean().reset_index()
        .groupby(["model", "prompt_variant"])["is_match"].mean().to_dict()
    )

    cells = []
    for (model, variant), grp in reps_df.groupby(["model", "prompt_variant"], sort=False):
        if (model, variant) not in CELL_LABEL:
            continue
        cells.append({
            "model": model,
            "variant": variant,
            "label": _label(model, variant, refusal_pct.get((model, variant), 0.0)),
            "color": CELL_COLOR[(model, variant)],
            "accuracy": rep_mean_acc.get((model, variant), grp["is_match"].mean()),
            "cost_whole_genome_usd": _whole_genome_cost(grp),
        })
    df = pd.DataFrame(cells).sort_values("cost_whole_genome_usd").reset_index(drop=True)

    fig, ax = plt.subplots(figsize=(9.5, 6))
    for _, row in df.iterrows():
        x = row["cost_whole_genome_usd"]
        y = row["accuracy"] * 100
        ax.scatter(
            x, y,
            s=180, c=row["color"], edgecolor=BRAND_INK, linewidth=0.8, zorder=3,
        )
        dx, dy = CELL_LABEL_OFFSET.get((row["model"], row["variant"]), (9, 0))
        # Labels are vertically centered on their anchor and grow away from
        # the point (left-anchored when dx > 0); the leader starts at the
        # dot's rim so it never crosses the marker.
        arrowprops = (
            dict(arrowstyle="-", color=BRAND_NEUTRAL,
                 linewidth=0.6, alpha=0.8, shrinkA=2, shrinkB=7.5,
                 # Attach to the label's near edge, not its center, so a
                 # leader to a long label doesn't cut across other points.
                 relpos=(0, 0.5) if dx >= 0 else (1, 0.5))
            if (dx * dx + dy * dy) ** 0.5 >= 18 else None
        )
        ax.annotate(
            row["label"], (x, y),
            xytext=(dx, dy), textcoords="offset points",
            ha="left" if dx >= 0 else "right", va="center",
            fontsize=9.75, color=_text_color(row["color"]),
            arrowprops=arrowprops,
        )
    ax.set_xscale("log")
    ax.set_xlabel("$ / whole-genome triage pass (19,324 genes, 1 replicate)")
    ax.set_ylabel("Verdict accuracy on\n147-gene bench (%)")
    ymin = min(c["accuracy"] for c in cells) * 100
    ax.set_ylim(max(78, ymin - 2), 100)
    legend_handles = [
        Line2D([0], [0], marker="o", linestyle="", markersize=11, markerfacecolor=color,
               markeredgecolor=BRAND_INK, label=label)
        for label, color in GENERATION_LEGEND
    ]
    ax.legend(
        handles=legend_handles, loc="lower left", fontsize=10, title_fontsize=10.5,
        alignment="left",
        title="Color: model generation (darker = larger model / more context).\n"
              "Refused calls are excluded from accuracy; refusal rate is labeled.",
    )
    sns.despine(ax=ax, top=True, right=True)

    out_pdf = Path("benchmark_cost_vs_accuracy.pdf")
    out_png = Path("benchmark_cost_vs_accuracy.png")
    fig.savefig(out_pdf, bbox_inches="tight", metadata={"Subject": GIST_URL})
    fig.savefig(out_png, bbox_inches="tight", dpi=600, metadata={"Source": GIST_URL})
    print(f"Wrote {out_pdf} + {out_png} ({len(df)} cells)")


if __name__ == "__main__":
    main()
