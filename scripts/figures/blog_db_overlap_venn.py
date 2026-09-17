# /// script
# requires-python = ">=3.11"
# dependencies = [
#   "matplotlib>=3.9",
#   "seaborn>=0.13",
#   "venn>=0.1.3",
# ]
# ///
"""Blog figure — 5-way DB-overlap Venn with count-scaled labels.

NOT a numbered paper figure. Figure 1 is now ``db_overlap_upset`` (an
UpSet), because a five-set Venn cannot be drawn area-proportionally:
all 31 regions are non-empty and span 3-1,063 proteins, and the best
least-squares ellipse fit draws the 188-protein five-way core at 305
while collapsing a 252-protein region to 9. This Venn keeps its place
as a blog / talk visual, where "these five databases barely agree" has
to land in one glance rather than survive re-analysis.

The label treatment is Nirmit Damania's (PR #217): each region's count
is redundantly encoded in its TYPE SIZE, with a constrained search that
keeps every label inside its own region while shrinking the scale until
nothing collides.

**The counts are exact.** Only their type size is exaggerated — this is
emphasis, not a redrawn geometry, and every number printed is the real
region count straight out of the TSV. The point of the figure is that
the five-way core is small; inflating the core would defeat it.

The exaggeration is stronger here than in the paper-figure lineage:
``sqrt`` rather than ``log1p`` (log compresses 188-vs-1,063 to about
1.6x) and a wider font band, so the size difference reads across a
room. See ``LABEL_SCALE`` below.

Outputs:
  data/analysis/blog/blog_db_overlap_venn.{pdf,png}
"""

from __future__ import annotations

import csv
import io
import math
from pathlib import Path

import matplotlib.font_manager as fm
import matplotlib.pyplot as plt
import seaborn as sns
from matplotlib.text import Text
from matplotlib.transforms import Bbox
from venn import venn

REPO = "Deliverome-Project/accessible-surfaceome"
BRANCH = "main"
# Dedicated per-figure TSV: the five databases' INITIAL (pre-recalibration)
# surface flags, union members only, with stable IDs — NOT the
# whole-proteome catalog. Figure 1 is a databases-overlap figure, so it
# ships its own minimal input (built by scripts/build_figure_tsvs.py),
# free of the catalog's triage/optimized/universe_version columns.

# Published reproduction gist (embedded into output PNG Source / PDF
# Subject metadata — mirrors save_figure in _plotting_config.py).
# No gist: d655abfc now serves the UpSet (Figure 1). A blog figure is
# reproduced from this in-repo script.

# ──── Inline brand styling — sentinel: brand-style-v3 ────
# Mirrors src/accessible_surfaceome/audit/_plotting_config.py so the gist
# stays self-contained (no in-repo imports — Substack readers run it
# standalone). Kept in sync via tests/test_figure_gists_styling.py.
BRAND_PALETTE = [
    "#BC3C4C",  # maroon-light
    "#3D6B60",  # teal-mid
    "#F4AA28",  # amber-bright
    "#8878C8",  # lavender-bright
    "#6E1428",  # maroon-dark
    "#7AAB9F",  # teal-light
]
BRAND_SEQUENTIAL = {
    "maroon": ["#3E0A18", "#6E1428", "#922038", "#BC3C4C", "#F0A098", "#FDE8E6"],
    "teal": ["#152E28", "#244840", "#3D6B60", "#4D8A80", "#7AAB9F", "#CCE8E4"],
    "amber": ["#5A2608", "#8C4210", "#C07830", "#F4AA28", "#F4C070", "#FAECD4"],
    "lavender": ["#1E1450", "#3A2888", "#5848A8", "#8878C8", "#A090D4", "#E4E0F8"],
}
# Count -> label-size mapping. sqrt is deliberately less compressive than
# the log1p used in the paper-figure lineage: this is a blog visual whose
# whole job is to make the size gap obvious at a glance. The counts
# themselves are untouched — only the type size is exaggerated.
LABEL_SCALE = math.sqrt
# Widened from (10, 32). With sqrt this puts the 3-protein regions at the
# floor and the 1,063-protein HPA-only region at the ceiling, a ~6x span
# rather than ~3x.
LABEL_FONT_BAND = (9.0, 56.0)

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
            for path in sorted(
                list(fonts_dir.glob("*.ttf")) + list(fonts_dir.glob("*.otf"))
            ):
                try:
                    fm.fontManager.addfont(str(path))
                except Exception:  # noqa: BLE001
                    continue
            return


