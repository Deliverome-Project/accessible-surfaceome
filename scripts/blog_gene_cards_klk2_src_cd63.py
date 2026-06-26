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
# Primary subcellular compartment (rec.biological_context
# .subcellular_localization.primary_compartment) — where the protein
# spends its time. Matches the viewer's FiltersCard.tsx "primary" chip
# which uses tone="teal" uniformly; here we tone-shift by compartment
# so the contrast is visible at a glance — plasma_membrane reads as
# "clean surface" (success green), lysosome / endosome / golgi as
# "intracellular trafficking" (lavender, matches the viewer's modulation
# pills), and other intracellular as muted.
PRIMARY_COMPARTMENT_TONE = {
    "plasma_membrane":  TOK["green_success"],
    "extracellular":    TOK["green_success"],
    "lysosome":         TOK["lavender_bright"],
    "endosome":         TOK["lavender_bright"],
    "golgi":            TOK["lavender_bright"],
    "endoplasmic_reticulum": TOK["amber_mid"],
    "mitochondria":     TOK["muted"],
    "nucleus":          TOK["muted"],
    "cytosol":          TOK["muted"],
}
# Evidence grade — agent's coded assessment of the supporting literature.
EVIDENCE_TONE = {
    "direct_multi_method":     TOK["green_success"],
    "direct_single_method":    TOK["amber_mid"],
    "supportive_but_indirect": TOK["amber_mid"],
    "weak":                    TOK["muted"],
}
# ECD accessibility class — large/moderate/small/minimal/none. Higher
# extracellular-domain length = more binder real-estate.
ECD_TONE = {
    "large":    TOK["green_success"],
    "moderate": TOK["amber_mid"],
    "small":    TOK["amber_mid"],
    "minimal":  TOK["maroon_light"],
    "none":     TOK["muted"],
}
# Induction trigger — what condition surfaces the protein when
# state_dependence is high. "none" = constitutive (not induced).
INDUCTION_TONE = {
    "none":            TOK["muted"],
    "oncogenic":       TOK["maroon_light"],
    "immune":          TOK["teal_mid"],
    "stress_hypoxia":  TOK["amber_mid"],
    "cell_death":      TOK["maroon_dark"],
    "infection":       TOK["lavender_bright"],
    "other":           TOK["muted"],
}
# Surface call reason (filters.surface_call_reason) — the agent's
# coded justification. Color by the bucket the reason falls into,
# mirroring the _YES_REASONS / _CONTEXTUAL_REASONS / _NO_REASONS
# split in models.py.
_YES_REASONS = {
    "classical_surface_receptor", "gpi_anchored",
    "multipass_with_exposed_loops", "extracellular_face_protein",
    "stable_complex_partner",
}
_CONTEXTUAL_REASONS = {
    "cell_state_induced", "tissue_restricted_surface",
    "lysosomal_exocytosis", "dual_localization",
    "stable_surface_attachment", "other",
}
_NO_REASONS = {
    "cytoplasmic", "nuclear", "mitochondrial_internal",
    "endomembrane_resident", "nuclear_envelope", "secreted_only",
    "inner_leaflet_anchored", "pmhc_only_intracellular",
}


def _reason_tone(reason: str) -> str:
    if reason in _YES_REASONS:
        return TOK["green_success"]
    if reason in _CONTEXTUAL_REASONS:
        return TOK["amber_mid"]
    if reason in _NO_REASONS:
        return TOK["muted"]
    return TOK["muted"]


# ── RYG ramp colors for vital displays — mirrors viewer's
# globals.css .h-vital-display.tone-{success, amber, danger, neutral}.
# Viewer comment: "Vital tones form a single red→amber→green
# traffic-light ramp (low→high), plus a gray neutral for unknown /
# unclear values. No teal / lavender / light-green — every vital reads
# on the same RYG+gray scale so the 2×2 grid feels uniform."
_VITAL_TONE = {
    "success": TOK["green_success"],   # green = strong yes
    "amber":   TOK["amber_mid"],       # amber = moderate / contextual
    "danger":  TOK["maroon_light"],    # red   = negative / weak
    "neutral": TOK["muted"],           # gray  = unknown / unclear
}


