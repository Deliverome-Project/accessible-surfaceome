"""Zero-DB rescues: how many proteins did the triage agent rescue from the 0-DB universe?

Fetches the public catalog at
``https://api.deliverome.org/surfaceome/v1/catalog`` (19,324 protein-coding
human genes with per-gene `db` vote count + canonical Sonnet+NCBI triage
`verdict` and `reason`), then tallies the slice where `db == 0` (no
classical surface DB flagged the gene) and Sonnet voted yes or contextual.

Output: two grouped bar panels (yes + contextual), each showing per-reason
counts on a shared y-axis, plus translational / surface-recognizable
gene callouts beneath each panel.

# Reproduction:
#   Public gist (reader-side standalone, PyPA inline-script-metadata deps):
#   https://gist.github.com/beccajcarlson/a4526c9e6de5e958826bf1d764744c1b
#   Reader-side mirror script:
#   data/analysis/figures/make_zero_db_rescues_by_triage.py.

Run:
    uv run python scripts/figures/zero_db_rescues_by_triage.py
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
    ("PVRIG",   "NK/T checkpoint; COM701 = anti-PVRIG mAb", "classical_surface_receptor"),
    ("ECEL1",   "Type-II TM; neprilysin/M13 family",   "classical_surface_receptor"),
    ("STEAP1",  "Prostate ADC + BiTE target",          "multipass_with_exposed_loops"),
    ("ORAI2",   "Store-operated Ca2+ channel",         "multipass_with_exposed_loops"),
    ("CRIPTO",  "GPI-anchored oncofetal antigen",      "gpi_anchored"),
    ("LY96",    "MD-2 — TLR4 co-receptor",             "stable_complex_partner"),
]
CONTEXTUAL_CALLOUTS = [
    ("IL15",    "Surface trans-presentation via IL-15Rα", "dual_localization"),
    ("KLK2",    "Prostate kallikrein; ADC-relevant rescue", "tissue_restricted_surface"),
    ("TIMP2",   "MT1-MMP ternary complex",             "stable_surface_attachment"),
    ("GSDMD",   "Gasdermin D/E/C — pyroptosis pores",  "cell_state_induced"),
    ("HSPA1A",  "Surface Hsp70; cmHsp70.1 mAb",        "cell_state_induced"),
    ("HSP90B1", "Surface GRP94 in tumor cells",        "cell_state_induced"),
    ("HPSE",    "Surface heparanase on activated platelets / tumor cells",
                                                       "lysosomal_exocytosis"),
]


def _load_catalog_rows() -> list[dict]:
    """Return rows of the whole-proteome catalog. As of 2026-06, the
    canonical source is the static TSV at
    ``data/processed/catalog/whole_proteome_catalog.tsv`` (~2 MB, ~19k
    rows, un-LFS so raw.githubusercontent.com serves plain text). The
    TSV is regenerated by
    ``scripts/tsv-export/export_whole_proteome_catalog_to_tsv.py`` from D1 — the
    Worker's ``/v1/catalog`` is no longer queried at figure-render
    time so the gist is self-contained.

    Each row has the v1-style expanded columns: ``hgnc_symbol``,
    ``uniprot_acc``, the five ``*_surface_flag`` fields,
    ``n_sources_surface``, ``sonnet_verdict``, ``sonnet_reason``,
    ``hgnc_id``, ``ensembl_gene``, ``ncbi_gene_id``,
    ``universe_version``.
    """
    import csv

    tsv_path = ROOT / "data/processed/catalog/whole_proteome_catalog.tsv"
    print(f"Reading {tsv_path} ...")
    with tsv_path.open() as fh:
        rows = list(csv.DictReader(fh, delimiter="\t"))
    # Normalize types: counts are integer in v1-style logic below.
    for r in rows:
        r["n_sources_surface"] = int(r.get("n_sources_surface", 0) or 0)
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


def main() -> None:
    rows = _load_catalog_rows()
    print(f"  loaded {len(rows):,} rows from whole_proteome_catalog.tsv")

    # Zero-DB slice: no surface DB voted "yes" for this gene.
    zero_db = [r for r in rows if r["n_sources_surface"] == 0]
    print(f"\nZero-DB universe: {len(zero_db):,} / {len(rows):,} "
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
