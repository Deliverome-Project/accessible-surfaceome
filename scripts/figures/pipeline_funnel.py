"""Cohort funnel — how 19,324 protein-coding genes become a 5,130-gene deep dive.

A schematic in the visual language of Figure 4 (the deep-dive stage
diagram): rounded maroon-outlined stage cards, pale-teal inner panels,
engine pills, heavy connector arrows. Figure 4 is a hand-drawn
Illustrator SVG; this one is generated, so the numbers on the canvas are
read from committed artifacts at render time rather than typed in.

Left to right:

* **Input** — the protein-coding cohort, which enters both lanes.
* **Five reference databases** — genes any of UniProt / GO CC / HPA /
  SURFY / CSPA flags as surface under the bench-optimized cutoffs (the
  thresholds the accuracy figures use, not Figure 1's native flags).
* **Accessibility Triage agent, both passes** — stage 1 reads NCBI gene
  and protein records for every gene; stage 2 re-reads the subset
  rejected for an ambiguous reason with a literature pass, flipping some
  to surface. The rescue slice (agent-positive, flagged by no database)
  is called out inside the card.
* **The trim** — the union of the two lanes is not the deep-dive cohort.
  Genes the agent rejected at high confidence with exactly one database
  flag are dropped; that gate is ``is_trim`` in
  ``scripts/build_candidate_universe_v3.py`` and it is drawn dashed
  because it removes rather than produces.
* **Deep dive** — the cohort that went on to a per-gene record.

**Why the arithmetic is not shown on the canvas.** Union (6,586) minus
the trim (1,457) minus one withdrawn-HGNC row is 5,128, the v3 candidate
universe; the completed sweep is 5,130. The two-gene gap is cohort
vintage, not a counting error — the sweep ran against a marginally
earlier universe. Printing 6,586 and 5,130 side by side would look like
an off-by-two, so the union total stays in the caption.

Data sources:
  data/processed/figures/zero_db_rescues_by_triage.tsv        whole proteome
  data/processed/figures/deep_dive_final_categories.tsv       deep-dive cohort
  data/processed/candidate_universe/candidate_universe_v3_dropped.tsv  the trim

One number has no committed TSV — how many genes the second triage pass
re-read. See ``STAGE2_REEXAMINED``.

Outputs (PDF + PNG):
  data/analysis/figures/pipeline_funnel.{pdf,png}
"""

from __future__ import annotations

import csv
from dataclasses import dataclass

import matplotlib.pyplot as plt
from matplotlib.patches import FancyArrowPatch, FancyBboxPatch

from accessible_surfaceome.audit._plotting_config import (
    save_figure,
    setup_plotting_style,
)
from accessible_surfaceome.paths import REPO_ROOT

OUT_DIR = REPO_ROOT / "data/analysis/figures"
# Whole-proteome triage table: per-gene database flags (native +
# bench-optimized) alongside the agent's verdict. Everything on the left
# two thirds of the canvas comes from here.
PROTEOME_TSV = REPO_ROOT / "data/processed/figures/zero_db_rescues_by_triage.tsv"
# The deep-dive roster. One row per gene that completed the sweep; only
# its length is needed, but reading the file beats hardcoding 5,130.
DEEP_DIVE_TSV = REPO_ROOT / "data/processed/figures/deep_dive_final_categories.tsv"
# The 1-of-5 trim: one row per gene dropped from the union because the
# agent called it "no" at high confidence and exactly one database
# flagged it. See scripts/build_candidate_universe_v3.py:is_trim.
TRIMMED_TSV = REPO_ROOT / "data/processed/candidate_universe/candidate_universe_v3_dropped.tsv"

# The one number on the canvas that no committed TSV carries: how many
# genes the second triage pass re-read. It lives only in D1, and only as
# a frozen historical run, so it cannot drift under us:
#
#   SELECT COUNT(DISTINCT gene_symbol) FROM triage_run
#   WHERE run_id = 'genome_full_sonnet_pubmed_ncbi_v1';   -- 2,626
#
# Verdicts on that run: 19 yes, 158 contextual, 2,447 no, 2 null.
STAGE2_RUN_ID = "genome_full_sonnet_pubmed_ncbi_v1"
STAGE2_REEXAMINED = 2_626

