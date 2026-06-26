"""Blog gene-card figure for KLK2 / SRC / CD63 — three deep-dive
contribution modes — rendered as a single HTML page with the viewer's
exact CSS + 3Dmol.js structures, then screenshotted via Playwright at
devicePixelRatio=3 (~480 DPI effective).

Why HTML+headless-Chrome instead of pure matplotlib: matplotlib can't
render the viewer's React typography (italic Playfair Display .h-vital-
display values, soft-fill StatusPill chips, .vitalK eyebrows), and it
can't render the actual 3Dmol.js cartoon ribbons. By generating the
page in the viewer's CSS + JS, the screenshot is pixel-faithful to
surfaceome.deliverome.org by construction.

Stages:
  1. Build a self-contained HTML file at ``scratchpad/blog_cards.html``
     with three columns. Each column uses class names borrowed from
     ``viewer/components/surfaceome/GeneHeader/GeneHeader.module.css``
     and design tokens from ``viewer/app/design-tokens.css``.
  2. Launch Playwright Chromium at ``viewport=1600x1200``,
     ``device_scale_factor=3``. Open the file:// URL, wait for 3Dmol
     to finish rendering each structure (signaled by a window-level
     flag the per-card init sets), then ``page.screenshot()``.
  3. Save the screenshot to ``data/analysis/figures/blog_gene_cards_
     klk2_src_cd63.png`` and write a companion PDF rendering of the
     same HTML for the vector deposit.

Run:
    uv run python scripts/blog_gene_cards_klk2_src_cd63.py
"""
from __future__ import annotations

import csv
import json
import os
import textwrap
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT_DIR = ROOT / "data/analysis/figures"
SLUG = "blog_gene_cards_klk2_src_cd63"
SCRATCH = Path(os.environ.get("TMPDIR", "/tmp")) / "blog_cards"
SCRATCH.mkdir(parents=True, exist_ok=True)
HTML_PATH = SCRATCH / "blog_cards.html"
PNG_PATH = OUT_DIR / f"{SLUG}.png"
PDF_PATH = OUT_DIR / f"{SLUG}.pdf"

