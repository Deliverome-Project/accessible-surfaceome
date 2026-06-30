"""Zero-DB rescues: how many proteins did the triage agent rescue from the 0-DB universe?

Reads the dedicated per-figure TSV at
``data/processed/figures/zero_db_rescues_by_triage.tsv`` (19,324
protein-coding human genes with per-gene surface-DB flags — both the
INITIAL ``n_sources_surface`` and the bench-OPTIMIZED
``n_sources_optimized`` vote counts — plus the canonical Sonnet+NCBI
triage `verdict` and `reason`), then tallies the slice where
``n_sources_optimized == 0`` (no classical surface DB flags the gene
under the bench-optimized cutoffs) and Sonnet voted yes or contextual.

Using ``n_sources_optimized`` (not the initial ``n_sources_surface``)
keeps the zero-DB definition consistent with the accuracy figures,
which all score the databases at their bench-optimized thresholds.

Output: two grouped bar panels (yes + contextual), each showing per-reason
counts on a shared y-axis, plus translational / surface-recognizable
gene callouts beneath each panel.

# Reproduction:
#   Public gist (reader-side standalone, PyPA inline-script-metadata deps):
#   https://gist.github.com/beccajcarlson/a4526c9e6de5e958826bf1d764744c1b
#   Reader-side mirror script:
#   data/analysis/figures/make_zero_db_rescues_by_triage.py.

Run:
    uv run python scripts/zero_db_rescues_by_triage.py
"""
from __future__ import annotations

from collections import Counter, defaultdict
from pathlib import Path

import matplotlib.pyplot as plt
import matplotlib.gridspec as gridspec
import seaborn as sns

from accessible_surfaceome.audit._plotting_config import (
    COLORS,
    save_figure,
    setup_plotting_style,
)

ROOT = Path(__file__).resolve().parents[1]
OUT_DIR = ROOT / "data/analysis/figures"

# Reason taxonomy per verdict bucket (matches the triage agent's closed
# enum). Display order = most → least common in the zero-DB rescue
# slice; "other" always last.
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

# Sequential green ramp for yes (definite surface), amber ramp for
# contextual (state / lineage / partner dependent). Both pulled from
# BRAND_SEQUENTIAL families with `other` as neutral grey.
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

# Callouts: db=0 rescues. The triage agent reports its own confidence
# per call (low/medium/high). YES callouts are all HIGH-confidence;
# CONTEXTUAL callouts mix HIGH (gasdermin pore-formers) with reputable
# MEDIUM picks where the agent's MEDIUM rating reflects mechanism-detail
# nuance (anchoring partner, state-dependence) rather than skepticism
# about whether surface display occurs — each MEDIUM pick has direct
# surface flow-cytometry / biotinylation evidence in the published
# literature. Each `reason` is verified at runtime against
# `triage.reason` in the catalog — the script raises RuntimeError if
# any callout symbol is missing from the expected (verdict, reason) slot.
# Ordered to match the per-reason bar order in the panel above
# (YES_REASONS / CONTEXTUAL_REASONS), so callouts read top-to-bottom in
# the same sequence as the bars left-to-right.
YES_CALLOUTS = [
    ("LVRN",    "Laeverin/APQ — trophoblast surface peptidase", "classical_surface_receptor"),
    ("ECEL1",   "Type-II TM; neprilysin/M13 family",   "classical_surface_receptor"),
    ("STEAP3",  "Six-TM metalloreductase; STEAP family", "multipass_with_exposed_loops"),
    ("RHCE",    "Rh blood-group surface antigen",      "multipass_with_exposed_loops"),
    ("NYX",     "GPI-anchored nyctalopin (retinal SLRP)", "gpi_anchored"),
    ("LY96",    "MD-2 — TLR4 co-receptor",             "stable_complex_partner"),
]
CONTEXTUAL_CALLOUTS = [
    ("KLK2",    "Prostate kallikrein",                 "tissue_restricted_surface"),
    ("KLK3",    "PSA; prostate kallikrein",            "dual_localization"),
    ("GSDME",   "Gasdermin E — pyroptosis pores",      "cell_state_induced"),
    ("HSPA1A",  "Surface Hsp70; cmHsp70.1 mAb",        "cell_state_induced"),
    ("MMP9",    "Gelatinase B; cell-surface zymogen",  "stable_surface_attachment"),
    ("LRG1",    "Leucine-rich α2-glycoprotein",        "stable_surface_attachment"),
    ("IL15",    "Surface trans-presentation via IL-15Rα", "dual_localization"),
    ("HPSE",    "Surface heparanase on activated platelets / tumor cells",
                                                       "lysosomal_exocytosis"),
]

