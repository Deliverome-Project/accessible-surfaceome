# /// script
# requires-python = ">=3.11"
# dependencies = [
#   "matplotlib>=3.9",
#   "seaborn>=0.13",
#   "numpy>=1.26",
# ]
# ///
"""Reproduce ``db_overlap_upset.{pdf,png}`` from the public repo.

Figure 1 — UpSet over the five M1 surface databases. Each bar counts
the proteins found in that database or combination of databases and no
others; columns are grouped by how many databases list the protein,
running from all five on the left to a single database on the right.

Visual styling matches the in-repo `_plotting_config` (Deliverome
categorical palette + Manrope-when-available). Inlined so the gist
runs standalone.

Standalone — ``uv run make_db_overlap_upset.py``.
"""
from __future__ import annotations

import csv
import io
from pathlib import Path

import matplotlib.font_manager as fm
import matplotlib.pyplot as plt
import seaborn as sns
import numpy as np

REPO = "Deliverome-Project/accessible-surfaceome"
BRANCH = "main"
# Dedicated per-figure TSV: the five databases' INITIAL (pre-recalibration)
# surface flags, union members only, with stable IDs — NOT the
# whole-proteome catalog. Figure 1 is a databases-overlap figure, so it
# ships its own minimal input (built by scripts/build_figure_tsvs.py),
# free of the catalog's triage/optimized/universe_version columns.
CAND_URL = (
    f"https://raw.githubusercontent.com/{REPO}/{BRANCH}"
    f"/data/processed/figures/db_overlap_upset.tsv"
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


def load_flags(text: str):
    rows = [
        [1 if row[FLAG[n]] == "1" else 0 for n in ORDER]
        for row in csv.DictReader(io.StringIO(text), delimiter="\t")
    ]
    return np.asarray(rows, dtype=int)


def build_columns(flags):
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


def main() -> None:
    _apply_brand_style()
    # Same six knobs, same values, same dict form as the canonical
    # generator — the fingerprint guard reads the LAST occurrence from
    # each file. The brand defaults above are tuned for much larger
    # figures than this 12.5x7.4 panel.
    plt.rcParams.update({
        "font.size": 11,
        "axes.labelsize": 13,
        "axes.titlesize": 0,
        "xtick.labelsize": 11,
        "ytick.labelsize": 11,
        "legend.fontsize": 11,
    })
    flags = load_flags(_fetch_csv_text(CAND_URL))
    sel, sizes = build_columns(flags)

    sel, sizes = build_columns(flags)

    # Declared as a dict literal, and LAST, so the canonical<->mirror
    # fingerprint guard (tests/test_figure_canonical_mirror_sync.py) reads
    # the same six knobs from both files. The gist mirror re-declares this
    # exact block after its inline brand style, whose defaults are tuned
    # for much larger figures than this 12.5x7.4 panel.
    plt.rcParams.update({
        "font.size": 11,
        "axes.labelsize": 13,
        "axes.titlesize": 0,
        "xtick.labelsize": 11,
        "ytick.labelsize": 11,
        "legend.fontsize": 11,
    })

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

    sns.despine(ax=ax_bar, top=True, right=True)

    out = Path(__file__).parent
    fig.savefig(out / "db_overlap_upset.pdf", bbox_inches="tight",
                metadata={"Subject": GIST_URL})
    fig.savefig(out / "db_overlap_upset.png", bbox_inches="tight", dpi=600,
                metadata={"Source": GIST_URL})
    print(f"wrote {out/'db_overlap_upset.pdf'} and .png")


if __name__ == "__main__":
    main()