def _ryg_tone_for_access(v: str) -> str:
    return {
        "high":     _VITAL_TONE["success"],
        "moderate": _VITAL_TONE["amber"],
        "low":      _VITAL_TONE["amber"],
        "no":       _VITAL_TONE["danger"],
    }.get(v, _VITAL_TONE["neutral"])


def _ryg_tone_for_conf(v: str) -> str:
    return {
        "high":     _VITAL_TONE["success"],
        "moderate": _VITAL_TONE["amber"],
        "low":      _VITAL_TONE["danger"],
    }.get(v, _VITAL_TONE["neutral"])


def _ryg_tone_for_state(v: str) -> str:
    # High state-dep = caution (amber / red). Low = "constitutive" =
    # success. Matches the viewer's RYG semantic (higher state
    # dependence = harder to target = warmer color).
    return {
        "low":      _VITAL_TONE["success"],
        "moderate": _VITAL_TONE["amber"],
        "high":     _VITAL_TONE["danger"],
    }.get(v, _VITAL_TONE["neutral"])


def _ryg_tone_for_expr(v: str) -> str:
    return {
        "pan_tissue": _VITAL_TONE["success"],
        "broad":      _VITAL_TONE["success"],
        "restricted": _VITAL_TONE["amber"],
        "rare":       _VITAL_TONE["danger"],
    }.get(v, _VITAL_TONE["neutral"])


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
        "evidence_grade":        "direct_multi_method",
        "ecd_class":             "large",
        "state_dependence":      "high",
        "expression_breadth":    "rare",
        "primary_compartment":   "plasma_membrane",
        "induction_trigger":     "none",
        "surface_call_reason":   "tissue_restricted_surface",
        "tumor_associated":      False,
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
        # SRC = DeepTMHMM GLOB (no TM helices), all "I" topology — the
        # viewer renders SRC as uniformly intracellular green WITHOUT a
        # membrane slab (it has nothing to cross). Matching the viewer
        # here: all "I" residues → green Cα trace, no slab. Earlier
        # "force-yellow + slab" override drifted from what the live
        # surfaceome.deliverome.org/SRC page actually shows.
        "topology_str": "I" * 536,
        "story": "2/5 DBs over-called — deep-dive nuanced",
        "surface_accessibility": "moderate",
        "confidence":            "low",
        "evidence_grade":        "direct_single_method",
        "ecd_class":             "none",
        "state_dependence":      "high",
        "expression_breadth":    "broad",
        "primary_compartment":   "plasma_membrane",
        "induction_trigger":     "oncogenic",
        "surface_call_reason":   "lysosomal_exocytosis",
        "tumor_associated":      True,
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
        "evidence_grade":        "direct_multi_method",
        "ecd_class":             "moderate",
        "state_dependence":      "high",
        "expression_breadth":    "pan_tissue",
        "primary_compartment":   "lysosome",
        "induction_trigger":     "oncogenic",
        "surface_call_reason":   "lysosomal_exocytosis",
        "tumor_associated":      False,
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