# ── Per-gene data — pulled from the committed records + catalog ──────
#
# Each gene mirrors what the live surfaceome.deliverome.org/{SYMBOL}
# page displays in the GeneHeader area: symbol + name + identifiers +
# SOURCES row + BENCHMARK + TRIAGE + executive summary + 2×2 vitals
# grid. The topology_str feeds the 3Dmol color-by-residue script.
GENES = [
    {
        "symbol": "KLK2",
        "name": "kallikrein related peptidase 2",
        "synonyms": "KLK2A2, hGK-1, hK2",
        "uniprot_acc": "P20151",
        "hgnc_id": "HGNC:6363",
        "ncbi_gene": "3817",
        "ensembl_gene": "ENSG00000167751",
        "n_db_votes": 0,
        "db_flags": {"UniProt": 0, "GO": 0, "HPA": 0, "SURFY": 0, "CSPA": 0},
        "benchmark_label": "CONTEXTUAL",
        "benchmark_tone": "amber",
        "benchmark_note": "agrees with deep dive",
        "triage_label": "Contextual",
        "triage_note": "initial pass · NO WEB SEARCH · agrees with deep dive",
        "summary": (
            "KLK2 (human kallikrein-2) is a canonical secreted serine protease with no "
            "transmembrane domain, but a 2025 preclinical study (PMC12580770) "
            "demonstrates surface accessibility on intact prostate cancer cells by "
            "live-cell FACS on VCaP and fresh mCRPC patient tumor cells, confocal IF, "
            "and functional engagement via three distinct therapeutic modalities. "
            "Surface expression is strictly prostate-lineage- and AR-state-restricted, "
            "absent in neuroendocrine/double-negative mCRPC variants. The primary risk "
            "is a large competing secreted pool (KLK2 is constitutively secreted into "
            "conditioned medium and seminal plasma), and the surface-docking mechanism "
            "remains uncharacterized."
        ),
        # Vital cells: (eyebrow, display value, tone class, sub-line)
        "vitals": [
            ("SURFACE VERDICT",     "Moderate",            "amber",   "Architecture · Other"),
            ("EXPERIMENTAL EVIDENCE", "Direct, multi-method", "success", "33 entries"),
            ("CONFIDENCE",          "Moderate",            "amber",   "22 primary · 11 secondary"),
            ("STATE DEPENDENCE",    "High",                "amber",   "tissue-restricted"),
        ],
        "topology_str": "S" * 17 + "O" * 244,  # SP + mature secreted
        "structure_legend": [("Extracellular", "#8878C8"), ("Signal peptide", "#DD5955")],
        "sonnet_verdict": "contextual",
        "sonnet_reason":  "tissue_restricted_surface",
        "extra_tags": ["✓ known ligand"],
    },
    {
        "symbol": "SRC",
        "name": "SRC proto-oncogene, non-receptor tyrosine kinase",
        "synonyms": "ASV, SRC1, THC6",
        "uniprot_acc": "P12931",
        "hgnc_id": "HGNC:11283",
        "ncbi_gene": "6714",
        "ensembl_gene": "ENSG00000197122",
        "n_db_votes": 2,
        "db_flags": {"UniProt": 0, "GO": 1, "HPA": 1, "SURFY": 0, "CSPA": 0},
        "benchmark_label": "CONTEXTUAL",
        "benchmark_tone": "amber",
        "benchmark_note": "agrees with deep dive",
        "triage_label": "Contextual",
        "triage_note": "initial pass · NO WEB SEARCH · agrees with deep dive",
        "summary": (
            "SRC is state-dependently surface-accessible in cancer cells — a canonical "
            "inner-leaflet kinase with a cancer-specific outer-surface form. Direct "
            "surface evidence is single-method: antibody-mediated tumor cell killing "
            "against extracellular-facing eSrc in cancer cell lines and xenograft "
            "models demonstrates outer-leaflet engagement. Surface presence is "
            "strictly state-gated, requiring cancer-state autophagolysosomal "
            "exocytosis (ALE) to invert the N-myristoylated kinase onto the outer "
            "leaflet; normal cells retain exclusively inner-leaflet, cytoplasmic-face "
            "localization."
        ),
        "vitals": [
            ("SURFACE VERDICT",     "Moderate",             "amber",   "Architecture · Other"),
            ("EXPERIMENTAL EVIDENCE", "Direct, single-method", "amber",  "36 entries"),
            ("CONFIDENCE",          "Low",                  "danger",  ""),
            ("STATE DEPENDENCE",    "High",                 "amber",   "lysosomal exocytosis"),
        ],
        # SRC = GLOB in DeepTMHMM (no TM helices). Live viewer paints
        # the whole structure in the M-tone (golden) and labels the
        # legend "Globular". Match that here.
        "topology_str": "M" * 536,
        "structure_legend": [("Globular", "#FFD579")],
        "is_glob_no_slab": True,
        "sonnet_verdict": "no",
        "sonnet_reason":  "inner_leaflet_anchored",
        "extra_tags": ["✓ tumor associated"],
    },
    {
        "symbol": "CD63",
        "name": "CD63 antigen",
        "synonyms": "AD1, HOP-26, ME491",
        "uniprot_acc": "P08962",
        "hgnc_id": "HGNC:1692",
        "ncbi_gene": "967",
        "ensembl_gene": "ENSG00000135404",
        "n_db_votes": 4,
        "db_flags": {"UniProt": 1, "GO": 1, "HPA": 0, "SURFY": 1, "CSPA": 1},
        "benchmark_label": "CONTEXTUAL",
        "benchmark_tone": "amber",
        "benchmark_note": "agrees with deep dive",
        "triage_label": "Contextual",
        "triage_note": "initial pass · NO WEB SEARCH · agrees with deep dive",
        "summary": (
            "CD63 is state-dependently surface-accessible as a pan-tissue tetraspanin "
            "whose dominant steady-state localization is lysosomal/endosomal but whose "
            "surface pool expands markedly upon cellular activation. Direct multi-"
            "method support: KO-validated live-cell flow cytometry on HEK293T cells "
            "and primary human granulocytes — basophils and eosinophils — across "
            "multiple independent studies. Surface levels are highly state-modulated: "
            "absent-to-low on resting granulocytes and stromal cells, rising sharply "
            "after IgE-mediated degranulation, platelet activation, TCR stimulation, "
            "and in disease states including HES, NPC, and the CRC tumor microenvironment."
        ),
        "vitals": [
            ("SURFACE VERDICT",     "High",                "success", "Architecture · Tetraspanin"),
            ("EXPERIMENTAL EVIDENCE", "Direct, multi-method", "success", "62 entries"),
            ("CONFIDENCE",          "High",                "success", ""),
            ("STATE DEPENDENCE",    "High",                "amber",   "lysosomal exocytosis"),
        ],
        # CD63 DeepTMHMM .3line topology — 4 TM helices through the
        # plasma membrane, large extracellular loop between TM3+TM4.
        "topology_str": (
            "IIIIIIIIIIII"
            "MMMMMMMMMMMMMMMMMMMMM"
            "OOOOOOOOOOOOOOOOOO"
            "MMMMMMMMMMMMMMMMMMMMMMM"
            "IIIIIIIII"
            "MMMMMMMMMMMMMMMMMMMMMMM"
            "OOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOO"
            "MMMMMMMMMMMMMMMMMMMMMMM"
            "IIIIIIIIIIIII"
        ),
        "structure_legend": [
            ("Extracellular", "#8878C8"),
            ("TM helix",      "#FFD579"),
            ("Intracellular", "#A9CFA8"),
        ],
        "sonnet_verdict": "contextual",
        "sonnet_reason":  "lysosomal_exocytosis",
        "extra_tags": ["✓ known ligand", "Primary · Lysosome"],
    },
]


