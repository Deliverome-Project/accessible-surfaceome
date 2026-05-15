"""Render a BiologicalContextDraft JSON file as a single self-contained HTML.

Usage:

    uv run python -m accessible_surfaceome.agents.biology_compiler.render_html \\
        .runs/a2_EGFR.json

Writes ``a2_EGFR.html`` alongside the input. No external assets — open it
straight in a browser.
"""

from __future__ import annotations

import html
import json
import sys
from pathlib import Path
from typing import Any


def _source_url(source_id: str) -> str | None:
    """Best-effort URL for a SourceRef id."""
    if source_id.startswith("PMID:"):
        return f"https://pubmed.ncbi.nlm.nih.gov/{source_id[5:].strip()}/"
    if source_id.startswith("PMC:PMC"):
        return f"https://europepmc.org/article/PMC/{source_id[4:].strip()}"
    if source_id.startswith("PMC:"):
        return f"https://europepmc.org/article/PMC/{source_id[4:].strip()}"
    if source_id.startswith("HPA:"):
        return f"https://www.proteinatlas.org/?query={source_id[4:].strip()}"
    if source_id.startswith("UniProt:"):
        return f"https://www.uniprot.org/uniprotkb/{source_id[8:].strip()}"
    if source_id.startswith("DOI:"):
        return f"https://doi.org/{source_id[4:].strip()}"
    if source_id.startswith("PDB:"):
        return f"https://www.rcsb.org/structure/{source_id[4:].strip()}"
    return None


def _src_link(source_id: str) -> str:
    """Source-id chip with a hyperlink when we can construct one."""
    safe = html.escape(source_id)
    url = _source_url(source_id)
    if url is None:
        return f'<span class="src">{safe}</span>'
    return f'<a class="src" href="{html.escape(url)}" target="_blank" rel="noopener">{safe}</a>'


def _badge(text: str, kind: str) -> str:
    return f'<span class="badge badge-{html.escape(kind)}">{html.escape(text)}</span>'


# tissue-presence enum → CSS badge kind
_PRESENCE_KIND = {
    "high": "green",
    "moderate": "blue",
    "low": "amber",
    "absent": "red",
    "mixed": "gray",
    "unknown": "gray",
}
_DISEASE_KIND = {"normal": "gray", "disease": "amber", "mixed": "gray", "unknown": "gray"}
_ACCESSIBILITY_KIND = {
    "accessible_systemic": "green",
    "accessible_local_only": "blue",
    "restricted_partial": "amber",
    "inaccessible_systemic": "red",
    "unclear": "gray",
}


def _render_evi_chips(ids: list[str]) -> str:
    if not ids:
        return ""
    chips = " ".join(
        f'<span class="evi-chip">{html.escape(eid)}</span>' for eid in ids
    )
    return f'<div class="cites">cited: {chips}</div>'


_EMPTY_CELL = '<span class="muted">—</span>'


def _tissue_row(t: dict[str, Any]) -> str:
    present = t.get("present", "?")
    disease = t.get("disease_context", "?")
    ctypes = ", ".join(html.escape(c) for c in t.get("cell_types", [])) or _EMPTY_CELL
    cstates = ", ".join(html.escape(c) for c in t.get("cell_states", [])) or _EMPTY_CELL
    cites = " ".join(html.escape(c) for c in t.get("cited_evidence_ids", []))
    return (
        "<tr>"
        f"<td>{html.escape(t.get('tissue', '?'))}</td>"
        f"<td>{_badge(present, _PRESENCE_KIND.get(present, 'gray'))}</td>"
        f"<td>{_badge(disease, _DISEASE_KIND.get(disease, 'gray'))}</td>"
        f"<td>{ctypes}</td>"
        f"<td>{cstates}</td>"
        f"<td>{cites}</td>"
        "</tr>"
    )


def _render_tissues(items: list[dict[str, Any]]) -> str:
    if not items:
        return '<p class="muted">none</p>'
    rows = "".join(_tissue_row(t) for t in items)
    return (
        '<table class="tissues"><thead><tr>'
        "<th>tissue</th><th>present</th><th>disease context</th>"
        "<th>cell types</th><th>cell states</th><th>cites</th>"
        "</tr></thead><tbody>" + rows + "</tbody></table>"
    )


