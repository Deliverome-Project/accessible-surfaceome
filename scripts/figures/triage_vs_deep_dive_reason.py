"""Triage → deep-dive comparison, three panels (Supplementary S13).

For each gene that has BOTH a triage record and a deep-dive record, we have the
triage-stage call (from the genome-wide Sonnet triage run) and the deep-dive's
evidence-anchored call. This figure shows how the two relate and — panel a —
whether the deep dive agrees more with Sonnet triage or with the surface
databases.

**Layout.** Panels a and b sit side by side on top, sharing one five-tier
legend beneath them; the reason confusion matrix (panel c) spans the full width
below, with its bucket legend underneath.

**Panel a — database concordance.** Among the genes the *deep dive* calls
surface (tier ``canonical`` / ``likely`` / ``low``), the fraction ALSO flagged
surface by each source: the 5 catalog databases (UniProt, GO, SURFY, CSPA, HPA)
plus Sonnet triage (verdict ``yes`` / ``contextual``), broken down by
deep-dive tier. Every source flags a larger share of canonical genes than
likely, and more likely than low. Sonnet triage is the most concordant source
at every tier (99 / 95 / 91%), and its lead over the best database (UniProt,
94 / 79 / 54%) widens as the deep dive's confidence drops.

**Panel b — verdict flow.** Slim 100%-stacked horizontal bars, one per triage
verdict (``yes`` / ``contextual`` / ``no``), each split by the deep-dive's
5-tier call (``canonical`` / ``likely`` / ``low`` / ``uncertain`` / ``no``,
from ``_dd_assign_bucket``). Reads as: given triage said X, where did the
evidence-anchored deep dive land? Triage-``yes`` genes overwhelmingly confirm
as canonical/likely surface; triage-``no`` genes mostly stay ``no`` but a
minority get rescued up to likely/low; triage-``contextual`` spreads across the
middle tiers.

**Panel c — reason confusion matrix.** The triage reason (rows) against the
deep-dive ``surface_call_reason`` (columns), both drawn from the same closed
``TriageReason`` enum (in ``src/accessible_surfaceome/tools/_shared/models.py``).
The 19 reasons collapse into 3 verdict buckets in ``models.py`` (yes /
contextual / no); the diagonal (highlighted in maroon) is exact reason-level
agreement, thick separators mark the bucket boundaries, and tick labels are
colored by bucket so a cross-bucket flip is visible at a glance.

**Real data.** Built from the per-figure TSV
``data/processed/figures/triage_vs_deep_dive_reason.tsv`` — one row per gene
with both a triage and a deep-dive record (n=5,332), carrying the triage
verdict/reason, the deep-dive reason/tier, and the 5 per-DB surface flags. The
same TSV backs the gist mirror
(``data/analysis/figures/make_triage_vs_deep_dive_reason.py``).

5,332 genes with both calls; 50% land on the reason diagonal. Of the rest,
about 29% are same-bucket relabels and about 71% are cross-bucket flips; the
largest flip block is yes-bucket triage reasons relabeled as contextual by the
deep dive.

Run:
    uv run python scripts/figures/triage_vs_deep_dive_reason.py
"""
from __future__ import annotations

from pathlib import Path

import matplotlib.patches as mpatches
import matplotlib.pyplot as plt
from matplotlib.transforms import offset_copy
import numpy as np
import pandas as pd
import seaborn as sns

from accessible_surfaceome.audit._plotting_config import (
    COLORS,
    save_figure,
    setup_plotting_style,
)

ROOT = Path(__file__).resolve().parents[2]
OUT_DIR = ROOT / "data/analysis/figures"
# Single per-figure TSV: one row per gene with a deep-dive record AND a
# triage hit. Columns: gene_symbol, uniprot_acc, triage_verdict,
# triage_reason, deep_dive_reason, deep_dive_tier, + per-DB surface
# membership (go/surfy/hpa _surface_flag + uniprot/cspa _optimized, 0/1).
# Same file the gist mirror bundles.
DATA_TSV = ROOT / "data/processed/figures/triage_vs_deep_dive_reason.tsv"
SLUG = "triage_vs_deep_dive_reason"