# ── Topology → 3Dmol color spec (per-residue cartoon coloring) ───────


def _topology_to_3dmol_colors(topo: str) -> list[dict]:
    """Build a list of 3Dmol setStyle invocations that color each
    contiguous topology run with the viewer's TOPOLOGY_COLORS palette."""
    palette = {
        "M": "#FFD579", "O": "#8878C8", "I": "#A9CFA8",
        "S": "#DD5955", "B": "#C7CED6",
    }
    out: list[dict] = []
    if not topo:
        return out
    run_start = 1
    run_char = topo[0]
    for i in range(1, len(topo)):
        if topo[i] != run_char:
            out.append({
                "resi_from": run_start, "resi_to": i,
                "color": palette.get(run_char, "#A9CFA8"),
            })
            run_start = i + 1
            run_char = topo[i]
    out.append({
        "resi_from": run_start, "resi_to": len(topo),
        "color": palette.get(run_char, "#A9CFA8"),
    })
    return out


# ── HTML generation ──────────────────────────────────────────────────


_DESIGN_TOKENS_CSS = """
:root {
  --maroon-deepest: #3e0a18; --maroon-dark: #6e1428; --maroon-light: #bc3c4c;
  --maroon-pale: #f0a098;   --maroon-blush: #fde8e6;
  --teal-deepest: #152e28;  --teal-dark: #244840; --teal-mid: #3d6b60; --teal-lt: #7aab9f;
  --amber-deepest: #5a2608; --amber-dark: #8c4210; --amber-mid: #c07830;
  --amber-bright: #f4aa28;  --amber-light: #f4c070;
  --lavender-deepest: #1e1450; --lavender-dark: #3a2888; --lavender-mid: #5848a8;
  --lavender-bright: #8878c8;
  --ink: #1f1718; --ink-soft: #2a2122; --muted: #6f5d5a; --muted-soft: #80706a;
  --line: rgba(31,23,24,0.10); --line-soft: rgba(31,23,24,0.06);
  --bg: #fefefe; --bg-soft: #ffffff; --bg-warm: #f3ece5;
  --success: #2e7a55; --accent: var(--maroon-light); --accent-deep: var(--maroon-dark);
  --radius-pill: 999px;
  --space-1: 0.25rem; --space-2: 0.5rem; --space-3: 0.75rem;
  --space-4: 1rem;    --space-5: 1.5rem; --space-6: 2rem;
  --fw-medium: 500;   --fw-semibold: 600;
}
"""

