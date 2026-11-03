# /// script
# requires-python = ">=3.11"
# dependencies = [
#   "matplotlib>=3.9",
#   "numpy>=1.26",
#   "pandas>=2.2",
#   "seaborn>=0.13",
# ]
# ///
"""Reproduce ``triage_vs_deep_dive_reason.{pdf,png}`` — the three-panel
triage → deep-dive comparison (Supplementary Figure 14) on the 5,332 genes
with both a triage and a deep-dive record.

**Layout.** Panels a and b sit side by side on top, sharing one five-tier
legend beneath them; the reason confusion matrix (panel c) spans the full width
below, with its bucket legend underneath.

**Panel a — database concordance.** For the genes the *deep dive* places in
the canonical / likely / low tiers, the share of each tier ALSO flagged surface
by each source: the 5 catalog databases (UniProt, GO, SURFY, CSPA, HPA) plus
Sonnet triage (verdict yes / contextual). One group of three tier-colored bars
per source; Sonnet triage is pinned on top and the databases follow in
descending order of canonical-tier concordance. HPA is scored only over the genes it
imaged (``hpa_in_atlas``), because a gene missing from HPA lacks an antibody
rather than being called non-surface; the benchmark treats HPA the same way. Every source flags more
canonical genes than likely, and more likely than low; Sonnet triage is the
most concordant source at every tier.

**Panel b — verdict flow.** Slim 100%-stacked horizontal bars, one per triage
verdict (yes / contextual / no), each split by the deep-dive's 5-tier call
(canonical / likely / low / uncertain / no). Shows how triage calls are
confirmed or downgraded once the deep dive reads full text.

**Panel c — reason confusion matrix.** The triage reason (rows) against the
deep-dive ``surface_call_reason`` (columns), both drawn from the same closed
``TriageReason`` enum. The diagonal (outlined in maroon) is exact
reason-level agreement; thick separators mark the yes/contextual/no bucket
boundaries and tick labels are colored by bucket so a cross-bucket flip is
visible at a glance.

Real data: 5,332 genes with both a triage and a deep-dive record. Half the
genes (50%) land on the reason diagonal; of the rest, about 29% are
within-bucket reassignments and about 71% are cross-bucket flips (the
largest block is yes-bucket triage reasons relabeled as contextual by the
deep dive). The
``canonical`` tier uses the PR #130 gate.

Standalone — ``uv run make_triage_vs_deep_dive_reason.py``.
"""
from __future__ import annotations

from pathlib import Path

import matplotlib.font_manager as fm
import matplotlib.patches as mpatches
import matplotlib.pyplot as plt
from matplotlib.transforms import offset_copy
import numpy as np
import pandas as pd
import seaborn as sns

REPO = "Deliverome-Project/accessible-surfaceome"
BRANCH = "main"  # pin to a commit SHA at publication
BASE = f"https://raw.githubusercontent.com/{REPO}/{BRANCH}"
# Single per-figure TSV: one row per gene with a deep-dive record AND
# a triage hit. Columns: gene_symbol, uniprot_acc, triage_verdict,
# triage_reason, deep_dive_reason, deep_dive_tier, + per-DB surface
# membership (go/surfy/hpa _surface_flag + uniprot/cspa _optimized, 0/1).
# Built by scripts/build_figure_tsvs.py.
DATA_TSV = f"{BASE}/data/processed/figures/triage_vs_deep_dive_reason.tsv"

# Filled at gist-creation time; the placeholder is harmless until then.
GIST_URL = "https://gist.github.com/beccajcarlson/152a4d8b4a1d156e2afaa73d205294b6"

# ──── Inline brand styling — sentinel: brand-style-v3 ────
BRAND_INK = "#1F1718"
BRAND_PALETTE = [
    "#BC3C4C",  # maroon-light
    "#3D6B60",  # teal-mid
    "#F4AA28",  # amber-bright
    "#8878C8",  # lavender-bright
    "#6E1428",  # maroon-dark
    "#7AAB9F",  # teal-light
]
BRAND_NEUTRAL = "#6F5D5A"
BRAND_GRID = "#E6DAD4"
BUCKET_COLOR = {"yes": "#2E7A55", "contextual": "#C07830", "no": "#6F5D5A"}
DIAGONAL_HIGHLIGHT = "#BC3C4C"

