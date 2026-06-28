"""Render the KLK2 / SRC / CD63 blog-card figure by writing a 3-column
HTML page (viewer-styled, 3Dmol structures, no executive summary, no
HGNC/aliases) and screenshotting it headlessly via Playwright at
device_scale_factor=3 — net effective resolution ≥ 600 DPI.

Why not matplotlib: the viewer's GeneHeader / StructureViewer styling
(italic Playfair display vitals, 3Dmol cartoon ribbons, membrane slabs,
soft-fill StatusPills with the exact design tokens) is far cleaner to
replicate by writing actual HTML/CSS than by re-implementing it patch
by patch in matplotlib. The temp HTML lives under scratchpad/; only
the final PNG/PDF ships under data/analysis/figures/.

CD63's membrane orientation is computed in Python (numpy) ported from
viewer/lib/structure-orientation.ts — I→O axis aligned to +Y, TM mean
shifted to Y=0 — so the structure renders upright with a horizontal
membrane slab. SRC (DeepTMHMM GLOB type) renders gold with no slab to
match the live viewer. KLK2 has no TM helices; rendered as ECF /
signal-peptide colored without a slab.

Run:
    uv run python scripts/blog_gene_cards_klk2_src_cd63.py
"""
from __future__ import annotations

import asyncio
import os
import shutil
import sys
import textwrap
from pathlib import Path
from typing import Any

import httpx
import numpy as np

ROOT = Path(__file__).resolve().parents[1]
SCRATCH = Path(os.environ.get(
    "BLOG_CARD_SCRATCH",
    "/tmp/blog_gene_cards_klk2_src_cd63",
))
SCRATCH.mkdir(parents=True, exist_ok=True)
OUT_DIR = ROOT / "data/analysis/figures"
SLUG = "blog_gene_cards_klk2_src_cd63"