# Figure 4's palette, so the two schematics read as a pair.
INK = "#1F1718"
MUTED = "#5A5A5A"
EYEBROW = "#6A6A6A"
MAROON = "#BC3C4C"
MAROON_DARK = "#6E1428"
TEAL = "#3D6B60"
PANEL_FILL = "#EFF4F2"
PANEL_EDGE = "#9CB7AE"
RESCUE_FILL = "#FBEFF0"
# The trim gate is a removal, not a stage — neutral grey keeps it from
# reading as a fourth engine card.
TRIM_EDGE = "#8A8A8A"

# Canvas in Figure 4's coordinate space (viewBox 0 0 1260 460).
CANVAS_W, CANVAS_H = 1600.0, 560.0

POSITIVE_VERDICTS = ("yes", "contextual")


@dataclass(frozen=True)
class Counts:
    """Every number that lands on the canvas."""

    proteome: int
    db_union: int
    triage_positive: int
    triage_yes: int
    triage_contextual: int
    rescued: int
    deep_dive: int
    deep_dive_db_free: int
    stage1_positive: int
    stage2_reexamined: int
    stage2_rescued: int
    trimmed: int


def _load() -> Counts:
    """Read the funnel's counts out of the committed TSVs.

    Two files rather than one: the whole-proteome table has no
    deep-dive column, and the deep-dive table has no database columns.
    A published gist takes exactly one bundled TSV, so promoting this
    figure means first cutting a joined ``pipeline_funnel.tsv`` in
    ``scripts/build_figure_tsvs.py``.
    """
    with PROTEOME_TSV.open(newline="", encoding="utf-8") as handle:
        proteome = list(csv.DictReader(handle, delimiter="\t"))
    with DEEP_DIVE_TSV.open(newline="", encoding="utf-8") as handle:
        deep_dive = list(csv.DictReader(handle, delimiter="\t"))

    def n_db(row: dict[str, str]) -> int:
        raw = (row.get("n_sources_optimized") or "").strip()
        return int(float(raw)) if raw else 0

    with TRIMMED_TSV.open(newline="", encoding="utf-8") as handle:
        trimmed = list(csv.DictReader(handle, delimiter="\t"))

    deep_dive_ids = {row["hgnc_id"] for row in deep_dive}
    positives = [r for r in proteome if r["sonnet_verdict"] in POSITIVE_VERDICTS]
    # ``verdict_source`` names the pass that produced the FINAL verdict, so
    # a positive row tagged pubmed_rescue is exactly a stage-2 flip.
    stage2_rescued = sum(1 for r in positives if r["verdict_source"] == "pubmed_rescue")

    return Counts(
        proteome=len(proteome),
        db_union=sum(1 for r in proteome if n_db(r) >= 1),
        triage_positive=len(positives),
        triage_yes=sum(1 for r in positives if r["sonnet_verdict"] == "yes"),
        triage_contextual=sum(
            1 for r in positives if r["sonnet_verdict"] == "contextual"
        ),
        rescued=sum(1 for r in positives if n_db(r) == 0),
        deep_dive=len(deep_dive),
        deep_dive_db_free=sum(
            1 for r in proteome if r["hgnc_id"] in deep_dive_ids and n_db(r) == 0
        ),
        stage1_positive=len(positives) - stage2_rescued,
        stage2_reexamined=STAGE2_REEXAMINED,
        stage2_rescued=stage2_rescued,
        trimmed=len(trimmed),
    )


def _card(ax, x, y, w, h, *, edge=MAROON, fill="white", lw=2.0, radius=10, z=2,
          ls="solid"):
    """A Figure-4 stage card: rounded rectangle, coloured outline."""
    ax.add_patch(
        FancyBboxPatch(
            (x, y),
            w,
            h,
            boxstyle=f"round,pad=0,rounding_size={radius}",
            facecolor=fill,
            edgecolor=edge,
            linewidth=lw,
            linestyle=ls,
            zorder=z,
        )
    )


def _pill(ax, x, y, label, *, fill=MAROON_DARK, fg="white", size=11):
    """Figure 4's engine chip."""
    ax.text(
        x,
        y,
        label,
        ha="center",
        va="center",
        fontsize=size,
        fontweight="bold",
        color=fg,
        zorder=5,
        bbox={
            "boxstyle": "round,pad=0.45,rounding_size=0.9",
            "facecolor": fill,
            "edgecolor": "none",
        },
    )


def _arrow(ax, start, end, *, color=INK, lw=2.6):
    ax.add_patch(
        FancyArrowPatch(
            start,
            end,
            arrowstyle="-|>",
            mutation_scale=22,
            linewidth=lw,
            color=color,
            shrinkA=0,
            shrinkB=0,
            joinstyle="miter",
            zorder=4,
        )
    )


