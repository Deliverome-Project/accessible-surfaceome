# /// script
# requires-python = ">=3.11"
# dependencies = [
#   "matplotlib>=3.9",
#   "pandas>=2.2",
#   "seaborn>=0.13",
#   "httpx>=0.27",
# ]
# ///
"""Reproduce ``positive_control_db_coverage_bars.{pdf,png}`` from the public repo.

Three-panel bar chart: per-database coverage of the three positive-control
target lists (ADC / TCE / ViralZone). One bar per source (Sonnet + 5 DBs),
canonical performance-ranked axis order and project palette.

Sonnet column = positive in the dual NCBI triage (v1 ∪ v2, verdict yes OR
contextual). PubMed-augmented variant is NOT part of the combined axis.

Standalone — ``uv run make_positive_control_db_coverage_bars.py``.
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

# Published reproduction gist — embedded into the output PNG's Source tEXt
# chunk and PDF's Subject info field. Read back with
# ``exiftool figure.png | grep Source`` or in Python with
# ``Image.open(p).info["Source"]``.
GIST_URL = "https://gist.github.com/beccajcarlson/3ab5df749b576912959c75fe7013d78c"

# Single long-form TSV — one row per (category × gene) with all per-DB flags
# + sonnet_full_flag + adc_source. Replaces the previous 3 per-category TSVs.
LONG_TSV = f"{BASE}/data/processed/positive_controls/positive_control_long.tsv"

# ──── Inline brand styling — sentinel: brand-style-v3 ────
# Mirrors src/accessible_surfaceome/audit/_plotting_config.py so the gist
# stays self-contained.
BRAND_CLAUDE_ORANGE = "#d87851"
BRAND_INK = "#1F1718"
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
    _register_brand_fonts()
    sns.set_style("whitegrid")
    sns.set_context("notebook", font_scale=1.0)
    plt.rcParams.update({
        "savefig.dpi": 600,
        "savefig.bbox": "tight",
        "figure.facecolor": "none",
        "savefig.facecolor": "none",
        "font.family": "sans-serif",
        "font.sans-serif": ["Manrope", "Outfit", "DejaVu Sans", "Liberation Sans", "Arial"],
        "font.weight": "medium",
        "font.size": 14,
        "axes.labelsize": 14,
        "axes.labelweight": "medium",
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
        "xtick.labelsize": 14,
        "ytick.labelsize": 14,
        "xtick.color": BRAND_INK,
        "ytick.color": BRAND_INK,
        "legend.frameon": False,
        "legend.fontsize": 14,
        "patch.edgecolor": "none",
        "patch.linewidth": 0.0,
    })


# Canonical DB axis order — performance-ranked, Sonnet first as implicit reference.
DB_ORDER = ["Sonnet", "UniProt", "SURFY", "CSPA", "GO", "HPA"]

DB_COLOR = {
    "Sonnet":  BRAND_CLAUDE_ORANGE,
    "UniProt": "#BC3C4C",
    "GO":      "#3D6B60",
    "HPA":     "#F4AA28",
    "SURFY":   "#8878C8",
    "CSPA":    "#6E1428",
}

# Spelled-out per-bar titles. Rendered above each bar so the column identity is
# legible without leaning on the rotated x-tick alone.
DB_TITLE = {
    "Sonnet":  "Sonnet 4.6",
    "UniProt": "UniProt",
    "SURFY":   "SURFY",
    "CSPA":    "CSPA",
    "GO":      "GO CC",
    "HPA":     "HPA",
}

DB_FLAG_COL = {
    "UniProt": "uniprot_flag",
    "GO":      "go_flag",
    "HPA":     "hpa_flag",
    "SURFY":   "surfy_flag",
    "CSPA":    "cspa_flag",
    "Sonnet":  "sonnet_full_flag",
}

CATEGORIES = [
    ("ADC", "ADC clinical/preclinical targets\n(TheraSAbDab ∪ Open Targets ∪ ADCdb)"),
    ("TCE", "CD3-bispecific T-cell engager\ntargets (TheraSAbDab)"),
    ("VZ",  "ViralZone human viral\nentry receptors"),
]

# ADC panel only: each bar is stacked by which ADC source contributed the
# target (priority TheraSAbDab > Open Targets > ADCdb). Sequential teal so
# the stacking reads as "darker = more rigorously curated source, lighter
# = broader catalog."
ADC_SOURCE_ORDER = ["TheraSAbDab", "Open Targets", "ADCdb"]
ADC_SOURCE_COLOR = {
    "TheraSAbDab":  "#244840",
    "Open Targets": "#4D8A80",
    "ADCdb":        "#7AAB9F",
}

LONG_TSV = f"{BASE}/data/processed/positive_controls/positive_control_long.tsv"


def _fetch_tsv(url: str) -> pd.DataFrame:
    """Sibling-first: when run from a published gist, the TSV is bundled
    next to this script. Falls back to the raw URL otherwise."""
    sibling = Path(__file__).parent / Path(url).name
    if sibling.is_file():
        return pd.read_csv(sibling, sep="\t")
    r = httpx.get(url, timeout=30)
    r.raise_for_status()
    return pd.read_csv(io.StringIO(r.text), sep="\t")


def _smart_yticks(n_total: int) -> list[int]:
    """Cap y-ticks at ``n_total`` so no displayed tick value exceeds the
    universe size. Picks a 'nice' step (1, 2, 5, 10, 20, 25, 50, 100, 200,
    500) targeting ~5 intermediate ticks, then appends ``n_total``; drops
    the second-to-last tick if it lands within half a step of ``n_total``."""
    candidates = [1, 2, 5, 10, 20, 25, 50, 100, 200, 500]
    step = next(s for s in candidates if n_total / s <= 5)
    ticks = list(range(0, n_total, step)) + [n_total]
    while len(ticks) >= 2 and (ticks[-1] - ticks[-2]) < step * 0.5:
        ticks = ticks[:-2] + [n_total]
    return sorted(set(ticks))


def _embed_source_in_metadata(out_path: Path, url: str) -> None:
    """Write the gist URL into the PNG's Source tEXt chunk + PDF's
    Subject info field so the URL travels with the file."""
    if out_path.suffix == ".png":
        try:
            from PIL import Image, PngImagePlugin
            img = Image.open(out_path)
            meta = PngImagePlugin.PngInfo()
            for k, v in img.info.items():
                if isinstance(v, (str, bytes)):
                    meta.add_text(k, v if isinstance(v, str) else v.decode("latin-1", "ignore"))
            meta.add_text("Source", url)
            img.save(out_path, "PNG", pnginfo=meta)
        except Exception:  # noqa: BLE001 — best-effort
            pass


def build_tidy() -> pd.DataFrame:
    """Aggregate per-(category, source) counts from the single long-form TSV."""
    long = _fetch_tsv(LONG_TSV)
    records = []
    for slug, _ in CATEGORIES:
        sub = long[long["category"] == slug]
        n_total = len(sub)
        for db in DB_ORDER:
            col = DB_FLAG_COL[db]
            n = int(sub[col].astype(int).sum())
            records.append(
                {"category": slug, "db": db, "n": n, "pct": n / n_total * 100, "n_total": n_total}
            )
    return pd.DataFrame(records)


def render(df_tidy: pd.DataFrame, out_dir: Path) -> Path:
    _apply_brand_style()
    fig, axes = plt.subplots(1, 3, figsize=(17, 6), sharey=False)

    long = _fetch_tsv(LONG_TSV)

    # Per-category Sonnet misses (gene names where sonnet_full_flag=0). With
    # Sonnet ≥98% per category there's 0-1 miss per panel — annotate inline
    # to make the figure self-explanatory.
    misses_per_category: dict[str, list[str]] = {}
    for cat in long["category"].unique():
        sub = long[long["category"] == cat]
        missed = sub[sub["sonnet_full_flag"] == 0]["hgnc_symbol"].tolist()
        misses_per_category[cat] = sorted(missed)

    for ax, (slug, panel_title) in zip(axes, CATEGORIES):
        sub = df_tidy[df_tidy["category"] == slug]
        n_total = int(sub["n_total"].iloc[0])

        if slug == "ADC":
            adc = long[long["category"] == "ADC"]
            for i, db in enumerate(DB_ORDER):
                col = DB_FLAG_COL[db]
                in_db = adc[adc[col].astype(int) == 1]
                bottom = 0
                for src in ADC_SOURCE_ORDER:
                    n_seg = int((in_db["adc_source"] == src).sum())
                    if n_seg == 0:
                        continue
                    ax.bar(i, n_seg, bottom=bottom, color=ADC_SOURCE_COLOR[src],
                           edgecolor="none", width=0.8)
                    bottom += n_seg
        else:
            bar_colors = [DB_COLOR[db] for db in DB_ORDER]
            sns.barplot(
                data=sub, x="db", y="n",
                order=DB_ORDER, hue="db", palette=bar_colors,
                legend=False, ax=ax, edgecolor="none",
            )
        # Three-row stacked text above each bar: spelled-out DB title (in the
        # bar's color) → count → percentage. Keeps the column identifiable
        # when the figure is shrunk.
        for i, db in enumerate(DB_ORDER):
            n = int(sub[sub["db"] == db]["n"].iloc[0])
            pct = n / n_total * 100
            label = f"{DB_TITLE[db]}\n{n}\n({pct:.0f}%)"
            ax.text(
                i, n + n_total * 0.025, label,
                ha="center", va="bottom", fontsize=10,
                color=DB_COLOR[db], weight="semibold", linespacing=1.25,
            )

        # Annotate the Sonnet bar with the gene name(s) Sonnet missed.
        # Rotated 90° to fit the narrow column.
        missed = misses_per_category.get(slug, [])
        if missed:
            sonnet_idx = DB_ORDER.index("Sonnet")
            sonnet_n = int(sub[sub["db"] == "Sonnet"]["n"].iloc[0])
            ax.text(
                sonnet_idx, sonnet_n - n_total * 0.04,
                f"missed: {', '.join(missed)}",
                ha="center", va="top",
                rotation=90,
                fontsize=10, style="italic",
                color="white", weight="semibold",
            )

        ax._panel_title_text = f"{panel_title}\n(n = {n_total} targets)"
        ax.set_ylabel("Targets\nrepresented", fontsize=13, weight="medium")
        ax.set_xlabel("")
        # Modest headroom (1.18×) over n_total to fit the per-bar text block.
        ax.set_ylim(0, n_total * 1.18)
        # Cap y-ticks at n_total so no displayed value exceeds the universe size.
        ax.set_yticks(_smart_yticks(n_total))
        sns.despine(ax=ax, top=True, right=True)
        ax.set_xticks([])

    # Panel titles + subpanel letters via fig.text — set_title was being
    # clipped by save_figure's bbox-tight cropping.
    fig.canvas.draw()
    for ax, letter in zip(axes, "abc"):
        bbox = ax.get_position()
        fig.text(
            (bbox.x0 + bbox.x1) / 2, bbox.y1 + 0.04,
            getattr(ax, "_panel_title_text", ""),
            fontsize=13, weight="bold",
            ha="center", va="bottom",
        )
        fig.text(
            bbox.x0 - 0.015, bbox.y1 + 0.04,
            letter, fontsize=22, fontweight=800, family="Manrope",
            ha="right", va="bottom",
        )

    # ADC panel legend — explain the 3-source teal stacking
    adc_ax = axes[0]
    legend_handles = [
        plt.Rectangle((0, 0), 1, 1, color=ADC_SOURCE_COLOR[src], label=src)
        for src in ADC_SOURCE_ORDER
    ]
    adc_ax.legend(
        handles=legend_handles, loc="upper right", frameon=False,
        fontsize=10, title="ADC source", title_fontsize=10,
    )

    # Explicit margins instead of tight_layout — reserves headroom for titles.
    plt.subplots_adjust(top=0.78, bottom=0.08, left=0.06, right=0.98, wspace=0.28)
    out_dir.mkdir(parents=True, exist_ok=True)
    pdf = out_dir / "positive_control_db_coverage_bars.pdf"
    png = out_dir / "positive_control_db_coverage_bars.png"
    fig.savefig(pdf, metadata={"Subject": GIST_URL})
    fig.savefig(png, metadata={"Source": GIST_URL})
    _embed_source_in_metadata(png, GIST_URL)
    plt.close(fig)
    return pdf


def main() -> None:
    df = build_tidy()
    print(df.to_string())
    out = render(df, Path.cwd())
    print(f"Wrote {out}")


if __name__ == "__main__":
    main()