# Clinical-target overlay (manually curated; verified against the
# ADCdb + T-cell-engager positive-control panels on the PR87 branch
# `claude/positive-controls-on-86`, 2026-06). These optimized zero-DB
# rescues are also approved/clinical ADC or TCE targets — the
# strongest validation that the agent recovers real, actionable
# surface biology the gating databases miss. NOTE: this is a hand
# annotation, NOT a data join (per design decision — the ADC/TCE TSVs
# live in PR87); reconcile into a proper join when PR87 merges. Of the
# eight, all are ADCdb targets and KLK2 is additionally a TCE target.
CLINICAL_TARGETS = {
    "KLK2": "ADC + TCE", "KLK3": "ADC", "GSDME": "ADC", "HSPA1A": "ADC",
    "MMP9": "ADC", "LRG1": "ADC", "ASPH": "ADC", "FMOD": "ADC",
}


def _load_catalog_rows() -> list[dict]:
    """Return rows of the dedicated zero-DB-rescue figure TSV at
    ``data/processed/figures/zero_db_rescues_by_triage.tsv`` (~19k rows,
    un-LFS so raw.githubusercontent.com serves plain text). The TSV is
    regenerated by ``scripts/build_figure_tsvs.py`` from D1 — the
    Worker's ``/v1/catalog`` is not queried at figure-render time so the
    gist is self-contained.

    Each row carries the per-gene surface-DB flags in BOTH the INITIAL
    form (the five ``*_surface_flag`` fields + ``n_sources_surface``)
    and the bench-OPTIMIZED form (``uniprot_optimized``,
    ``cspa_optimized``, … + ``n_sources_optimized``), plus
    ``sonnet_verdict`` / ``sonnet_reason`` and stable IDs
    (``hgnc_id``, ``hgnc_symbol``, ``uniprot_acc``, ``ensembl_gene``,
    ``ncbi_gene_id``). This figure selects on ``n_sources_optimized``.
    """
    import csv

    tsv_path = ROOT / "data/processed/figures/zero_db_rescues_by_triage.tsv"
    print(f"Reading {tsv_path} ...")
    with tsv_path.open() as fh:
        rows = list(csv.DictReader(fh, delimiter="\t"))
    # Normalize types: vote counts are integer in the selection logic below.
    for r in rows:
        r["n_sources_surface"] = int(r.get("n_sources_surface", 0) or 0)
        r["n_sources_optimized"] = int(r.get("n_sources_optimized", 0) or 0)
    return rows


def _sonnet_verdict_reason(row: dict) -> tuple[str, str]:
    """Pull the Sonnet (canonical) verdict + reason from a TSV row.
    The TSV is sourced from D1's
    ``genome_full_sonnet_ncbi_v2`` triage sweep, so the Sonnet model
    is implicit — no per-row models[] index resolution needed."""
    v = (row.get("sonnet_verdict") or "").strip() or "unknown"
    reason = (row.get("sonnet_reason") or "").strip() or "other"
    return v, reason


def _draw_reason_bars(
    ax,
    counts: dict,
    reasons: list[str],
    palette: dict,
    header_label: str,
    header_color: str,
    y_max: float,
) -> None:
    """Render one panel: one bar per non-zero reason + header text."""
    visible = [r for r in reasons if counts.get(r, 0) > 0]
    n_bars = len(visible)
    x_positions = list(range(n_bars))
    heights = [counts[r] for r in visible]
    colors = [palette[r] for r in visible]

    # Wider per-bucket slot (1.4×) and narrower bars (width=0.55) so the
    # 3-line reason labels have horizontal breathing room and don't
    # collide with neighboring x-tick text.
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
        fontsize=15, color=COLORS["dark"],
    )
    ax.tick_params(axis="y", labelsize=16)
    ax.set_xlim(-0.9, x_positions[-1] + 0.9)
    sns.despine(ax=ax, top=True, right=True)


