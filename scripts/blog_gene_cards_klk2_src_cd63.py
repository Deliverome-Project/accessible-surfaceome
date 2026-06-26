"""Blog gene cards for KLK2, SRC, CD63 — three deep-dive contribution modes.

Visual design matches the viewer (https://surfaceome.deliverome.org/{SYMBOL}):

  * editorial register — no boxy card backgrounds, just clean columns
    with hairline separators between sections
  * Playfair Display for the gene symbols (maroon-deepest), Manrope
    for everything else (sourced via _plotting_config.register_bundled_fonts)
  * outlined StatusPill-style chips — transparent fill, tone-colored
    border + UPPERCASE text. Tones reach into the design-token palette
    (var(--maroon-light), --teal-mid, etc.); no per-pill hex codes
  * ChipLabelValue format for vitals — dim label, bold UPPERCASE value
    at the SAME font size (emphasis by weight/case, not size)
  * brand DB-source colors that match make_db_correctness_by_class.py
    so a reader scanning between figures gets the SAME color for the
    SAME source

Structure rendering: each gene's AlphaFold canonical PDB is fetched
from AFDB (cached under data/external/alphafold_db_structures/),
parsed for Cα coordinates with Bio.PDB, and rendered as a 3D backbone
trace colored by DeepTMHMM per-residue topology (the same palette the
viewer's 3Dmol renderer uses — TM=#FFD579, OUT=#8878C8, IN=#A9CFA8,
SP=#DD5955).

Three contrasting topologies illustrate three contrasting deep-dive
contribution modes:

  * KLK2 (P20151) — secreted serine protease, all extracellular after
    signal cleavage. 0/5 DBs flagged it; Sonnet+rescue caught the
    tissue-restricted prostate-surface display.
  * SRC (P12931) — N-terminal myristoyl anchor, otherwise cytoplasmic
    (all "I" in DeepTMHMM). 2/5 DBs over-called surface; deep-dive
    nuanced the call to lysosomal_exocytosis.
  * CD63 (P08962) — 4-TM tetraspanin (LAMP-3). 4/5 DBs flagged as
    canonical surface; deep-dive refined to lysosomal_exocytosis with
    high state-dependence.

Run:
    uv run python scripts/blog_gene_cards_klk2_src_cd63.py
"""
from __future__ import annotations

import json
import textwrap
import urllib.request
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
from matplotlib.patches import FancyBboxPatch
from mpl_toolkits.mplot3d.art3d import Line3DCollection

from accessible_surfaceome.audit._plotting_config import (
    register_bundled_fonts,
    save_figure,
    setup_plotting_style,
)

ROOT = Path(__file__).resolve().parents[1]
OUT_DIR = ROOT / "data/analysis/figures"
SLUG = "blog_gene_cards_klk2_src_cd63"
PDB_CACHE = ROOT / "data/external/alphafold_db_structures"


# ── Design-token mirror (viewer/app/design-tokens.css) ───────────────
# Single source of truth in the viewer is `:root` in design-tokens.css.
# We mirror only the tokens this figure reaches into; the canonical
# pinning convention (no per-figure hex) is the SAME rule as the viewer's
# component CSS.
TOK = {
    "maroon_deepest": "#3e0a18",
    "maroon_dark":    "#6e1428",
    "maroon_light":   "#bc3c4c",
    "teal_mid":       "#3d6b60",
    "teal_lt":        "#7aab9f",
    "amber_mid":      "#c07830",
    "amber_bright":   "#f4aa28",
    "lavender_bright":"#8878c8",
    "green_success":  "#2E7A55",
    "ink":            "#1f1718",
    "muted":          "#6f5d5a",
    "line":           "#E6DAD4",
    "bg_warm":        "#f3ece5",
}

# Viewer's TOPOLOGY_COLORS (from viewer/lib/structure-viewer-types.ts).
# Pinned to the exact hex — these are the same colors 3Dmol paints
# residues with on the live viewer.
TOPO_COLOR = {
    "M": "#FFD579",  # TM helix
    "O": "#8878C8",  # extracellular
    "I": "#A9CFA8",  # intracellular
    "S": "#DD5955",  # signal peptide
    "B": "#C7CED6",  # beta-strand
}
MEMBRANE_COLOR = "#A0A4AB"

# Brand source-color palette — must match make_db_correctness_by_class.py
# + make_topology_coverage_by_source.py so a reader gets the same color
# for the same source across the figure family.
DB_COLOR = {
    "UniProt": "#BC3C4C",
    "GO":      "#3D6B60",
    "HPA":     "#F4AA28",
    "SURFY":   "#8878C8",
    "CSPA":    "#6E1428",
}

