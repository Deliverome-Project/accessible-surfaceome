"""Render a SurfaceEvidenceDraft JSON file as a single self-contained HTML.

Usage:

    uv run python -m accessible_surfaceome.agents.surface_evidence_compiler.render_html \\
        .runs/a1_EGFR.json

Writes ``a1_EGFR.html`` alongside the input. No external assets — open it
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


# evidence-grade → CSS badge kind
_GRADE_KIND = {
    "direct_multi_method": "green",
    "direct_single_method": "green",
    "supportive_but_indirect": "amber",
    "conflicting": "red",
    "weak": "red",
}
_RELEVANCE_KIND = {
    "direct_surface_accessibility": "green",
    "supports_surface_localization": "blue",
    "supports_membrane_association": "blue",
    "expression_only": "amber",
    "weak_or_ambiguous": "amber",
}
_SEVERITY_KIND = {"high": "red", "moderate": "amber", "low": "blue", "unclear": "gray"}


def _render_antibody(ab: dict[str, Any]) -> str:
    pieces: list[str] = [
        f"<strong>{html.escape(ab.get('name', '—'))}</strong>",
    ]
    if ab.get("clone"):
        pieces.append(f"clone {html.escape(ab['clone'])}")
    if ab.get("vendor"):
        pieces.append(html.escape(ab["vendor"]))
    if ab.get("rrid"):
        pieces.append(f"<code>{html.escape(ab['rrid'])}</code>")
    line1 = " · ".join(pieces)
    chips = (
        f'{_badge(ab.get("monoclonal_or_polyclonal", "?"), "gray")} '
        f'{_badge("epitope: " + ab.get("antibody_epitope_region", "?"), "gray")} '
        f'{_badge("validation: " + ab.get("validation_strategy", "?"), "gray")} '
        f'{_badge(ab.get("validation_strength", "?") + " evidence", "gray")}'
    )
    note = (
        f'<div class="note">{html.escape(ab["cross_reactivity_notes"])}</div>'
        if ab.get("cross_reactivity_notes")
        else ""
    )
    return f'<div class="antibody">{line1}<div class="chips">{chips}</div>{note}</div>'


def _render_expression_obs(obs: dict[str, Any]) -> str:
    cites = " ".join(_src_link("evi:" + c) for c in obs.get("cited_evidence_ids", []))
    cites_html = (
        f'<span class="cites">{cites}</span>' if obs.get("cited_evidence_ids") else ""
    )
    return (
        f'<tr><td>{html.escape(obs.get("context", ""))}</td>'
        f'<td>{html.escape(obs.get("sample_type", ""))}</td>'
        f'<td>{_badge(obs.get("level", "?"), "gray")}</td>'
        f"<td>{cites_html}</td></tr>"
    )


def _render_method(m: dict[str, Any]) -> str:
    rel_kind = _RELEVANCE_KIND.get(m.get("accessibility_relevance", ""), "gray")
    abs_html = (
        "".join(_render_antibody(ab) for ab in m["antibodies"])
        if m.get("antibodies")
        else ""
    )
    obs_rows = "".join(_render_expression_obs(o) for o in m.get("expression_observations", []))
    obs_table = (
        f"<table class=\"obs\"><thead><tr><th>context</th><th>sample</th><th>level</th><th>cites</th></tr></thead><tbody>{obs_rows}</tbody></table>"
        if obs_rows
        else ""
    )
    cite_chips = " ".join(
        f'<span class="evi-chip">{html.escape(eid)}</span>'
        for eid in m.get("cited_evidence_ids", [])
    )
    return f"""
<div class="method">
  <div class="method-header">
    <div class="method-title">
      <span class="family">{html.escape(m.get("method_family", "?"))}</span>
      <span class="subclass">{html.escape(m.get("method_subclass", "?"))}</span>
    </div>
    <div class="method-chips">
      {_badge("perm: " + m.get("permeabilization", "?"), "gray")}
      {_badge("system: " + m.get("expression_system", "?"), "gray")}
      {_badge(m.get("accessibility_relevance", "?").replace("_", " "), rel_kind)}
      {_badge(m.get("surface_claim_type", "?").replace("_", " "), "gray")}
    </div>
  </div>
  {f'<div class="antibodies">{abs_html}</div>' if abs_html else ""}
  {obs_table}
  <div class="cites">cited: {cite_chips}</div>
