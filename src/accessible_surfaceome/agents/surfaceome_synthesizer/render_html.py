"""Render a SynthesizerDraft JSON file as a single self-contained HTML.

Usage:

    uv run python -m accessible_surfaceome.agents.surfaceome_synthesizer.render_html \\
        .runs/b_EGFR.json

Writes ``b_EGFR.html`` alongside the input. No external assets — open it
straight in a browser.
"""

from __future__ import annotations

import html
import json
import sys
from pathlib import Path
from typing import Any


def _badge(text: str, kind: str) -> str:
    return f'<span class="badge badge-{html.escape(kind)}">{html.escape(text)}</span>'


_ACCESSIBILITY_KIND = {
    "high": "green",
    "moderate": "amber",
    "low": "red",
    "uncertain": "gray",
}
_GRADE_KIND = {
    "direct_multi_method": "green",
    "direct_single_method": "green",
    "supportive_but_indirect": "amber",
    "conflicting": "red",
    "weak": "red",
}
_CONFIDENCE_KIND = {"high": "green", "moderate": "amber", "low": "red"}
_SEVERITY_KIND = {"high": "red", "moderate": "amber", "low": "blue", "unknown": "gray"}
_STRENGTH_KIND = {
    "strong": "green",
    "moderate": "amber",
    "weak": "amber",
    "inferred": "gray",
}
_STATE_KIND = {"low": "green", "moderate": "amber", "high": "red", "unclear": "gray"}


def _chip(text: str, kind: str = "gray") -> str:
    return _badge(text, kind)


def _cites(ids: list[str]) -> str:
    if not ids:
        return ""
    return (
        '<div class="cites">cited: '
        + " ".join(f'<span class="evi-chip">{html.escape(i)}</span>' for i in ids)
        + "</div>"
    )


def _render_executive(es: dict[str, Any]) -> str:
    sa = es.get("surface_accessibility", "?")
    egs = es.get("evidence_grade_summary", "?")
    conf = es.get("confidence", "?")
    sd = es.get("state_dependence", "?")
    sub = es.get("subcategory", "?")
    risks = es.get("headline_risks", [])
    risks_html = (
        " ".join(_chip(r.replace("_", " "), "amber") for r in risks)
        if risks
        else '<span class="muted">none flagged</span>'
    )
    return f"""
<div class="exec">
  <p class="exec-paragraph">{html.escape(es.get("one_paragraph", ""))}</p>
  <div class="exec-chips">
    {_chip("surface: " + sa, _ACCESSIBILITY_KIND.get(sa, "gray"))}
    {_chip("grade: " + egs.replace("_", " "), _GRADE_KIND.get(egs, "gray"))}
    {_chip("confidence: " + conf, _CONFIDENCE_KIND.get(conf, "gray"))}
    {_chip("state-dep: " + sd, _STATE_KIND.get(sd, "gray"))}
    {_chip("subcategory: " + sub.replace("_", " "), "gray")}
  </div>
  <div class="exec-risks"><strong>headline risks:</strong> {risks_html}</div>
  {_cites(es.get("cited_evidence_ids", []))}
</div>"""


def _risk_card(title: str, body: str, sev: str | None, strength: str | None) -> str:
    chips: list[str] = []
    if sev is not None:
        chips.append(_chip("severity: " + sev, _SEVERITY_KIND.get(sev, "gray")))
    if strength is not None:
        chips.append(_chip("evidence: " + strength, _STRENGTH_KIND.get(strength, "gray")))
    chips_html = (
        f'<div class="risk-chips">{" ".join(chips)}</div>' if chips else ""
    )
    return f"""
<div class="risk">
  <div class="risk-head">
    <h3>{html.escape(title)}</h3>
    {chips_html}
  </div>
  {body}
</div>"""


