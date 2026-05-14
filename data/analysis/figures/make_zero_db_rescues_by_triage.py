# /// script
# requires-python = ">=3.11"
# dependencies = [
#   "matplotlib>=3.9",
#   "seaborn>=0.13",
#   "httpx>=0.27",
# ]
# ///
"""Reproduce ``zero_db_rescues_by_triage.{pdf,png}`` from the public catalog.

Whole-genome view of zero-DB rescues: genes where no classical surface
DB (UniProt / GO CC / HPA / SURFY / CSPA) voted yes, yet the Sonnet+NCBI
triage agent voted `yes` (definite surface) or `contextual` (state/lineage
dependent). Two grouped bar panels on a shared y-axis: per-reason counts
within each verdict bucket. Beneath each panel, hand-picked select gene
callouts illustrate the kind of biology the triage agent surfaces.

Data: fetched live from ``https://api.deliverome.org/surfaceome/v1/catalog``
(19,324 protein-coding human genes with per-gene `db` vote count + canonical
Sonnet+NCBI `verdict` and `reason`).

Visual styling matches the in-repo ``_plotting_config`` (Deliverome
categorical palette + Manrope-when-available). Inlined so the gist runs
standalone.

Standalone — ``uv run make_zero_db_rescues_by_triage.py``.
"""
from __future__ import annotations

from collections import Counter, defaultdict
from pathlib import Path

import httpx
import matplotlib.font_manager as fm
import matplotlib.gridspec as gridspec
import matplotlib.pyplot as plt
import seaborn as sns

CATALOG_URL = "https://api.deliverome.org/surfaceome/v1/catalog"

# Published reproduction gist (embedded into output PNG Source / PDF
# Subject metadata — mirrors save_figure in _plotting_config.py).
GIST_URL = "https://gist.github.com/beccajcarlson/a4526c9e6de5e958826bf1d764744c1b"

# ──── Inline brand styling — sentinel: brand-style-v1 ────
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
            for ttf in sorted(fonts_dir.glob("*.ttf")):
                try:
                    fm.fontManager.addfont(str(ttf))
                except Exception:  # noqa: BLE001
                    continue
            return


def _apply_brand_style() -> None:
    """Inline equivalent of `setup_plotting_style`. Sentinel: brand-style-v1."""
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
        "font.size": 17,
        "axes.labelsize": 19,
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


# Reason taxonomy per verdict bucket (matches the triage agent's closed enum).
YES_REASONS = [
    "classical_surface_receptor",
    "multipass_with_exposed_loops",
    "gpi_anchored",
    "stable_complex_partner",
    "other",
]
CONTEXTUAL_REASONS = [
    "dual_localization",
    "tissue_restricted_surface",
    "stable_surface_attachment",
    "cell_state_induced",
    "lysosomal_exocytosis",
    "other",
]
REASON_LABEL = {
    "classical_surface_receptor":   "classical\nsurface\nreceptor",
    "multipass_with_exposed_loops": "multipass\nw/ exposed\nloops",
    "gpi_anchored":                 "GPI-\nanchored",
    "stable_complex_partner":       "stable\ncomplex\npartner",
    "dual_localization":            "dual\nlocalization",
    "tissue_restricted_surface":    "tissue-\nrestricted\nsurface",
    "stable_surface_attachment":    "stable\nsurface\nattachment",
    "cell_state_induced":           "cell-state\ninduced",
    "lysosomal_exocytosis":         "lysosomal\nexocytosis",
    "other":                        "other",
}

# Sequential green ramp for yes (definite surface); amber ramp for contextual
# (state / lineage / partner dependent). `other` neutral grey.
YES_PALETTE = {
    "classical_surface_receptor":   "#2E7A55",
    "multipass_with_exposed_loops": "#4D8A80",
    "gpi_anchored":                 "#7AAB9F",
    "stable_complex_partner":       "#A8C8C0",
    "other":                        "#6F5D5A",
}
CONTEXTUAL_PALETTE = {
    "dual_localization":            "#8C4210",
    "tissue_restricted_surface":    "#C07830",
    "stable_surface_attachment":    "#F4AA28",
    "cell_state_induced":           "#F4C070",
    "lysosomal_exocytosis":         "#FAECD4",
    "other":                        "#6F5D5A",
}

