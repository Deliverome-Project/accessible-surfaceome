"""Cohort funnel — how 19,324 protein-coding genes become a 5,130-gene deep dive.

A schematic in the visual language of Figure 4 (the deep-dive stage
diagram): rounded maroon-outlined stage cards, pale-teal inner panels,
engine pills, heavy connector arrows. Figure 4 is a hand-drawn
Illustrator SVG; this one is generated, so every number on the canvas is
read from the committed TSVs at render time rather than typed in.

The story in four boxes:

* **Input** — the protein-coding cohort the triage sweep covers.
* **Five reference databases** — how many of those genes any one of
  UniProt / GO CC / HPA / SURFY / CSPA flags as surface under the
  bench-optimized cutoffs (the same thresholds the accuracy figures
  use).
* **Accessibility Triage agent** — how many the agent calls surface
  ("yes") or conditionally surface ("contextual"), and the rescue
  slice inside that: agent-positive genes no database flags at all.
* **Deep dive** — the cohort that went on to a per-gene record.

The deep-dive box is not a clean set operation on the two lanes and is
not drawn as one: the sweep is an operational cohort (every
triage-positive gene, plus database-supported genes the agent rejected)
rather than a predicate. Its database-free composition is reported in
the caption, not on the canvas, so the figure stays readable.

Data sources (two, deliberately — see the note above ``_load``):
  data/processed/figures/zero_db_rescues_by_triage.tsv   whole proteome
  data/processed/figures/deep_dive_final_categories.tsv  deep-dive cohort

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

# Canvas in Figure 4's coordinate space (viewBox 0 0 1260 460).
CANVAS_W, CANVAS_H = 1260.0, 460.0

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

    deep_dive_ids = {row["hgnc_id"] for row in deep_dive}
    positives = [r for r in proteome if r["sonnet_verdict"] in POSITIVE_VERDICTS]

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
    )


def _card(ax, x, y, w, h, *, edge=MAROON, fill="white", lw=2.0, radius=10, z=2):
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
    fig, ax = plt.subplots(figsize=(14.0, 4.7))
    ax.set_xlim(0, CANVAS_W)
    ax.set_ylim(0, CANVAS_H)
    ax.invert_yaxis()  # top-left origin, like the SVG
    ax.axis("off")

    # ---- Box A: the input cohort -------------------------------------
    ax.text(
        24, 152, "Human protein-coding genes",
        ha="left", va="center", fontsize=13.5, color=MUTED, zorder=5,
    )
    ax.text(
        24, 196, f"{counts.proteome:,}",
        ha="left", va="center", fontsize=42, fontweight="bold",
        color=INK, zorder=5,
    )
    ax.text(
        24, 234, "every gene enters both lanes",
        ha="left", va="center", fontsize=12.5, color=EYEBROW, zorder=5,
    )

    # ---- Split from A into the two lanes -----------------------------
    junction = 344.0
    ax.plot([300, junction], [194, 194], color=INK, lw=2.6, zorder=4)
    ax.plot([junction, junction], [110, 322], color=INK, lw=2.6, zorder=4)
    _arrow(ax, (junction, 110), (416, 110))
    _arrow(ax, (junction, 322), (416, 322))

    # ---- Box B: the database lane ------------------------------------
    _card(ax, 420, 48, 372, 124)
    _eyebrow(ax, 444, 72, "FIVE REFERENCE DATABASES")
    _run(
        ax, 444, 114,
        [
            (f"{counts.db_union:,}", 34, "bold", INK),
            ("   flagged surface", 13, "normal", MUTED),
        ],
    )
    ax.text(
        444, 150, "UniProt \u00b7 GO CC \u00b7 HPA \u00b7 SURFY \u00b7 CSPA",
        ha="left", va="center", fontsize=12.5, color=MUTED, zorder=5,
    )
    _pill(ax, 736, 72, "no LLM", fill=TEAL, size=10)

    # ---- Box C: the triage lane --------------------------------------
    _card(ax, 420, 240, 372, 172)
    _eyebrow(ax, 444, 264, "ACCESSIBILITY TRIAGE AGENT")
    _run(
        ax, 444, 306,
        [
            (f"{counts.triage_positive:,}", 34, "bold", INK),
            ("   called surface", 13, "normal", MUTED),
        ],
    )
    ax.text(
        444, 342,
        f"{counts.triage_yes:,} yes \u00b7 {counts.triage_contextual:,} contextual",
        ha="left", va="center", fontsize=12.5, color=MUTED, zorder=5,
    )
    _pill(ax, 740, 264, "Sonnet", fill=MAROON_DARK, size=10)

    # The rescue slice, called out inside the triage card.
    _card(ax, 444, 356, 324, 44, edge=MAROON, fill=RESCUE_FILL,
          lw=1.6, radius=6, z=3)
    _run(
        ax, 462, 378,
        [
            (f"{counts.rescued:,}", 21, "bold", MAROON_DARK),
            ("  flagged by no database", 12.5, "normal", MAROON_DARK),
        ],
    )

    # ---- Merge into the deep dive ------------------------------------
    merge = 848.0
    _arrow(ax, (796, 110), (merge, 110))
    _arrow(ax, (796, 322), (merge, 322))
    ax.plot([merge, merge], [110, 322], color=INK, lw=2.6, zorder=4)
    _arrow(ax, (merge, 216), (908, 216))

    # ---- Box D: the deep dive ----------------------------------------
    _card(ax, 912, 134, 326, 164, fill=PANEL_FILL, edge=MAROON)
    _eyebrow(ax, 936, 162, "PER-GENE DEEP DIVE", color=TEAL)
    ax.text(
        936, 206, f"{counts.deep_dive:,}",
        ha="left", va="center", fontsize=42, fontweight="bold",
        color=INK, zorder=5,
    )
    ax.text(
        936, 244, "genes with a validated record",
        ha="left", va="center", fontsize=12.5, color=MUTED, zorder=5,
    )
    ax.text(
        936, 270, f"including all {counts.rescued:,} triage rescues",
        ha="left", va="center", fontsize=12.5, fontweight="bold",
        color=MAROON_DARK, zorder=5,
    )

    # Cutoff provenance: the union above is the bench-optimized one, not
    # Figure 1's native flags (5,546) \u2014 say so rather than let the two
    # figures look like they disagree.
    ax.text(
        24, 440,
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
        f"proteome={counts.proteome:,}  db_union={counts.db_union:,}  "
        f"triage+={counts.triage_positive:,} "
        f"({counts.triage_yes:,} yes / {counts.triage_contextual:,} ctx)  "
        f"rescued={counts.rescued:,}  deep_dive={counts.deep_dive:,} "
        f"({counts.deep_dive_db_free:,} db-free)"
    )
    fig = build(counts)
    save_figure(fig, "pipeline_funnel", OUT_DIR, formats=("pdf", "png"))
    plt.close(fig)


if __name__ == "__main__":
    main()