def _apply_brand_style() -> None:
    """Inline equivalent of `setup_plotting_style`. Sentinel: brand-style-v3.
    v2: bumped sizes ~25% + explicit medium weight (avoids ExtraLight default
    that matplotlib picks from the Manrope variable file). Companion to the
    static Manrope-{regular,medium,semibold,bold}.otf files in assets/fonts/."""
    _register_brand_fonts()
    sns.set_style("whitegrid")
    sns.set_context("notebook", font_scale=1.0)
    plt.rcParams.update(
        {
            "savefig.dpi": 600,
            "savefig.bbox": "tight",
            "figure.facecolor": "none",
            "savefig.facecolor": "none",
            "font.family": "sans-serif",
            "font.sans-serif": [
                "Manrope",
                "Outfit",
                "DejaVu Sans",
                "Liberation Sans",
                "Arial",
            ],
            "font.weight": "medium",
            "font.size": 21,
            "axes.labelsize": 25,
            "axes.labelweight": "medium",
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
            "xtick.labelsize": 20,
            "ytick.labelsize": 20,
            "xtick.color": BRAND_INK,
            "ytick.color": BRAND_INK,
            "legend.frameon": False,
            "legend.fontsize": 20,
            "patch.edgecolor": "none",
            "patch.linewidth": 0.0,
        }
    )


DB_FLAGS = [
    ("uniprot_surface_flag", "UniProt"),
    ("go_surface_flag", "GO CC"),
    ("hpa_surface_flag", "HPA"),
    ("surfy_surface_flag", "SURFY"),
    ("cspa_surface_flag", "CSPA"),
]
# Brand categorical palette, in DB_FLAGS order.
PALETTE_BY_LABEL = {label: BRAND_PALETTE[i] for i, (_, label) in enumerate(DB_FLAGS)}


def _fetch_csv_text(_url: str = "") -> str:
    """Read the per-figure TSV from the repo.

    This is an in-repo canonical generator, not a gist mirror, so the
    sibling-first / network fallback the mirrors carry does not apply —
    the TSV is always a fixed path relative to the repo root.
    """
    tsv = Path(__file__).resolve().parents[2] / "data/processed/figures/db_overlap_venn.tsv"
    if not tsv.is_file():
        raise FileNotFoundError(f"figure TSV not found at {tsv}")
    return tsv.read_text(encoding="utf-8")