# Verdict tone — mirrors the viewer's StatusPill tone families.
VERDICT_TONE = {
    "yes":        TOK["green_success"],
    "contextual": TOK["amber_mid"],
    "no":         TOK["muted"],
}

# Mapping from filter value → outlined-pill tone color. Filtered
# vocabulary mirrors the viewer's catalog preset toolbar.
ACCESS_TONE = {
    "high":     TOK["green_success"],
    "moderate": TOK["amber_mid"],
    "low":      TOK["muted"],
    "no":       TOK["maroon_dark"],
}
CONF_TONE = {"high": TOK["green_success"], "moderate": TOK["amber_mid"], "low": TOK["muted"]}
STATE_TONE = {
    "high":     TOK["amber_mid"],
    "moderate": TOK["amber_bright"],
    "low":      TOK["green_success"],
    "unclear":  TOK["muted"],
}
EXPR_TONE = {
    "pan_tissue": TOK["green_success"],
    "broad":      TOK["amber_bright"],
    "restricted": TOK["amber_mid"],
    "rare":       TOK["maroon_light"],
}


# ── Per-gene data ────────────────────────────────────────────────────
#
# Pulled from the committed records (viewer/public/data/surfaceome/*.json)
# + the catalog (data/processed/catalog/whole_proteome_catalog.tsv).
# `topology` is the DeepTMHMM per-residue string we'll feed into the
# Cα-trace colorer. KLK2 isn't in the deeptmhmm_surfaceome_predictions
# `.3line` (secreted proteins are filtered out at the cohort level) —
# treated here as S for the signal peptide (residues 1-17 per UniProt
# P20151 annotation) and O for the mature secreted protein.
GENES = [
    {
        "symbol": "KLK2",
        "name": "Kallikrein-2",
        "uniprot": "P20151",
        "lede": (
            "Secreted serine protease; a 2025 study (PMC12580770) demonstrates "
            "surface accessibility on prostate cancer cells via live-cell FACS, "
            "confocal IF, and three distinct therapeutic modalities."
        ),
        "topology_str": "S" * 17 + "O" * 244,   # SP + mature secreted
        "story": "0/5 DBs missed it — Sonnet+rescue caught it",
        "surface_accessibility": "moderate",
        "confidence":            "moderate",
        "state_dependence":      "high",
        "expression_breadth":    "rare",
        "db_flags":      {"UniProt": 0, "GO": 0, "HPA": 0, "SURFY": 0, "CSPA": 0},
        "sonnet_verdict": "contextual",
        "sonnet_reason":  "tissue_restricted_surface",
    },
    {
        "symbol": "SRC",
        "name": "Proto-oncogene tyrosine kinase Src",
        "uniprot": "P12931",
        "lede": (
            "N-terminal myristoyl anchor tethers SRC to the inner leaflet; "
            "DBs read this as cytoplasmic. Deep-dive flagged context-dependent "
            "lysosomal-exocytosis surface display."
        ),
        "topology_str": "I" * 536,
        "story": "2/5 DBs over-called — deep-dive nuanced",
        "surface_accessibility": "moderate",
        "confidence":            "low",
        "state_dependence":      "high",
        "expression_breadth":    "broad",
        "db_flags":      {"UniProt": 0, "GO": 1, "HPA": 1, "SURFY": 0, "CSPA": 0},
        "sonnet_verdict": "no",
        "sonnet_reason":  "inner_leaflet_anchored",
    },
    {
        "symbol": "CD63",
        "name": "Tetraspanin-30 (LAMP-3)",
        "uniprot": "P08962",
        # From data/external/deeptmhmm_surfaceome_predictions/.../predicted_topologies.3line
        "topology_str": (
            "IIIIIIIIIIII"                                          # 1-12 I
            "MMMMMMMMMMMMMMMMMMMMM"                                 # 13-33 TM1
            "OOOOOOOOOOOOOOOOOO"                                    # 34-51 O
            "MMMMMMMMMMMMMMMMMMMMMMM"                               # 52-74 TM2
            "IIIIIIIII"                                              # 75-83 I
            "MMMMMMMMMMMMMMMMMMMMMMM"                                # 84-106 TM3
            "OOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOO"  # 107-204 LEL
            "MMMMMMMMMMMMMMMMMMMMMMM"                                # 205-227 TM4
            "IIIIIIIIIIIII"                                          # 228-240 I
        ),
        "lede": (
            "4-TM tetraspanin, lysosomal in steady state but heavily "
            "exocytosed to the cell surface during membrane trafficking. "
            "DBs flagged classical surface; deep-dive added the context."
        ),
        "story": "4/5 DBs called surface — deep-dive added context",
        "surface_accessibility": "high",
        "confidence":            "high",
        "state_dependence":      "high",
        "expression_breadth":    "pan_tissue",
        "db_flags":      {"UniProt": 1, "GO": 1, "HPA": 0, "SURFY": 1, "CSPA": 1},
        "sonnet_verdict": "contextual",
        "sonnet_reason":  "lysosomal_exocytosis",
    },
]