# ── Panel b: triage verdicts (rows/bars) × deep-dive tiers (stack segments) ──
TRIAGE_VERDICT_ORDER = ["yes", "contextual", "no"]
TRIAGE_VERDICT_LABEL = {
    "yes":        "triage: yes",
    "contextual": "triage: contextual",
    "no":         "triage: no",
}
# 5-tier deep-dive spectrum (best → worst) with the canonical tier colors
# shared across every deep-dive figure (see deep_dive_final_categories).
DD_TIER_ORDER = ["canonical", "likely", "low", "uncertain", "no"]
DD_TIER_COLOR = {
    "canonical": "#2E7A55",  # success green — strict tier
    "likely":    "#3D6B60",  # teal-mid — broader tier
    "low":       "#C99A5B",  # amber-tan — low/moderate access, weak evidence
    "uncertain": "#C7BDB6",  # light warm grey — ambiguous
    "no":        "#9C8C88",  # lifted neutral — leaned not-surface
}
DD_TIER_LABEL = {
    "canonical": "canonical",
    "likely":    "likely",
    "low":       "low",
    "uncertain": "uncertain",
    "no":        "no",
}
# Deep-dive tiers that count as a positive "surface call" for panel a.
DD_SURFACE_TIERS = ["canonical", "likely", "low"]
# Panel a groups concordance by these three deep-dive tiers; distinct
# colors so the reader can see whether DB agreement climbs with the
# deep dive's own confidence (canonical > likely > low).
TIER_C_COLOR = {"canonical": "#2E7A55", "likely": "#3D6B60", "low": "#C99A5B"}

# ── Panel a: DB concordance sources ──
# The 5 catalog databases (canonical palette by identity — see the
# canonical-db-palette memory) + Sonnet triage as a peer source, given a
# visually distinct Claude-orange so it doesn't read as a 6th database.
# UniProt/CSPA are recalibrated -> OPTIMIZED membership (uniprot_optimized /
# cspa_optimized); GO/SURFY/HPA were never recalibrated -> native *_surface_flag.
# The native UniProt/CSPA flags are forbidden outside Fig 1
# (test_figures_use_optimized_cutoffs).
DB_SOURCES = [
    ("UniProt", "uniprot_optimized",  "#BC3C4C"),  # maroon-light
    ("GO",      "go_surface_flag",    "#3D6B60"),  # teal-mid
    ("SURFY",   "surfy_surface_flag", "#8878C8"),  # lavender-bright
    ("CSPA",    "cspa_optimized",     "#6E1428"),  # maroon-dark
    ("HPA",     "hpa_surface_flag",   "#F4AA28"),  # amber-bright
]
SONNET_LABEL = "Sonnet triage"
SONNET_COLOR = "#d87851"  # Claude-orange — distinct from the 5 DB bars

# ── Panel c: the shared 19-value TriageReason vocabulary ──
REASONS_ORDERED = [
    # YES bucket
    "classical_surface_receptor",
    "multipass_with_exposed_loops",
    "gpi_anchored",
    "extracellular_face_protein",
    "stable_complex_partner",
    # CONTEXTUAL bucket
    "stable_surface_attachment",
    "cell_state_induced",
    "tissue_restricted_surface",
    "lysosomal_exocytosis",
    "dual_localization",
    # NO bucket
    "cytoplasmic",
    "nuclear",
    "mitochondrial_internal",
    "endomembrane_resident",
    "nuclear_envelope",
    "secreted_only",
    "inner_leaflet_anchored",
    "pmhc_only_intracellular",
    "other",
]
BUCKET = {r: "yes" for r in REASONS_ORDERED[:5]}
BUCKET.update({r: "contextual" for r in REASONS_ORDERED[5:10]})
BUCKET.update({r: "no" for r in REASONS_ORDERED[10:]})
BUCKET_COLOR = {
    "yes":        "#2E7A55",
    "contextual": "#C07830",
    "no":         "#6F5D5A",
}
DIAGONAL_HIGHLIGHT = "#BC3C4C"  # maroon — diagonal border

# Short tick labels (full enum names wrap badly). Two-line breaks
# chosen at natural word boundaries.
LABEL_SHORT = {
    "classical_surface_receptor":   "single-pass",
    "multipass_with_exposed_loops": "multi-pass",
    "gpi_anchored":                 "GPI\nanchored",
    "extracellular_face_protein":   "ECF\nprotein",
    "stable_complex_partner":       "stable cplx\npartner",
    "stable_surface_attachment":    "stable surf\nattachment",
    "cell_state_induced":           "cell-state\ninduced",
    "tissue_restricted_surface":    "tissue\nrestricted",
    "lysosomal_exocytosis":         "lysosomal\nexocytosis",
    "dual_localization":            "dual\nlocalization",
    "cytoplasmic":                  "cytoplasmic",
    "nuclear":                      "nuclear",
    "mitochondrial_internal":       "mito\ninternal",
    "endomembrane_resident":        "endomem\nresident",
    "nuclear_envelope":             "nuclear\nenvelope",
    "secreted_only":                "secreted\nonly",
    "inner_leaflet_anchored":       "inner leaflet\nanchored",
    "pmhc_only_intracellular":      "pMHC\nonly",
    "other":                        "other",
}