YES_HEADER_COLOR = "#2E7A55"
CONTEXTUAL_HEADER_COLOR = "#8C4210"

YES_CALLOUTS = [
    ("PVRIG",   "NK/T checkpoint; COM701 = anti-PVRIG surface mAb", "classical_surface_receptor"),
    ("STEAP1",  "Prostate ADC + BiTE target",          "multipass_with_exposed_loops"),
    ("CRIPTO",  "GPI-anchored oncofetal antigen",      "gpi_anchored"),
    ("ORAI2",   "Store-operated Ca2+ channel",         "multipass_with_exposed_loops"),
    ("ECEL1",   "Type-II TM; neprilysin/M13 family",   "classical_surface_receptor"),
    ("LY96",    "MD-2 — TLR4 co-receptor",             "stable_complex_partner"),
]
CONTEXTUAL_CALLOUTS = [
    ("GSDMD",   "Gasdermin D/E/C — pyroptosis pores",  "cell_state_induced"),
    ("HSPA1A",  "Surface Hsp70; cmHsp70.1 mAb",        "cell_state_induced"),
    ("HSP90B1", "Surface GRP94 in tumor cells",        "cell_state_induced"),
    ("TIMP2",   "MT1-MMP ternary complex",             "stable_surface_attachment"),
    ("HPSE",    "Surface heparanase on activated platelets / tumor cells",
                                                       "lysosomal_exocytosis"),
    ("IL15",    "Surface trans-presentation via IL-15Rα", "dual_localization"),
]


def _fetch_catalog() -> list[dict]:
    print(f"Fetching {CATALOG_URL} ...")
    r = httpx.get(CATALOG_URL, timeout=60.0)
    r.raise_for_status()
    return r.json()["rows"]


def _draw_reason_bars(ax, counts, reasons, palette, header_label, header_color, y_max):
    visible = [r for r in reasons if counts.get(r, 0) > 0]
    n_bars = len(visible)
    x_positions = list(range(n_bars))
    heights = [counts[r] for r in visible]
    colors = [palette[r] for r in visible]

    BAR_SPACING = 1.4
    x_positions = [x * BAR_SPACING for x in x_positions]
    ax.bar(
        x_positions, heights,
        color=colors, edgecolor="white",
        linewidth=1.2, width=0.55 * BAR_SPACING,
    )

    for x, h in zip(x_positions, heights, strict=True):
        ax.text(
            x, h + y_max * 0.015,
            f"{h}",
            ha="center", va="bottom",
            fontsize=20, fontweight="bold", color=header_color,
        )

    ax.set_title(
        header_label,
        fontsize=20, color=header_color, fontweight="bold",
        loc="left", pad=16,
    )
    ax.set_xticks(x_positions)
    ax.set_xticklabels(
        [REASON_LABEL[r] for r in visible],
        fontsize=15, color=BRAND_INK,
    )
    ax.tick_params(axis="y", labelsize=16)
    ax.set_xlim(-0.9, x_positions[-1] + 0.9)
    sns.despine(ax=ax, top=True, right=True)


def _draw_callouts(ax, callouts, palette, title):
    ax.set_axis_off()
    ax.text(
        0.0, 1.0, title,
        transform=ax.transAxes, ha="left", va="top",
        fontsize=19, color=BRAND_NEUTRAL, fontweight="bold",
    )
    y0 = 0.82
    n = len(callouts)
    row_h = (y0 - 0.05) / max(n - 1, 1) if n > 1 else 0.0
    row_h = min(row_h, 0.155)
    for i, (symbol, desc, reason) in enumerate(callouts):
        y = y0 - i * row_h
        ax.scatter(
            [0.025], [y],
            marker="s", s=260,
            color=palette.get(reason, BRAND_NEUTRAL),
            edgecolor="none", transform=ax.transAxes, zorder=10,
        )
        ax.text(
            0.07, y, symbol,
            transform=ax.transAxes, ha="left", va="center",
            fontsize=19, fontweight="bold", color=BRAND_INK,
        )
        ax.text(
            0.28, y, f"— {desc}",
            transform=ax.transAxes, ha="left", va="center",
            fontsize=16, color=BRAND_NEUTRAL,
        )