def _orient_for_membrane(ca: np.ndarray, tm_mask: np.ndarray) -> np.ndarray:
    """If the protein has TM-labelled residues, rotate so the average
    per-helix direction (membrane normal) is vertical.

    Earlier version PCA'd the full TM Cα cluster and used the first
    principal axis — that picks the longest dimension of the bundle,
    which for a multi-pass TM protein (CD63, GPCRs) is usually
    PERPENDICULAR to the membrane normal (the bundle is wider than it
    is tall). That left CD63 lying on its side.

    Fix: identify each contiguous TM segment, compute (end - start)
    Cα vector for each, sign-correct them to point the same way, then
    average. That's the membrane normal regardless of how the helices
    are arranged laterally."""
    if not tm_mask.any():
        return ca
    # Find contiguous TM runs (their start/end indices in ca).
    runs: list[tuple[int, int]] = []
    in_run = False
    s_idx = 0
    for i, m in enumerate(tm_mask):
        if m and not in_run:
            s_idx = i
            in_run = True
        elif not m and in_run:
            runs.append((s_idx, i - 1))
            in_run = False
    if in_run:
        runs.append((s_idx, len(tm_mask) - 1))

    # Per-helix direction vector (end - start), normalised.
    helix_dirs: list[np.ndarray] = []
    for s_i, e_i in runs:
        v = ca[e_i] - ca[s_i]
        norm = np.linalg.norm(v)
        if norm > 1e-6:
            helix_dirs.append(v / norm)
    if not helix_dirs:
        return ca

    # Sign-correct each vector to point the same way as the first
    # (TM helices in a bundle alternate direction; flip the ones that
    # face the opposite way so they average constructively).
    ref = helix_dirs[0]
    aligned = [d if d @ ref >= 0 else -d for d in helix_dirs]
    axis = np.mean(aligned, axis=0)
    axis = axis / np.linalg.norm(axis)

    z_hat = np.array([0.0, 0.0, 1.0])
    v = np.cross(axis, z_hat)
    s = np.linalg.norm(v)
    c = float(np.dot(axis, z_hat))
    if s < 1e-8:
        return ca
    vx = np.array([[ 0.0,   -v[2],  v[1]],
                   [ v[2],   0.0,  -v[0]],
                   [-v[1],  v[0],   0.0]])
    R = np.eye(3) + vx + vx @ vx * ((1 - c) / (s * s))
    return ca @ R.T


def _render_structure(ax, gene: dict) -> None:
    """Render the Cα trace as a 3D backbone colored by DeepTMHMM
    topology, viewer-style. TM-containing structures are rotated so
    the helix principal axis is vertical, the membrane slab sits
    horizontally, and the helices visibly cross it.

    Lines are drawn thinner (lw=1.2) than the prior pass — the viewer's
    3Dmol cartoon ribbons read as crisp single-pixel-ish strokes; matching
    that aesthetic means dropping the thick markers that were dominating
    the image."""
    try:
        pdb = _fetch_pdb(gene["uniprot"])
        ca = _extract_ca(pdb)
    except Exception as exc:  # noqa: BLE001 — network / parse failures
        ax.text2D(0.5, 0.5, f"({gene['uniprot']} structure unavailable: {exc})",
                  ha="center", va="center", transform=ax.transAxes,
                  fontsize=8, color=TOK["muted"])
        ax.set_axis_off()
        return

    n = len(ca)
    colors = _topology_colors(gene["topology_str"], n)
    tm_mask = np.array([c == TOPO_COLOR["M"] for c in colors])

    # Center, normalize scale, then orient so TM proteins render upright
    ca = ca - ca.mean(axis=0)
    ca = _orient_for_membrane(ca, tm_mask)
    span = np.max(np.ptp(ca, axis=0))
    if span > 0:
        ca = ca * (40.0 / span)

    # Thin backbone strokes — matches the viewer's crisp ribbon read.
    segs = np.stack([ca[:-1], ca[1:]], axis=1)
    seg_colors = colors[:-1]
    lc = Line3DCollection(segs, colors=seg_colors, linewidths=1.2, alpha=0.95)
    ax.add_collection3d(lc)

    # Smaller Cα markers (was 22/10, now 6/3) so the line is the
    # dominant visual element rather than the dot stipple.
    sizes = [6 if c == TOPO_COLOR["M"] else 3 for c in colors]
    ax.scatter(ca[:, 0], ca[:, 1], ca[:, 2], c=colors, s=sizes,
               edgecolors="none", alpha=0.85, depthshade=False)

    # Membrane slab for TM proteins — horizontal at the TM-median Z
    # after the upright rotation, so it reads as a true bilayer.
    if tm_mask.any():
        # After upright rotation, TM extent is along Z; the slab sits
        # at the median Z of TM residues with the standard ~14 Å
        # bilayer half-thickness (in our normalized units, ~5).
        tm_z = ca[tm_mask, 2]
        z_mid = float(np.median(tm_z))
        z_half = 5.0
        x0, x1 = ca[:, 0].min() - 3, ca[:, 0].max() + 3
        y0, y1 = ca[:, 1].min() - 3, ca[:, 1].max() + 3
        xx, yy = np.meshgrid([x0, x1], [y0, y1])
        for z in (z_mid - z_half, z_mid + z_half):
            ax.plot_surface(xx, yy, np.full_like(xx, z),
                            color=MEMBRANE_COLOR, alpha=0.10,
                            shade=False, edgecolor="none")

    # Camera + axis cleanup.
    ax.set_xticks([]); ax.set_yticks([]); ax.set_zticks([])
    ax.set_xlabel(""); ax.set_ylabel(""); ax.set_zlabel("")
    for axis_obj in (ax.xaxis, ax.yaxis, ax.zaxis):
        axis_obj.set_pane_color((1.0, 1.0, 1.0, 0.0))
        axis_obj.line.set_color((1.0, 1.0, 1.0, 0.0))
    ax.set_facecolor("none")
    ax.grid(False)
    lim = 24
    ax.set_xlim(-lim, lim); ax.set_ylim(-lim, lim); ax.set_zlim(-lim, lim)
    # View from the side: TM helices vertical + membrane horizontal
    # for TM proteins (CD63). Same angle for the others — they're
    # globular so the angle doesn't matter much, and consistent angle
    # makes the three cards look like a series.
    ax.view_init(elev=4, azim=-90)