_PAGE_CSS = """
* { box-sizing: border-box; }
html, body {
  margin: 0; padding: 0;
  background: var(--bg);
  font-family: 'Manrope', -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
  color: var(--ink);
  -webkit-font-smoothing: antialiased; -moz-osx-font-smoothing: grayscale;
}
.cards {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 1.75rem;
  padding: 1.5rem;
  align-items: start;
}
.card { min-width: 0; }
.card .symbol {
  font-family: 'Playfair Display', 'Georgia', serif;
  font-weight: 700; font-size: 3.6rem; line-height: 1;
  color: var(--maroon-deepest);
  margin: 0 0 0.4rem;
  letter-spacing: -0.01em;
}
.card .name {
  font-style: italic; color: var(--ink-soft); font-size: 0.92rem;
  font-weight: 400;
  margin: 0 0 0.4rem;
}
.card .synonyms { color: var(--muted); font-size: 0.78rem; margin-left: 0.5rem; }
.card .idRow {
  display: flex; flex-wrap: wrap; gap: 0.9rem;
  font-size: 0.72rem; font-family: 'Manrope', sans-serif;
  color: var(--ink); margin: 0.5rem 0 0.7rem;
}
.card .idK { color: var(--muted); font-weight: 500; letter-spacing: 0.04em; text-transform: uppercase; font-size: 0.62rem; }
.card .idV { color: var(--ink); font-weight: 500; }
.card .sourcesRow {
  display: flex; align-items: center; gap: 0.6rem; flex-wrap: wrap;
  font-size: 0.72rem; margin-bottom: 0.45rem;
}
.card .sourcesK {
  color: var(--muted); text-transform: uppercase; letter-spacing: 0.1em;
  font-size: 0.62rem; font-weight: 500;
}
.card .dot {
  width: 9px; height: 9px; border-radius: 50%;
  display: inline-block; vertical-align: middle; margin-right: 4px;
}
.card .dotOff { background: rgba(31,23,24,0.18); }
.card .src { display: inline-flex; align-items: center; gap: 0.3rem; font-size: 0.72rem; }
.card .srcOff { color: var(--muted); }
.card .miniRow {
  display: flex; align-items: center; gap: 0.6rem;
  font-size: 0.72rem; color: var(--ink); margin: 0.3rem 0;
}
.card .miniK {
  color: var(--muted); text-transform: uppercase; letter-spacing: 0.1em;
  font-size: 0.62rem; font-weight: 500;
}
.card .pill {
  display: inline-flex; align-items: center;
  font-family: 'Manrope', sans-serif; font-weight: 500;
  text-transform: uppercase; letter-spacing: 0.05em;
  line-height: 1; white-space: nowrap;
  padding: 0.22rem 0.55rem; border-radius: var(--radius-pill);
  font-size: 0.68rem; border: 1px solid transparent;
}
.pill.tone-amber { color: var(--amber-dark); background: rgba(192,120,48,0.10); }
.pill.tone-success { color: #1b5e3f; background: rgba(46,122,85,0.10); }
.pill.tone-maroon { color: var(--maroon-dark); background: rgba(146,32,56,0.10); }
.pill.tone-teal { color: var(--teal-deepest); background: rgba(61,107,96,0.10); }
.pill.tone-lavender { color: var(--lavender-dark); background: rgba(88,72,168,0.10); }
.pill.tone-neutral { color: var(--ink-soft); background: transparent; border-color: var(--line); }
.card .summary {
  font-size: 0.78rem; line-height: 1.55; color: var(--ink);
  margin: 0.8rem 0;
}
.card .vitals {
  display: grid; grid-template-columns: 1fr 1fr;
  gap: 0.9rem 1.4rem;
  margin: 0.85rem 0 0.6rem;
  padding-top: 0.7rem;
  border-top: 1px solid var(--line);
}
.vital { min-width: 0; display: flex; flex-direction: column; gap: 0.25rem; }
.vitalK {
  color: var(--muted); font-size: 0.66rem; font-weight: 500; letter-spacing: 0.1em;
  text-transform: uppercase;
}
.vitalV {
  margin: 0;
  font-family: 'Playfair Display', 'Georgia', serif;
  font-style: italic; font-weight: 500; font-size: 1.45rem;
  line-height: 1.05; letter-spacing: -0.015em;
  color: var(--ink);
}
.vitalV.tone-success { color: var(--success); }
.vitalV.tone-amber   { color: var(--amber-dark); }
.vitalV.tone-danger  { color: var(--accent-deep); }
.vitalV.tone-neutral { color: var(--muted); }
.vitalSub { color: var(--muted); font-size: 0.68rem; line-height: 1.35; }
.card .extraTags {
  display: flex; flex-wrap: wrap; gap: 0.35rem;
  margin: 0.5rem 0 0.6rem;
}
.card .structure {
  margin-top: 0.6rem;
  background: var(--bg-soft);
  border: 1px solid var(--line);
  border-radius: 10px;
  overflow: hidden;
}
.card .structureFrame { width: 100%; height: 280px; position: relative; }
.card .structureFooter {
  font-size: 0.66rem; color: var(--muted);
  padding: 0.4rem 0.6rem; border-top: 1px solid var(--line);
  display: flex; gap: 0.6rem; align-items: center; flex-wrap: wrap;
}
.card .legendSwatch {
  display: inline-block; width: 10px; height: 10px; border-radius: 2px;
  margin-right: 4px; vertical-align: middle;
}
.card .verdictBar {
  margin-top: 0.7rem; padding: 0.5rem 0.8rem;
  border-radius: var(--radius-pill); text-align: center;
  font-size: 0.74rem; letter-spacing: 0.05em; font-weight: 600;
  text-transform: uppercase;
}
.verdictBar.tone-amber   { background: rgba(192,120,48,0.10); color: var(--amber-dark); }
.verdictBar.tone-neutral { background: rgba(31,23,24,0.04);   color: var(--ink-soft); border: 1px solid var(--line); }
.verdictBar.tone-success { background: rgba(46,122,85,0.10); color: #1b5e3f; }
"""