def _run(ax, x, y, parts):
    """Draw text segments left to right, measuring each so they abut.

    Matplotlib has no rich-text run, and eyeballing an offset for a
    bold number followed by regular prose drifts the moment the number
    gains a digit — so measure the drawn extent and continue from it.
    """
    fig = ax.get_figure()
    fig.canvas.draw()
    to_data = ax.transData.inverted()
    cursor = x
    for text, size, weight, color in parts:
        drawn = ax.text(
            cursor,
            y,
            text,
            ha="left",
            va="center",
            fontsize=size,
            fontweight=weight,
            color=color,
            zorder=5,
        )
        extent = drawn.get_window_extent(fig.canvas.get_renderer())
        x0, _ = to_data.transform((extent.x0, extent.y0))
        x1, _ = to_data.transform((extent.x1, extent.y1))
        cursor += x1 - x0
    return cursor


def _eyebrow(ax, x, y, text, color=EYEBROW):
    ax.text(
        x,
        y,
        text,
        ha="left",
        va="center",
        fontsize=11,
        fontweight="bold",
        color=color,
        zorder=5,
    )


def build(counts: Counts):
    fig, ax = plt.subplots(figsize=(16.0, 5.6))
    ax.set_xlim(0, CANVAS_W)
    ax.set_ylim(0, CANVAS_H)
    ax.invert_yaxis()  # top-left origin, like the SVG
    ax.axis("off")

    # ---- Box A: the input cohort -------------------------------------
    ax.text(
        20, 232, "Human protein-coding genes",
        ha="left", va="center", fontsize=13.5, color=MUTED, zorder=5,
    )
    ax.text(
        20, 276, f"{counts.proteome:,}",
        ha="left", va="center", fontsize=42, fontweight="bold",
        color=INK, zorder=5,
    )
    ax.text(
        20, 314, "every gene enters both lanes",
        ha="left", va="center", fontsize=12.5, color=EYEBROW, zorder=5,
    )

    # ---- Split from A into the two lanes -----------------------------
    # Each lane is entered at its card's own summary row, so the
    # connectors never cut through a card's inner panel.
    top, bottom = 116.0, 430.0
    junction = 320.0
    ax.plot([286, junction], [273, 273], color=INK, lw=2.6, zorder=4)
    ax.plot([junction, junction], [top, bottom], color=INK, lw=2.6, zorder=4)
    _arrow(ax, (junction, top), (396, top))
    _arrow(ax, (junction, bottom), (396, bottom))

    # ---- Box B: the database lane ------------------------------------
    _card(ax, 400, 52, 430, 128)
    _eyebrow(ax, 424, 76, "FIVE REFERENCE DATABASES")
    _run(
        ax, 424, 118,
        [
            (f"{counts.db_union:,}", 34, "bold", INK),
            ("   flagged surface", 13, "normal", MUTED),
        ],
    )
    ax.text(
        424, 154, "UniProt \u00b7 GO CC \u00b7 HPA \u00b7 SURFY \u00b7 CSPA",
        ha="left", va="center", fontsize=12.5, color=MUTED, zorder=5,
    )
    _pill(ax, 776, 76, "no LLM", fill=TEAL, size=10)

    # ---- Box C: the triage lane, both stages on the canvas -----------
    _card(ax, 400, 212, 430, 300)
    _eyebrow(ax, 424, 236, "ACCESSIBILITY TRIAGE AGENT")
    _pill(ax, 780, 236, "Sonnet", fill=MAROON_DARK, size=10)

    # The two passes, in Figure 4's pale inner panel.
    _card(ax, 422, 254, 386, 118, edge=PANEL_EDGE, fill=PANEL_FILL,
          lw=1.2, radius=6, z=3)
    ax.text(
        440, 276, "STAGE 1  NCBI gene + protein records",
        ha="left", va="center", fontsize=11, fontweight="bold",
        color=TEAL, zorder=5,
    )
    ax.text(
        440, 296,
        f"{counts.proteome:,} screened \u2192 {counts.stage1_positive:,} surface",
        ha="left", va="center", fontsize=12, color=MUTED, zorder=5,
    )
    ax.text(
        440, 324, "STAGE 2  literature pass on ambiguous rejects",
        ha="left", va="center", fontsize=11, fontweight="bold",
        color=TEAL, zorder=5,
    )
    ax.text(
        440, 344,
        f"{counts.stage2_reexamined:,} re-read \u2192 "
        f"{counts.stage2_rescued:,} more surface",
        ha="left", va="center", fontsize=12, color=MUTED, zorder=5,
    )

    _run(
        ax, 424, 424,
        [
            (f"{counts.triage_positive:,}", 34, "bold", INK),
            ("   called surface", 13, "normal", MUTED),
        ],
    )
    ax.text(
        424, 456,
        f"{counts.triage_yes:,} yes \u00b7 {counts.triage_contextual:,} contextual",
        ha="left", va="center", fontsize=12.5, color=MUTED, zorder=5,
    )

    # The rescue slice, called out inside the triage card.
    _card(ax, 424, 470, 322, 42, edge=MAROON, fill=RESCUE_FILL,
          lw=1.6, radius=6, z=3)
    _run(
        ax, 442, 491,
        [
            (f"{counts.rescued:,}", 21, "bold", MAROON_DARK),
            ("  flagged by no database", 12.5, "normal", MAROON_DARK),
        ],
    )

    # ---- Merge, then the trim gate -----------------------------------
    merge = 886.0
    _arrow(ax, (834, top), (merge, top))
    _arrow(ax, (834, bottom), (merge, bottom))
    ax.plot([merge, merge], [top, bottom], color=INK, lw=2.6, zorder=4)
    _arrow(ax, (merge, 273), (912, 273))

    _card(ax, 916, 206, 286, 134, edge=TRIM_EDGE, fill="white", lw=1.8,
          ls=(0, (5, 3)))
    _eyebrow(ax, 940, 232, "TRIMMED FROM THE UNION", color=TRIM_EDGE)
    ax.text(
        940, 274, f"\u2212{counts.trimmed:,}",
        ha="left", va="center", fontsize=30, fontweight="bold",
        color=TRIM_EDGE, zorder=5,
    )
    ax.text(
        940, 304, "high-confidence \u201cno\u201d with a",
        ha="left", va="center", fontsize=11.5, color=TRIM_EDGE, zorder=5,
    )
    ax.text(
        940, 322, "single database flag",
        ha="left", va="center", fontsize=11.5, color=TRIM_EDGE, zorder=5,
    )
    _arrow(ax, (1206, 273), (1250, 273))

    # ---- Box D: the deep dive ----------------------------------------
    _card(ax, 1254, 191, 342, 164, fill=PANEL_FILL, edge=MAROON)
    _eyebrow(ax, 1278, 219, "PER-GENE DEEP DIVE", color=TEAL)
    ax.text(
        1278, 263, f"{counts.deep_dive:,}",
        ha="left", va="center", fontsize=42, fontweight="bold",
        color=INK, zorder=5,
    )
    ax.text(
        1278, 301, "genes with a validated record",
        ha="left", va="center", fontsize=12.5, color=MUTED, zorder=5,
    )
    ax.text(
        1278, 327, f"including all {counts.rescued:,} triage rescues",
        ha="left", va="center", fontsize=12.5, fontweight="bold",
        color=MAROON_DARK, zorder=5,
    )

    # Cutoff provenance: the union above is the bench-optimized one, not
    # Figure 1's native flags (5,546) \u2014 say so rather than let the two
    # figures look like they disagree.
    ax.text(
        20, 544,
        "Database flags use the SurfaceBench-optimized cutoffs, as in the "
        "accuracy figures.",
        ha="left", va="center", fontsize=11, color=EYEBROW, zorder=5,
    )

    fig.tight_layout()
    return fig


def main() -> None:
    setup_plotting_style()
    counts = _load()
    print(
        f"proteome={counts.proteome:,}  db_union={counts.db_union:,}\n"
        f"triage stage1+={counts.stage1_positive:,}  "
        f"stage2 re-read={counts.stage2_reexamined:,} -> "
        f"+{counts.stage2_rescued:,}  total+={counts.triage_positive:,} "
        f"({counts.triage_yes:,} yes / {counts.triage_contextual:,} ctx)\n"
        f"rescued(zero-DB)={counts.rescued:,}  trimmed={counts.trimmed:,}  "
        f"deep_dive={counts.deep_dive:,} ({counts.deep_dive_db_free:,} db-free)"
    )
    fig = build(counts)
    save_figure(fig, "pipeline_funnel", OUT_DIR, formats=("pdf", "png"))
    plt.close(fig)


if __name__ == "__main__":
    main()