# ── StatusPill primitives — soft-filled, matching the viewer ─────────
#
# Per viewer/components/surfaceome/StatusPill/StatusPill.module.css:
# Tones are SOFT-FILLED (10% alpha tint on the tone hue) with DEEPER
# tone text — NO border (border is transparent on all colored tones;
# only the neutral tone keeps a 1px line so a white chip still reads
# as a chip). I had this wrong as outlined originally.
#
# tone string → (bg_hex, text_color). The viewer's StatusPill uses
# rgba(<tone>, 0.10) over the page bg_warm. We pre-blend that to a
# solid hex here so matplotlib's alpha-compositing quirks (different
# answer in interactive vs savefig depending on figure facecolor
# state) can't push the fill toward over-saturation. Verified visually:
# this matches the level of subtlety the viewer's CSS produces on a
# Chrome-rendered page.
def _hex_to_rgb_unit(h: str) -> tuple[float, float, float]:
    h = h.lstrip("#")
    return tuple(int(h[i:i+2], 16) / 255 for i in (0, 2, 4))


def _rgb_to_hex(r: float, g: float, b: float) -> str:
    return "#{:02x}{:02x}{:02x}".format(
        int(round(r * 255)), int(round(g * 255)), int(round(b * 255)),
    )


def _soft_blend(tone_hex: str, alpha: float = 0.10, bg_hex: str = "#f3ece5") -> str:
    """Premultiplied blend: alpha * tone + (1-alpha) * bg. Returns a
    solid hex, NOT an rgba tuple — keeps every downstream renderer
    (FancyBboxPatch, Rectangle, set_facecolor) honest about the exact
    pixel value the chip should show."""
    tr, tg, tb = _hex_to_rgb_unit(tone_hex)
    br, bg, bb = _hex_to_rgb_unit(bg_hex)
    return _rgb_to_hex(
        alpha * tr + (1 - alpha) * br,
        alpha * tg + (1 - alpha) * bg,
        alpha * tb + (1 - alpha) * bb,
    )