# ── PDB fetch + Cα extraction ────────────────────────────────────────


def _fetch_pdb(uniprot_acc: str) -> Path:
    """Download AFDB PDB to ``data/external/alphafold_db_structures/`` if
    not cached, return the local path. Pinned to ``v6`` to match
    LATEST_KNOWN_AFDB_VERSION in viewer/lib/structure-viewer-types.ts —
    the viewer fetches the same URL at view time via 3Dmol."""
    PDB_CACHE.mkdir(parents=True, exist_ok=True)
    local = PDB_CACHE / f"AF-{uniprot_acc}-F1-model_v6.pdb"
    if local.is_file():
        return local
    url = f"https://alphafold.ebi.ac.uk/files/AF-{uniprot_acc}-F1-model_v6.pdb"
    print(f"  fetching {url} …")
    with urllib.request.urlopen(url, timeout=60) as r:
        data = r.read()
    local.write_bytes(data)
    return local


def _extract_ca(pdb_path: Path) -> np.ndarray:
    """Parse the PDB file and return Cα coords as an (N, 3) array.
    Uses Bio.PDB; quiet warnings about partial atoms."""
    import warnings
    from Bio.PDB import PDBParser
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        parser = PDBParser(QUIET=True)
        struct = parser.get_structure("X", str(pdb_path))
    coords: list[tuple[float, float, float]] = []
    for atom in struct.get_atoms():
        if atom.get_name() == "CA":
            x, y, z = atom.get_coord()
            coords.append((float(x), float(y), float(z)))
    return np.asarray(coords)


def _topology_colors(topology_str: str, n: int) -> list[str]:
    """Per-residue color array, matching the structure to the topology
    string. If the strings differ in length (rare — PDB sometimes drops
    terminal residues), pad / truncate to match."""
    s = topology_str
    if len(s) < n:
        s = s + "I" * (n - len(s))
    elif len(s) > n:
        s = s[:n]
    return [TOPO_COLOR.get(ch, TOK["muted"]) for ch in s]