# Per-gene data drawn from viewer/public/data/surfaceome/*.json plus
# the public catalog. Only fields that actually render on the card
# are stored; everything else is pruned to keep the figure tight.
GENES: list[dict[str, Any]] = [
    {
        "symbol": "KLK2",
        "name": "Kallikrein-2",
        "uniprot": "P20151",
        "ncbi": "3817",
        "ensembl": "ENSG00000167751",
        # 5-DB votes
        "db_flags": {"UniProt": 0, "GO": 0, "HPA": 0, "SURFY": 0, "CSPA": 0},
        # Triage / deep-dive
        "sonnet_verdict": "contextual",
        "sonnet_reason":  "tissue_restricted_surface",
        # Vitals (4 — viewer's GeneHeader pattern)
        "vitals": [
            ("SURFACE VERDICT",     "Moderate",              "amber"),
            ("EXPERIMENTAL EVIDENCE","Direct, multi-method", "success"),
            ("CONFIDENCE",          "Moderate",              "amber"),
            # High state-dep = green per viewer's uniform RYG ramp
            # (.h-vital-display.tone-success). Viewer treats HIGH as
            # the "green" end of every vital, regardless of whether
            # the field semantically means "good"/"bad" — uniformity
            # over semantics so the 2×2 grid reads consistently.
            ("STATE DEPENDENCE",    "High",                  "success"),
        ],
        # KLK2 chip set. dual_localization array has 1 entry (secreted
        # in androgen-stimulated prostate cancer) → ✓; has_secreted_form
        # is True → ✓. KLK2 has no trigger-carrying modulation rows so
        # there's no "induced by" chip — the gene is tissue-restricted
        # rather than cell-state-induced.
        # Uniform 9-chip schema across all 3 genes — every chip slot
        # exists on every card so the 2-column grid stays the same
        # height. "Also in" condensed to one comma-separated chip
        # (matching the "induced by" pattern). "induced by" is "—" on
        # KLK2 since the gene has no trigger-carrying modulation rows.
        # Chip order — uniform 9-slot schema across all genes. 2-col
        # grid layout:
        #   Row 1: primary           | reason
        #   Row 2: surface vs intra  | n surface evidence
        #   Row 3: also in           | ✓/✗ secreted form
        #   Row 4: expression level  | expression breadth
        #   Row 5: induced by        | (empty cell)
        "chips": [
            ("primary",      "Plasma membrane",        "teal"),
            ("reason",       "Tissue-restricted",      "amber"),
            ("surface vs intracellular",  "Mixed",   "amber"),
            ("n surface evidence", "2",                "success"),
            ("also in",      "Secreted",               "lavender"),
            (None,           "✓ secreted form",        "success"),
            ("expression level",   "High",             "success"),
            ("expression breadth", "Rare",             "danger"),
            ("induced by",   "—",                      "neutral"),
        ],
        # Topology: no TM helices (it's a secreted protease, signal
        # peptide cleaved). Keep N-terminal residues 1-17 colored as
        # signal peptide (S) before the cleavage site.
        "topology_str": "S" * 17 + "O" * (261 - 17),  # secreted, no TM
        "has_membrane_slab": False,
    },
    {
        "symbol": "SRC",
        "name": "Proto-oncogene tyrosine kinase Src",
        "uniprot": "P12931",
        "ncbi": "6714",
        "ensembl": "ENSG00000197122",
        "db_flags": {"UniProt": 0, "GO": 1, "HPA": 1, "SURFY": 0, "CSPA": 0},
        "sonnet_verdict": "no",
        "sonnet_reason":  "inner_leaflet_anchored",
        "vitals": [
            ("SURFACE VERDICT",      "Moderate",              "amber"),
            ("EXPERIMENTAL EVIDENCE","Direct, single method", "amber"),
            ("CONFIDENCE",           "Low",                   "danger"),
            ("STATE DEPENDENCE",     "High",                  "success"),
        ],
        # SRC's modulation rows have 4 distinct cell_state_trigger
        # values BUT only oncogenic_transformation (rows 0+1) actually
        # exposes an extracellular epitope. The immune_activation /
        # mechanical_stress / infection_bacterial rows all describe
        # inner-leaflet effects that don't surface-induce — explicitly
        # called out in their accessibility_implication text. Only
        # listing oncogenic here so the chip honestly reflects what
        # actually causes surface accessibility. Also adding the
        # ✓ dual_localization chip because modulation row [2] has
        # dual_loc_partner_compartment='lysosome'.
        # SRC chip set. dual_localization array has 4 entries (LE/lyso,
        # outer PM in cancer, cytoplasm, peri-nuclear) → ✓;
        # has_secreted_form=False → ✗. tumor-associated chip dropped
        # per user request. "induced by" moved last so the boolean
        # ✓/✗ chips group together visually.
        "chips": [
            ("primary",      "Plasma membrane",         "teal"),
            ("reason",       "Lysosomal exocytosis",    "amber"),
            ("surface vs intracellular",  "Mostly intracellular", "amber"),
            ("n surface evidence", "1",                "amber"),
            ("also in",      "Late endo/lyso, outer PM, cytoplasm, peri-nuclear", "lavender"),
            (None,           "✗ secreted form",        "danger"),
            ("expression level",   "Moderate",         "amber"),
            ("expression breadth", "Broad",            "success"),
            ("induced by",   "Oncogenic",              "maroon"),
        ],
        # DeepTMHMM type GLOB → all "M" so 3Dmol paints the cartoon
        # gold (M tone) without a membrane slab, mirroring the live
        # viewer's "Globular" render.
        "topology_str": "M" * 536,
        "has_membrane_slab": False,
    },
    {
        "symbol": "CD63",
        "name": "Tetraspanin-30 (LAMP-3)",
        "uniprot": "P08962",
        "ncbi": "967",
        "ensembl": "ENSG00000135404",
        "db_flags": {"UniProt": 1, "GO": 1, "HPA": 0, "SURFY": 1, "CSPA": 1},
        "sonnet_verdict": "contextual",
        "sonnet_reason":  "lysosomal_exocytosis",
        "vitals": [
            ("SURFACE VERDICT",      "High",                  "success"),
            ("EXPERIMENTAL EVIDENCE","Direct, multi-method",  "success"),
            ("CONFIDENCE",           "High",                  "success"),
            ("STATE DEPENDENCE",     "High",                  "success"),
        ],
        # CD63's 9 trigger-carrying modulation rows span
        # immune_activation (×3), antigen_stimulation (×3),
        # infection_viral (×1), oncogenic_transformation (×1),
        # other (×1). The single filters.induction_trigger="oncogenic"
        # roll-up under-represents the immune component — immune is
        # actually the dominant trigger. Listing all 5 makes the
        # multi-trigger picture explicit.
        "chips": [
            ("primary",      "Lysosome",               "lavender"),
            ("reason",       "Lysosomal exocytosis",   "amber"),
            ("surface vs intracellular",  "Mostly intracellular", "amber"),
            ("n surface evidence", "7",                "success"),
            ("also in",      "Plasma membrane, endosome, MVB, secretory granule, EV", "lavender"),
            (None,           "✗ secreted form",        "danger"),
            ("expression level",   "Moderate",         "amber"),
            ("expression breadth", "Pan-tissue",       "success"),
            ("induced by",   "Immune, antigen, infection, oncogenic, other", "maroon"),
        ],
        # CD63 (P08962) DeepTMHMM topology — 4 TM bundle. Verified
        # against data/external/deeptmhmm_surfaceome_predictions/
        # human_canonical_non_hla/predicted_topologies.3line on
        # 2026-06-26.
        "topology_str": (
            "I" * 12
            + "M" * 21
            + "O" * 18
            + "M" * 23
            + "I" * 9
            + "M" * 23
            + "O" * 93
            + "M" * 23
            + "I" * 13
        ),
        "has_membrane_slab": True,
    },
]


