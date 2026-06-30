"""Build the manuscript-side spot-check deliverables:

  • paper/figure_index.md       — one row per figure: doc number,
    slug, gist link (or "pending"), bundled-TSV name, and the
    scientist-facing caption from data/analysis/figures/<slug>.caption.md.

  • paper/figure_tsv_spotcheck.html — one section per per-figure
    TSV in data/processed/figures/, showing the head (first ten
    rows) in a styled HTML table so the user can spot-check the
    bundled TSV at a glance without opening each gist.

Run::

    uv run python scripts/build_figure_index.py

Inputs (all in-repo, no network):
  • data/analysis/figures/gist_map.json      — slug → gist_id
  • data/analysis/figures/swhid_map.json     — slug → swh:1:rev:<sha>
  • data/analysis/figures/<slug>.caption.md  — per-figure caption
  • data/processed/figures/<slug>.tsv        — per-figure bundled TSV

Outputs:
  • paper/figure_index.md
  • paper/figure_tsv_spotcheck.html
"""
from __future__ import annotations

import csv
import html
import json
import os
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
GIST_MAP = ROOT / "data/analysis/figures/gist_map.json"
SWHID_MAP = ROOT / "data/analysis/figures/swhid_map.json"
CAPTIONS_DIR = ROOT / "data/analysis/figures"
OUT_DIR_FIG = ROOT / "data/analysis/figures"   # rendered PNG/SVG live here
TSVS_DIR = ROOT / "data/processed/figures"
PAPER_DIR = ROOT / "paper"                     # HTML lives here; img src is relative to it
OUT_MD = ROOT / "paper/figure_index.md"
OUT_HTML = ROOT / "paper/figure_tsv_spotcheck.html"

# Doc figure number → slug, in the order they appear in the manuscript.
# Pulled from the Drive MCP read of the working doc. S3/S7/S13 are
# placeholders in the doc (db_cutoff_tradeoff has no caption row but
# is referenced; S7 ADCs/TCEs/ViralZone is being built in PR87; S13
# not yet built).
FIGURE_ORDER: list[tuple[str, str]] = [
    ("Figure 1",  "db_overlap_venn"),
    ("Figure 2",  "db_correctness_by_class"),
    ("Figure 3",  "zero_db_rescues_by_triage"),
    ("Figure 4",  "deep_dive_flow"),
    ("Figure 5",  "deep_dive_final_categories"),
    ("Figure 6",  "deep_dive_record_richness"),
    ("Figure 7",  "web_preview"),
    ("Supp S1",   "db_correctness_overall"),
    ("Supp S2",   "benchmark_cost_vs_accuracy"),
    ("Supp S3",   "db_cutoff_tradeoff"),
    ("Supp S4",   "curator_vs_agent_reason"),
    ("Supp S5",   "ensemble_vs_best_db_vs_sonnet"),
    ("Supp S6",   "db_vs_sonnet_whole_proteome"),
    ("Supp S8",   "bench_topology_vs_universe"),
    ("Supp S9",   "topology_coverage_by_source"),
    ("Supp S10",  "paywall_bot_block_compare"),
    ("Supp S11",  "evidence_corpus_vs_selected"),
    ("Supp S12",  "triage_vs_deep_dive_reason"),
]


def _load_caption(slug: str) -> str:
    p = CAPTIONS_DIR / f"{slug}.caption.md"
    if not p.is_file():
        return "_(no caption file)_"
    return p.read_text().strip()


def _gist_link(slug: str, gist_map: dict, swhid_map: dict) -> str:
    gid = gist_map.get(slug)
    if not gid:
        return "_(pending publication)_"
    url = f"https://gist.github.com/beccajcarlson/{gid}"
    swhid = swhid_map.get(slug)
    if swhid:
        return f"[gist]({url}) · `{swhid}`"
    return f"[gist]({url})"


# Figures whose gist bundles a canonical TSV from elsewhere in the
# tree rather than a per-figure consolidated one. The single-TSV
# invariant still holds — the gist just sources the data from a TSV
# that lives in its analysis-area folder, not the per-figure-folder.
# Genuine SVG mockups (deep_dive_flow, web_preview) are absent here.
_CANONICAL_TSV: dict[str, Path] = {
    "db_overlap_venn":            ROOT / "data/processed/catalog/whole_proteome_catalog.tsv",
    "zero_db_rescues_by_triage":  ROOT / "data/processed/catalog/whole_proteome_catalog.tsv",
    "db_cutoff_tradeoff":         ROOT / "data/processed/triage_bench/db_cutoff_tradeoff_points.tsv",
    "topology_coverage_by_source": ROOT / "data/analysis/db_vs_sonnet_inclusion/per_protein_features.tsv",
    "paywall_bot_block_compare":  ROOT / "data/processed/paywall_bot_block/paywall_bot_block_compare.tsv",
}