def _draw_callouts(ax, callouts: list[tuple[str, str, str]], palette: dict, title: str) -> None:
    """Render a column of gene callouts in its own axes. Row spacing scales
    with callout count so 8+ entries fit without overflowing the axes."""
    ax.set_axis_off()
    ax.text(
        0.0, 1.0, title,
        transform=ax.transAxes, ha="left", va="top",
        fontsize=19, color=COLORS["neutral"], fontweight="bold",
    )
    y0 = 0.82
    n = len(callouts)
    row_h = (y0 - 0.05) / max(n - 1, 1) if n > 1 else 0.0
    row_h = min(row_h, 0.155)  # cap at row spacing for small n
    for i, (symbol, desc, reason) in enumerate(callouts):
        y = y0 - i * row_h
        ax.scatter(
            [0.025], [y],
            marker="s", s=260,
            color=palette.get(reason, COLORS["neutral"]),
            edgecolor="none", transform=ax.transAxes, zorder=10,
        )
        ax.text(
            0.07, y, symbol,
            transform=ax.transAxes, ha="left", va="center",
            fontsize=19, fontweight="bold", color=COLORS["dark"],
        )
        ax.text(
            0.28, y, f"— {desc}",
            transform=ax.transAxes, ha="left", va="center",
            fontsize=16, color=COLORS["neutral"],
        )
        # Clinical-target badge: mark callouts that are also approved/
        # clinical ADC or TCE targets (ADCdb / TCE panel). KLK2 (ADC+TCE)
        # gets the brand-primary maroon; ADC-only gets the teal accent.
        modality = CLINICAL_TARGETS.get(symbol)
        if modality:
            badge_color = COLORS["primary"] if "TCE" in modality else COLORS["secondary"]
            ax.text(
                0.985, y, modality,
                transform=ax.transAxes, ha="right", va="center",
                fontsize=13, fontweight="bold", color="white",
                bbox={"boxstyle": "round,pad=0.3", "facecolor": badge_color,
                      "edgecolor": "none"},
                zorder=11,
            )


