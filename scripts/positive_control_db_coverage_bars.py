"""Render `positive_control_db_coverage_bars.{pdf,png}`.

Three-panel bar chart: per-database coverage of the three positive-control
target lists (ADC / TCE / ViralZone). One bar per source (Sonnet + 5 DBs),
canonical performance-ranked axis order and project palette.

# Reproduction: https://gist.github.com/beccajcarlson/PENDING-positive-control

Run:

    uv run python scripts/positive_control_db_coverage_bars.py
"""

from __future__ import annotations

from pathlib import Path

import matplotlib.pyplot as plt
import pandas as pd
import seaborn as sns

from accessible_surfaceome.audit._plotting_config import save_figure, setup_plotting_style


REPO_ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = REPO_ROOT / "data/processed/positive_controls"
OUT_DIR = REPO_ROOT / "data/analysis/figures"
OUT_DIR.mkdir(parents=True, exist_ok=True)

# Canonical DB axis order — performance-ranked, Sonnet first as implicit reference.
# See ~/.claude/.../memory/canonical_db_palette.md.
DB_ORDER = ["Sonnet", "UniProt", "SURFY", "CSPA", "GO", "HPA"]

# Canonical hex matches scripts/audit_db_vs_sonnet_inclusion.py:1213 +
# data/analysis/figures/make_db_correctness_by_class.py so a reader scanning
# across figures sees the same color for the same source.
DB_COLOR = {
    "Sonnet":  "#d87851",  # Claude-orange (implicit reference)
    "UniProt": "#BC3C4C",  # maroon-light
    "GO":      "#3D6B60",  # teal-mid
    "HPA":     "#F4AA28",  # amber-bright
    "SURFY":   "#8878C8",  # lavender-bright
    "CSPA":    "#6E1428",  # maroon-dark
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

# Column-name mapping from indicator-TSV flag → display label
DB_FLAG_COL = {
    "UniProt": "uniprot_flag",
    "GO":      "go_flag",
    "HPA":     "hpa_flag",
    "SURFY":   "surfy_flag",
    "CSPA":    "cspa_flag",
    "Sonnet":  "sonnet_ncbi_dual_flag",
}

CATEGORIES = [
    ("ADC", "ADC targets\n(TheraSAbDab ∪ Open Targets)"),
    ("TCE", "TCE targets\n(TheraSAbDab CD3-bispecific + BiTE/DART)"),
    ("VZ",  "ViralZone\nhuman entry receptors"),
]

GIST_URL = "https://gist.github.com/beccajcarlson/PENDING-positive-control"


def _smart_yticks(n_total: int) -> list[int]:
    """Return 4-6 yticks ending exactly at ``n_total``.

    Picks a 'nice' step (1, 2, 5, 10, 20, 25, 50, 100, 200, 500) such that
    the axis carries at most ~5 intermediate ticks, then appends ``n_total``
    as the topmost tick. If the second-to-last tick lands within half a step
    of ``n_total`` (e.g. 60 next to 62), it's dropped to avoid crowding.

    Why this exists: matplotlib's auto-tick locator selects ticks at round
    numbers that can exceed ``n_total`` (e.g. an 80 tick for n_total=62),
    which visually implies the bar count can exceed the universe size and
    confuses readers. Capping the topmost tick at ``n_total`` removes the
    ambiguity.
    """
    candidates = [1, 2, 5, 10, 20, 25, 50, 100, 200, 500]
    step = next(s for s in candidates if n_total / s <= 5)
    ticks = list(range(0, n_total, step)) + [n_total]
    while len(ticks) >= 2 and (ticks[-1] - ticks[-2]) < step * 0.5:
        ticks = ticks[:-2] + [n_total]
    return sorted(set(ticks))


def build_tidy() -> pd.DataFrame:
    records = []
    for slug, _ in CATEGORIES:
        df = pd.read_csv(DATA_DIR / f"positive_control_{slug}.tsv", sep="\t")
        n_total = len(df)
        for db in DB_ORDER:
            col = DB_FLAG_COL[db]
            n = int(df[col].astype(int).sum())
            records.append(
                {"category": slug, "db": db, "n": n, "pct": n / n_total * 100, "n_total": n_total}
            )
    return pd.DataFrame(records)


def render(df_tidy: pd.DataFrame) -> None:
    setup_plotting_style(font_scale=1.0)
    # Layout-fingerprint settings kept in lockstep with the gist mirror
    # (data/analysis/figures/make_positive_control_db_coverage_bars.py) so
    # tests/test_figure_canonical_mirror_sync.py doesn't flag drift.
    plt.rcParams.update({
        "font.size":       14,
        "axes.labelsize":  14,
        "xtick.labelsize": 14,
        "ytick.labelsize": 14,
        "legend.fontsize": 14,
    })
    fig, axes = plt.subplots(1, 3, figsize=(17, 6), sharey=False)

    for ax, (slug, panel_title) in zip(axes, CATEGORIES):
        sub = df_tidy[df_tidy["category"] == slug]
        n_total = int(sub["n_total"].iloc[0])
        bar_colors = [DB_COLOR[db] for db in DB_ORDER]

        sns.barplot(
            data=sub, x="db", y="n",
            order=DB_ORDER, hue="db", palette=bar_colors,
            legend=False, ax=ax, edgecolor="none",
        )
        # Three-row stacked text above each bar: spelled-out DB title (bold,
        # in the bar's color) → count (semibold) → percentage (regular).
        # Keeps each column identifiable when the figure is shrunk.
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
        # Extra headroom now (1.32×) because each bar carries three lines of text.
        ax.set_ylim(0, n_total * 1.32)
        # Cap y-ticks at n_total so no displayed value exceeds the universe size.
        ax.set_yticks(_smart_yticks(n_total))
        sns.despine(ax=ax, top=True, right=True)
        # X-ticks now redundant with the spelled-out titles — hide them.
        ax.set_xticks([])

    for ax, letter in zip(axes, "abc"):
        ax.text(
            -0.12, 1.07, letter, transform=ax.transAxes,
            fontsize=22, fontweight=800, family="Manrope",
            ha="left", va="bottom",
        )

    plt.tight_layout()
    save_figure(
        fig, "positive_control_db_coverage_bars", OUT_DIR,
        formats=("pdf", "png"), gist_url=GIST_URL,
    )
    plt.close(fig)
    print(f"Wrote {OUT_DIR / 'positive_control_db_coverage_bars.pdf'} (+ .png)")


def main() -> None:
    df = build_tidy()
    print(df.to_string())
    render(df)


if __name__ == "__main__":
    main()