# Slugs that are SVG mockups (no underlying TSV at all).
_SVG_MOCKUPS = {"deep_dive_flow", "web_preview"}


def _tsv_path_for(slug: str) -> Path | None:
    """Find the TSV that this figure's gist bundles. Per-figure-folder
    first (the default for new figures); fall back to the canonical
    TSV from elsewhere in the tree if the figure was published before
    the per-figure consolidation pattern."""
    p = TSVS_DIR / f"{slug}.tsv"
    if p.is_file():
        return p
    return _CANONICAL_TSV.get(slug)


def _bundled_tsv(slug: str) -> str:
    if slug in _SVG_MOCKUPS:
        return "_(SVG mockup — no data TSV)_"
    p = _tsv_path_for(slug)
    if not p or not p.is_file():
        return "_(no TSV resolved)_"
    n_rows = sum(1 for _ in p.read_text().splitlines()) - 1  # minus header
    size_kb = p.stat().st_size / 1024
    return f"`{p.name}` ({n_rows:,} rows · {size_kb:.1f} KB)"


def build_md(gist_map: dict, swhid_map: dict) -> str:
    lines: list[str] = [
        "# Figure index — gists, captions, bundled TSVs",
        "",
        "Generated by `scripts/build_figure_index.py`. One row per "
        "figure in document order; the caption is the scientist-facing "
        "text from `data/analysis/figures/<slug>.caption.md` and the "
        "bundled TSV is the single per-figure file under "
        "`data/processed/figures/`.",
        "",
        "| Doc # | Slug | Gist | Bundled TSV |",
        "|---|---|---|---|",
    ]
    for fig_no, slug in FIGURE_ORDER:
        gist = _gist_link(slug, gist_map, swhid_map)
        tsv = _bundled_tsv(slug)
        lines.append(f"| **{fig_no}** | `{slug}` | {gist} | {tsv} |")
    lines.append("")
    lines.append("---")
    lines.append("")

    for fig_no, slug in FIGURE_ORDER:
        caption = _load_caption(slug)
        lines.append(f"## {fig_no} — `{slug}`")
        lines.append("")
        gist = _gist_link(slug, gist_map, swhid_map)
        tsv = _bundled_tsv(slug)
        lines.append(f"- **Gist:** {gist}")
        lines.append(f"- **Bundled TSV:** {tsv}")
        lines.append("")
        lines.append(caption)
        lines.append("")
        lines.append("---")
        lines.append("")
    return "\n".join(lines)


def _tsv_head(path: Path, n_rows: int = 10) -> tuple[list[str], list[list[str]]]:
    with path.open() as f:
        reader = csv.reader(f, delimiter="\t")
        header = next(reader)
        rows = []
        for i, row in enumerate(reader):
            if i >= n_rows:
                break
            rows.append(row)
    return header, rows


def _html_table(header: list[str], rows: list[list[str]]) -> str:
    parts = ["<table>"]
    parts.append("<thead><tr>")
    for col in header:
        parts.append(f"<th>{html.escape(col)}</th>")
    parts.append("</tr></thead>")
    parts.append("<tbody>")
    for r in rows:
        parts.append("<tr>")
        for cell in r:
            # Truncate any cell over 80 chars
            txt = cell if len(cell) <= 80 else cell[:77] + "…"
            parts.append(f"<td>{html.escape(txt)}</td>")
        parts.append("</tr>")
    parts.append("</tbody></table>")
    return "".join(parts)