def _render_structure(ax, gene: dict) -> None:
    """Render the Cα trace as a 3D backbone colored by DeepTMHMM
    topology. Axes are stripped (no ticks, no spines, no background)
    so the structure reads as a clean schematic, matching the viewer's
    structure-card aesthetic. Camera angle chosen empirically per
    gene to expose the topology meaningfully."""
    try:
        pdb = _fetch_pdb(gene["uniprot"])
        ca = _extract_ca(pdb)
    except Exception as exc:  # noqa: BLE001 — network / parse failures
        # Axes3D.text needs (x, y, z, s); use text2D which behaves like
        # the regular Axes.text for our fallback string.
        ax.text2D(0.5, 0.5, f"({gene['uniprot']} structure unavailable: {exc})",
                  ha="center", va="center", transform=ax.transAxes,
                  fontsize=8, color=TOK["muted"])
        ax.set_axis_off()
        return

    n = len(ca)
    colors = _topology_colors(gene["topology_str"], n)

    # Center coords around origin so each gene renders at the same
    # visual scale regardless of absolute coordinates.
    ca = ca - ca.mean(axis=0)
    span = np.max(np.ptp(ca, axis=0))
    if span > 0:
        ca = ca * (40.0 / span)

    # Backbone as a Line3DCollection — colored per-segment by the
    # residue at the segment's start. Smooth visually since adjacent
    # residues usually share topology bucket.
    segs = np.stack([ca[:-1], ca[1:]], axis=1)
    seg_colors = colors[:-1]
    lc = Line3DCollection(segs, colors=seg_colors, linewidths=2.6, alpha=0.95)
    ax.add_collection3d(lc)

    # Cα atoms as small markers (sized down for non-TM, up for TM so
    # the helices read clearly).
    sizes = [22 if c == TOPO_COLOR["M"] else 10 for c in colors]
    ax.scatter(ca[:, 0], ca[:, 1], ca[:, 2], c=colors, s=sizes,
               edgecolors="none", alpha=0.95, depthshade=False)

    # Translucent membrane slab for TM-containing genes. Drawn as a
    # horizontal plane at the mid-z of the TM residues so the helices
    # visibly cross it (matches the viewer's bilayer-slab rendering).
    tm_mask = np.array([c == TOPO_COLOR["M"] for c in colors])
    if tm_mask.any():
        tm_z = ca[tm_mask, 2]
        z_mid = float(np.median(tm_z))
        z_half = 7.0  # half-thickness of the slab in coord units
        xx, yy = np.meshgrid(
            np.linspace(ca[:, 0].min() - 4, ca[:, 0].max() + 4, 2),
            np.linspace(ca[:, 1].min() - 4, ca[:, 1].max() + 4, 2),
        )
        for z in (z_mid - z_half, z_mid + z_half):
            ax.plot_surface(xx, yy, np.full_like(xx, z),
                            color=MEMBRANE_COLOR, alpha=0.12,
                            shade=False, edgecolor="none")

    # Camera + axis cleanup.
    ax.set_xticks([]); ax.set_yticks([]); ax.set_zticks([])
    ax.set_xlabel(""); ax.set_ylabel(""); ax.set_zlabel("")
    for axis in (ax.xaxis, ax.yaxis, ax.zaxis):
        axis.set_pane_color((1.0, 1.0, 1.0, 0.0))
        axis.line.set_color((1.0, 1.0, 1.0, 0.0))
    ax.set_facecolor("none")
    ax.grid(False)
    # Equal aspect-ish on all three axes so the structure isn't squished.
    lim = 24
    ax.set_xlim(-lim, lim); ax.set_ylim(-lim, lim); ax.set_zlim(-lim, lim)
    ax.view_init(elev=18, azim=-60)


# ── Outlined-pill primitives (mirror viewer's StatusPill) ────────────


def _outlined_pill(ax, x, y, w, h, text, tone, fs=8.5,
                   tx=None, *, transform=None):
    """Outlined StatusPill — transparent fill, tone-colored border,
    tone-colored UPPERCASE text. ``tone`` controls both border and
    text color. ``transform`` defaults to ax.transAxes."""
    if transform is None:
        transform = ax.transAxes
    box = FancyBboxPatch(
        (x, y), w, h,
        boxstyle="round,pad=0,rounding_size=0.025",
        facecolor="none", edgecolor=tone, lw=1.2,
        transform=transform, clip_on=False,
    )
    ax.add_patch(box)
    if tx is None:
        tx = x + w / 2
    ax.text(tx, y + h / 2, text.upper(),
            ha="center", va="center", fontsize=fs,
            color=tone, fontweight="medium",
            transform=transform, clip_on=False,
            family="Manrope")


def _label_value_chip(ax, x, y, w, h, label, value, tone, fs=9):
    """ChipLabelValue: "LABEL · VALUE" — label dim, value bold UPPERCASE.
    Same size, emphasis by weight/case. Outlined pill carries them."""
    box = FancyBboxPatch(
        (x, y), w, h,
        boxstyle="round,pad=0,rounding_size=0.025",
        facecolor="none", edgecolor=TOK["line"], lw=1.0,
        transform=ax.transAxes, clip_on=False,
    )
    ax.add_patch(box)
    # Label dim + normal weight
    ax.text(x + 0.024, y + h / 2, label.upper(),
            ha="left", va="center", fontsize=fs, color=TOK["muted"],
            fontweight="normal", alpha=0.85,
            transform=ax.transAxes, clip_on=False, family="Manrope")
    # Separator dot
    ax.text(x + 0.025 + 0.075, y + h / 2, "·",
            ha="left", va="center", fontsize=fs, color=TOK["muted"],
            alpha=0.55, transform=ax.transAxes, family="Manrope")
    # Value: bold UPPERCASE, tone-colored
    ax.text(x + w - 0.024, y + h / 2, value.upper().replace("_", " "),
            ha="right", va="center", fontsize=fs, color=tone,
            fontweight="bold",
            transform=ax.transAxes, clip_on=False, family="Manrope")


# ── Column render ────────────────────────────────────────────────────