def _ctype_row(ct: dict[str, Any]) -> str:
    tissues = (
        ", ".join(html.escape(t) for t in ct.get("present_in_tissues", []))
        or _EMPTY_CELL
    )
    return (
        "<tr>"
        f"<td><strong>{html.escape(ct.get('cell_type', '?'))}</strong></td>"
        f"<td>{html.escape(ct.get('ontology_id') or '—')}</td>"
        f"<td>{tissues}</td>"
        f"<td>{' '.join(html.escape(c) for c in ct.get('cited_evidence_ids', []))}</td>"
        "</tr>"
    )


def _render_cell_types(items: list[dict[str, Any]]) -> str:
    if not items:
        return '<p class="muted">none</p>'
    rows = "".join(_ctype_row(ct) for ct in items)
    return (
        '<table class="ctypes"><thead><tr>'
        "<th>cell type</th><th>ontology</th><th>present in</th><th>cites</th>"
        "</tr></thead><tbody>" + rows + "</tbody></table>"
    )


def _cstate_row(s: dict[str, Any]) -> str:
    return (
        "<tr>"
        f"<td><strong>{html.escape(s.get('state', '?'))}</strong></td>"
        f"<td>{html.escape(s.get('descriptor', ''))}</td>"
        f"<td>{' '.join(html.escape(c) for c in s.get('cited_evidence_ids', []))}</td>"
        "</tr>"
    )


def _render_cell_states(items: list[dict[str, Any]]) -> str:
    if not items:
        return '<p class="muted">none</p>'
    rows = "".join(_cstate_row(s) for s in items)
    return (
        '<table class="cstates"><thead><tr>'
        "<th>state</th><th>descriptor</th><th>cites</th>"
        "</tr></thead><tbody>" + rows + "</tbody></table>"
    )


def _dual_row(d: dict[str, Any]) -> str:
    frac = d.get("fraction_estimate")
    frac_text = "—" if frac is None else f"{frac:.2f}"
    return (
        "<tr>"
        f"<td>{html.escape(d.get('compartment', '?'))}</td>"
        f"<td>{html.escape(frac_text)}</td>"
        f"<td>{html.escape(d.get('condition') or '—')}</td>"
        f"<td>{' '.join(html.escape(c) for c in d.get('cited_evidence_ids', []))}</td>"
        "</tr>"
    )


def _subdomain_card(s: dict[str, Any]) -> str:
    badge = _badge(s.get("subdomain", "?"), "blue")
    cites = _render_evi_chips(s.get("cited_evidence_ids", []))
    return f'<div class="subdomain">{badge}{cites}</div>'


def _render_subcellular(loc: dict[str, Any]) -> str:
    primary = loc.get("primary_compartment", "?")
    dual = loc.get("dual_localization", [])
    subs = loc.get("membrane_subdomains", [])
    dual_html = ""
    if dual:
        rows = "".join(_dual_row(d) for d in dual)
        dual_html = (
            "<h3>Dual localization</h3>"
            '<table class="dual"><thead><tr>'
            "<th>compartment</th><th>fraction</th><th>condition</th><th>cites</th>"
            "</tr></thead><tbody>" + rows + "</tbody></table>"
        )
    sub_html = ""
    if subs:
        chips = " ".join(_subdomain_card(s) for s in subs)
        sub_html = (
            "<h3>Membrane subdomains</h3>"
            f'<div class="subdomains">{chips}</div>'
        )
    primary_kind = "green" if primary == "plasma_membrane" else "gray"
    primary_html = (
        '<div class="primary-loc">primary compartment: '
        f"{_badge(primary, primary_kind)}</div>"
    )
    return primary_html + dual_html + sub_html


def _render_anatomical(items: list[dict[str, Any]]) -> str:
    if not items:
        return '<p class="muted">none</p>'
    cards = "".join(
        f"""
<div class="anat">
  <div class="anat-head">
    {_badge("orientation: " + a.get("orientation", "?"), "gray")}
    {_badge(a.get("accessibility_implication", "?").replace("_", " "),
            _ACCESSIBILITY_KIND.get(a.get("accessibility_implication", ""), "gray"))}
  </div>
  <p><strong>context:</strong> {html.escape(a.get("context", ""))}</p>
  <p class="rationale">{html.escape(a.get("rationale", ""))}</p>
  {_render_evi_chips(a.get("cited_evidence_ids", []))}
</div>"""
        for a in items
    )
    return cards