# Brand DB colors — same source-to-color mapping as make_db_correctness_by_class.py
_DB_COLOR = {
    "UniProt": "#BC3C4C",
    "GO":      "#3D6B60",
    "HPA":     "#F4AA28",
    "SURFY":   "#8878C8",
    "CSPA":    "#6E1428",
}


def _render_sources_row(g: dict) -> str:
    parts = [f'<span class="sourcesK">SOURCES · {g["n_db_votes"]}/5</span>']
    for name, called in g["db_flags"].items():
        color = _DB_COLOR[name]
        if called:
            parts.append(
                f'<span class="src"><span class="dot" style="background:{color}"></span>'
                f'<span style="color:var(--ink); font-weight:500">{name}</span></span>'
            )
        else:
            parts.append(
                f'<span class="src srcOff"><span class="dot dotOff"></span>'
                f'<span>{name}</span></span>'
            )
    return f'<div class="sourcesRow">{"".join(parts)}</div>'


def _render_vitals(g: dict) -> str:
    cells: list[str] = []
    for eyebrow, value, tone, sub in g["vitals"]:
        sub_html = f'<div class="vitalSub">{sub}</div>' if sub else ""
        cells.append(textwrap.dedent(f"""\
          <div class="vital">
            <div class="vitalK">{eyebrow}</div>
            <p class="vitalV tone-{tone}">{value}</p>
            {sub_html}
          </div>"""))
    return f'<div class="vitals">{"".join(cells)}</div>'