def build_html() -> str:
    head = """<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<title>Figure TSV spot-check — accessible-surfaceome</title>
<style>
  body { font-family: -apple-system, BlinkMacSystemFont, 'Inter',
         'Helvetica Neue', sans-serif;
         max-width: 1400px; margin: 2em auto; padding: 0 1em;
         color: #1F1718; background: #FAF7F2; line-height: 1.55; }
  h1 { font-size: 1.7em; border-bottom: 2px solid #BC3C4C; padding-bottom: 6px; }
  h2 { font-size: 1.2em; margin-top: 2em; color: #BC3C4C;
       border-bottom: 1px solid #E6DAD4; padding-bottom: 4px; }
  .meta { color: #6F5D5A; font-size: 0.9em; margin: 0.2em 0 0.8em 0; }
  table { border-collapse: collapse; font-size: 0.78em; margin: 0.6em 0 2em 0;
          background: white; box-shadow: 0 1px 3px rgba(0,0,0,0.05); }
  th { background: #F3ECE5; padding: 6px 9px; text-align: left;
       border-bottom: 2px solid #BC3C4C; font-weight: 600;
       color: #1F1718; white-space: nowrap; }
  td { padding: 5px 9px; border-bottom: 1px solid #E6DAD4;
       font-family: 'SF Mono', Menlo, Consolas, monospace; }
  tbody tr:hover { background: #F7F1EA; }
  .preamble { background: #FFFCF6; padding: 12px 16px; border-left: 3px solid #BC3C4C;
              margin-bottom: 2em; font-size: 0.95em; }
  .empty { color: #999; font-style: italic; }
  .figrow { display: flex; gap: 20px; align-items: flex-start; flex-wrap: wrap; }
  .figthumb { flex: 0 0 360px; }
  .figthumb img { width: 360px; max-width: 100%; height: auto;
                  border: 1px solid #E6DAD4; border-radius: 4px; background: white;
                  box-shadow: 0 1px 3px rgba(0,0,0,0.06); }
  .figdata { flex: 1 1 600px; min-width: 0; overflow-x: auto; }
</style>
</head>
<body>
<h1>Figure TSV spot-check</h1>
<div class="preamble">
One section per per-figure TSV in <code>data/processed/figures/</code> — the
single bundled TSV each gist ships. First ten rows shown. Use this to
spot-check that the gist data matches what the manuscript figure claims.
Generated by <code>scripts/build_figure_index.py</code>.
</div>
"""
    body_parts = [head]
    for fig_no, slug in FIGURE_ORDER:
        body_parts.append(f'<h2>{html.escape(fig_no)} — <code>{html.escape(slug)}</code></h2>')
        body_parts.append('<div class="figrow">')
        # Left: the rendered figure thumbnail so the reader is reminded
        # what the TSV drives. PNG first, then the SVG mockups.
        png = OUT_DIR_FIG / f"{slug}.png"
        svg = OUT_DIR_FIG / f"{slug}.svg"
        img = png if png.is_file() else (svg if svg.is_file() else None)
        if img is not None:
            # img src relative to the HTML's own dir (paper/). os.path.relpath
            # walks up — Path.relative_to(walk_up=) is 3.12+, we're on 3.11.
            rel = os.path.relpath(img, PAPER_DIR)
            body_parts.append(
                f'<div class="figthumb"><img src="{rel}" '
                f'alt="{html.escape(slug)}" loading="lazy"></div>'
            )
        # Right: the TSV head (or the SVG-mockup note).
        body_parts.append('<div class="figdata">')
        if slug in _SVG_MOCKUPS:
            body_parts.append('<p class="empty">SVG mockup — no data TSV.</p>')
        else:
            tsv_path = _tsv_path_for(slug)
            if not tsv_path or not tsv_path.is_file():
                body_parts.append('<p class="empty">No bundled TSV resolved.</p>')
            else:
                n_rows = sum(1 for _ in tsv_path.read_text().splitlines()) - 1
                size_kb = tsv_path.stat().st_size / 1024
                header, rows = _tsv_head(tsv_path, n_rows=10)
                body_parts.append(
                    f'<p class="meta"><code>{tsv_path.name}</code> · '
                    f'{len(header)} cols · {n_rows:,} rows · {size_kb:.1f} KB · '
                    f'<code>{tsv_path.relative_to(ROOT)}</code></p>'
                )
                body_parts.append(_html_table(header, rows))
        body_parts.append('</div>')   # .figdata
        body_parts.append('</div>')   # .figrow
    body_parts.append("</body></html>\n")
    return "\n".join(body_parts)


def main() -> int:
    gist_map = json.loads(GIST_MAP.read_text())
    try:
        swhid_map = json.loads(SWHID_MAP.read_text())
    except FileNotFoundError:
        swhid_map = {}
    OUT_MD.parent.mkdir(parents=True, exist_ok=True)
    OUT_MD.write_text(build_md(gist_map, swhid_map))
    OUT_HTML.write_text(build_html())
    print(f"  wrote {OUT_MD.relative_to(ROOT)}")
    print(f"  wrote {OUT_HTML.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
