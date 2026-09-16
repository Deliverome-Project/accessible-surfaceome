"""UpSet over the five M1 surface databases — main-paper Figure 1.

Replaces the 5-way Venn in the numbered figure set. The Venn is not
area-proportional and cannot be made so: all 31 regions are non-empty and
span 3–1,063 proteins, and a least-squares fit of five ellipses to those
areas draws the 188-protein five-way core at 305 (+62%) while collapsing
the 252-protein UniProt∩SURFY∩CSPA region to 9. An UpSet has no such
constraint — every bar is a true count.

Three deliberate departures from a stock ``upsetplot`` render:

* **Ordered by degree, not cardinality.** Columns run "in all five
  databases" → "in one database", so the reader's eye travels down the
  agreement axis rather than the size axis.
* **Canonical per-DB colours** (see the canonical_db_palette convention)
  on the dot matrix, the row labels and the set-size bars, so a reader
  cross-referencing other figures sees UniProt maroon everywhere. A bar
  for a single database takes that database's colour; shared
  combinations stay neutral ink. The five-database consensus is the one
  highlight colour, deliberately outside the DB palette so it reads as
  emphasis and not as a sixth source.
* **An explicit column set** — the ten largest combinations plus every
  database-alone bar, so no source is missing its own exclusive count.

Note ``upsetplot`` is NOT used: it cannot order by descending degree,
colour per set, or take an arbitrary column subset, and its
``show_counts=True`` path is broken against matplotlib 3.9 (array-valued
text position). The matrix is drawn directly instead.

Outputs (PDF + PNG):
  data/analysis/figures/{db_overlap_upset}.{pdf,png}
"""

from __future__ import annotations

import csv
import io
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np

from accessible_surfaceome.audit._plotting_config import (
    save_figure,
    setup_plotting_style,
)
from accessible_surfaceome.paths import REPO_ROOT

OUT_DIR = REPO_ROOT / "data/analysis/figures"
# Shares the Venn's bundled TSV: identical five flags, one row per
# accession. Per the figure-TSV convention, fit a new figure into an
# existing TSV rather than adding another near-duplicate.
TSV = REPO_ROOT / "data/processed/figures/db_overlap_venn.tsv"

# Canonical DB-only order + canonical colours.
ORDER = ["UniProt", "SURFY", "CSPA", "GO CC", "HPA"]
COLOR = {
    "UniProt": "#BC3C4C",
    "SURFY": "#8878C8",
    "CSPA": "#6E1428",
    "GO CC": "#3D6B60",
    "HPA": "#F4AA28",
}
FLAG = {
    "UniProt": "uniprot_surface_flag",
    "SURFY": "surfy_surface_flag",
    "CSPA": "cspa_surface_flag",
    "GO CC": "go_surface_flag",
    "HPA": "hpa_surface_flag",
}
INK, OFF = "#1f1718", "#E4DAD6"
HILITE = "#E03131"
TOP_N = 10


def load_flags(path: Path) -> np.ndarray:
    """One row per accession, one boolean column per database in ORDER."""
    rows = []
    with path.open(encoding="utf-8") as fh:
        for row in csv.DictReader(io.StringIO(fh.read()), delimiter="\t"):
            rows.append([1 if row[FLAG[n]] == "1" else 0 for n in ORDER])
    return np.asarray(rows, dtype=int)


def build_columns(flags: np.ndarray):
    """Return (selected combinations, per-database set sizes).

    Combinations are the TOP_N largest plus every singleton, ordered by
    degree descending then size descending.
    """
    codes = (flags * (1 << np.arange(len(ORDER)))).sum(1)
    counts = np.bincount(codes, minlength=1 << len(ORDER))[1:]
    combos = [
        {
            "code": code,
            "members": tuple(i for i in range(len(ORDER)) if code >> i & 1),
            "n": int(counts[code - 1]),
        }
        for code in range(1, 1 << len(ORDER))
    ]
    by_size = sorted(combos, key=lambda c: -c["n"])
    keep = {c["code"] for c in by_size[:TOP_N]}
    keep |= {c["code"] for c in combos if len(c["members"]) == 1}
    sel = [c for c in combos if c["code"] in keep]
    sel.sort(key=lambda c: (-len(c["members"]), -c["n"]))
    sizes = {n: int(flags[:, i].sum()) for i, n in enumerate(ORDER)}
    return sel, sizes