def _verdict_tone(verdict: str) -> str:
    return {"yes": "success", "contextual": "amber", "no": "neutral"}.get(verdict, "neutral")


def _render_card(g: dict) -> str:
    color_specs = _topology_to_3dmol_colors(g["topology_str"])
    color_specs_json = json.dumps(color_specs)
    pdb_url = f"https://alphafold.ebi.ac.uk/files/AF-{g['uniprot_acc']}-F1-model_v6.pdb"
    is_glob = bool(g.get("is_glob_no_slab"))
    extra_tags_html = "".join(
        f'<span class="pill tone-neutral">{t}</span>' for t in g.get("extra_tags", [])
    )
    legend_html = " · ".join(
        f'<span><span class="legendSwatch" style="background:{c}"></span>{name}</span>'
        for name, c in g["structure_legend"]
    )
    verdict_tone = _verdict_tone(g["sonnet_verdict"])
    return f"""
  <div class="card">
    <h1 class="symbol">{g['symbol']}</h1>
    <p class="name">{g['name']}<span class="synonyms">Synonyms: {g['synonyms']}</span></p>
    <div class="idRow">
      <span><span class="idK">HGNC</span> <span class="idV">{g['hgnc_id']}</span></span>
      <span><span class="idK">UniProt</span> <span class="idV">{g['uniprot_acc']}</span></span>
      <span><span class="idK">NCBI gene</span> <span class="idV">{g['ncbi_gene']}</span></span>
      <span><span class="idK">Ensembl</span> <span class="idV">{g['ensembl_gene']}</span></span>
    </div>
    {_render_sources_row(g)}
    <div class="miniRow">
      <span class="miniK">Benchmark</span>
      <span class="pill tone-{g['benchmark_tone']}">{g['benchmark_label']}</span>
      <span class="vitalSub">{g['benchmark_note']}</span>
    </div>
    <div class="miniRow">
      <span class="miniK">Triage</span>
      <span class="vitalSub">{g['triage_label']} — {g['triage_note']}</span>
    </div>
    <p class="summary">{g['summary']}</p>
    {_render_vitals(g)}
    <div class="extraTags">{extra_tags_html}</div>
    <div class="structure">
      <div class="structureFrame" id="viewer-{g['symbol']}" data-pdb="{pdb_url}"
           data-colorspecs='{color_specs_json}'
           data-is-glob="{'1' if is_glob else '0'}"></div>
      <div class="structureFooter">
        <span style="color:var(--ink-soft); font-weight:500">AlphaFold</span>
        <span>AFDB {g['uniprot_acc']} · v6</span>
        <span style="flex:1"></span>
        {legend_html}
      </div>
    </div>
    <div class="verdictBar tone-{verdict_tone}">
      Sonnet · {g['sonnet_verdict']} · {g['sonnet_reason'].replace('_', ' ')}
    </div>
  </div>
"""