def _load_pairs() -> pd.DataFrame:
    """Read the per-figure TSV (triage_verdict, triage_reason,
    deep_dive_reason, deep_dive_tier, 5 per-DB flags) — one row per gene."""
    return pd.read_csv(DATA_TSV, sep="\t")


def _build_matrix(df: pd.DataFrame) -> np.ndarray:
    """Materialise the (triage, deep-dive) reason pairs into an n×n integer
    ndarray, ordered per REASONS_ORDERED on both axes."""
    n = len(REASONS_ORDERED)
    m = np.zeros((n, n), dtype=int)
    idx_of = {r: i for i, r in enumerate(REASONS_ORDERED)}
    for _, row in df.iterrows():
        t = row.get("triage_reason")
        d = row.get("deep_dive_reason")
        if t in idx_of and d in idx_of:
            m[idx_of[t], idx_of[d]] += 1
    return m


def _concordance_by_tier(df: pd.DataFrame) -> list[tuple[str, dict[str, float]]]:
    """Panel a — per source, the % of EACH deep-dive tier's genes the
    source also flags surface. Breaking concordance down by tier shows
    whether DB agreement is higher on the deep dive's higher-confidence
    tiers (canonical) than its weakest (low). Returns
    ``(label, {tier: pct})`` with Sonnet triage first, then the databases
    sorted descending by the canonical-tier pct."""
    out: list[tuple[str, dict[str, float]]] = []
    for label, col, _color in DB_SOURCES:
        by_tier = {}
        for tier in DD_SURFACE_TIERS:
            sub = df[df["deep_dive_tier"] == tier]
            d = len(sub)
            by_tier[tier] = 100.0 * int((sub[col] == 1).sum()) / d if d else 0.0
        out.append((label, by_tier))
    by_tier = {}
    for tier in DD_SURFACE_TIERS:
        sub = df[df["deep_dive_tier"] == tier]
        d = len(sub)
        by_tier[tier] = 100.0 * int(sub["triage_verdict"].isin(["yes", "contextual"]).sum()) / d if d else 0.0
    out.append((SONNET_LABEL, by_tier))
    # Pin Sonnet triage on top (it's the peer non-DB source), then the DBs by
    # canonical-tier concordance descending.
    out.sort(key=lambda r: (r[0] != SONNET_LABEL, -r[1]["canonical"]))
    return out


def _bucket_boundaries() -> list[int]:
    """Return the row/col indices BETWEEN bucket changes (for separator lines)."""
    boundaries: list[int] = []
    prev_bucket = None
    for i, reason in enumerate(REASONS_ORDERED):
        b = BUCKET[reason]
        if prev_bucket is not None and b != prev_bucket:
            boundaries.append(i)
        prev_bucket = b
    return boundaries


