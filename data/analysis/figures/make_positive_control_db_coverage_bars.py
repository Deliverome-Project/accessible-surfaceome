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
GIST_URL = "https://gist.github.com/beccajcarlson/PENDING-positive-control"

# Input TSVs — augmented indicator tables keyed on hgnc_id.
ADC_TSV = f"{BASE}/data/processed/positive_controls/positive_control_ADC.tsv"
TCE_TSV = f"{BASE}/data/processed/positive_controls/positive_control_TCE.tsv"
VZ_TSV  = f"{BASE}/data/processed/positive_controls/positive_control_VZ.tsv"

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
    "Sonnet":  "sonnet_ncbi_dual_flag",
}

CATEGORIES = [
    (ADC_TSV, "ADC", "ADC targets\n(TheraSAbDab ∪ Open Targets)"),
    (TCE_TSV, "TCE", "TCE targets\n(TheraSAbDab CD3-bispecific + BiTE/DART)"),
    (VZ_TSV,  "VZ",  "ViralZone\nhuman entry receptors"),
]


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
    records = []
    for url, slug, _ in CATEGORIES:
        df = _fetch_tsv(url)
        n_total = len(df)
        for db in DB_ORDER:
            col = DB_FLAG_COL[db]
            n = int(df[col].astype(int).sum())
            records.append(
                {"category": slug, "db": db, "n": n, "pct": n / n_total * 100, "n_total": n_total}
            )
    return pd.DataFrame(records)


def render(df_tidy: pd.DataFrame, out_dir: Path) -> Path:
    _apply_brand_style()
    fig, axes = plt.subplots(1, 3, figsize=(17, 6), sharey=False)

    for ax, (_, slug, panel_title) in zip(axes, CATEGORIES):
        sub = df_tidy[df_tidy["category"] == slug]
        n_total = int(sub["n_total"].iloc[0])
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

        ax.set_title(f"{panel_title}\n(n = {n_total} targets)", fontsize=12, weight="bold", pad=14)
        ax.set_ylabel("Targets\nrepresented", fontsize=13, weight="medium")
        ax.set_xlabel("")
        # Extra headroom (1.32×) because each bar carries three lines of text.
        ax.set_ylim(0, n_total * 1.32)
        # Cap y-ticks at n_total so no displayed value exceeds the universe size.
        ax.set_yticks(_smart_yticks(n_total))
        sns.despine(ax=ax, top=True, right=True)
        ax.set_xticks([])

    for ax, letter in zip(axes, "abc"):
        ax.text(
            -0.12, 1.07, letter, transform=ax.transAxes,
            fontsize=22, fontweight=800, family="Manrope",
            ha="left", va="bottom",
        )

    plt.tight_layout()
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