</div>"""


def _render_non_surface(items: list[dict[str, Any]]) -> str:
    if not items:
        return '<p class="muted">none</p>'
    rows = "".join(
        f'<tr><td>{html.escape(n.get("measurement_type", "?"))}</td>'
        f'<td>{_badge(n.get("level", "?"), "gray")}</td>'
        f'<td>{html.escape(n.get("sample_type", "?"))}</td>'
        f'<td>{html.escape(n.get("context", ""))}</td>'
        f'<td>{" ".join(html.escape(c) for c in n.get("cited_evidence_ids", []))}</td></tr>'
        for n in items
    )
    return f"""<table class="nse"><thead><tr><th>measurement</th><th>level</th><th>sample</th><th>context</th><th>cites</th></tr></thead><tbody>{rows}</tbody></table>"""


def _render_therapeutic(te: dict[str, Any] | None) -> str:
    if te is None:
        return '<p class="muted">none documented</p>'
    return f"""
<div class="te">
  <div class="te-stage">{_badge(te.get("highest_stage", "?").replace("_", " "), "blue")}
    <span class="disclaimer">(not a comprehensive landscape)</span></div>
  <p>{html.escape(te.get("description", ""))}</p>
  <p class="te-rationale"><strong>surface-form rationale:</strong>
    {html.escape(te.get("surface_form_rationale", ""))}</p>
  <div class="cites">cited: {" ".join(html.escape(c) for c in te.get("cited_evidence_ids", []))}</div>
</div>"""


def _render_contradictions(items: list[dict[str, Any]]) -> str:
    if not items:
        return '<p class="muted">none</p>'
    cards = "".join(
        f"""
<div class="contradiction">
  <div class="contra-head">
    {_badge(c.get("contradiction_type", "?").replace("_", " "), "gray")}
    {_badge("severity: " + c.get("severity_for_surface_accessibility", "?"),
            _SEVERITY_KIND.get(c.get("severity_for_surface_accessibility", ""), "gray"))}
  </div>
  <p><strong>claim:</strong> {html.escape(c.get("claim", ""))}</p>
  {f'<p class="muted"><strong>likely explanation:</strong> {html.escape(c["likely_explanation"])}</p>' if c.get("likely_explanation") else ""}
  <div class="cites">cited: {" ".join(html.escape(x) for x in c.get("cited_evidence_ids", []))}</div>
</div>"""
        for c in items
    )
    return cards


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
.summary { display: flex; align-items: baseline; gap: 18px; flex-wrap: wrap;
           margin-top: 8px; }
.summary .count { color: var(--muted); font-variant-numeric: tabular-nums; }
.grade-rationale { background: white; border: 1px solid var(--rule);
                   padding: 14px 18px; border-radius: 8px; }
.method, .te, .contradiction, .claim { background: white;
    border: 1px solid var(--rule); border-radius: 8px; padding: 14px 18px;
    margin-bottom: 12px; }
.method-header { display: flex; justify-content: space-between;
                 align-items: flex-start; gap: 12px; flex-wrap: wrap; }
.method-title .family { font-weight: 600; }
.method-title .subclass { color: var(--muted); margin-left: 8px;
                          font-family: "SF Mono", "Menlo", monospace;
                          font-size: 13px; }
.method-chips, .te-stage, .chips, .claim-head, .contra-head {
    display: flex; gap: 6px; flex-wrap: wrap; align-items: center; }
.badge { display: inline-block; padding: 2px 8px; border-radius: 999px;
         font-size: 12px; font-weight: 500; line-height: 1.4; }
.badge-green { background: rgba(31,122,69,0.12); color: var(--green); }
.badge-amber { background: rgba(154,106,20,0.12); color: var(--amber); }
.badge-red   { background: rgba(140,42,35,0.12); color: var(--red); }
.badge-blue  { background: rgba(42,77,140,0.12); color: var(--blue); }
.badge-gray  { background: rgba(28,22,18,0.06); color: var(--ink); }
.evi-chip { background: rgba(42,77,140,0.10); color: var(--blue); padding: 1px 6px;
            border-radius: 4px; font-family: "SF Mono", monospace; font-size: 12px; }
.antibodies { margin-top: 10px; }
.antibody { padding: 8px 10px; border-left: 3px solid var(--blue);
            background: rgba(42,77,140,0.04); margin-top: 6px; font-size: 14px; }
.antibody .note { color: var(--muted); font-size: 13px; margin-top: 4px; font-style: italic; }
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
.te-rationale { background: rgba(154,106,20,0.06); padding: 8px 10px;
                border-radius: 6px; font-size: 14px; }
.disclaimer { color: var(--muted); font-size: 12px; font-style: italic; }
.muted { color: var(--muted); }
.meta { color: var(--muted); font-size: 13px; margin-top: 4px; }
"""