def _draw_verdict_flow(ax: plt.Axes, df: pd.DataFrame) -> None:
    """Panel b — slim 100%-stacked horizontal bars: one bar per triage
    verdict, each split by the deep-dive tier composition (fraction), with
    the raw count annotated inside each meaningful segment. Bars are thin
    with whitespace between so the panel reads as an elegant flow strip."""
    ct = pd.crosstab(df["triage_verdict"], df["deep_dive_tier"])
    ct = ct.reindex(index=TRIAGE_VERDICT_ORDER, columns=DD_TIER_ORDER, fill_value=0)
    totals = ct.sum(axis=1)
    frac = ct.div(totals.replace(0, np.nan), axis=0).fillna(0.0)

    bar_h = 0.46  # slim bars — plenty of whitespace between the three
    y_pos = np.arange(len(TRIAGE_VERDICT_ORDER))[::-1]  # yes on top
    for yi, verdict in zip(y_pos, TRIAGE_VERDICT_ORDER):
        left = 0.0
        for tier in DD_TIER_ORDER:
            w = float(frac.loc[verdict, tier])
            if w <= 0:
                continue
            ax.barh(yi, w, left=left, height=bar_h,
                    color=DD_TIER_COLOR[tier], edgecolor="white", linewidth=0.8)
            n = int(ct.loc[verdict, tier])
            if w >= 0.05:  # annotate segments wide enough to hold a label
                txt_color = "white" if tier in ("canonical", "likely") else COLORS["dark"]
                # Narrow segments carry the % only; "(n)" would spill over.
                lab = f"{w * 100:.0f}%\n({n})" if w >= 0.08 else f"{w * 100:.0f}%"
                ax.text(left + w / 2, yi, lab,
                        ha="center", va="center", fontsize=14.6,
                        color=txt_color, fontweight="semibold")
            left += w

    ax.set_yticks(y_pos)
    ax.set_yticklabels([f"{TRIAGE_VERDICT_LABEL[v]}\n(n={int(totals[v])})"
                        for v in TRIAGE_VERDICT_ORDER])
    ax.set_ylim(-0.6, len(TRIAGE_VERDICT_ORDER) - 0.4)
    ax.set_xlim(0, 1)
    ax.set_xticks([0, 0.25, 0.5, 0.75, 1.0])
    ax.set_xticklabels(["0", "25", "50", "75", "100%"])
    ax.set_xlabel("Deep-dive tier composition (per triage verdict)")
    ax.set_title("Verdict flow: triage call → deep-dive tier",
                 fontsize=16, fontweight="semibold", pad=12)

    handles = [mpatches.Patch(facecolor=DD_TIER_COLOR[t], edgecolor="none",
                              label=DD_TIER_LABEL[t]) for t in DD_TIER_ORDER]
    # Centred under BOTH top panels (x=-0.16 in this axes' coords): panel
    # a uses the same tier colours, so this one legend serves a and b.
    ax.legend(handles=handles, title="deep-dive tier", loc="upper center",
              bbox_to_anchor=(-0.16, -0.21), ncols=5, frameon=False,
              title_fontsize=18)
    sns.despine(ax=ax, top=True, right=True)


def _draw_concordance_by_tier(
    ax: plt.Axes, rows: list[tuple[str, dict[str, float]]]
) -> None:
    """Panel a — DB concordance broken down by deep-dive tier: one group
    per source, 3 tier-colored bars (canonical / likely / low), showing
    the % of each tier's genes that source also flags. If DB agreement
    tracks the deep dive's confidence, the canonical bar sits above low
    within each source group."""
    n = len(rows)
    y_base = np.arange(n)[::-1]
    bar_h = 0.26
    offsets = {"canonical": +bar_h, "likely": 0.0, "low": -bar_h}
    for yb, (label, by_tier) in zip(y_base, rows):
        for tier in DD_SURFACE_TIERS:
            pct = by_tier[tier]
            ax.barh(yb + offsets[tier], pct, height=bar_h * 0.92,
                    color=TIER_C_COLOR[tier], edgecolor="white", linewidth=0.5)
            ax.text(pct + 1.2, yb + offsets[tier], f"{pct:.0f}", va="center",
                    ha="left", fontsize=14.6, color=COLORS["dark"])
    ax.set_yticks(y_base)
    ax.set_yticklabels([r[0] for r in rows])
    ax.set_ylim(-0.6, n - 0.4)
    ax.set_xlim(0, 108)
    ax.set_xticks([0, 25, 50, 75, 100])
    ax.set_xticklabels(["0", "25", "50", "75", "100%"])
    ax.set_xlabel("% of each deep-dive tier's genes\nthe source also flags")
    ax.set_title("Database concordance: does the deep dive agree with "
                 "Sonnet or the DBs?",
                 fontsize=16, fontweight="semibold", pad=12)
    # No legend of its own: tier colours are identical to panel b's, whose
    # five-tier legend is centred under both panels (two legends collided).
    sns.despine(ax=ax, top=True, right=True)