def main() -> None:
    rows = _load_catalog_rows()
    print(f"  loaded {len(rows):,} rows from zero_db_rescues_by_triage.tsv")

    # Zero-DB slice: no surface DB flags this gene under the
    # bench-OPTIMIZED cutoffs (consistent with the accuracy figures).
    zero_db = [r for r in rows if r["n_sources_optimized"] == 0]
    print(f"\nZero-DB universe (optimized cutoffs): {len(zero_db):,} / {len(rows):,} "
          f"({100*len(zero_db)/len(rows):.1f}%); sonnet model = claude-sonnet-4-6")

    def verdict_reason(row: dict) -> tuple[str, str]:
        return _sonnet_verdict_reason(row)

    yes_counts: Counter = Counter()
    ctx_counts: Counter = Counter()
    yes_symbols: dict[str, list[str]] = defaultdict(list)
    ctx_symbols: dict[str, list[str]] = defaultdict(list)
    for r in zero_db:
        v, reason = verdict_reason(r)
        sym = r.get("hgnc_symbol", "")
        if v == "yes":
            yes_counts[reason] += 1
            yes_symbols[reason].append(sym)
        elif v == "contextual":
            ctx_counts[reason] += 1
            ctx_symbols[reason].append(sym)

    n_yes = sum(yes_counts.values())
    n_ctx = sum(ctx_counts.values())
    print(f"\nRescues: yes={n_yes}, contextual={n_ctx}")
    for r in YES_REASONS:
        print(f"  yes / {r:32s}  {yes_counts.get(r, 0):>4}")
    for r in CONTEXTUAL_REASONS:
        print(f"  ctx / {r:32s}  {ctx_counts.get(r, 0):>4}")

    print("\nCallout verification:")
    bad = []
    for sym, _, reason in YES_CALLOUTS:
        ok = sym in yes_symbols.get(reason, [])
        if not ok:
            bad.append(("yes", sym, reason))
        print(f"  yes:        {sym:14s} reason={reason:32s} {'OK' if ok else 'MISSING'}")
    for sym, _, reason in CONTEXTUAL_CALLOUTS:
        ok = sym in ctx_symbols.get(reason, [])
        if not ok:
            bad.append(("contextual", sym, reason))
        print(f"  contextual: {sym:14s} reason={reason:32s} {'OK' if ok else 'MISSING'}")
    if bad:
        raise RuntimeError(f"Callouts not found in rescue slice: {bad}")

    # ─── Figure ─── 2×2: top row = per-reason bar panels (shared y-axis);
    # bottom row = callout columns.
    setup_plotting_style(style="whitegrid", context="notebook", font_scale=1.0)
    # Brand-style-v3 font sizes (mirror parity). The gist mirror at
    # data/analysis/figures/make_zero_db_rescues_by_triage.py sets these
    # inline; this canonical script applies them via rcParams so its
    # render matches the published gist. See CLAUDE.md "Canonical
    # generator vs gist mirror".
    plt.rcParams.update({
        "font.size": 20, "axes.labelsize": 20, "axes.titlesize": 0,
        "xtick.labelsize": 20, "ytick.labelsize": 20, "legend.fontsize": 20,
    })
    # Layout numbers match the gist-mirror at
    # data/analysis/figures/make_zero_db_rescues_by_triage.py (single
    # source of truth for the published figure shape). Brought into the
    # canonical script via commit 44d8ae5cf's subpanel-a/b layout bump:
    #   - figsize 11 → 13 (taller)
    #   - height_ratios [2.2, 1.05] → [2.2, 1.55] (more bottom-row room)
    #   - hspace 0.20 → 0.55, wspace 0.10 → 0.28 (clear x-labels +
    #                                              callout headers)
    #   - top 0.92 → 0.93 (headroom for subpanel labels)
    fig = plt.figure(figsize=(19, 13))
    gs = gridspec.GridSpec(
        2, 2, figure=fig,
        height_ratios=[2.2, 1.55],
        width_ratios=[1.0, 1.5],
        hspace=0.30, wspace=0.28,
        top=0.93, bottom=0.04, left=0.06, right=0.97,
    )
    ax_yes = fig.add_subplot(gs[0, 0])
    ax_ctx = fig.add_subplot(gs[0, 1], sharey=ax_yes)
    ax_callouts_yes = fig.add_subplot(gs[1, 0])
    ax_callouts_ctx = fig.add_subplot(gs[1, 1])

    # Subpanel labels — Manrope ExtraBold (weight 800), upper-left of
    # each bar panel. Project-wide convention from
    # ``MEMORY.md figure_subpanel_labels`` — any multi-data-panel
    # figure marks each panel with a lowercase letter.
    for ax, letter in ((ax_yes, "a"), (ax_ctx, "b")):
        ax.text(
            -0.06, 1.08, letter,
            transform=ax.transAxes, ha="left", va="bottom",
            fontsize=32, fontweight=800, color=COLORS["dark"],
        )

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

    ax_yes.set_ylabel("Genes rescued from\nzero-DB universe", fontsize=20)
    ax_yes.tick_params(axis="y", labelsize=16)
    plt.setp(ax_ctx.get_yticklabels(), visible=False)

    _draw_callouts(
        ax_callouts_yes, YES_CALLOUTS, YES_PALETTE,
        title="Select yes rescues",
    )
    _draw_callouts(
        ax_callouts_ctx, CONTEXTUAL_CALLOUTS, CONTEXTUAL_PALETTE,
        title="Select contextual rescues",
    )

    save_figure(
        fig, filename="zero_db_rescues_by_triage",
        output_dir=str(OUT_DIR), formats=["pdf", "png"],
        gist_url="https://gist.github.com/beccajcarlson/a4526c9e6de5e958826bf1d764744c1b",
    )
    plt.close(fig)


if __name__ == "__main__":
    main()