def main() -> None:
    _apply_brand_style()

    rows = _fetch_catalog()
    print(f"  fetched {len(rows):,} rows")

    zero_db = [r for r in rows if r.get("db", 0) == 0]
    print(f"\nZero-DB universe: {len(zero_db):,} / {len(rows):,} "
          f"({100*len(zero_db)/len(rows):.1f}%)")

    def verdict_reason(row):
        t = row.get("triage") or {}
        return (t.get("verdict") or "unknown"), (t.get("reason") or "other")

    yes_counts: Counter = Counter()
    ctx_counts: Counter = Counter()
    yes_symbols: dict[str, list[str]] = defaultdict(list)
    ctx_symbols: dict[str, list[str]] = defaultdict(list)
    for r in zero_db:
        v, reason = verdict_reason(r)
        sym = r.get("symbol", "")
        if v == "yes":
            yes_counts[reason] += 1
            yes_symbols[reason].append(sym)
        elif v == "contextual":
            ctx_counts[reason] += 1
            ctx_symbols[reason].append(sym)

    n_yes = sum(yes_counts.values())
    n_ctx = sum(ctx_counts.values())
    print(f"\nRescues: yes={n_yes}, contextual={n_ctx}")

    # Validate callouts.
    bad = []
    for sym, _, reason in YES_CALLOUTS:
        if sym not in yes_symbols.get(reason, []):
            bad.append(("yes", sym, reason))
    for sym, _, reason in CONTEXTUAL_CALLOUTS:
        if sym not in ctx_symbols.get(reason, []):
            bad.append(("contextual", sym, reason))
    if bad:
        raise RuntimeError(f"Callouts not found in rescue slice: {bad}")

    fig = plt.figure(figsize=(19, 11))
    gs = gridspec.GridSpec(
        2, 2, figure=fig,
        height_ratios=[2.2, 1.05],
        width_ratios=[1.0, 1.5],
        hspace=0.20, wspace=0.10,
        top=0.92, bottom=0.04, left=0.06, right=0.97,
    )
    ax_yes = fig.add_subplot(gs[0, 0])
    ax_ctx = fig.add_subplot(gs[0, 1], sharey=ax_yes)
    ax_callouts_yes = fig.add_subplot(gs[1, 0])
    ax_callouts_ctx = fig.add_subplot(gs[1, 1])

    max_count = max(
        max(yes_counts.values(), default=0),
        max(ctx_counts.values(), default=0),
    )
    y_max = max_count * 1.18
    ax_yes.set_ylim(0, y_max)

    _draw_reason_bars(
        ax_yes, yes_counts, YES_REASONS, YES_PALETTE,
        header_label=f"yes — definite surface  (n = {n_yes})",
        header_color=YES_HEADER_COLOR, y_max=y_max,
    )
    _draw_reason_bars(
        ax_ctx, ctx_counts, CONTEXTUAL_REASONS, CONTEXTUAL_PALETTE,
        header_label=f"contextual — state / lineage dependent  (n = {n_ctx})",
        header_color=CONTEXTUAL_HEADER_COLOR, y_max=y_max,
    )

    ax_yes.set_ylabel("Genes rescued from zero-DB universe", fontsize=20)
    ax_yes.tick_params(axis="y", labelsize=16)
    plt.setp(ax_ctx.get_yticklabels(), visible=False)

    _draw_callouts(ax_callouts_yes, YES_CALLOUTS, YES_PALETTE, title="Select yes rescues")
    _draw_callouts(ax_callouts_ctx, CONTEXTUAL_CALLOUTS, CONTEXTUAL_PALETTE, title="Select contextual rescues")

    out_pdf = Path("zero_db_rescues_by_triage.pdf")
    out_png = Path("zero_db_rescues_by_triage.png")
    fig.savefig(out_pdf, bbox_inches="tight", metadata={"Subject": GIST_URL})
    fig.savefig(out_png, bbox_inches="tight", dpi=300, metadata={"Source": GIST_URL})
    print(f"Wrote {out_pdf} + {out_png}")


if __name__ == "__main__":
    main()