# ── Topology coloring (mirrors viewer's TOPOLOGY_COLORS) ─────────────
TOPOLOGY_COLORS = {
    "M": "#FFD579",  # TM helix / membrane-associated — gold
    "O": "#8878C8",  # extracellular — lavender
    "I": "#A9CFA8",  # intracellular — soft green
    "S": "#DD5955",  # signal peptide — red
}


# ── Pure-Python port of viewer/lib/structure-orientation.ts ─────────


def _parse_ca(pdb_text: str) -> tuple[list[str], dict[int, np.ndarray]]:
    """Return (lines, resi→CA-coord) for an AlphaFold PDB."""
    lines = pdb_text.splitlines()
    ca: dict[int, np.ndarray] = {}
    for line in lines:
        if not (line.startswith("ATOM") or line.startswith("HETATM")):
            continue
        if len(line) < 54:
            continue
        if line[12:16].strip() != "CA":
            continue
        try:
            resi = int(line[22:26].strip())
            x = float(line[30:38])
            y = float(line[38:46])
            z = float(line[46:54])
        except ValueError:
            continue
        if resi <= 0 or resi in ca:
            continue
        ca[resi] = np.array([x, y, z])
    return lines, ca


def _orient_pdb_by_topology(
    pdb_text: str, topology: str
) -> tuple[str, dict | None]:
    """Port of viewer/lib/structure-orientation.ts. Rotates PDB so
    the I→O axis maps to +Y and the TM-helix mean Y sits at 0. Returns
    the transformed PDB plus a membrane-slab spec (or ``None`` when
    the protein has no TM residues)."""
    lines, ca = _parse_ca(pdb_text)
    states: dict[str, list[np.ndarray]] = {"M": [], "O": [], "I": []}
    for resi, coord in ca.items():
        if 1 <= resi <= len(topology):
            s = topology[resi - 1]
            if s in states:
                states[s].append(coord)
    if not states["M"]:
        return pdb_text, None

    m_centroid = np.mean(states["M"], axis=0)
    o_centroid = (np.mean(states["O"], axis=0)
                  if states["O"] else m_centroid + np.array([0.0, 1.0, 0.0]))
    i_centroid = (np.mean(states["I"], axis=0)
                  if states["I"] else m_centroid - np.array([0.0, 1.0, 0.0]))
    axis = o_centroid - i_centroid
    n = np.linalg.norm(axis)
    if n < 1e-8:
        return pdb_text, None
    axis = axis / n

    target = np.array([0.0, 1.0, 0.0])
    v = np.cross(axis, target)
    s = np.linalg.norm(v)
    c = float(np.dot(axis, target))
    if s < 1e-8:
        R = np.eye(3) if c > 0 else np.diag([1.0, -1.0, -1.0])
    else:
        vx = np.array([
            [0.0,  -v[2],  v[1]],
            [v[2],  0.0,  -v[0]],
            [-v[1], v[0],  0.0],
        ])
        R = np.eye(3) + vx + (vx @ vx) * ((1.0 - c) / (s * s))

    # Translation so TM mean Y == 0
    rotated_m = R @ m_centroid
    y_shift = -rotated_m[1]

    out_lines: list[str] = []
    rotated_tm_y: list[float] = []
    rotated_xz: list[tuple[float, float]] = []
    for line in lines:
        if (line.startswith("ATOM") or line.startswith("HETATM")) and len(line) >= 54:
            try:
                x = float(line[30:38])
                y = float(line[38:46])
                z = float(line[46:54])
            except ValueError:
                out_lines.append(line)
                continue
            new = R @ np.array([x, y, z])
            new[1] += y_shift
            new_line = (
                line[:30]
                + f"{new[0]:8.3f}{new[1]:8.3f}{new[2]:8.3f}"
                + line[54:]
            )
            out_lines.append(new_line)
            atom_name = line[12:16].strip()
            try:
                resi = int(line[22:26].strip())
            except ValueError:
                resi = 0
            if atom_name == "CA" and 1 <= resi <= len(topology):
                if topology[resi - 1] == "M":
                    rotated_tm_y.append(float(new[1]))
                rotated_xz.append((float(new[0]), float(new[2])))
        else:
            out_lines.append(line)

    if not rotated_tm_y:
        return "\n".join(out_lines), None

    y_min = min(rotated_tm_y)
    y_max = max(rotated_tm_y)
    xs = [p[0] for p in rotated_xz]
    zs = [p[1] for p in rotated_xz]
    membrane = {
        "y_min": y_min,
        "y_max": y_max,
        "x_min": min(xs) - 4,
        "x_max": max(xs) + 4,
        "z_min": min(zs) - 4,
        "z_max": max(zs) + 4,
    }
    return "\n".join(out_lines), membrane