_3DMOL_INIT_JS = """
window.__viewersReady = 0;
window.__expectedViewers = document.querySelectorAll('[id^="viewer-"]').length;

function initViewers() {
  document.querySelectorAll('[id^="viewer-"]').forEach(function(el) {
    const pdbUrl = el.getAttribute('data-pdb');
    const colorSpecs = JSON.parse(el.getAttribute('data-colorspecs'));
    const isGlob = el.getAttribute('data-is-glob') === '1';
    const viewer = $3Dmol.createViewer(el, {backgroundColor: 'white'});
    fetch(pdbUrl).then(r => r.text()).then(function(pdb) {
      viewer.addModel(pdb, 'pdb');
      // Base cartoon style
      viewer.setStyle({}, {cartoon: {color: '#A9CFA8'}});
      // Per-topology coloring
      colorSpecs.forEach(function(spec) {
        viewer.setStyle({resi: spec.resi_from + '-' + spec.resi_to},
                        {cartoon: {color: spec.color}});
      });
      // Membrane slab for true TM proteins (not GLOB-flagged ones).
      // Slab drawn as a thin disk at the median z of TM residues.
      const hasTM = colorSpecs.some(function(s) { return s.color === '#FFD579'; });
      if (hasTM && !isGlob) {
        const tmAtoms = viewer.selectedAtoms({chain: 'A'}).filter(function(a) {
          return a.atom === 'CA' && a.resi && colorSpecs.some(function(s) {
            return s.color === '#FFD579' && a.resi >= s.resi_from && a.resi <= s.resi_to;
          });
        });
        if (tmAtoms.length) {
          const zs = tmAtoms.map(function(a) { return a.z; }).sort(function(a,b){return a-b;});
          const zMid = zs[Math.floor(zs.length/2)];
          viewer.addBox({
            corner: {x: -22, y: -22, z: zMid - 6},
            dimensions: {w: 44, h: 44, d: 12},
            color: '#A0A4AB', opacity: 0.12, wireframe: false,
          });
        }
      }
      viewer.zoomTo();
      viewer.zoom(1.05);
      viewer.render();
      window.__viewersReady += 1;
    });
  });
}
"""


def _render_html() -> str:
    body = "\n".join(_render_card(g) for g in GENES)
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<title>Surfaceome blog cards · KLK2 · SRC · CD63</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Manrope:wght@400;500;600;700&family=Playfair+Display:ital,wght@0,400..900;1,400..900&display=swap" rel="stylesheet">
<script src="https://3dmol.org/build/3Dmol-min.js"></script>
<style>
{_DESIGN_TOKENS_CSS}
{_PAGE_CSS}
</style>
</head>
<body>
<div class="cards">
{body}
</div>
<script>
{_3DMOL_INIT_JS}
window.addEventListener('load', initViewers);
</script>
</body>
</html>
"""


def _render_and_screenshot() -> None:
    HTML_PATH.write_text(_render_html())
    print(f"  wrote {HTML_PATH}")

    from playwright.sync_api import sync_playwright
    with sync_playwright() as p:
        browser = p.chromium.launch()
        # 1600×1200 viewport at devicePixelRatio=3 → 4800×3600 screenshot.
        # 16-inch print width → 300 DPI. Good for blog + Zenodo.
        ctx = browser.new_context(
            viewport={"width": 1600, "height": 1200},
            device_scale_factor=3,
        )
        page = ctx.new_page()
        page.goto(f"file://{HTML_PATH}")
        # Wait for all 3Dmol viewers to finish rendering (window flag
        # set by the init script).
        page.wait_for_function(
            "window.__viewersReady === window.__expectedViewers",
            timeout=30_000,
        )
        # Extra beat for fonts + 3Dmol last-frame settle
        page.wait_for_timeout(800)
        OUT_DIR.mkdir(parents=True, exist_ok=True)
        page.screenshot(path=str(PNG_PATH), full_page=True)
        print(f"  Saved: {PNG_PATH}")
        page.pdf(path=str(PDF_PATH), width="16in", height="11in", print_background=True)
        print(f"  Saved: {PDF_PATH}")
        browser.close()


def main() -> None:
    _render_and_screenshot()


if __name__ == "__main__":
    main()