# ── Panel b: triage verdicts (bars) × deep-dive tiers (stack segments) ──
TRIAGE_VERDICT_ORDER = ["yes", "contextual", "no"]
TRIAGE_VERDICT_LABEL = {
    "yes":        "triage: yes",
    "contextual": "triage: contextual",
    "no":         "triage: no",
}
# 5-tier deep-dive spectrum (best → worst) with the canonical tier colors
# shared across every deep-dive figure.
DD_TIER_ORDER = ["canonical", "likely", "low", "uncertain", "no"]
DD_TIER_COLOR = {
    "canonical": "#2E7A55",
    "likely":    "#3D6B60",
    "low":       "#C99A5B",
    "uncertain": "#C7BDB6",
    "no":        "#9C8C88",
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
# The 5 catalog databases (canonical palette by identity) + Sonnet triage
# as a peer source, given a distinct Claude-orange so it doesn't read as a
# 6th database.
# UniProt/CSPA are recalibrated -> OPTIMIZED membership (uniprot_optimized /
# cspa_optimized); GO/SURFY/HPA were never recalibrated -> native *_surface_flag.
# The native UniProt/CSPA flags are forbidden outside Fig 1
# (test_figures_use_optimized_cutoffs).
DB_SOURCES = [
    ("UniProt", "uniprot_optimized",  "#BC3C4C"),  # maroon-light
    ("GO",      "go_surface_flag",    "#3D6B60"),  # teal-mid
    ("SURFY",   "surfy_surface_flag", "#8878C8"),  # lavender-bright
    ("CSPA",    "cspa_optimized",     "#6E1428"),  # maroon-dark
    ("HPA (imaged)", "hpa_surface_flag", "#F4AA28"),  # amber-bright
]
SONNET_LABEL = "Sonnet triage"
SONNET_COLOR = "#d87851"  # Claude-orange — distinct from the 5 DB bars

REASONS_ORDERED = [
    # YES
    "classical_surface_receptor", "multipass_with_exposed_loops",
    "gpi_anchored", "extracellular_face_protein", "stable_complex_partner",
    # CONTEXTUAL
    "stable_surface_attachment", "cell_state_induced",
    "tissue_restricted_surface", "lysosomal_exocytosis", "dual_localization",
    # NO
    "cytoplasmic", "nuclear", "mitochondrial_internal", "endomembrane_resident",
    "nuclear_envelope", "secreted_only", "inner_leaflet_anchored",
    "pmhc_only_intracellular", "other",
]
BUCKET = {r: "yes" for r in REASONS_ORDERED[:5]}
BUCKET.update({r: "contextual" for r in REASONS_ORDERED[5:10]})
BUCKET.update({r: "no" for r in REASONS_ORDERED[10:]})

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
        "figure.facecolor": "none", "savefig.facecolor": "none",
        "font.family": ["Manrope", "DejaVu Sans"],
        "font.sans-serif": ["Manrope", "Outfit", "DejaVu Sans", "Liberation Sans", "Arial"],
        "font.weight": "semibold", "font.size": 14,
        "axes.labelsize": 18, "axes.labelweight": "semibold",
        "axes.titlesize": 16, "axes.titlepad": 12,
        "axes.spines.top": False, "axes.spines.right": False,
        "axes.grid": True, "axes.axisbelow": True,
        "axes.edgecolor": BRAND_GRID, "axes.labelcolor": BRAND_INK,
        "axes.facecolor": "none", "text.color": BRAND_INK,
        "grid.alpha": 0.35, "grid.linestyle": "-",
        "grid.linewidth": 0.7, "grid.color": BRAND_GRID,
        "xtick.labelsize": 11, "ytick.labelsize": 11,
        "xtick.color": BRAND_INK, "ytick.color": BRAND_INK,
        "legend.frameon": False, "legend.fontsize": 12,
        "patch.edgecolor": "none", "patch.linewidth": 0.0,
        "savefig.dpi": 600, "savefig.bbox": "tight",
    })


def _fetch_tsv(url: str) -> pd.DataFrame:
    """Sibling-only: bundled TSV must sit next to this script. No
    network fetch — the gist is the single citable reproduction unit."""
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