def render_html(draft: dict[str, Any], gene: str) -> str:
    se = draft["surface_evidence"]
    claims = draft.get("evidence_claims", [])
    grade = se.get("evidence_grade", "?")
    grade_kind = _GRADE_KIND.get(grade, "gray")
    methods_html = "".join(_render_method(m) for m in se.get("methods", []))
    nse_html = _render_non_surface(se.get("non_surface_expression", []))
    te_html = _render_therapeutic(se.get("therapeutic_engagement"))
    contra_html = _render_contradictions(se.get("contradicting_evidence", []))
    claims_html = "".join(_render_claim(c) for c in claims)

    return f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8">
<title>A1 surface_evidence — {html.escape(gene)}</title>
<style>{_STYLE}</style>
</head><body><div class="wrap">

<header>
  <h1>{html.escape(gene)} — surface evidence</h1>
  <div class="summary">
    {_badge("grade: " + grade.replace("_", " "), grade_kind)}
    <span class="count">{len(se.get("methods", []))} methods</span>
    <span class="count">{len(claims)} claims</span>
    <span class="count">{len(se.get("non_surface_expression", []))} non-surface</span>
    <span class="count">{len(se.get("contradicting_evidence", []))} contradictions</span>
  </div>
  <p class="meta">Section 1 of <code>SurfaceomeRecord</code> v1.0.0 — agent
   A1 (Surface Evidence Compiler) output.</p>
</header>

<h2>Grade rationale</h2>
<div class="grade-rationale">{html.escape(se.get("grade_rationale", ""))}</div>

<h2>Methods ({len(se.get("methods", []))})</h2>
{methods_html}

<h2>Non-surface expression ({len(se.get("non_surface_expression", []))})</h2>
<p class="muted">RNA / bulk-protein / IHC observations <em>not</em> tied to a
surface-evidence panel — kept separate so expression isn't confused with
surface accessibility.</p>
{nse_html}

<h2>Therapeutic engagement</h2>
{te_html}

<h2>Contradicting evidence ({len(se.get("contradicting_evidence", []))})</h2>
{contra_html}

<h2>Evidence ledger ({len(claims)})</h2>
<p class="muted">The agent's per-claim ledger. Every <code>cited_evidence_ids</code>
above resolves into this list.</p>
{claims_html}

</div></body></html>
"""


def _main(argv: list[str] | None = None) -> int:
    args = argv if argv is not None else sys.argv[1:]
    if not args:
        print("usage: render_html <a1_GENE.json> [more.json ...]", file=sys.stderr)
        return 2
    for path_str in args:
        path = Path(path_str)
        draft = json.loads(path.read_text())
        gene = path.stem.removeprefix("a1_")
        out = path.with_suffix(".html")
        out.write_text(render_html(draft, gene))
        print(f"wrote {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(_main())