# ── PDB fetch (with disk cache so re-renders are instant) ────────────


def _fetch_pdb(uniprot: str) -> str:
    cache = SCRATCH / f"AF-{uniprot}-F1-model_v6.pdb"
    if cache.exists():
        return cache.read_text()
    url = f"https://alphafold.ebi.ac.uk/files/AF-{uniprot}-F1-model_v6.pdb"
    print(f"  fetching {url}")
    r = httpx.get(url, timeout=60, follow_redirects=True)
    r.raise_for_status()
    cache.write_text(r.text)
    return r.text


# ── HTML composition ────────────────────────────────────────────────


_CSS = """
:root {
  --maroon-deepest: #3e0a18;
  --maroon-dark: #6e1428;
  --maroon-mid: #922038;
  --maroon-light: #bc3c4c;
  --teal-deepest: #152e28;
  --teal-mid: #3d6b60;
  --amber-dark: #8c4210;
  --amber-mid: #c07830;
  --amber-bright: #f4aa28;
  --lavender-dark: #3a2888;
  --lavender-bright: #8878c8;
  --success: #1b5e3f;
  --ink: #1f1718;
  --ink-soft: #2a2122;
  --muted: #6f5d5a;
  --line: rgba(31, 23, 24, 0.10);
  --line-soft: rgba(31, 23, 24, 0.06);
  --bg: #fefefe;
  --bg-warm: #f3ece5;
  --surface-soft: #fbf7f2;
  --font-display: "Playfair Display", Georgia, serif;
  --font-sans: "Manrope", -apple-system, "Helvetica Neue", sans-serif;
}

* { box-sizing: border-box; }
html, body {
  margin: 0;
  padding: 24px;
  background: var(--bg);
  font-family: var(--font-sans);
  color: var(--ink);
  -webkit-font-smoothing: antialiased;
  -moz-osx-font-smoothing: grayscale;
}

.grid {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 18px;
  width: 100%;
}

.card {
  background: var(--bg);
  border: 1px solid var(--line);
  border-radius: 14px;
  padding: 22px 22px 18px;
  display: flex;
  flex-direction: column;
  gap: 14px;
  min-width: 0;
}

.header-row { display: flex; flex-direction: column; gap: 4px; }
.symbol {
  font-family: var(--font-display);
  font-weight: 700;
  font-size: 44px;
  line-height: 1;
  letter-spacing: -0.02em;
  color: var(--maroon-deepest);
  margin: 0 0 4px;
}
.name {
  font-family: var(--font-sans);
  font-weight: 500;
  font-size: 13px;
  color: var(--ink);
  margin: 0;
  line-height: 1.3;
}
/* .idrow removed — UniProt / NCBI / Ensembl identifier row dropped */

.sources {
  display: flex;
  align-items: center;
  gap: 8px;
  font-family: var(--font-sans);
  font-size: 11px;
  color: var(--muted);
  letter-spacing: 0.04em;
  text-transform: uppercase;
}
.dot {
  display: inline-block;
  width: 10px; height: 10px;
  border-radius: 50%;
  vertical-align: -1px;
  margin-right: 4px;
}
.src-label { font-weight: 500; }
.benchmark-row {
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  gap: 10px;
  font-family: var(--font-sans);
  font-size: 11px;
  text-transform: uppercase;
  letter-spacing: 0.04em;
  color: var(--muted);
}

/* StatusPill — soft-fill tinted bg + deeper-tone text, no border
   (except neutral). Matches viewer's StatusPill.module.css */
.pill {
  display: inline-flex;
  align-items: center;
  gap: 0.35rem;
  padding: 0.18rem 0.5rem;
  border-radius: 999px;
  font-family: var(--font-sans);
  font-weight: 500;
  text-transform: uppercase;
  letter-spacing: 0.05em;
  font-size: 10px;
  line-height: 1;
  background: transparent;
  border: 1px solid transparent;
}
.pill.lg { padding: 0.22rem 0.6rem; font-size: 11px; }
.tone-neutral  { color: var(--ink-soft); border-color: var(--line); }
.tone-maroon   { color: var(--maroon-dark); background: rgba(146, 32, 56, 0.10); }
.tone-teal     { color: var(--teal-deepest); background: rgba(61, 107, 96, 0.10); }
.tone-amber    { color: var(--amber-dark); background: rgba(192, 120, 48, 0.10); }
.tone-lavender { color: var(--lavender-dark); background: rgba(88, 72, 168, 0.10); }
.tone-success  { color: var(--success); background: rgba(46, 122, 85, 0.10); }
.tone-danger   { color: var(--maroon-dark); background: rgba(146, 32, 56, 0.10); }

/* Pill with embedded label: "LABEL · VALUE" */
.pill .lbl { opacity: 0.72; font-weight: 400; margin-right: 0.2rem; }

/* Structure card — NO border, no background. Same height across all
   3 cards so the card bottoms align. KLK2's globular shape gets
   extra zoom (inside the same 240px box) so it fills the area —
   see the per-gene zoom factor in the JS init below. */
.structure {
  border: none;
  background: var(--bg);
  border-radius: 10px;
  height: 240px;
  position: relative;
}
.structure-legend {
  font-family: var(--font-sans);
  font-size: 9.5px;
  color: var(--muted);
  letter-spacing: 0.05em;
  display: flex;
  gap: 12px;
  margin-top: 4px;
  flex-wrap: wrap;
}
.legend-swatch {
  display: inline-block;
  width: 9px; height: 9px;
  border-radius: 2px;
  vertical-align: -1px;
  margin-right: 4px;
}

/* Vitals 2×2 grid — pure typography, NO background fills. Eyebrow
   label in muted Manrope; value in italic Playfair, tone-colored
   via the .h-vital-display.tone-* convention from the viewer. The
   tone classes set TEXT color only, no background. */
.vitals {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 12px 18px;
  margin: 4px 0;
  background: transparent;
}
.vital { display: flex; flex-direction: column; gap: 4px; min-width: 0; background: transparent; }
.vitalK {
  font-family: var(--font-sans);
  font-size: 9px;
  font-weight: 500;
  letter-spacing: 0.10em;
  text-transform: uppercase;
  color: var(--muted);
  background: transparent;
}
.vitalV {
  font-family: var(--font-display);
  font-style: italic;
  font-weight: 500;
  font-size: 18px;
  line-height: 1.1;
  letter-spacing: -0.015em;
  color: var(--ink);
  background: transparent;
}
.vitalV.tone-success { color: var(--success); }
.vitalV.tone-amber   { color: var(--amber-dark); }
.vitalV.tone-danger  { color: var(--maroon-light); }
.vitalV.tone-neutral { color: var(--muted); }

/* Secondary chips — 2 clean columns for readability. Pills keep
   the viewer's soft-fill styling (10% tint + deeper text color)
   because chips IS where the viewer puts colored tints. */
.chips {
  display: grid;
  grid-template-columns: 1fr 1fr;
  /* Pin each chip row to a minimum height so corresponding rows
     line up across the 3-card strip — without this, a card with a
     short chip on row N renders at a different y-coord than a card
     whose row-N chip wraps to 2+ lines. Min covers a 1-line chip
     comfortably; rows grow taller naturally when content wraps. */
  grid-auto-rows: minmax(2.4rem, auto);
  align-items: stretch;
  column-gap: 8px;
  row-gap: 6px;
  margin-top: 2px;
}
.chips .pill {
  /* In a 2-column grid each chip is its own cell — start text from
     the left so the column reads as an aligned list. */
  justify-content: flex-start;
  /* Vertical fill within the cell so all chips in a row share the
     same height — pairs with grid-auto-rows minmax for cross-card
     row alignment. */
  align-self: stretch;
  align-items: center;
}
"""