def _render_modulation(items: list[dict[str, Any]]) -> str:
    if not items:
        return '<p class="muted">none</p>'
    cards: list[str] = []
    for m in items:
        sub_chips: list[str] = []
        if m.get("cell_state_trigger"):
            sub_chips.append(_badge("trigger: " + m["cell_state_trigger"], "amber"))
        if m.get("restricted_lineage"):
            sub_chips.append(_badge("lineage: " + m["restricted_lineage"], "blue"))
        if m.get("dual_loc_partner_compartment"):
            sub_chips.append(
                _badge("partner: " + m["dual_loc_partner_compartment"], "blue")
            )
        if m.get("category_other_label"):
            sub_chips.append(_badge("label: " + m["category_other_label"], "gray"))
        cards.append(
            f"""
<div class="mod">
  <div class="mod-head">
    {_badge("category: " + m.get("category", "?").replace("_", " "), "green")}
    {" ".join(sub_chips)}
  </div>
  <p><strong>baseline:</strong> {html.escape(m.get("baseline_context", ""))}</p>
  <p><strong>modulating state:</strong> {html.escape(m.get("modulating_state", ""))}</p>
  <p><strong>change:</strong> {html.escape(m.get("change", ""))}</p>
  <p class="rationale"><strong>accessibility implication:</strong>
    {html.escape(m.get("accessibility_implication", ""))}</p>
  {_render_evi_chips(m.get("cited_evidence_ids", []))}
</div>"""
        )
    return "".join(cards)


def _render_claim(c: dict[str, Any]) -> str:
    src = _src_link(c.get("source_id", ""))
    fig = (
        f' · <em>{html.escape(c["figure_or_table_id"])}</em>'
        if c.get("figure_or_table_id")
        else ""
    )
    return f"""
<div class="claim" id="{html.escape(c["evidence_id"])}">
  <div class="claim-head">
    <code class="evi-id">{html.escape(c["evidence_id"])}</code>
    {_badge(c.get("claim_type", "?"), "gray")}
    {_badge(c.get("evidence_type", "?").replace("_", " "), "gray")}
    {_badge(c.get("evidence_tier", "?"), "gray")}
    {_badge(c.get("confidence", "?"), "gray")}
    {src}
    <span class="section-tag">{html.escape(c.get("section", "?"))}{fig}</span>
  </div>
  <p class="claim-text">{html.escape(c.get("claim", ""))}</p>
  <blockquote>“{html.escape(c.get("quote", ""))}”</blockquote>
</div>"""


_STYLE = """
:root { --ink:#1c1612; --paper:#fbf9f6; --muted:#7a6f66; --rule:#e6dfd6;
        --green:#1f7a45; --amber:#9a6a14; --red:#8c2a23; --blue:#2a4d8c; }
* { box-sizing: border-box; }
body { font-family: -apple-system, BlinkMacSystemFont, "Manrope", "Inter",
       sans-serif; color: var(--ink); background: var(--paper); margin: 0;
       line-height: 1.5; }
.wrap { max-width: 960px; margin: 0 auto; padding: 32px 28px 64px; }
h1 { font-size: 32px; font-weight: 600; letter-spacing: -0.01em; margin: 0; }
h2 { font-size: 18px; font-weight: 600; letter-spacing: 0.04em;
     text-transform: uppercase; color: var(--muted); margin: 40px 0 14px;
     padding-bottom: 6px; border-bottom: 1px solid var(--rule); }
h3 { font-size: 14px; font-weight: 600; letter-spacing: 0.04em;
     text-transform: uppercase; color: var(--muted); margin: 18px 0 8px; }
.summary { display: flex; align-items: baseline; gap: 18px; flex-wrap: wrap;
           margin-top: 8px; }
.summary .count { color: var(--muted); font-variant-numeric: tabular-nums; }
.primary-loc { background: white; border: 1px solid var(--rule);
               padding: 12px 16px; border-radius: 8px; font-weight: 500; }
.anat, .mod, .claim { background: white; border: 1px solid var(--rule);
    border-radius: 8px; padding: 14px 18px; margin-bottom: 12px; }
.anat p, .mod p { margin: 6px 0; font-size: 14px; }
.anat-head, .mod-head, .claim-head, .chips {
    display: flex; gap: 6px; flex-wrap: wrap; align-items: center; }
.subdomains { display: flex; gap: 10px; flex-wrap: wrap; }
.subdomain { padding: 8px 10px; background: white; border: 1px solid var(--rule);
             border-radius: 8px; }
.badge { display: inline-block; padding: 2px 8px; border-radius: 999px;
         font-size: 12px; font-weight: 500; line-height: 1.4; }
.badge-green { background: rgba(31,122,69,0.12); color: var(--green); }
.badge-amber { background: rgba(154,106,20,0.12); color: var(--amber); }
.badge-red   { background: rgba(140,42,35,0.12); color: var(--red); }
.badge-blue  { background: rgba(42,77,140,0.12); color: var(--blue); }
.badge-gray  { background: rgba(28,22,18,0.06); color: var(--ink); }
.evi-chip { background: rgba(42,77,140,0.10); color: var(--blue); padding: 1px 6px;
            border-radius: 4px; font-family: "SF Mono", monospace; font-size: 12px; }
table { width: 100%; border-collapse: collapse; margin-top: 10px;
        font-size: 13px; }
table th { text-align: left; color: var(--muted); font-weight: 500;
           text-transform: uppercase; font-size: 11px; letter-spacing: 0.04em;
           padding: 6px 8px; border-bottom: 1px solid var(--rule); }
table td { padding: 6px 8px; border-bottom: 1px solid var(--rule);
           vertical-align: top; }
table tr:last-child td { border-bottom: none; }
.claim .claim-text { margin: 8px 0; }
.claim blockquote { margin: 8px 0 0; padding-left: 12px; border-left: 3px solid var(--rule);
                    color: var(--ink); font-style: italic; }
.evi-id { background: rgba(28,22,18,0.06); padding: 1px 6px; border-radius: 4px; }
.src { font-family: "SF Mono", monospace; font-size: 12px; color: var(--blue);
       text-decoration: none; padding: 1px 6px; border-radius: 4px;
       background: rgba(42,77,140,0.06); }
.src:hover { background: rgba(42,77,140,0.14); }
.section-tag { color: var(--muted); font-size: 12px; }
.cites { color: var(--muted); font-size: 12px; margin-top: 6px; }
.rationale { background: rgba(154,106,20,0.06); padding: 8px 10px;
             border-radius: 6px; font-size: 14px; }
.muted { color: var(--muted); }
.meta { color: var(--muted); font-size: 13px; margin-top: 4px; }
"""


