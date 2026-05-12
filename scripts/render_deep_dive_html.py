"""Render a single-file HTML viewer for one surface-annotator record.

Mirrors the look-and-feel of ``docs/eval/triage_agent_reference.html``
(Manrope + Playfair Display + project palette) but reads a real
record from ``data/annotations/<SYMBOL>.json`` and renders the key
fields as sections.

Usage:
    uv run python scripts/render_deep_dive_html.py TGOLN2

Output: ``docs/eval/deep_dive_<symbol>.html`` (single self-contained
file, JSON embedded inline, no external requests except CDN fonts).
"""

from __future__ import annotations

import argparse
import html
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def _e(s: object) -> str:
    """HTML-escape an arbitrary scalar value."""
    if s is None:
        return "<span class='nil'>—</span>"
    if isinstance(s, bool):
        return "yes" if s else "no"
    return html.escape(str(s))


def _source_link(src: dict) -> str:
    """Build a hyperlink for an evidence span's source."""
    kind = (src.get("source_type") or "").lower()
    sid = src.get("source_id") or ""
    label = f"{kind}:{sid}" if sid else kind
    if kind == "pubmed" and sid:
        url = f"https://pubmed.ncbi.nlm.nih.gov/{sid}/"
    elif kind == "pmc" and sid:
        url = f"https://www.ncbi.nlm.nih.gov/pmc/articles/{sid}/"
    elif kind == "uniprot" and sid:
        url = f"https://www.uniprot.org/uniprotkb/{sid}"
    else:
        return _e(label)
    return f"<a href='{url}' target='_blank' rel='noopener'>{_e(label)}</a>"


def _render_evidence(evidence_list: list[dict]) -> str:
    parts = []
    for ev in evidence_list:
        eid = ev.get("evidence_id", "")
        claim = ev.get("claim", "")
        direction = ev.get("direction", "")
        tier = ev.get("evidence_tier", "")
        etype = ev.get("evidence_type", "")
        confidence = ev.get("confidence", "")
        spans = ev.get("spans") or []
        chips = [
            f"<span class='chip chip-{tier}'>{_e(tier)}</span>",
            f"<span class='chip chip-{direction}'>{_e(direction)}</span>",
            f"<span class='chip'>{_e(etype)}</span>",
            f"<span class='chip'>conf: {_e(confidence)}</span>",
        ]
        span_links = " · ".join(
            _source_link(sp.get("source") or {})
            for sp in spans
            if (sp.get("source") or {}).get("source_id")
        )
        parts.append(f"""
        <div class='evi'>
          <div class='evi-head'>
            <span class='evi-id'>{_e(eid)}</span>
            {' '.join(chips)}
          </div>
          <div class='evi-claim'>{_e(claim)}</div>
          {f"<div class='evi-spans'>Sources: {span_links}</div>" if span_links else ""}
        </div>""")
    return "\n".join(parts)


def _render_induced(items: list[dict]) -> str:
    if not items:
        return "<p class='nil'>none documented</p>"
    parts = []
    for it in items:
        kind = it.get("context_kind") or "—"
        desc = it.get("description") or ""
        cells = it.get("cell_context") or "any"
        cited = ", ".join(it.get("cited_evidence_ids") or []) or "—"
        parts.append(f"""
        <div class='induced'>
          <div class='induced-head'><strong>{_e(kind)}</strong> <span class='nil'>· cell context: {_e(cells)}</span></div>
          <p>{_e(desc)}</p>
          <div class='cited'>cited evidence: {_e(cited)}</div>
        </div>""")
    return "\n".join(parts)


def _render_assays(items: list[dict]) -> str:
    if not items:
        return "<p class='nil'>none documented</p>"
    parts = []
    for it in items:
        assay = it.get("assay") or "—"
        species = (it.get("assay_context") or {}).get("species") or "—"
        result = it.get("result") or "—"
        cited = ", ".join(it.get("cited_evidence_ids") or []) or "—"
        parts.append(f"""
        <div class='assay'>
          <div><strong>{_e(assay)}</strong> <span class='nil'>· {_e(species)}</span></div>
          <div>{_e(result)}</div>
          <div class='cited'>cited evidence: {_e(cited)}</div>
        </div>""")
    return "\n".join(parts)