# Tone family → (fill, text). Pre-blended to solid hex so the chip
# always renders at the same subtlety regardless of where it's drawn.
_PILL_TONE = {
    "maroon":   (_soft_blend("#922038"), TOK["maroon_dark"]),
    "teal":     (_soft_blend("#3D6B60"), "#152e28"),     # teal-deepest
    "amber":    (_soft_blend("#C07830"), "#8c4210"),     # amber-dark
    "lavender": (_soft_blend("#5848A8"), "#3a2888"),     # lavender-dark
    "success":  (_soft_blend("#2E7A55"), "#1b5e3f"),     # darker than --success
    "neutral":  ("none",                 "#2a2122"),     # transparent fill + ink-soft
}


def _tone_for(value_color: str) -> str:
    """Map a tone hex back to its CSS .tone_* family for soft-fill lookup.
    Falls back to neutral. The function lets the rest of the code keep
    passing brand hex values around without caring which CSS class
    they'd render as in the viewer."""
    m = {
        TOK["green_success"]:  "success",
        TOK["amber_mid"]:      "amber",
        TOK["amber_bright"]:   "amber",
        TOK["maroon_light"]:   "maroon",
        TOK["maroon_dark"]:    "maroon",
        TOK["teal_mid"]:       "teal",
        TOK["teal_lt"]:        "teal",
        TOK["lavender_bright"]:"lavender",
        TOK["muted"]:          "neutral",
    }
    return m.get(value_color, "neutral")


def _pill(ax, x, y, w, h, text, tone_hex, *, fs=8.5, transform=None):
    """Single StatusPill — soft-filled + deeper-tone text. ``tone_hex``
    is the brand hex the caller passes for the chip's *meaning* (e.g.
    success green); the renderer looks up the .tone_* family and
    applies the matching soft-fill bg + deeper text."""
    if transform is None:
        transform = ax.transAxes
    fill, text_color = _PILL_TONE[_tone_for(tone_hex)]
    is_neutral = fill == "none"
    edge = TOK["line"] if is_neutral else "none"
    lw = 0.9 if is_neutral else 0
    fc = "none" if is_neutral else fill
    box = FancyBboxPatch(
        (x, y), w, h,
        boxstyle=f"round,pad=0,rounding_size={h * 0.5}",  # makes rounding behave like a true pill
        facecolor=fc, edgecolor=edge, lw=lw,
        transform=transform, clip_on=False,
    )
    ax.add_patch(box)
    ax.text(x + w / 2, y + h / 2, text.upper(),
            ha="center", va="center", fontsize=fs,
            color=text_color, fontweight="medium",
            transform=transform, clip_on=False,
            family="Manrope")