def render_html(draft: dict[str, Any], gene: str) -> str:
    bc = draft["biological_context"]
    claims = draft.get("evidence_claims", [])
    tissues = bc.get("tissues", [])
    cell_types = bc.get("cell_types", [])
    cell_states = bc.get("cell_states", [])
    sub_loc = bc.get("subcellular_localization", {})
    anat = bc.get("anatomical_accessibility", [])
    mod = bc.get("accessibility_modulation", [])

    return f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8">
<title>A2 biological_context — {html.escape(gene)}</title>
<style>{_STYLE}</style>
</head><body><div class="wrap">

<header>
  <h1>{html.escape(gene)} — biological context</h1>
  <div class="summary">
    <span class="count">{len(tissues)} tissues</span>
    <span class="count">{len(cell_types)} cell types</span>
    <span class="count">{len(cell_states)} cell states</span>
    <span class="count">{len(anat)} anatomical</span>
    <span class="count">{len(mod)} modulations</span>
    <span class="count">{len(claims)} claims</span>
  </div>
  <p class="meta">Section 2 of <code>SurfaceomeRecord</code> v1.0.0 — agent
   A2 (Biology Compiler) output.</p>
</header>

<h2>Tissues ({len(tissues)})</h2>
{_render_tissues(tissues)}

<h2>Cell types ({len(cell_types)})</h2>
{_render_cell_types(cell_types)}

<h2>Cell states ({len(cell_states)})</h2>
{_render_cell_states(cell_states)}

<h2>Subcellular localization</h2>
{_render_subcellular(sub_loc)}

<h2>Anatomical accessibility ({len(anat)})</h2>
{_render_anatomical(anat)}

<h2>Accessibility modulation ({len(mod)})</h2>
{_render_modulation(mod)}

<h2>Evidence ledger ({len(claims)})</h2>
<p class="muted">The agent's per-claim ledger. Every <code>cited_evidence_ids</code>
above resolves into this list.</p>
{"".join(_render_claim(c) for c in claims)}

</div></body></html>
"""


def _main(argv: list[str] | None = None) -> int:
    args = argv if argv is not None else sys.argv[1:]
    if not args:
        print("usage: render_html <a2_GENE.json> [more.json ...]", file=sys.stderr)
        return 2
    for path_str in args:
        path = Path(path_str)
        draft = json.loads(path.read_text())
        gene = path.stem.removeprefix("a2_")
        out = path.with_suffix(".html")
        out.write_text(render_html(draft, gene))
        print(f"wrote {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(_main())
