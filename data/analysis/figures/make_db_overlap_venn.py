# /// script
# requires-python = ">=3.11"
# dependencies = [
#   "matplotlib>=3.9",
#   "seaborn>=0.13",
#   "venn>=0.1.3",
# ]
# ///
"""Reproduce ``db_overlap_venn.{pdf,png}`` from the public repo.

5-way topologically-correct ellipse Venn of the M1 surface-DB votes.
Reads ``candidate_universe.tsv`` from raw.githubusercontent.com and
renders one set per surface-prediction DB.

Visual styling matches the in-repo `_plotting_config` (Deliverome
categorical palette + Manrope-when-available). Inlined so the gist
runs standalone.

Standalone — ``uv run make_db_overlap_venn.py``.
"""
from __future__ import annotations

import csv
import io
from pathlib import Path

import matplotlib.font_manager as fm
import matplotlib.pyplot as plt
import seaborn as sns
from venn import venn

REPO = "Deliverome-Project/accessible-surfaceome"
BRANCH = "main"
# Dedicated per-figure TSV: the five databases' INITIAL (pre-recalibration)
# surface flags, union members only, with stable IDs — NOT the
# whole-proteome catalog. Figure 1 is a databases-overlap figure, so it
# ships its own minimal input (built by scripts/build_figure_tsvs.py),
# free of the catalog's triage/optimized/universe_version columns.
CAND_URL = (
    f"https://raw.githubusercontent.com/{REPO}/{BRANCH}"
    f"/data/processed/figures/db_overlap_venn.tsv"
)

# Published reproduction gist (embedded into output PNG Source / PDF
# Subject metadata — mirrors save_figure in _plotting_config.py).
GIST_URL = "https://gist.github.com/beccajcarlson/d655abfc9c7deeaff1cfbe584de96ffa"

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
            for path in sorted(list(fonts_dir.glob("*.ttf")) + list(fonts_dir.glob("*.otf"))):
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
    plt.rcParams.update({
        "savefig.dpi": 600,
        "savefig.bbox": "tight",
        "figure.facecolor": "none",
        "savefig.facecolor": "none",
        "font.family": "sans-serif",
        "font.sans-serif": ["Manrope", "Outfit", "DejaVu Sans", "Liberation Sans", "Arial"],
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
    })


DB_FLAGS = [
    ("uniprot_surface_flag", "UniProt"),
    ("go_surface_flag",      "GO CC"),
    ("hpa_surface_flag",     "HPA"),
    ("surfy_surface_flag",   "SURFY"),
    ("cspa_surface_flag",    "CSPA"),
]
# Brand categorical palette, in DB_FLAGS order.
PALETTE_BY_LABEL = {label: BRAND_PALETTE[i] for i, (_, label) in enumerate(DB_FLAGS)}


def _fetch_csv_text(url: str) -> str:
    """Bundled-only: the gist HEAD commit SHA is the SWHID for the
    whole reproduction unit (script + data + README), so we must
    never read a *different* TSV than what's bundled. Sibling-first
    (gist case); fall back to the in-repo TSV path (dev case). No
    network fetch — a missing sibling in a gist is a hard error."""
    sibling = Path(__file__).parent / Path(url).name
    if sibling.is_file():
        return sibling.read_text()
    local = Path(__file__).resolve().parents[3] / url[len(f"https://raw.githubusercontent.com/{REPO}/{BRANCH}/"):]
    if local.is_file():
        return local.read_text()
    raise FileNotFoundError(
        f"TSV not found at sibling ({sibling.name}) or local ({local}). "
        f"In a gist, the bundled TSV must sit next to this script."
    )


def main() -> None:
    _apply_brand_style()
    text = _fetch_csv_text(CAND_URL)
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

    fig, ax = plt.subplots(figsize=(11, 10))
    venn(sorted_sets, ax=ax, cmap=cmap, fontsize=22, legend_loc=None)
    ax.set_xticks([])
    ax.set_yticks([])
    sns.despine(ax=ax, top=True, right=True, bottom=True, left=True)

    # Hide intersection counts below MIN_DISPLAY — the 32 regions of a
    # 5-set Venn include many small sliver intersections (3-DB / 4-DB /
    # 5-DB cells with double-digit counts) whose labels collide with
    # neighboring labels visually and read as noise rather than
    # information. Suppress them; the per-DB totals still match the
    # legend's `n = X,XXX` chips and the figure caption.
    MIN_DISPLAY = 100
    for t in ax.texts:
        raw = t.get_text().strip().replace(",", "")
        try:
            if int(raw) < MIN_DISPLAY:
                t.set_text("")
        except ValueError:
            # Non-integer label (set name etc.) — preserve.
            continue

    handles = [
        plt.Rectangle((0, 0), 1, 1, color=PALETTE_BY_LABEL[k], alpha=0.6)
        for k in sorted_keys
    ]
    labels = [f"{k}  (n = {len(sets[k]):,})" for k in sorted_keys]
    # Two-row legend (ceil(N/2)) so the 5 DB chips fit at v3 fontsize
    # without overflowing the figure width. 5 entries → ncols=3 → 3-on-top
    # + 2-on-bottom rather than the v2 single-row layout that overflowed.
    ax.legend(
        handles, labels,
        loc="upper center", bbox_to_anchor=(0.5, -0.02),
        ncols=(len(sorted_keys) + 1) // 2, frameon=False, fontsize=21,
    )

    out_pdf = Path("db_overlap_venn.pdf")
    out_png = Path("db_overlap_venn.png")
    fig.savefig(out_pdf, bbox_inches="tight", metadata={"Subject": GIST_URL})
    fig.savefig(out_png, bbox_inches="tight", dpi=600, metadata={"Source": GIST_URL})
    print(f"Wrote {out_pdf} + {out_png}  ({sum(len(s) for s in sets.values()):,} "
          f"per-DB votes across {len(set().union(*sets.values())):,} unique proteins)")


if __name__ == "__main__":
    main()