def _build_topology_segments(topology: str) -> list[tuple[int, int, str]]:
    """Compress a topology string into (start_resi, end_resi, state) runs.
    1-indexed residue numbers."""
    if not topology:
        return []
    out: list[tuple[int, int, str]] = []
    start = 1
    cur = topology[0]
    for i in range(1, len(topology)):
        if topology[i] != cur:
            out.append((start, i, cur))
            start = i + 1
            cur = topology[i]
    out.append((start, len(topology), cur))
    return out


def _verdict_tone(verdict: str) -> str:
    return {
        "yes": "success",
        "contextual": "amber",
        "no": "neutral",
    }.get(verdict, "neutral")


def _build_html(genes: list[dict]) -> str:
    cards: list[str] = []
    for g in genes:
        # Source dot row
        db_dots = []
        for db_name, called in g["db_flags"].items():
            color = {
                "UniProt": "#bc3c4c",  # maroon-light
                "GO":      "#3d6b60",  # teal-mid
                "HPA":     "#f4aa28",  # amber-bright
                "SURFY":   "#8878c8",  # lavender-bright
                "CSPA":    "#6e1428",  # maroon-dark
            }[db_name]
            dot_color = color if called else "rgba(31,23,24,0.15)"
            db_dots.append(
                f'<span class="src-label">'
                f'<span class="dot" style="background:{dot_color}"></span>{db_name}</span>'
            )
        n_called = sum(g["db_flags"].values())
        src_strip = (
            f'<div class="sources">Sources · {n_called}/5 · '
            + " ".join(db_dots) + "</div>"
        )

        # Vital cells (4)
        vital_cells = "".join(
            f'<div class="vital"><div class="vitalK">{k}</div>'
            f'<div class="vitalV tone-{tone}">{v}</div></div>'
            for k, v, tone in g["vitals"]
        )

        # Chips
        chips = []
        for entry in g["chips"]:
            label, value, tone = entry
            if label is None:
                chips.append(f'<span class="pill tone-{tone}">{value}</span>')
            else:
                chips.append(
                    f'<span class="pill tone-{tone}">'
                    f'<span class="lbl">{label}</span>{value}</span>'
                )

        # Topology legend (only show states actually present in the protein)
        states_present = set(g["topology_str"])
        legend_items = []
        legend_map = [
            ("O", "Extracellular"),
            ("M", "Membrane"),
            ("I", "Intracellular"),
            ("S", "Signal peptide"),
        ]
        for state, label in legend_map:
            if state in states_present:
                legend_items.append(
                    f'<span><span class="legend-swatch" '
                    f'style="background:{TOPOLOGY_COLORS[state]}"></span>{label}</span>'
                )
        legend_html = (
            f'<div class="structure-legend">{"".join(legend_items)}</div>'
            if legend_items else ""
        )

        card_html = textwrap.dedent(f"""
        <div class="card">
          <div class="header-row">
            <h1 class="symbol">{g["symbol"]}</h1>
            <p class="name">{g["name"]}</p>
          </div>
          {src_strip}
          <div class="structure" id="viewer-{g["symbol"]}"></div>
          {legend_html}
          <div class="vitals">{vital_cells}</div>
          <div class="chips">{"".join(chips)}</div>
        </div>
        """).strip()
        cards.append(card_html)

    # 3Dmol initialization JS — one viewer per card, oriented PDB
    # injected from Python, topology coloring applied per-segment.
    js_parts: list[str] = []
    for g in genes:
        symbol = g["symbol"]
        pdb_path = SCRATCH / f"oriented_{symbol}.pdb"
        # JS expects the PDB content inline (not loaded over fetch);
        # gives playwright a deterministic page that doesn't depend on
        # AFDB being reachable at screenshot time.
        pdb_js = pdb_path.read_text().replace("\\", "\\\\").replace("`", "\\`")
        segments = _build_topology_segments(g["topology_str"])
        segment_calls = []
        for start, end, state in segments:
            color = TOPOLOGY_COLORS.get(state, "#cccccc")
            segment_calls.append(
                f'  viewer.setStyle({{resi: "{start}-{end}"}}, '
                f'{{cartoon: {{color: "{color}", opacity: 1.0}}}});'
            )
        slab_call = ""
        if g.get("has_membrane_slab") and g.get("membrane"):
            m = g["membrane"]
            cx = (m["x_min"] + m["x_max"]) / 2
            cz = (m["z_min"] + m["z_max"]) / 2
            cy = (m["y_min"] + m["y_max"]) / 2
            w = m["x_max"] - m["x_min"]
            h = abs(m["y_max"] - m["y_min"])
            d = m["z_max"] - m["z_min"]
            # Thicken slab to ~28 Å so it reads as a true bilayer
            h = max(h, 28.0)
            slab_call = (
                f'  viewer.addBox({{'
                f'center: {{x: {cx:.2f}, y: {cy:.2f}, z: {cz:.2f}}}, '
                f'dimensions: {{w: {w:.2f}, h: {h:.2f}, d: {d:.2f}}}, '
                f'color: "#FBE3A7", opacity: 0.32, wireframe: false}});'
            )
        # Per-gene zoom factor. KLK2's globular shape was small inside
        # the 240px structure box — zoom in more so it fills the area
        # and the card bottom stays aligned with SRC/CD63 instead of
        # extending the card. TM-containing structures (SRC, CD63)
        # stay at the standard 1.15 so the helices + membrane slab
        # have room to breathe.
        zoom_factor = 1.75 if symbol == "KLK2" else 1.15
        js_parts.append(textwrap.dedent(f"""
        (function() {{
          var el = document.getElementById("viewer-{symbol}");
          var viewer = $3Dmol.createViewer(el, {{backgroundColor: "white"}});
          var pdbText = `{pdb_js}`;
          viewer.addModel(pdbText, "pdb");
{chr(10).join(segment_calls)}
{slab_call}
          viewer.zoomTo();
          viewer.zoom({zoom_factor});
          viewer.render();
          window["__rendered_{symbol}"] = true;
        }})();
        """).strip())

    html = f"""<!DOCTYPE html>
<html>
<head>
  <meta charset="utf-8">
  <link rel="preconnect" href="https://fonts.googleapis.com">
  <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
  <link href="https://fonts.googleapis.com/css2?family=Manrope:wght@400;500;600;700;800&family=Playfair+Display:ital,wght@0,400..900;1,400..900&display=swap" rel="stylesheet">
  <script src="https://3Dmol.org/build/3Dmol-min.js"></script>
  <style>{_CSS}</style>
</head>
<body>
  <div class="grid">
    {chr(10).join(cards)}
  </div>
  <script>
    document.fonts.ready.then(function() {{
      {chr(10).join(js_parts)}
    }});
  </script>
</body>
</html>
"""
    return html