def main() -> None:
    _apply_brand_style()
    text = _fetch_csv_text()
    sets: dict[str, set[str]] = {label: set() for _, label in DB_FLAGS}
    reader = csv.DictReader(io.StringIO(text), delimiter="\t")
    for row in reader:
        acc = row["uniprot_acc"]
        for flag, label in DB_FLAGS:
            if row.get(flag, "0") == "1":
                sets[label].add(acc)

    sorted_keys = sorted(sets, key=lambda k: -len(sets[k]))
    sorted_sets = {k: sets[k] for k in sorted_keys}
    cmap = [PALETTE_BY_LABEL[k] for k in sorted_keys]

    fig, ax = plt.subplots(figsize=(17, 14))
    venn(sorted_sets, ax=ax, cmap=cmap, fontsize=22, legend_loc=None)
    # Leave print-safe space around labels at the ellipse perimeter.
    ax.margins(x=0.18, y=0.10)
    ax.set_xticks([])
    ax.set_yticks([])
    sns.despine(ax=ax, top=True, right=True, bottom=True, left=True)

    # Redundantly encode protein count in the label size. Log scaling
    # preserves visible differences across the wide count range without
    # making small intersections unreadable or large labels overwhelming.
    numeric_labels: list[tuple[Text, int]] = []
    for t in ax.texts:
        raw = t.get_text().strip().replace(",", "")
        try:
            numeric_labels.append((t, int(raw)))
        except ValueError:
            # Non-integer label (set name etc.) — preserve.
            continue

    if numeric_labels:
        # sqrt, not log1p. log squashes the thing the figure exists to show:
        # across this data it maps 188 -> 0.69 of the band and 1,063 -> 1.0,
        # so the five-way core reads nearly as large as the biggest region.
        # sqrt keeps small regions legible while letting the large ones
        # actually dominate. Swap LABEL_SCALE to change the emphasis.
        scaled = [LABEL_SCALE(value) for _, value in numeric_labels]
        log_values = scaled
        low, high = min(scaled), max(scaled)
        min_font, max_font = LABEL_FONT_BAND
        proportions = [
            (log_value - low) / (high - low) if high > low else 0.5
            for log_value in log_values
        ]
        for text_artist, value in numeric_labels:
            text_artist.set_fontweight("bold")
            text_artist.set_text(f"{value:,}")
            text_artist.set_zorder(20)
            text_artist.set_color("black")
            text_artist.set_clip_on(False)

        # Keep each label in its correct Venn region while searching for the
        # widest collision-free font range. A candidate movement is accepted
        # only when the label center retains its original five-ellipse
        # membership signature. One monotonic scale is applied to every count,
        # so larger counts can never appear in smaller type.
        text_artists = [text_artist for text_artist, _ in numeric_labels]
        # Finalize the equal-aspect axes transform before converting label
        # coordinates to display pixels for the constrained search.
        fig.canvas.draw()
        original_data_positions = [
            text_artist.get_position() for text_artist in text_artists
        ]
        original_display_positions = [
            tuple(ax.transData.transform(position))
            for position in original_data_positions
        ]
        ellipse_patches = tuple(ax.patches)
        region_signatures = [
            tuple(patch.contains_point(display_position) for patch in ellipse_patches)
            for display_position in original_display_positions
        ]
        collisions: list[tuple[int, int]] = []
        renderer = None
        selected_max = min_font
        range_steps = int((max_font - min_font) / 0.5) + 1
        for range_step in range(range_steps):
            candidate_max = max_font - range_step * 0.5
            for text_artist, proportion, original_position in zip(
                text_artists,
                proportions,
                original_data_positions,
                strict=True,
            ):
                text_artist.set_position(original_position)
                text_artist.set_fontsize(
                    min_font + proportion * (candidate_max - min_font)
                )

            fig.canvas.draw()
            renderer = fig.canvas.get_renderer()
            axes_box = ax.get_window_extent(renderer=renderer)
            original_boxes = [
                text_artist.get_window_extent(renderer=renderer).expanded(1.02, 1.08)
                for text_artist in text_artists
            ]
            candidate_positions: list[list[tuple[float, float]]] = []
            candidate_boxes: list[list[Bbox]] = []
            for index, (origin, original_box, signature) in enumerate(
                zip(
                    original_display_positions,
                    original_boxes,
                    region_signatures,
                    strict=True,
                )
            ):
                positions: list[tuple[float, float]] = []
                boxes_for_label: list[Bbox] = []
                for radius in range(0, 41, 4):
                    angle_steps = (0,) if radius == 0 else range(24)
                    for angle_step in angle_steps:
                        angle = math.tau * angle_step / 24
                        candidate = (
                            origin[0] + radius * math.cos(angle),
                            origin[1] + radius * math.sin(angle),
                        )
                        if (
                            tuple(
                                patch.contains_point(candidate)
                                for patch in ellipse_patches
                            )
                            != signature
                        ):
                            continue
                        dx, dy = candidate[0] - origin[0], candidate[1] - origin[1]
                        candidate_box = Bbox.from_extents(
                            original_box.x0 + dx,
                            original_box.y0 + dy,
                            original_box.x1 + dx,
                            original_box.y1 + dy,
                        )
                        if not (
                            axes_box.contains(candidate_box.x0, candidate_box.y0)
                            and axes_box.contains(candidate_box.x1, candidate_box.y1)
                        ):
                            continue
                        positions.append(candidate)
                        boxes_for_label.append(candidate_box)
                candidate_positions.append(positions)
                candidate_boxes.append(boxes_for_label)

            selected_candidates = [0] * len(text_artists)
            boxes = [boxes_for_label[0] for boxes_for_label in candidate_boxes]
            for _ in range(60):
                changed = False
                for index in range(len(text_artists)):
                    best_candidate = selected_candidates[index]
                    best_score: tuple[int, float, float] | None = None
                    for candidate_index, candidate_box in enumerate(
                        candidate_boxes[index]
                    ):
                        overlap_count = 0
                        overlap_area = 0.0
                        for other_index, other_box in enumerate(boxes):
                            if other_index == index:
                                continue
                            overlap_width = max(
                                0.0,
                                min(candidate_box.x1, other_box.x1)
                                - max(candidate_box.x0, other_box.x0),
                            )
                            overlap_height = max(
                                0.0,
                                min(candidate_box.y1, other_box.y1)
                                - max(candidate_box.y0, other_box.y0),
                            )
                            if overlap_width and overlap_height:
                                overlap_count += 1
                                overlap_area += overlap_width * overlap_height
                        candidate_position = candidate_positions[index][candidate_index]
                        movement = (
                            candidate_position[0] - original_display_positions[index][0]
                        ) ** 2 + (
                            candidate_position[1] - original_display_positions[index][1]
                        ) ** 2
                        score = (overlap_count, overlap_area, movement)
                        if best_score is None or score < best_score:
                            best_score = score
                            best_candidate = candidate_index
                    if best_candidate != selected_candidates[index]:
                        selected_candidates[index] = best_candidate
                        boxes[index] = candidate_boxes[index][best_candidate]
                        changed = True

                collisions = [
                    (i, j)
                    for i, first in enumerate(boxes)
                    for j, second in enumerate(boxes[i + 1 :], start=i + 1)
                    if first.overlaps(second)
                ]
                if not collisions or not changed:
                    break

            if collisions:
                continue

            inverse_transform = ax.transData.inverted()
            for text_artist, positions, candidate_index in zip(
                text_artists,
                candidate_positions,
                selected_candidates,
                strict=True,
            ):
                text_artist.set_position(
                    inverse_transform.transform(positions[candidate_index])
                )

            # Validate the actual rendered boxes after applying all moves.
            fig.canvas.draw()
            renderer = fig.canvas.get_renderer()
            boxes = [
                text_artist.get_window_extent(renderer=renderer).expanded(1.02, 1.08)
                for text_artist in text_artists
            ]
            collisions = [
                (i, j)
                for i, first in enumerate(boxes)
                for j, second in enumerate(boxes[i + 1 :], start=i + 1)
                if first.overlaps(second)
            ]
            if not collisions:
                selected_max = candidate_max
                break

        assert renderer is not None
        if collisions:
            raise RuntimeError(
                "Venn label collision remains at uniform 14-point type: "
                + ", ".join(
                    f"{text_artists[i].get_text()} / {text_artists[j].get_text()}"
                    for i, j in collisions
                )
            )
        print(
            f"Selected collision-free monotonic font range: "
            f"{min_font:.1f}–{selected_max:.1f} pt"
        )

    handles = [
        plt.Rectangle((0, 0), 1, 1, color=PALETTE_BY_LABEL[k], alpha=0.6)
        for k in sorted_keys
    ]
    labels = [f"{k}  (n = {len(sets[k]):,})" for k in sorted_keys]
    # Two-row legend (ceil(N/2)) so the 5 DB chips fit at v3 fontsize
    # without overflowing the figure width. 5 entries → ncols=3 → 3-on-top
    # + 2-on-bottom rather than the v2 single-row layout that overflowed.
    ax.legend(
        handles,
        labels,
        loc="upper center",
        bbox_to_anchor=(0.5, -0.02),
        ncols=(len(sorted_keys) + 1) // 2,
        frameon=False,
        fontsize=21,
    )

    out_dir = Path(__file__).resolve().parents[2] / "data/analysis/blog"
    out_dir.mkdir(parents=True, exist_ok=True)
    out_pdf = out_dir / "blog_db_overlap_venn.pdf"
    out_png = out_dir / "blog_db_overlap_venn.png"
    fig.savefig(
        out_pdf,
        bbox_inches="tight",
        pad_inches=0.3,
    )
    fig.savefig(
        out_png,
        bbox_inches="tight",
        pad_inches=0.3,
        dpi=600,
    )
    print(
        f"Wrote {out_pdf} + {out_png}  ({sum(len(s) for s in sets.values()):,} "
        f"per-DB votes across {len(set().union(*sets.values())):,} unique proteins)"
    )


if __name__ == "__main__":
    main()