def _label_value_chip(ax, x, y, w, h, label, value, tone_hex, fs=9):
    """ChipLabelValue: "LABEL · VALUE" inside a single soft-filled
    StatusPill. Label is dim (label color = text_color @ 72% opacity
    per viewer's CSS); value is BOLD UPPERCASE at full opacity.
    Same font size; emphasis comes from weight + opacity, not size."""
    fill, text_color = _PILL_TONE[_tone_for(tone_hex)]
    is_neutral = fill == "none"
    edge = TOK["line"] if is_neutral else "none"
    lw = 0.9 if is_neutral else 0
    fc = "none" if is_neutral else fill
    box = FancyBboxPatch(
        (x, y), w, h,
        boxstyle=f"round,pad=0,rounding_size={h * 0.5}",
        facecolor=fc, edgecolor=edge, lw=lw,
        transform=ax.transAxes, clip_on=False,
    )
    ax.add_patch(box)
    # Label dim (opacity 0.72 per .label CSS rule). matplotlib doesn't
    # let us set per-color opacity in the text() kwarg; emulate by
    # taking the text_color's alpha down. Easier: just lower-saturation
    # the label by using the muted token.
    ax.text(x + 0.026, y + h / 2, label.upper(),
            ha="left", va="center", fontsize=fs - 0.5, color=text_color,
            fontweight="normal", alpha=0.72,
            transform=ax.transAxes, clip_on=False, family="Manrope")
    # Value: bold UPPERCASE, full opacity, same tone text color.
    ax.text(x + w - 0.026, y + h / 2, value.upper().replace("_", " "),
            ha="right", va="center", fontsize=fs, color=text_color,
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
    # Header gets less space than the previous layout (was 0.80-0.98 =
    # 18%; now 0.84-0.98 = 14%) so the structure can take more, per
    # user request.
    text_ax = axes_at(0.84, 0.14)
    text_ax.axis("off")
    text_ax.set_xlim(0, 1); text_ax.set_ylim(0, 1)
    text_ax.text(0.5, 0.85, gene["symbol"],
                 transform=text_ax.transAxes,
                 ha="center", va="center",
                 fontsize=46, fontweight="bold",
                 color=TOK["maroon_deepest"], family="Playfair Display")
    text_ax.text(0.5, 0.42, gene["name"],
                 transform=text_ax.transAxes,
                 ha="center", va="center",
                 fontsize=10.5, color=TOK["ink"],
                 family="Manrope", fontweight="medium")
    text_ax.text(0.5, 0.22, f"UniProt  {gene['uniprot']}",
                 transform=text_ax.transAxes,
                 ha="center", va="center",
                 fontsize=8, color=TOK["muted"],
                 family="Manrope", fontweight="normal")

    # Lede — smaller (fs=7.5) so it doesn't dominate the column
    lede_ax = axes_at(0.78, 0.05)
    lede_ax.axis("off")
    lede_ax.set_xlim(0, 1); lede_ax.set_ylim(0, 1)
    wrapped = textwrap.fill(gene["lede"], width=58)
    lede_ax.text(0.5, 0.5, wrapped,
                 transform=lede_ax.transAxes,
                 ha="center", va="center",
                 fontsize=7.5, color=TOK["muted"],
                 family="Manrope", style="italic",
                 linespacing=1.35)

    # Hairline separator
    sep_ax = axes_at(0.775, 0.003)
    sep_ax.axhline(0.5, color=TOK["line"], lw=0.8)
    sep_ax.axis("off")

    # ── 3D structure — real AFDB Cα trace ────────────────────────────
    # Structure now takes 30% of figure height (was 22%) per user
    # request — gives the topology trace room to breathe.
    struct_ax = fig.add_axes((x_left + 0.005, 0.47, col_width - 0.01, 0.30),
                             projection="3d")
    _render_structure(struct_ax, gene)

    # Hairline separator
    sep_ax2 = axes_at(0.465, 0.003)
    sep_ax2.axhline(0.5, color=TOK["line"], lw=0.8)
    sep_ax2.axis("off")

    # ── Vitals 2×2 grid + secondary chip strip ───────────────────────
    # Matches the viewer's GeneHeader pattern (viewer/components/
    # surfaceome/GeneHeader/GeneHeader.module.css `.vitals`):
    #   * each cell is .vitalK eyebrow (UPPERCASE 0.78rem, muted,
    #     letter-spacing 0.1em) over a .h-vital-display value (italic
    #     Playfair Display, ~1.4rem, tone-colored via .tone-success /
    #     .tone-amber / .tone-danger / .tone-neutral)
    #   * 2-column grid, 4 cells total
    # The viewer ships exactly 4 vitals: Accessibility, Confidence,
    # State dependence, Expression. We match that set.
    #
    # Below the vital grid, a slim flex row of small StatusPills carries
    # the secondary tags the user wants — Evidence, Primary loc.,
    # Induced by, Reason, and ✓ tumor-associated (when true).
    vital_ax = axes_at(0.265, 0.195)
    vital_ax.axis("off")
    vital_ax.set_xlim(0, 1); vital_ax.set_ylim(0, 1)
    vital_cells = [
        ("ACCESSIBILITY", gene["surface_accessibility"],
            _ryg_tone_for_access(gene["surface_accessibility"])),
        ("CONFIDENCE",    gene["confidence"],
            _ryg_tone_for_conf(gene["confidence"])),
        ("STATE DEP.",    gene["state_dependence"],
            _ryg_tone_for_state(gene["state_dependence"])),
        ("EXPRESSION",    gene["expression_breadth"].replace("_", " "),
            _ryg_tone_for_expr(gene["expression_breadth"])),
    ]
    cell_w, cell_h = 0.48, 0.42
    cell_gap_x, cell_gap_y = 0.04, 0.08
    grid_w = 2 * cell_w + cell_gap_x
    grid_left = (1 - grid_w) / 2
    grid_top = 0.96
    for idx, (label, value, ryg_tone) in enumerate(vital_cells):
        col, row = idx % 2, idx // 2
        cx = grid_left + col * (cell_w + cell_gap_x)
        cy = grid_top - (row + 1) * cell_h - row * cell_gap_y
        # .vitalK eyebrow
        vital_ax.text(cx, cy + cell_h, label,
                      ha="left", va="top",
                      fontsize=8.5, color=TOK["muted"], family="Manrope",
                      fontweight="medium",
                      transform=vital_ax.transAxes, clip_on=False)
        # .h-vital-display value — italic Playfair Display, tone color
        vital_ax.text(cx, cy + cell_h * 0.35, value.upper(),
                      ha="left", va="center",
                      fontsize=20, color=ryg_tone,
                      family="Playfair Display", style="italic",
                      fontweight="medium",
                      transform=vital_ax.transAxes, clip_on=False)

    # ── Secondary chip strip — small StatusPills with the extra tags
    chips_ax = axes_at(0.08, 0.115)
    chips_ax.axis("off")
    chips_ax.set_xlim(0, 1); chips_ax.set_ylim(0, 1)
    # Build chip set (label, value, tone). Skip "Induced by" when none.
    chip_set: list[tuple[str, str, str]] = [
        ("evidence", gene["evidence_grade"].replace("_", " "),
            EVIDENCE_TONE.get(gene["evidence_grade"], TOK["muted"])),
        ("primary",  gene["primary_compartment"].replace("_", " "),
            PRIMARY_COMPARTMENT_TONE.get(gene["primary_compartment"], TOK["muted"])),
        ("reason",   gene["surface_call_reason"].replace("_", " "),
            _reason_tone(gene["surface_call_reason"])),
    ]
    if gene["induction_trigger"] != "none":
        chip_set.append((
            "induced",
            gene["induction_trigger"].replace("_", " "),
            INDUCTION_TONE.get(gene["induction_trigger"], TOK["muted"]),
        ))
    if gene.get("tumor_associated"):
        chip_set.append(("", "✓ tumor associated", TOK["maroon_light"]))

    # Tight flex-row layout: chips flow left-to-right with wrap. Each
    # chip's width is content-sized (label · value text length × char
    # width estimate).
    pad_x = 0.022
    chip_h_pct = 0.20  # in transAxes coords
    char_w = 0.0072    # approx text-width per char in transAxes at fs=7.5
    gap = 0.01
    y_cursor = 0.78    # top row
    x_cursor = 0.0
    for label, value, tone in chip_set:
        full_text = (label + " · " + value).upper() if label else value.upper()
        chip_w_pct = len(full_text) * char_w + pad_x * 2
        # Wrap to next row if needed
        if x_cursor + chip_w_pct > 1.0:
            y_cursor -= chip_h_pct + 0.06
            x_cursor = 0.0
        if label:
            _label_value_chip(chips_ax, x_cursor, y_cursor,
                              chip_w_pct, chip_h_pct,
                              label, value, tone, fs=7.5)
        else:
            _pill(chips_ax, x_cursor, y_cursor,
                  chip_w_pct, chip_h_pct, value, tone, fs=7.5)
        x_cursor += chip_w_pct + gap

    # Hairline separator
    sep_ax3 = axes_at(0.16, 0.003)
    sep_ax3.axhline(0.5, color=TOK["line"], lw=0.8)
    sep_ax3.axis("off")

    # ── DB strip — swatch-dot pattern matching the viewer ────────────
    # Per viewer/components/surfaceome/DatabasePresenceCard, every DB
    # chip is the SAME white outlined pill regardless of called/not;
    # what differs is the 10px colored swatch dot inside, which is
    # the brand color when called and faded line-color when not. This
    # reads as a quiet row, not five tone-tagged banners.
    db_ax = axes_at(0.085, 0.075)
    db_ax.axis("off")
    db_ax.set_xlim(0, 1); db_ax.set_ylim(0, 1)
    db_ax.text(0.5, 0.92, "DATABASE CALLS",
               ha="center", va="top", fontsize=8, color=TOK["muted"],
               family="Manrope", fontweight="medium",
               transform=db_ax.transAxes)
    n_db = 5
    db_w, db_h = 0.17, 0.42
    db_gap = 0.015
    total_w = n_db * db_w + (n_db - 1) * db_gap
    db_x0 = (1 - total_w) / 2
    db_y = 0.18
    for i, (db_name, called) in enumerate(gene["db_flags"].items()):
        x = db_x0 + i * (db_w + db_gap)
        # White outlined pill — same shape always
        box = FancyBboxPatch(
            (x, db_y), db_w, db_h,
            boxstyle=f"round,pad=0,rounding_size={db_h * 0.5}",
            facecolor="white" if called else "none",
            edgecolor=TOK["line"], lw=0.9,
            transform=db_ax.transAxes, clip_on=False,
        )
        db_ax.add_patch(box)
        # Swatch dot — brand color when called, faded when not.
        # Drawn as a small circle (FancyBboxPatch with high rounding) so
        # we don't need matplotlib's Circle in transAxes coords.
        swatch_size = 0.07
        swatch_x = x + 0.030
        swatch_y = db_y + db_h / 2 - swatch_size / 2
        swatch_color = DB_COLOR.get(db_name, TOK["muted"]) if called else TOK["line"]
        swatch = FancyBboxPatch(
            (swatch_x, swatch_y), swatch_size, swatch_size,
            boxstyle=f"round,pad=0,rounding_size={swatch_size * 0.5}",
            facecolor=swatch_color, edgecolor="none",
            transform=db_ax.transAxes, clip_on=False,
        )
        db_ax.add_patch(swatch)
        # Label text — ink for called, muted for not (matches the
        # viewer's .cellNo .link color: var(--muted) rule)
        text_color = TOK["ink"] if called else TOK["muted"]
        ax_text_x = swatch_x + swatch_size + 0.018
        db_ax.text(ax_text_x, db_y + db_h / 2, db_name,
                   ha="left", va="center", fontsize=7.5,
                   color=text_color, fontweight="medium",
                   transform=db_ax.transAxes, family="Manrope")

    # ── Sonnet verdict — single filled pill ──────────────────────────
    verd_ax = axes_at(0.025, 0.05)
    verd_ax.axis("off")
    verd_ax.set_xlim(0, 1); verd_ax.set_ylim(0, 1)
    verd_w, verd_h = 0.84, 0.65
    verd_x = (1 - verd_w) / 2
    verd_y = 0.18
    # Sonnet verdict — single soft-tinted pill matching the chip family
    # above. Same rendering path as ``_pill`` so subtle-fill stays
    # consistent.
    tone = VERDICT_TONE.get(gene["sonnet_verdict"], TOK["muted"])
    _pill(verd_ax, verd_x, verd_y, verd_w, verd_h,
          f"SONNET  ·  {gene['sonnet_verdict'].upper()}  ·  "
          f"{gene['sonnet_reason'].replace('_', ' ').upper()}",
          tone, fs=9.5)


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