# ── Playwright driver ───────────────────────────────────────────────


async def _screenshot_html(html_path: Path, png_path: Path) -> None:
    from playwright.async_api import async_playwright
    async with async_playwright() as p:
        browser = await p.chromium.launch()
        # Viewport sized to comfortably fit 3 cards side-by-side; DPR=3
        # so the final PNG is effectively 600+ DPI when displayed at
        # ~16 inches wide in print.
        context = await browser.new_context(
            viewport={"width": 1640, "height": 1100},
            device_scale_factor=3,
        )
        page = await context.new_page()
        await page.goto(html_path.as_uri())
        # Wait for all three 3Dmol viewers to flag themselves rendered.
        for sym in ("KLK2", "SRC", "CD63"):
            await page.wait_for_function(
                f"window['__rendered_{sym}'] === true",
                timeout=30000,
            )
        # Extra settle so cartoon ribbons finish drawing
        await page.wait_for_timeout(800)
        # Full-page screenshot (cards content sets page height naturally)
        await page.screenshot(path=str(png_path), full_page=True, omit_background=False)
        await context.close()
        await browser.close()


def _open_folder(target: Path) -> None:
    """Auto-open the figures folder per the auto_open_figures_folder
    memory — user has asked us to do this by default."""
    if shutil.which("open"):
        os.system(f"open {target}")