def _render_search_log(items: list[dict]) -> str:
    if not items:
        return "<p class='nil'>none</p>"
    rows = []
    for it in items:
        q = it.get("query") or "—"
        n = it.get("n_results") if it.get("n_results") is not None else "—"
        src = it.get("source") or "—"
        rows.append(f"<tr><td><code>{_e(q)}</code></td><td>{_e(src)}</td><td>{_e(n)}</td></tr>")
    return f"""
    <table class='searchlog'>
      <thead><tr><th>query</th><th>source</th><th>n_results</th></tr></thead>
      <tbody>{''.join(rows)}</tbody>
    </table>"""


HTML_TEMPLATE = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<title>{symbol} — surface_annotator deep dive</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Manrope:wght@300;400;500;600;700;800&family=Playfair+Display:ital,wght@0,400..700;1,400..600&display=swap" rel="stylesheet">
<style>
:root {{
  --primary: #BC3C4C; --secondary: #3D6B60; --accent: #F4AA28;
  --bg: #FBF7F2; --bg-warm: #F3ECE5; --ink: #1F1718; --line: #E6DAD4;
  --neutral: #6F5D5A; --code-bg: #F5EFE8; --code-line: #E6DAD4;
}}
* {{ box-sizing: border-box; }}
html, body {{ margin: 0; padding: 0; background: var(--bg); }}
body {{ font-family: "Manrope", -apple-system, BlinkMacSystemFont, system-ui, sans-serif;
  font-size: 15.5px; line-height: 1.6; color: var(--ink); font-weight: 400; }}