def _render_coreceptor(r: dict[str, Any]) -> str:
    dep = r.get("surface_expression_dependency", "?")
    basis = r.get("evidence_basis", "?")
    partners = r.get("partners", [])
    partners_html = (
        ", ".join(html.escape(p) for p in partners)
        if partners
        else '<span class="muted">none</span>'
    )
    body = (
        f'<p><strong>surface-expression dependency:</strong> {_chip(dep, "gray")}</p>'
        f"<p><strong>partners:</strong> {partners_html}</p>"
        f'<p><strong>evidence basis:</strong> {_chip(basis, "gray")}</p>'
        f'<p class="rationale">{html.escape(r.get("rationale", ""))}</p>'
        f"{_cites(r.get('cited_evidence_ids', []))}"
    )
    return _risk_card("Co-receptor requirements", body, None, None)


def _render_shed(r: dict[str, Any]) -> str:
    body = (
        f'<p><strong>present:</strong> {r.get("present", False)}</p>'
        + (
            f"<p><strong>mechanism:</strong> {html.escape(r['mechanism'])}</p>"
            if r.get("mechanism")
            else ""
        )
        + (
            f"<p><strong>sheddase:</strong> {html.escape(r['sheddase_if_known'])}</p>"
            if r.get("sheddase_if_known")
            else ""
        )
        + _cites(r.get("cited_evidence_ids", []))
    )
    return _risk_card("Shed form", body, r.get("severity"), r.get("evidence_strength"))


def _render_secreted(r: dict[str, Any]) -> str:
    extras: list[str] = []
    if r.get("ratio_to_membrane") is not None:
        extras.append(f"<p><strong>ratio_to_membrane:</strong> {r['ratio_to_membrane']}</p>")
    if r.get("source"):
        extras.append(f'<p><strong>source:</strong> {_chip(r["source"], "gray")}</p>')
    body = (
        f'<p><strong>present:</strong> {r.get("present", False)}</p>'
        + "".join(extras)
        + _cites(r.get("cited_evidence_ids", []))
    )
    return _risk_card(
        "Secreted form", body, r.get("severity"), r.get("evidence_strength")
    )


def _render_subdomain(r: dict[str, Any]) -> str:
    body = (
        f'<p><strong>present:</strong> {r.get("present", False)}</p>'
        f'<p><strong>domain:</strong> {_chip(r.get("domain", "?"), "gray")}</p>'
        f'<p class="rationale">{html.escape(r.get("rationale", ""))}</p>'
        f"{_cites(r.get('cited_evidence_ids', []))}"
    )
    return _risk_card(
        "Restricted subdomain", body, r.get("severity"), r.get("evidence_strength")
    )


def _render_ecd_size(r: dict[str, Any]) -> str:
    cls = r.get("ecd_accessibility_class", "?")
    body = (
        f'<p><strong>class:</strong> {_chip(cls.replace("_", " "), "gray")}</p>'
        f'<p class="rationale">{html.escape(r.get("rationale", ""))}</p>'
        f"{_cites(r.get('cited_evidence_ids', []))}"
    )
    return _risk_card("ECD size assessment", body, None, None)


def _render_epitope_masking(r: dict[str, Any]) -> str:
    mechs = r.get("mechanism", [])
    mech_html = (
        " ".join(_chip(m.replace("_", " "), "gray") for m in mechs)
        if mechs
        else '<span class="muted">none</span>'
    )
    body = (
        f"<p><strong>mechanism:</strong> {mech_html}</p>"
        f'<p class="rationale">{html.escape(r.get("rationale", ""))}</p>'
        f"{_cites(r.get('cited_evidence_ids', []))}"
    )
    return _risk_card(
        "Epitope masking", body, r.get("severity"), r.get("evidence_strength")
    )


def _render_risks(ar: dict[str, Any]) -> str:
    return "".join(
        [
            _render_coreceptor(ar.get("co_receptor_requirements", {})),
            _render_shed(ar.get("shed_form", {})),
            _render_secreted(ar.get("secreted_form", {})),
            _render_subdomain(ar.get("restricted_subdomain", {})),
            _render_ecd_size(ar.get("ecd_size_assessment", {})),
            _render_epitope_masking(ar.get("epitope_masking", {})),
        ]
    )