def make_plot(out_dir: Path) -> None:
    flags = load_flags(TSV)
    sel, sizes = build_columns(flags)

    setup_plotting_style(style="white", context="notebook", font_scale=1.0)
    plt.rcParams["axes.labelsize"] = 13
    plt.rcParams["xtick.labelsize"] = 11
    plt.rcParams["ytick.labelsize"] = 11
    plt.rcParams["legend.fontsize"] = 11

    fig = plt.figure(figsize=(12.5, 7.4))
    gs = fig.add_gridspec(
        2, 2, width_ratios=[1.0, 4.3], height_ratios=[2.25, 1.55],
        wspace=0.30, hspace=0.06,
    )
    ax_bar = fig.add_subplot(gs[0, 1])
    ax_mat = fig.add_subplot(gs[1, 1], sharex=ax_bar)
    ax_set = fig.add_subplot(gs[1, 0])
    fig.add_subplot(gs[0, 0]).axis("off")

    x = np.arange(len(sel))
    heights = [c["n"] for c in sel]
    colors = [
        HILITE if len(c["members"]) == len(ORDER)
        else COLOR[ORDER[c["members"][0]]] if len(c["members"]) == 1
        else INK
        for c in sel
    ]
    ax_bar.bar(x, heights, color=colors, width=0.64)
    for xi, c in zip(x, sel):
        full = len(c["members"]) == len(ORDER)
        ax_bar.text(
            xi, c["n"] + 22, f"{c['n']:,}", ha="center", va="bottom",
            fontsize=10.5, fontweight="bold", color=HILITE if full else INK,
        )
    ax_bar.set_ylabel("Proteins found in\nonly these databases")
    ax_bar.set_ylim(0, max(heights) * 1.16)
    ax_bar.spines[["top", "right"]].set_visible(False)
    ax_bar.tick_params(labelbottom=False)
    ax_bar.grid(axis="y", alpha=0.25, lw=0.7)
    ax_bar.set_axisbelow(True)

    for i in range(len(ORDER)):
        ax_mat.axhspan(i - 0.5, i + 0.5,
                       color="#FBF7F4" if i % 2 == 0 else "white", zorder=0)
    for j, c in enumerate(sel):
        mem = list(c["members"])
        ax_mat.plot([j, j], [min(mem), max(mem)], color=INK, lw=2.4,
                    zorder=2, solid_capstyle="round")
        for i, name in enumerate(ORDER):
            ax_mat.plot(j, i, "o", ms=13, zorder=3,
                        color=COLOR[name] if i in mem else OFF)
    ax_mat.set_yticks(range(len(ORDER)))
    ax_mat.set_yticklabels(ORDER, fontsize=12.5, fontweight="bold")
    for tick, name in zip(ax_mat.get_yticklabels(), ORDER):
        tick.set_color(COLOR[name])
    ax_mat.tick_params(axis="y", length=0, pad=8)
    ax_mat.set_ylim(len(ORDER) - 0.5, -1.45)
    ax_mat.set_xlim(-0.7, len(sel) - 0.3)
    ax_mat.set_xticks([])
    for spine in ax_mat.spines.values():
        spine.set_visible(False)
    ax_mat.set_xlabel(
        "Grouped by how many of the five databases list the protein\n"
        "(each column counts proteins found in that database or combination of\n"
        "databases, and no others)",
        labelpad=12, fontsize=12,
    )

    ax_set.barh(range(len(ORDER)), [sizes[n] for n in ORDER],
                color=[COLOR[n] for n in ORDER], height=0.6)
    for i, name in enumerate(ORDER):
        ax_set.text(sizes[name] - 70, i, f"{sizes[name]:,}", va="center",
                    ha="left", fontsize=10, color="white", fontweight="bold")
    mean_size = float(np.mean([sizes[n] for n in ORDER]))
    # Rule stops below its own label rather than striking through it.
    ax_set.axvline(mean_size, color=INK, lw=1.6, ls=(0, (4, 3)), zorder=5,
                   ymin=0.0, ymax=0.90)
    ax_set.text(mean_size, -1.02, f"average database size\n{mean_size:,.0f}",
                ha="center", va="bottom", fontsize=9.5, color=INK,
                style="italic", zorder=6)
    ax_set.invert_xaxis()
    ax_set.set_xlabel("Set size")
    ax_set.set_yticks([])
    ax_set.set_ylim(len(ORDER) - 0.5, -1.45)
    ax_set.set_xlim(3600, 0)
    ax_set.spines[["top", "left", "right"]].set_visible(False)
    ax_set.grid(axis="x", alpha=0.25, lw=0.7)
    ax_set.set_axisbelow(True)

    degrees = [len(c["members"]) for c in sel]
    for j in range(1, len(sel)):
        if degrees[j] != degrees[j - 1]:
            for ax in (ax_bar, ax_mat):
                ax.axvline(j - 0.5, color="#CBBDB8", lw=1.0,
                           ls=(0, (3, 3)), zorder=1)
    for d in sorted(set(degrees), reverse=True):
        idx = np.where(np.asarray(degrees) == d)[0]
        ax_bar.text(idx.mean(), max(heights) * 1.10, f"{d}", ha="center",
                    fontsize=13, fontweight="bold",
                    color=HILITE if d == len(ORDER) else "#6f5d5a")

    out_dir.mkdir(parents=True, exist_ok=True)
    save_figure(fig, filename="db_overlap_upset", output_dir=str(out_dir),
                formats=("pdf", "png"))
    plt.close(fig)


def main() -> None:
    make_plot(OUT_DIR)


if __name__ == "__main__":
    main()