header {{ background: linear-gradient(135deg, #F3ECE5 0%, #FBF7F2 100%);
  border-bottom: 1px solid var(--line); padding: 36px 48px 28px; }}
header .eyebrow {{ font-size: 11px; font-weight: 700; letter-spacing: 0.12em;
  text-transform: uppercase; color: var(--primary); margin: 0 0 8px 0; }}
header h1 {{ font-family: "Playfair Display", Georgia, serif; font-weight: 600;
  font-size: 38px; letter-spacing: -0.02em; margin: 0 0 12px 0; color: var(--ink); }}
header .tagline {{ color: var(--neutral); font-size: 14.5px; margin: 0 0 16px 0; max-width: 720px; }}
header .meta-row {{ display: flex; flex-wrap: wrap; gap: 8px; font-size: 12.5px; }}
header .meta-row .chip {{ display: inline-flex; align-items: center; gap: 6px;
  background: white; border: 1px solid var(--line); padding: 4px 12px;
  border-radius: 999px; color: var(--neutral); font-weight: 500; }}
header .meta-row .chip strong {{ color: var(--ink); font-weight: 600; }}
nav {{ position: sticky; top: 0; background: rgba(251, 247, 242, 0.95);
  backdrop-filter: blur(8px); border-bottom: 1px solid var(--line); padding: 12px 48px;
  display: flex; gap: 6px; z-index: 10; flex-wrap: wrap; }}
nav a {{ color: var(--neutral); text-decoration: none; font-size: 13px;
  font-weight: 500; padding: 6px 12px; border-radius: 999px; }}
nav a:hover {{ background: var(--bg-warm); color: var(--primary); }}
main {{ max-width: 1040px; margin: 0 auto; padding: 36px 48px 96px; }}
section {{ margin-bottom: 56px; scroll-margin-top: 80px; }}
section h2 {{ font-family: "Playfair Display", Georgia, serif; font-weight: 600;
  font-size: 26px; letter-spacing: -0.01em; margin: 0 0 6px 0; color: var(--ink); }}
section h2::after {{ content: ""; display: block; width: 48px; height: 3px;
  margin-top: 10px; background: var(--primary); border-radius: 2px; }}
section .lede {{ color: var(--neutral); font-size: 13.5px; margin: 0 0 20px 0; }}
.kv {{ display: grid; grid-template-columns: 220px 1fr; gap: 6px 18px;
  background: white; border: 1px solid var(--line); border-radius: 10px; padding: 18px 24px; }}
.kv dt {{ color: var(--neutral); font-weight: 500; font-size: 13.5px; }}
.kv dd {{ margin: 0; color: var(--ink); font-size: 14.5px; }}
.rationale, .reasoning {{ background: white; border: 1px solid var(--line);
  border-left: 4px solid var(--primary); border-radius: 8px; padding: 22px 28px;
  white-space: pre-wrap; font-size: 15px; }}
.reasoning {{ border-left-color: var(--secondary); }}
.evi {{ background: white; border: 1px solid var(--line); border-radius: 8px;
  padding: 16px 22px; margin-bottom: 14px; }}
.evi-head {{ display: flex; gap: 8px; flex-wrap: wrap; align-items: center; margin-bottom: 8px; }}
.evi-id {{ font-family: "JetBrains Mono", Menlo, monospace; font-size: 12.5px;
  color: var(--neutral); font-weight: 600; }}
.evi-claim {{ font-size: 14.5px; line-height: 1.55; color: var(--ink); }}
.evi-spans {{ margin-top: 8px; font-size: 12.5px; color: var(--neutral); }}
.evi-spans a {{ color: var(--secondary); text-decoration: none; font-weight: 500; }}
.evi-spans a:hover {{ text-decoration: underline; }}
.chip {{ display: inline-flex; align-items: center; padding: 2px 10px;
  border-radius: 999px; font-size: 11px; font-weight: 600;
  background: var(--bg-warm); color: var(--neutral); border: 1px solid var(--line); }}
.chip-primary {{ background: #fde8eb; color: var(--primary); border-color: #f4c8cf; }}
.chip-secondary {{ background: #e3eee9; color: var(--secondary); border-color: #c7ddd1; }}
.chip-supports {{ background: #e8f0e3; color: #4a7c3a; border-color: #cfdfc4; }}
.chip-refutes {{ background: #fce8e8; color: #b34646; border-color: #f0c8c8; }}
.chip-neutral {{ background: #f0ece6; color: var(--neutral); border-color: var(--line); }}
.induced, .assay {{ background: white; border: 1px solid var(--line); border-radius: 8px;
  padding: 14px 20px; margin-bottom: 12px; }}
.induced p {{ margin: 6px 0 8px 0; font-size: 14px; }}
.cited {{ font-size: 12px; color: var(--neutral); font-family: "JetBrains Mono", Menlo, monospace; }}
.nil {{ color: var(--neutral); font-style: italic; }}
table.searchlog {{ width: 100%; border-collapse: collapse; background: white;
  border: 1px solid var(--line); border-radius: 8px; overflow: hidden; font-size: 13.5px; }}
table.searchlog th {{ background: var(--bg-warm); text-align: left; padding: 10px 14px;
  font-weight: 600; color: var(--neutral); font-size: 12px; text-transform: uppercase; letter-spacing: 0.05em; }}
table.searchlog td {{ padding: 8px 14px; border-top: 1px solid var(--line); vertical-align: top; }}
table.searchlog code {{ font-family: "JetBrains Mono", Menlo, monospace; font-size: 12px;
  background: var(--code-bg); padding: 1px 6px; border-radius: 4px; color: var(--ink); }}
details.raw {{ background: var(--code-bg); border: 1px solid var(--code-line);
  border-radius: 8px; padding: 0; margin-top: 12px; }}
details.raw summary {{ cursor: pointer; padding: 12px 18px; font-weight: 600;
  color: var(--neutral); font-size: 13px; }}
details.raw pre {{ margin: 0; padding: 16px 22px; max-height: 480px; overflow: auto;
  font-family: "JetBrains Mono", Menlo, monospace; font-size: 11.5px; line-height: 1.5; }}
footer {{ max-width: 1040px; margin: 0 auto; padding: 24px 48px 64px;
  color: var(--neutral); font-size: 12.5px; border-top: 1px solid var(--line); }}
</style>
</head>
<body>
<header>
  <p class="eyebrow">surface_annotator deep dive · {schema_version}</p>
  <h1>{symbol} <span style="color: var(--neutral); font-weight: 400; font-size: 24px;">({uniprot_acc})</span></h1>
  <p class="tagline">{tldr}</p>
  <div class="meta-row">
    <span class="chip"><strong>Tier:</strong> {tier}</span>
    <span class="chip"><strong>Confidence:</strong> {confidence}</span>
    <span class="chip"><strong>Triage signal:</strong> {triage_signal}</span>
    <span class="chip"><strong>Model:</strong> {model_path}</span>
    <span class="chip"><strong>Evidence:</strong> {n_evi} ({n_primary} primary / {n_secondary} secondary)</span>
  </div>
</header>
<nav>
  <a href="#summary">Summary</a>
  <a href="#rationale">Rationale</a>
  <a href="#surface">Surface biology</a>
  <a href="#induced">Induced presentation</a>
  <a href="#assays">Assays</a>
  <a href="#features">Protein features</a>
  <a href="#evidence">Evidence ({n_evi})</a>
  <a href="#search">Search log</a>
  <a href="#raw">Raw JSON</a>
</nav>
<main>

<section id="summary">
  <h2>Summary</h2>
  <p class="lede">gene → uniprot → triage signal in one glance.</p>
  <dl class="kv">
    <dt>HGNC symbol</dt><dd>{symbol} ({hgnc_id})</dd>
    <dt>UniProt accession</dt><dd><a href="https://www.uniprot.org/uniprotkb/{uniprot_acc}" target="_blank" rel="noopener">{uniprot_acc}</a></dd>
    <dt>NCBI gene ID</dt><dd><a href="https://www.ncbi.nlm.nih.gov/gene/{ncbi_gene_id}" target="_blank" rel="noopener">{ncbi_gene_id}</a></dd>
    <dt>Ensembl gene</dt><dd>{ensembl_gene}</dd>
    <dt>Canonical isoform</dt><dd>{canonical_isoform}</dd>
    <dt>Surface status</dt><dd>{surface_status}</dd>
    <dt>Topology</dt><dd>{topology}</dd>
    <dt>Anchor type</dt><dd>{anchor_type}</dd>
    <dt>Exposure class</dt><dd>{exposure_class}</dd>
  </dl>
</section>

<section id="rationale">
  <h2>Rationale</h2>
  <p class="lede">Sonnet's synthesis across the evidence pool.</p>
  <div class="rationale">{rationale}</div>
  <h3 style="margin: 24px 0 8px 0; font-family: 'Playfair Display'; font-size: 18px;">Confidence reasoning</h3>
  <div class="reasoning">{confidence_reasoning}</div>
</section>

<section id="surface">
  <h2>Surface biology</h2>
  <dl class="kv">
    <dt>Surface status</dt><dd>{surface_status}</dd>
    <dt>Topology</dt><dd>{topology}</dd>
    <dt>Anchor type</dt><dd>{anchor_type}</dd>
    <dt>Exposure class</dt><dd>{exposure_class}</dd>
    <dt>Extracellular domain size (aa)</dt><dd>{ecd_size}</dd>
    <dt>Accessibility</dt><dd>{ecd_access}</dd>
    <dt>Shedding documented</dt><dd>{shedding}</dd>
  </dl>
  <p class="lede" style="margin-top: 16px;">{ecd_notes}</p>
</section>

<section id="induced">
  <h2>Induced presentation</h2>
  <p class="lede">Context-specific contexts where the protein reaches the cell surface.</p>
  {induced_html}
</section>

<section id="assays">
  <h2>Surface-localization assays</h2>
  <p class="lede">Experimental observations of PM localization.</p>
  {assays_html}
</section>

<section id="features">
  <h2>Protein features</h2>
  <dl class="kv">
    <dt>Length (aa)</dt><dd>{protein_length}</dd>
    <dt>TM domain count</dt><dd>{tm_count}</dd>
    <dt>Signal peptide</dt><dd>{signal_peptide}</dd>
    <dt>Topology string</dt><dd><code>{topology_string}</code></dd>
    <dt>UniProt keywords</dt><dd>{uniprot_keywords}</dd>
    <dt>SURFY ML score</dt><dd>{surfy_score}</dd>
    <dt>Almén class</dt><dd>{almen}</dd>
    <dt>CD designation</dt><dd>{cd_designation}</dd>
  </dl>
</section>

<section id="evidence">
  <h2>Evidence ({n_evi})</h2>
  <p class="lede">Each evidence packet is a claim with at least one supporting source span (UniProt / PubMed / PMC).</p>
  {evidence_html}
</section>

<section id="search">
  <h2>Search log</h2>
  <p class="lede">Queries the deep-dive agent issued during evidence gathering.</p>
  {search_html}
</section>

<section id="raw">
  <h2>Raw JSON</h2>
  <p class="lede">Full annotation record as emitted by the surface_annotator agent.</p>
  <details class="raw">
    <summary>Show / hide ({n_chars:,} chars)</summary>
    <pre>{raw_json}</pre>
  </details>
</section>

</main>
<footer>
  Generated from <code>data/annotations/{symbol}.json</code> · schema {schema_version} · model {model_path}
</footer>
</body>
</html>
"""


def render(symbol: str) -> str:
    json_path = ROOT / "data" / "annotations" / f"{symbol}.json"
    if not json_path.exists():
        raise FileNotFoundError(json_path)
    d = json.loads(json_path.read_text())

    gene = d["gene"]
    pf = d["protein_features"]
    tb = d["targetability"]
    sb = d["surface_biology"]
    ecd = sb.get("extracellular_domain") or {}

    return HTML_TEMPLATE.format(
        symbol=_e(gene["hgnc_symbol"]),
        schema_version=_e(d.get("schema_version", "")),
        uniprot_acc=_e(gene.get("uniprot_acc", "")),
        hgnc_id=_e(gene.get("hgnc_id", "")),
        ncbi_gene_id=_e(gene.get("ncbi_gene_id", "")),
        ensembl_gene=_e(gene.get("ensembl_gene", "")),
        canonical_isoform=_e(d.get("canonical_isoform", "")),
        tier=_e(tb.get("tier", "")),
        tldr=_e(tb.get("tldr", "")),
        confidence=_e(d.get("confidence", "")),
        triage_signal=_e(d.get("triage_signal", "")),
        model_path=_e(d.get("model_path", "")),
        n_evi=len(d.get("evidence") or []),
        n_primary=_e(d.get("primary_evidence_count", 0)),
        n_secondary=_e(d.get("secondary_evidence_count", 0)),
        rationale=_e(d.get("rationale", "")),
        confidence_reasoning=_e(d.get("confidence_reasoning", "")),
        surface_status=_e(sb.get("surface_status", "")),
        topology=_e(sb.get("topology", "")),
        anchor_type=_e(sb.get("anchor_type", "")),
        exposure_class=_e(sb.get("exposure_class", "")),
        ecd_size=_e(ecd.get("size_aa")),
        ecd_access=_e(ecd.get("accessibility")),
        ecd_notes=_e(ecd.get("notes", "")),
        shedding=_e(sb.get("shedding_documented")),
        induced_html=_render_induced(sb.get("induced_presentation") or []),
        assays_html=_render_assays(sb.get("surface_localization_assays") or []),
        protein_length=_e(pf.get("protein_length_aa")),
        tm_count=_e(pf.get("tm_domain_count")),
        signal_peptide=_e(pf.get("signal_peptide")),
        topology_string=_e(pf.get("topology_string", "")),
        uniprot_keywords=_e(", ".join(pf.get("uniprot_keywords") or [])),
        surfy_score=_e(pf.get("surfy_ml_score")),
        almen=_e(pf.get("almen_main_class", "")),
        cd_designation=_e(pf.get("cd_designation")),
        evidence_html=_render_evidence(d.get("evidence") or []),
        search_html=_render_search_log(d.get("search_log") or []),
        raw_json=_e(json.dumps(d, indent=2)),
        n_chars=len(json.dumps(d)),
    )


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("symbol", help="HGNC symbol (e.g. TGOLN2)")
    p.add_argument("-o", "--output", type=Path, default=None,
                   help="Output HTML path (default: docs/eval/deep_dive_<symbol>.html)")
    args = p.parse_args()

    out = args.output or (ROOT / "docs" / "eval" / f"deep_dive_{args.symbol.lower()}.html")
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(render(args.symbol))
    print(f"wrote {out}")


if __name__ == "__main__":
    main()