def _render_filters(f: dict[str, Any]) -> str:
    return f"""
<div class="filters">
  {_chip("expression_level: " + f.get("expression_level", "?"), "gray")}
  {_chip("expression_breadth: " + f.get("expression_breadth", "?"), "gray")}
  {_chip("surface_specificity: " + f.get("surface_specificity", "?").replace("_", " "), "gray")}
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
h3 { font-size: 15px; font-weight: 600; margin: 0; }
p { margin: 6px 0; }
.exec, .risk, .filters, .conf-card { background: white;
    border: 1px solid var(--rule); border-radius: 8px; padding: 14px 18px;
    margin-bottom: 12px; }
.exec-paragraph { font-size: 15px; }
.exec-chips, .risk-chips, .filters, .risk-head {
    display: flex; gap: 6px; flex-wrap: wrap; align-items: center; }
.exec-chips { margin-top: 10px; }
.exec-risks { margin-top: 10px; }
.risk-head { justify-content: space-between; }
.risk .rationale { color: var(--ink); font-size: 14px;
                   background: rgba(28,22,18,0.03); padding: 8px 10px;
                   border-radius: 6px; }
.badge { display: inline-block; padding: 2px 8px; border-radius: 999px;
         font-size: 12px; font-weight: 500; line-height: 1.4; }
.badge-green { background: rgba(31,122,69,0.12); color: var(--green); }
.badge-amber { background: rgba(154,106,20,0.12); color: var(--amber); }
.badge-red   { background: rgba(140,42,35,0.12); color: var(--red); }
.badge-blue  { background: rgba(42,77,140,0.12); color: var(--blue); }
.badge-gray  { background: rgba(28,22,18,0.06); color: var(--ink); }
.evi-chip { background: rgba(42,77,140,0.10); color: var(--blue); padding: 1px 6px;
            border-radius: 4px; font-family: "SF Mono", monospace; font-size: 12px; }
.cites { color: var(--muted); font-size: 12px; margin-top: 6px;
         display: flex; gap: 6px; flex-wrap: wrap; align-items: center; }
.muted { color: var(--muted); }
.meta { color: var(--muted); font-size: 13px; margin-top: 4px; }
.conf-reasoning { font-size: 14px; background: rgba(28,22,18,0.03);
                  padding: 10px 12px; border-radius: 6px; margin-top: 8px; }
"""


def render_html(draft: dict[str, Any], gene: str) -> str:
    es = draft["executive_summary"]
    ar = draft["accessibility_risks"]
    flt = draft["filters_llm"]
    conf = draft.get("confidence", "?")
    reasoning = draft.get("confidence_reasoning", "")

    return f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8">
<title>B synthesizer — {html.escape(gene)}</title>
<style>{_STYLE}</style>
</head><body><div class="wrap">

<header>
  <h1>{html.escape(gene)} — synthesizer (B)</h1>
  <p class="meta">Cross-section integration over the merged A1 + A2 evidence
   ledger. Executive summary, accessibility risks, LLM-only filter rollups,
   and confidence — agent B output for <code>SurfaceomeRecord</code> v1.0.0.</p>
</header>

<h2>Executive summary</h2>
{_render_executive(es)}

<h2>Accessibility risks</h2>
{_render_risks(ar)}

<h2>Filter rollups (LLM-only)</h2>
{_render_filters(flt)}

<h2>Confidence</h2>
<div class="conf-card">
  {_chip("confidence: " + conf, _CONFIDENCE_KIND.get(conf, "gray"))}
  <div class="conf-reasoning">{html.escape(reasoning) if reasoning else '<span class="muted">(none)</span>'}</div>
</div>

</div></body></html>
"""


def _main(argv: list[str] | None = None) -> int:
    args = argv if argv is not None else sys.argv[1:]
    if not args:
        print("usage: render_html <b_GENE.json> [more.json ...]", file=sys.stderr)
        return 2
    for path_str in args:
        path = Path(path_str)
        draft = json.loads(path.read_text())
        gene = path.stem.removeprefix("b_")
        out = path.with_suffix(".html")
        out.write_text(render_html(draft, gene))
        print(f"wrote {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(_main())