def _draw_reason_matrix(ax: plt.Axes, m: np.ndarray, cbar_ax: plt.Axes) -> None:
    """Panel c — the 19×19 triage × deep-dive reason confusion matrix."""
    n = m.shape[0]
    cmap = sns.light_palette("#3D6B60", as_cmap=True)
    sns.heatmap(
        m, ax=ax, cmap=cmap, square=True, linewidths=0.5, linecolor="#FFFFFF",
        annot=True, fmt="d", annot_kws={"fontsize": 14.6, "color": "#1F1718"},
        cbar_ax=cbar_ax, cbar_kws={"label": "genes"},
        # Single-line labels: two-line ones overlap at the cell pitch.
        xticklabels=[LABEL_SHORT[r].replace("\n", " ") for r in REASONS_ORDERED],
        yticklabels=[LABEL_SHORT[r].replace("\n", " ") for r in REASONS_ORDERED],
    )
    for tick, reason in zip(ax.get_xticklabels(), REASONS_ORDERED, strict=True):
        tick.set_color(BUCKET_COLOR[BUCKET[reason]])
        tick.set_fontweight("semibold")
    for tick, reason in zip(ax.get_yticklabels(), REASONS_ORDERED, strict=True):
        tick.set_color(BUCKET_COLOR[BUCKET[reason]])
        tick.set_fontweight("semibold")
    ax.tick_params(axis="x", rotation=45, pad=4)
    plt.setp(ax.get_xticklabels(), ha="right", rotation_mode="anchor")
    ax.tick_params(axis="y", rotation=0, pad=4)

    for b in _bucket_boundaries():
        ax.axhline(b, color="#1F1718", lw=2.0, alpha=0.85)
        ax.axvline(b, color="#1F1718", lw=2.0, alpha=0.85)
    for i in range(n):
        ax.add_patch(mpatches.Rectangle(
            (i, i), 1, 1, fill=False, edgecolor=DIAGONAL_HIGHLIGHT,
            lw=2.5, zorder=10,
        ))
    ax.set_xlabel("Deep-dive surface_call_reason", labelpad=10)
    ax.set_ylabel("Triage\nsurface_call_reason", labelpad=10)
    ax.set_title("Reason confusion: triage reason × deep-dive reason",
                 fontsize=16, fontweight="semibold", pad=12)

    handles = [
        mpatches.Patch(facecolor=BUCKET_COLOR[b], edgecolor="none",
                       label=f"{b}-bucket reasons")
        for b in ("yes", "contextual", "no")
    ]
    handles.append(
        mpatches.Patch(facecolor="none", edgecolor=DIAGONAL_HIGHLIGHT,
                       lw=2.5, label="diagonal (reason agrees)")
    )
    ax.legend(handles=handles, loc="upper center", bbox_to_anchor=(0.5, -0.30),
              ncols=4, frameon=False)


def make_plot() -> tuple[plt.Figure, list[plt.Axes]]:
    setup_plotting_style(style="whitegrid", context="notebook", font_scale=1.0)
    plt.rcParams.update({
        "font.size": 18, "axes.labelsize": 18, "axes.titlesize": 16,
        "xtick.labelsize": 16, "ytick.labelsize": 16, "legend.fontsize": 16,
    })
    df = _load_pairs()
    m = _build_matrix(df)
    conc = _concordance_by_tier(df)

    fig = plt.figure(figsize=(14, 19.5))
    # Manual layout in inches (tight/constrained layout both mis-handle the
    # heatmap colorbar). Panels a (DB concordance) and b (verdict flow) side
    # by side on top, their shared tier legend beneath them; the reason
    # matrix (panel c) full width below, at a cell size that holds its counts.
    fw, fh = fig.get_size_inches()

    def _axes_in(left: float, bottom: float, width: float, height: float) -> plt.Axes:
        return fig.add_axes((left / fw, bottom / fh, width / fw, height / fh))

    ax_a = _axes_in(1.9, 14.3, 3.6, 4.6)   # top-left  — DB concordance
    ax_b = _axes_in(8.3, 14.3, 5.5, 4.6)   # top-right — verdict flow
    ax_c = _axes_in(3.4, 3.0, 8.6, 8.6)    # bottom    — reason matrix
    cbar_ax = _axes_in(12.3, 5.3, 0.28, 4.0)

    _draw_concordance_by_tier(ax_a, conc)
    _draw_verdict_flow(ax_b, df)
    _draw_reason_matrix(ax_c, m, cbar_ax)

    # Letters sit left of each panel's tick/axis labels (fixed inch offset
    # measured after a draw, so they never land on the labels).
    fig.canvas.draw()
    renderer = fig.canvas.get_renderer()
    for ax, letter in ((ax_a, "a"), (ax_b, "b"), (ax_c, "c")):
        dx = (ax.get_window_extent(renderer).x0
              - ax.yaxis.get_tightbbox(renderer).x0) / fig.dpi
        ax.text(0.0, 1.0, letter,
                transform=offset_copy(ax.transAxes, fig=fig, x=-dx, y=0.12,
                                      units="inches"),
                ha="left", va="bottom", fontsize=24, fontweight=800,
                color=COLORS["dark"])

    return fig, [ax_a, ax_b, ax_c]


def main() -> None:
    fig, _ = make_plot()
    save_figure(fig, SLUG, output_dir=OUT_DIR, formats=("pdf", "png"))


if __name__ == "__main__":
    main()