def _build_matrix(df: pd.DataFrame) -> np.ndarray:
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
            if col == "hpa_surface_flag":
                # HPA abstains where it has no antibody data, so it is scored
                # over the genes it imaged — the benchmark's rule too.
                sub = sub[sub["hpa_in_atlas"] == 1]
            d = len(sub)
            by_tier[tier] = 100.0 * int((sub[col] == 1).sum()) / d if d else 0.0
        out.append((label, by_tier))
    by_tier = {}
    for tier in DD_SURFACE_TIERS:
        sub = df[df["deep_dive_tier"] == tier]
        d = len(sub)
        by_tier[tier] = 100.0 * int(sub["triage_verdict"].isin(["yes", "contextual"]).sum()) / d if d else 0.0
    out.append((SONNET_LABEL, by_tier))
    # Pin Sonnet triage on top, then DBs by canonical-tier concordance desc.
    out.sort(key=lambda r: (r[0] != SONNET_LABEL, -r[1]["canonical"]))
    return out


def _bucket_boundaries() -> list[int]:
    bounds: list[int] = []
    prev = None
    for i, r in enumerate(REASONS_ORDERED):
        b = BUCKET[r]
        if prev is not None and b != prev:
            bounds.append(i)
        prev = b
    return bounds


def _draw_verdict_flow(ax: plt.Axes, df: pd.DataFrame) -> None:
    """Panel b — slim 100%-stacked horizontal bars: one bar per triage
    verdict, each split by the deep-dive tier composition. Bars are thin
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
            if w >= 0.05:
                txt_color = "white" if tier in ("canonical", "likely") else BRAND_INK
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
                    ha="left", fontsize=14.6, color=BRAND_INK)
    ax.set_yticks(y_base)
    ax.set_yticklabels([r[0] for r in rows])
    ax.set_ylim(-0.6, n - 0.4)
    ax.set_xlim(0, 108)
    ax.set_xticks([0, 25, 50, 75, 100])
    ax.set_xticklabels(["0", "25", "50", "75", "100%"])
    ax.set_xlabel("% of each deep-dive tier's genes\nthe source also flags")
    # No legend of its own: tier colours are identical to panel b's, whose
    # five-tier legend is centred under both panels (two legends collided).
    sns.despine(ax=ax, top=True, right=True)


def _draw_reason_matrix(ax: plt.Axes, m: np.ndarray, cbar_ax: plt.Axes) -> None:
    """Panel c — the 19×19 triage × deep-dive reason confusion matrix."""
    n = m.shape[0]
    cmap = sns.light_palette("#3D6B60", as_cmap=True)
    sns.heatmap(
        m, ax=ax, cmap=cmap, square=True, linewidths=0.5, linecolor="#FFFFFF",
        annot=True, fmt="d", annot_kws={"fontsize": 14.6, "color": BRAND_INK},
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
        ax.axhline(b, color=BRAND_INK, lw=2.0, alpha=0.85)
        ax.axvline(b, color=BRAND_INK, lw=2.0, alpha=0.85)
    for i in range(n):
        ax.add_patch(mpatches.Rectangle(
            (i, i), 1, 1, fill=False, edgecolor=DIAGONAL_HIGHLIGHT,
            lw=2.5, zorder=10,
        ))
    ax.set_xlabel("Deep-dive surface_call_reason", labelpad=10)
    ax.set_ylabel("Triage\nsurface_call_reason", labelpad=10)

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


def main() -> None:
    _apply_brand_style()
    # Three-panel canvas needs bigger type than the base single-panel style —
    # match the canonical generator's fingerprint (font 18 / labelsize 20 /
    # titlesize 16 / xtick 12 / ytick 14 / legend 13).
    plt.rcParams.update({
        "font.size": 18, "axes.labelsize": 18, "axes.titlesize": 16,
        "xtick.labelsize": 16, "ytick.labelsize": 16, "legend.fontsize": 16,
    })
    df = _fetch_tsv(DATA_TSV)
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
                color=BRAND_INK)

    cohort_n = int(m.sum())
    on_diag = int(np.trace(m))

    out_pdf = Path("triage_vs_deep_dive_reason.pdf")
    out_png = Path("triage_vs_deep_dive_reason.png")
    fig.savefig(out_pdf, bbox_inches="tight", metadata={"Subject": GIST_URL})
    fig.savefig(out_png, bbox_inches="tight", dpi=600, metadata={"Source": GIST_URL})
    print(f"Wrote {out_pdf} + {out_png} (cohort n={cohort_n}, diagonal={on_diag})")


if __name__ == "__main__":
    main()