def main() -> int:
    # 1) Fetch + orient each PDB
    for g in GENES:
        pdb = _fetch_pdb(g["uniprot"])
        if g.get("has_membrane_slab"):
            oriented, slab = _orient_pdb_by_topology(pdb, g["topology_str"])
            g["membrane"] = slab
        else:
            oriented, _ = pdb, None
            g["membrane"] = None
        out = SCRATCH / f"oriented_{g['symbol']}.pdb"
        out.write_text(oriented)

    # 2) Build HTML
    html = _build_html(GENES)
    html_path = SCRATCH / "blog_cards.html"
    html_path.write_text(html)
    print(f"  wrote {html_path}")

    # 3) Screenshot via playwright
    png_path = OUT_DIR / f"{SLUG}.png"
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    asyncio.run(_screenshot_html(html_path, png_path))
    print(f"  Saved: {png_path}")

    # PDF wrapping the PNG via matplotlib (Pillow's PDF writer needs
    # JPEG support which this build doesn't have). Vector PDF would
    # require a different render pipeline; PNG-in-PDF is fine for a
    # blog figure where the PNG is the canonical artifact.
    import matplotlib.pyplot as plt
    from PIL import Image
    pdf_path = OUT_DIR / f"{SLUG}.pdf"
    img = Image.open(png_path)
    w, h = img.size
    fig, ax = plt.subplots(figsize=(w / 300, h / 300), dpi=300)
    ax.imshow(img)
    ax.axis("off")
    fig.subplots_adjust(left=0, right=1, top=1, bottom=0)
    fig.savefig(pdf_path, dpi=300, bbox_inches="tight", pad_inches=0)
    plt.close(fig)
    print(f"  Saved: {pdf_path}")

    _open_folder(OUT_DIR)
    return 0


if __name__ == "__main__":
    sys.exit(main())