def _render_column(fig, gene: dict, x_left: float, col_width: float) -> None:
    """One vertical column for one gene. Layout (top → bottom):

        symbol  (Playfair Display, large, maroon-deepest)
        name + UniProt link  (Manrope, muted)
        lede paragraph  (Manrope, ink, 3-line cap)
        ─── hairline ───
        structure  (3D Cα backbone trace, viewer-color topology)
        ─── hairline ───
        VITALS strip  (4 ChipLabelValue chips)
        DB strip  (5 outlined source chips, filled if called)
        Sonnet verdict pill  (one tone-filled pill)
        story line  (italic muted)
    """
    # We use a vertical strip of "phantom" axes for each section to
    # bypass gridspec's rigidity. Each phantom is positioned in
    # figure coords; the inset 3D axes is attached to the structure
    # phantom.
    #
    # Section y-positions in figure coords, top-aligned. Heights tuned
    # so the figure exports at 15×11.
    def axes_at(y_bottom, height):
        return fig.add_axes((x_left, y_bottom, col_width, height))

    # ── Symbol + name + UniProt + lede ───────────────────────────────
    text_ax = axes_at(0.72, 0.26)
    text_ax.axis("off")
    text_ax.set_xlim(0, 1); text_ax.set_ylim(0, 1)
    text_ax.text(0.5, 0.88, gene["symbol"],
                 transform=text_ax.transAxes,
                 ha="center", va="center",
                 fontsize=46, fontweight="bold",
                 color=TOK["maroon_deepest"], family="Playfair Display")
    text_ax.text(0.5, 0.66, gene["name"],
                 transform=text_ax.transAxes,
                 ha="center", va="center",
                 fontsize=11, color=TOK["ink"],
                 family="Manrope", fontweight="medium")
    text_ax.text(0.5, 0.58, f"UniProt  {gene['uniprot']}",
                 transform=text_ax.transAxes,
                 ha="center", va="center",
                 fontsize=8.5, color=TOK["muted"],
                 family="Manrope", fontweight="normal")
    # Lede — Manrope, ink, italic for the editorial register.
    # matplotlib's ``wrap=True`` is unreliable for multi-line text in
    # nested axes; pre-wrap with textwrap so line breaks are explicit
    # and the lede sits as a 4-5-line paragraph.
    wrapped = textwrap.fill(gene["lede"], width=50)
    text_ax.text(0.5, 0.30, wrapped,
                 transform=text_ax.transAxes,
                 ha="center", va="center",
                 fontsize=8.5, color=TOK["ink"],
                 family="Manrope", style="italic",
                 linespacing=1.4)

    # Hairline separator
    sep_ax = axes_at(0.715, 0.003)
    sep_ax.axhline(0.5, color=TOK["line"], lw=0.8)
    sep_ax.axis("off")

    # ── 3D structure — real AFDB Cα trace ────────────────────────────
    struct_ax = fig.add_axes((x_left + 0.005, 0.38, col_width - 0.01, 0.32),
                             projection="3d")
    _render_structure(struct_ax, gene)

    # Hairline separator
    sep_ax2 = axes_at(0.375, 0.003)
    sep_ax2.axhline(0.5, color=TOK["line"], lw=0.8)
    sep_ax2.axis("off")

    # ── Vitals — 4 ChipLabelValue rows ───────────────────────────────
    chip_ax = axes_at(0.165, 0.20)
    chip_ax.axis("off")
    chip_ax.set_xlim(0, 1); chip_ax.set_ylim(0, 1)
    chip_w, chip_h = 0.92, 0.16
    chip_x = (1 - chip_w) / 2
    gap = 0.04
    for i, (label, value, tone) in enumerate([
        ("Accessibility", gene["surface_accessibility"],
            ACCESS_TONE.get(gene["surface_accessibility"], TOK["muted"])),
        ("Confidence", gene["confidence"],
            CONF_TONE.get(gene["confidence"], TOK["muted"])),
        ("State dep.", gene["state_dependence"],
            STATE_TONE.get(gene["state_dependence"], TOK["muted"])),
        ("Expression", gene["expression_breadth"].replace("_", " "),
            EXPR_TONE.get(gene["expression_breadth"], TOK["muted"])),
    ]):
        y = 1 - (i + 1) * chip_h - i * gap
        _label_value_chip(chip_ax, chip_x, y, chip_w, chip_h,
                          label, value, tone, fs=9.5)

    # Hairline separator
    sep_ax3 = axes_at(0.16, 0.003)
    sep_ax3.axhline(0.5, color=TOK["line"], lw=0.8)
    sep_ax3.axis("off")

    # ── DB strip — 5 outlined source chips, filled if called ─────────
    db_ax = axes_at(0.085, 0.075)
    db_ax.axis("off")
    db_ax.set_xlim(0, 1); db_ax.set_ylim(0, 1)
    db_ax.text(0.5, 0.92, "DATABASE CALLS",
               ha="center", va="top", fontsize=8, color=TOK["muted"],
               family="Manrope", fontweight="medium",
               transform=db_ax.transAxes)
    n_db = 5
    db_w, db_h = 0.16, 0.42
    db_gap = 0.02
    total_w = n_db * db_w + (n_db - 1) * db_gap
    db_x0 = (1 - total_w) / 2
    db_y = 0.20
    for i, (db_name, called) in enumerate(gene["db_flags"].items()):
        x = db_x0 + i * (db_w + db_gap)
        tone = DB_COLOR.get(db_name, TOK["muted"])
        if called:
            # Filled when called — outlined-pill style but with
            # tone-filled background + white text.
            box = FancyBboxPatch(
                (x, db_y), db_w, db_h,
                boxstyle="round,pad=0,rounding_size=0.025",
                facecolor=tone, edgecolor=tone, lw=1.2,
                transform=db_ax.transAxes, clip_on=False,
            )
            db_ax.add_patch(box)
            db_ax.text(x + db_w / 2, db_y + db_h / 2, db_name,
                       ha="center", va="center", fontsize=8,
                       color="white", fontweight="bold",
                       transform=db_ax.transAxes, family="Manrope")
        else:
            _outlined_pill(db_ax, x, db_y, db_w, db_h, db_name,
                           TOK["muted"], fs=8)

    # ── Sonnet verdict — single filled pill ──────────────────────────
    verd_ax = axes_at(0.025, 0.05)
    verd_ax.axis("off")
    verd_ax.set_xlim(0, 1); verd_ax.set_ylim(0, 1)
    verd_w, verd_h = 0.84, 0.65
    verd_x = (1 - verd_w) / 2
    verd_y = 0.18
    tone = VERDICT_TONE.get(gene["sonnet_verdict"], TOK["muted"])
    box = FancyBboxPatch(
        (verd_x, verd_y), verd_w, verd_h,
        boxstyle="round,pad=0,rounding_size=0.025",
        facecolor=tone, edgecolor=tone, lw=1.2,
        transform=verd_ax.transAxes, clip_on=False,
    )
    verd_ax.add_patch(box)
    verd_ax.text(verd_x + verd_w / 2, verd_y + verd_h / 2,
                 f"SONNET  ·  {gene['sonnet_verdict'].upper()}  ·  "
                 f"{gene['sonnet_reason'].replace('_', ' ').upper()}",
                 ha="center", va="center", fontsize=9.5,
                 color="white", fontweight="bold",
                 transform=verd_ax.transAxes, family="Manrope")

    # Story tag
    story_ax = axes_at(0.005, 0.02)
    story_ax.axis("off")
    story_ax.set_xlim(0, 1); story_ax.set_ylim(0, 1)
    story_ax.text(0.5, 0.5, gene["story"],
                  ha="center", va="center", fontsize=8.5,
                  color=TOK["muted"], style="italic",
                  family="Manrope",
                  transform=story_ax.transAxes)


def make_plot():
    # Don't apply setup_plotting_style — that suppresses titles + sets
    # axes spines off for chart-style plots. This is editorial.
    register_bundled_fonts()
    plt.rcParams.update({
        "font.family": "Manrope",
        "font.sans-serif": ["Manrope", "Outfit", "DejaVu Sans"],
        "font.serif": ["Playfair Display", "Georgia"],
        "savefig.dpi": 600,
        "savefig.bbox": "tight",
        "figure.facecolor": "none",
        "savefig.facecolor": "none",
        "axes.facecolor": "none",
    })
    fig = plt.figure(figsize=(15, 12))
    fig.set_facecolor(TOK["bg_warm"])  # warm bg like the viewer

    # 3 columns at fixed x positions in figure coords. Padding on the
    # outside + a small inner gap between columns.
    col_width = 0.30
    gap = 0.015
    total = 3 * col_width + 2 * gap
    left = (1.0 - total) / 2
    for i, gene in enumerate(GENES):
        x_left = left + i * (col_width + gap)
        _render_column(fig, gene, x_left, col_width)

    return fig


def main() -> None:
    fig = make_plot()
    save_figure(fig, SLUG, output_dir=OUT_DIR, formats=("pdf", "png"))


if __name__ == "__main__":
    main()
