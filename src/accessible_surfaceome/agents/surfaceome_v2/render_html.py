"""Render a v2 SurfaceomeRecord JSON dump as a single self-contained QC HTML.

Usage:

    uv run python -m accessible_surfaceome.agents.surfaceome_v2.render_html \\
        .runs/surfaceome_v2_GPR75.json

Writes ``<input>.html`` next to the input JSON. No external assets.

The viewer is organized as a full QC pass over a v1.0.0 SurfaceomeRecord:

* Top banner: gene + identifiers + verdict (surface_accessibility,
  evidence_grade, confidence, subcategory) + total spend (info only).
* Section 0 — Executive summary (B synthesizer prose).
* Section 1 — Surface Evidence: evidence_grade + grade_rationale,
  methods[] cards (with antibody table + expression_observations),
  non_surface_expression[] (the RNA / bulk-protein bucket that prevents
  expression from being misread as accessibility),
  therapeutic_engagement, contradicting_evidence[].
* Section 2 — Biological Context: tissues[], cell_types[], cell_states[],
  subcellular_localization (primary_compartment + dual_localization[]
  + membrane_subdomains[]), anatomical_accessibility[],
  accessibility_modulation[] (the heaviest — colored by ModulationCategory).
* Section 3 — Deterministic features (canonical_topology, structure,
  orthologs/paralogs counts).
* Section 4 — Filters rollups (catalog-facing flat fields).
* Section 5 — Accessibility risks (shed, secreted, epitope masking,
  restricted subdomain, co-receptor, ECD assessment).
* Section 6 — Evidence ledger (one card per Evidence row with the
  verbatim quote, classifications, and source link).
* Confidence + reasoning footer.

Every ``cited_evidence_ids`` chip is a hyperlink to the matching
Evidence card in Section 6, so the user can click through from any
block-level field straight to the supporting quote.
"""

from __future__ import annotations

import html
import json
import sys
from datetime import datetime
from pathlib import Path
from typing import Any


# ---------------------------------------------------------------------------
# Source-id → external URL
# ---------------------------------------------------------------------------


def _source_url(
    source_id: str, *, bundle: dict[str, Any] | None = None
) -> str | None:
    if source_id.startswith("PMID:"):
        return f"https://pubmed.ncbi.nlm.nih.gov/{source_id[5:].strip()}/"
    if source_id.startswith("PMC:PMC"):
        return f"https://europepmc.org/article/PMC/{source_id[4:].strip()}"
    if source_id.startswith("PMC:"):
        return f"https://europepmc.org/article/PMC/{source_id[4:].strip()}"
    if source_id.startswith("HPA:"):
        ens = (bundle or {}).get("ensembl_gene")
        sym = (bundle or {}).get("hgnc_symbol") or source_id[4:].strip()
        if ens and sym:
            return f"https://www.proteinatlas.org/{ens}-{sym}"
        return f"https://www.proteinatlas.org/search/{sym}"
    if source_id.startswith("UniProt:"):
        return f"https://www.uniprot.org/uniprotkb/{source_id[8:].strip()}"
    if source_id.startswith("DOI:"):
        return f"https://doi.org/{source_id[4:].strip()}"
    if source_id.startswith("PDB:"):
        return f"https://www.rcsb.org/structure/{source_id[4:].strip()}"
    return None


def _src_link(source_id: str, *, bundle: dict[str, Any] | None = None) -> str:
    safe = html.escape(source_id)
    url = _source_url(source_id, bundle=bundle)
    if url is None:
        return f'<span class="src">{safe}</span>'
    return (
        f'<a class="src" href="{html.escape(url)}" '
        f'target="_blank" rel="noopener">{safe} ↗</a>'
    )


def _evi_chip(evi_id: str) -> str:
    """Cited-evidence-id chip that jumps to the evidence card in section 6."""
    safe = html.escape(evi_id)
    return (
        f'<a class="evi-chip" href="#{safe}">{safe}</a>'
    )


def _evi_chip_row(evi_ids: list[str]) -> str:
    if not evi_ids:
        return '<span class="muted small">(no citations)</span>'
    return (
        '<span class="evi-chips">'
        + "".join(_evi_chip(eid) for eid in evi_ids)
        + "</span>"
    )


# ---------------------------------------------------------------------------
# Generic badge
# ---------------------------------------------------------------------------


def _badge(text: str | None, kind: str) -> str:
    if text is None or text == "":
        text = "—"
    return (
        f'<span class="badge badge-{html.escape(kind)}">'
        f"{html.escape(str(text))}</span>"
    )


_DIRECTION_KIND = {"supports": "green", "refutes": "red", "ambiguous": "amber"}
_TIER_KIND = {"primary": "green", "secondary": "amber"}
_CONFIDENCE_KIND = {
    "strong": "green",
    "moderate": "amber",
    "weak": "red",
    "high": "green",
    "low": "red",
    "unknown": "gray",
}
_GRADE_KIND = {
    "direct_multi_method": "green",
    "direct_single_method": "green",
    "supportive_but_indirect": "amber",
    "conflicting": "red",
    "weak": "red",
}
_ACC_KIND = {
    "high": "green",
    "moderate": "amber",
    "low": "red",
    "context_dependent": "amber",
    "unknown": "gray",
}
_RELEVANCE_KIND = {
    "direct_surface_accessibility": "green",
    "supports_surface_localization": "blue",
    "supports_membrane_association": "blue",
    "expression_only": "amber",
    "weak_or_ambiguous": "amber",
}
_SEVERITY_KIND = {"high": "red", "moderate": "amber", "low": "blue", "unclear": "gray"}
_PRESENCE_KIND = {
    "high": "green",
    "moderate": "blue",
    "low": "amber",
    "absent": "gray",
    "mixed": "amber",
    "unknown": "gray",
}
_MODULATION_KIND = {
    "cell_state_induced": "lavender",
    "tissue_restricted_surface": "blue",
    "lysosomal_exocytosis": "lavender",
    "dual_localization": "amber",
    "stable_surface_attachment": "green",
    "activation_induced": "lavender",
    "stress_induced": "lavender",
    "disease_state_induced": "red",
    "polarization_dependent": "amber",
    "post_translational_dependent": "lavender",
    "developmental_stage": "blue",
    "none": "gray",
    "other": "gray",
    "unknown": "gray",
}


# ---------------------------------------------------------------------------
# Top banner
# ---------------------------------------------------------------------------


def _render_banner(record: dict[str, Any]) -> str:
    gene = record.get("gene") or {}
    symbol = html.escape(gene.get("hgnc_symbol") or "—")
    uniprot = html.escape(gene.get("uniprot_acc") or "—")
    hgnc = html.escape(gene.get("hgnc_id") or "—")
    ensembl = html.escape(gene.get("ensembl_gene") or "—")
    ncbi = html.escape(str(gene.get("ncbi_gene_id") or "—"))

    es = record.get("executive_summary") or {}
    accessibility = es.get("surface_accessibility") or "unknown"
    subcategory = es.get("subcategory") or "—"
    conf = record.get("confidence") or "unknown"
    se = record.get("surface_evidence") or {}
    grade = se.get("evidence_grade") or "—"

    n_evi = record.get("evidence_count", 0)
    n_primary = record.get("primary_evidence_count", 0)
    n_secondary = record.get("secondary_evidence_count", 0)

    ts_raw = record.get("record_generated_at") or ""
    try:
        ts_disp = datetime.fromisoformat(ts_raw.replace("Z", "+00:00")).strftime(
            "%Y-%m-%d %H:%M UTC"
        )
    except (ValueError, AttributeError):
        ts_disp = ts_raw or "—"

    return f"""
    <header class="record-banner">
      <h1>{symbol}</h1>
      <div class="id-row">
        <span class="id"><span class="id-key">UniProt</span> {uniprot}</span>
        <span class="id"><span class="id-key">HGNC</span> {hgnc}</span>
        <span class="id"><span class="id-key">Ensembl</span> {ensembl}</span>
        <span class="id"><span class="id-key">NCBI</span> {ncbi}</span>
      </div>
      <div class="verdict-row">
        <div class="verdict">
          <div class="verdict-label">surface accessibility</div>
          <div class="verdict-val">{_badge(accessibility, _ACC_KIND.get(accessibility, "gray"))}</div>
        </div>
        <div class="verdict">
          <div class="verdict-label">evidence grade</div>
          <div class="verdict-val">{_badge(grade, _GRADE_KIND.get(grade, "gray"))}</div>
        </div>
        <div class="verdict">
          <div class="verdict-label">confidence</div>
          <div class="verdict-val">{_badge(conf, _CONFIDENCE_KIND.get(conf, "gray"))}</div>
        </div>
        <div class="verdict">
          <div class="verdict-label">subcategory</div>
          <div class="verdict-val">{_badge(subcategory, "blue")}</div>
        </div>
        <div class="verdict">
          <div class="verdict-label">evidence rows</div>
          <div class="verdict-val big">{n_evi}</div>
          <div class="verdict-sub">{n_primary} primary · {n_secondary} secondary</div>
        </div>
        <div class="verdict">
          <div class="verdict-label">generated</div>
          <div class="verdict-val small">{html.escape(ts_disp)}</div>
          <div class="verdict-sub">{html.escape(record.get("model_path", "—"))}</div>
        </div>
      </div>
    </header>
    """


# ---------------------------------------------------------------------------
# Section 0 — Executive summary
# ---------------------------------------------------------------------------


def _render_executive_summary(record: dict[str, Any]) -> str:
    es = record.get("executive_summary") or {}
    if not es:
        return ""
    body_paragraph = html.escape(es.get("one_paragraph") or "—")
    state = html.escape(es.get("state_dependence") or "—")
    grade_summary = html.escape(es.get("evidence_grade_summary") or "—")
    headline_risks = es.get("headline_risks") or []
    risks_html = (
        "<ul class='risks'>"
        + "".join(f"<li>{html.escape(r)}</li>" for r in headline_risks)
        + "</ul>"
        if headline_risks
        else "<em class='muted'>none flagged</em>"
    )
    cited = es.get("cited_evidence_ids") or []
    return f"""
    <section class="block">
      <h2>Executive summary</h2>
      <div class="prose-block">{body_paragraph}</div>
      <div class="sub-grid">
        <div class="sub">
          <div class="sub-label">state dependence</div>
          <div class="sub-val">{state}</div>
        </div>
        <div class="sub">
          <div class="sub-label">evidence grade summary</div>
          <div class="sub-val">{grade_summary}</div>
        </div>
        <div class="sub">
          <div class="sub-label">headline risks</div>
          <div class="sub-val">{risks_html}</div>
        </div>
      </div>
      <div class="citations">{_evi_chip_row(cited)}</div>
    </section>
    """


def _render_confidence(record: dict[str, Any]) -> str:
    conf = record.get("confidence") or "unknown"
    reasoning = html.escape(record.get("confidence_reasoning") or "—")
    return f"""
    <section class="block">
      <h2>Confidence reasoning</h2>
      <div class="prose-block">
        {_badge(conf, _CONFIDENCE_KIND.get(conf, "gray"))}
        <span class="reasoning">{reasoning}</span>
      </div>
    </section>
    """


# ---------------------------------------------------------------------------
# Section 0.5 — Step timeline (per-step wall clock)
# ---------------------------------------------------------------------------


_PHASE_KIND = {
    "plan_trim_select_a1": "blue",
    "plan_trim_select_a2": "lavender",
    "plan_trim_select": "blue",
    "builders_a1": "green",
    "builders_a2": "amber",
    "synthesizer": "red",
    "post": "gray",
}


def _render_timing_section(record: dict[str, Any]) -> str:
    """Section 0.5 — per-step wall-clock breakdown.

    Reads ``record["timing"]`` (list of dicts emitted by
    :class:`TimingRecorder`). Renders a stacked-bar overview (one row
    per phase) above a detail table sorted by elapsed_s descending so
    the bottleneck step is on top. Skips silently when no timing data
    is present.
    """
    rows = record.get("timing") or []
    if not rows:
        return ""

    # Two distinct totals to surface honestly:
    # * sum_steps = sum(elapsed_s) — what we use to compute "% of work"
    #   per phase in the stacked bar (each pixel represents one second
    #   of model/CPU work, regardless of who was waiting on whom).
    # * wall_clock = max(end) - min(start) over all rows — what the
    #   user actually waited for. With concurrency this is < sum_steps.
    sum_steps = sum(float(r.get("elapsed_s", 0.0)) for r in rows) or 1e-9
    wall_clock = float(
        record.get("total_elapsed_s")
        or record.get("total_step_seconds")
        or sum_steps
    )
    sum_step_seconds = float(record.get("total_step_seconds") or sum_steps)
    parallelism = (sum_step_seconds / wall_clock) if wall_clock > 0 else 0.0
    # The bar segments use sum_steps as the denominator so phase
    # percentages reflect work allocation; the title shows wall clock.
    total = sum_steps
    total_disp = wall_clock

    # Roll up per phase for the stacked bar.
    by_phase: dict[str, float] = {}
    for r in rows:
        phase = r.get("phase") or "other"
        by_phase[phase] = by_phase.get(phase, 0.0) + float(r.get("elapsed_s", 0.0))

    bar_segments: list[str] = []
    legend_items: list[str] = []
    for phase, seconds in sorted(by_phase.items(), key=lambda kv: -kv[1]):
        pct = 100.0 * seconds / total
        kind = _PHASE_KIND.get(phase, "gray")
        bar_segments.append(
            f'<div class="bar-seg badge-{kind}" '
            f'style="width:{pct:.2f}%" '
            f'title="{html.escape(phase)} — {seconds:.1f}s ({pct:.1f}%)"></div>'
        )
        legend_items.append(
            f'<span class="bar-legend">'
            f'{_badge(phase, kind)} '
            f'<span class="muted small">{seconds:.1f}s · {pct:.1f}%</span>'
            f'</span>'
        )

    # Detail table — sort slowest first.
    detail_rows: list[str] = []
    for r in sorted(rows, key=lambda x: -float(x.get("elapsed_s", 0.0))):
        elapsed = float(r.get("elapsed_s", 0.0))
        pct = 100.0 * elapsed / total
        n_items = r.get("n_items")
        model = r.get("model") or "—"
        out_tok = r.get("output_tokens")
        in_tok = r.get("input_tokens")
        cost = r.get("cost_usd")
        token_disp = (
            f"{in_tok:,} → {out_tok:,}"
            if (in_tok is not None and out_tok is not None)
            else "—"
        )
        cost_disp = f"${cost:.4f}" if cost is not None else "—"
        items_disp = f"{n_items}" if n_items is not None else "—"
        phase = r.get("phase") or "other"
        phase_kind = _PHASE_KIND.get(phase, "gray")
        detail_rows.append(
            "<tr>"
            f"<td><code>{html.escape(str(r.get('step_name', '?')))}</code></td>"
            f"<td>{_badge(phase, phase_kind)}</td>"
            f"<td class='num'>{elapsed:.2f}s</td>"
            f"<td class='num small'>{pct:.1f}%</td>"
            f"<td class='num small'>{items_disp}</td>"
            f"<td class='small'>{html.escape(model)}</td>"
            f"<td class='num small'>{token_disp}</td>"
            f"<td class='num small'>{cost_disp}</td>"
            "</tr>"
        )

    return f"""
    <section class="block timing-block">
      <h2>Step timeline · {total_disp:.1f}s wall clock
          <span class="muted small">
            (sum-of-steps {sum_step_seconds:.1f}s · parallelism {parallelism:.1f}×)
          </span>
      </h2>
      <div class="timing-bar" role="img"
           aria-label="phase breakdown of {total_disp:.1f}s total runtime">
        {''.join(bar_segments)}
      </div>
      <div class="bar-legend-row">{''.join(legend_items)}</div>
      <details class="timing-detail">
        <summary>per-step detail ({len(rows)} steps, sorted by elapsed)</summary>
        <table class="compact timing-table">
          <thead>
            <tr>
              <th>Step</th><th>Phase</th><th>Elapsed</th><th>%</th>
              <th>Items</th><th>Model</th><th>Tokens (in→out)</th><th>Cost</th>
            </tr>
          </thead>
          <tbody>
            {''.join(detail_rows)}
          </tbody>
        </table>
      </details>
    </section>
    """


# ---------------------------------------------------------------------------
# Section 1 — Surface Evidence
# ---------------------------------------------------------------------------


def _render_antibody(ab: dict[str, Any]) -> str:
    pieces: list[str] = []
    pieces.append(f"<strong>{html.escape(ab.get('name', '—'))}</strong>")
    if ab.get("clone"):
        pieces.append(f"clone {html.escape(ab['clone'])}")
    if ab.get("vendor"):
        pieces.append(html.escape(ab["vendor"]))
    if ab.get("rrid"):
        pieces.append(f"<code>{html.escape(ab['rrid'])}</code>")
    if ab.get("monoclonal_or_polyclonal") and ab["monoclonal_or_polyclonal"] != "unknown":
        pieces.append(html.escape(ab["monoclonal_or_polyclonal"]))
    if ab.get("antibody_epitope_region") and ab["antibody_epitope_region"] != "unknown":
        pieces.append(f"epitope: {html.escape(ab['antibody_epitope_region'])}")
    if ab.get("validation_strategy") and ab["validation_strategy"] not in ("none", "unknown"):
        pieces.append(
            f"validation: {html.escape(ab['validation_strategy'])} "
            f"({html.escape(ab.get('validation_strength', '—'))})"
        )
    if ab.get("cross_reactivity_notes"):
        pieces.append(f"x-react: {html.escape(ab['cross_reactivity_notes'])}")
    return "<div class='ab'>" + " · ".join(pieces) + "</div>"


def _render_method_card(m: dict[str, Any]) -> str:
    abs_html = "".join(_render_antibody(ab) for ab in (m.get("antibodies") or []))
    obs_rows = ""
    for obs in m.get("expression_observations") or []:
        obs_rows += (
            f"<tr><td>{html.escape(obs.get('context', '—'))}</td>"
            f"<td>{_badge(obs.get('sample_type', '—'), 'gray')}</td>"
            f"<td>{_badge(obs.get('level', '—'), _PRESENCE_KIND.get(obs.get('level') or '', 'gray'))}</td>"
            f"<td>{_evi_chip_row(obs.get('cited_evidence_ids') or [])}</td></tr>"
        )
    obs_table = (
        f"<table class='compact'><thead><tr><th>context</th><th>sample</th>"
        f"<th>level</th><th>cites</th></tr></thead><tbody>{obs_rows}</tbody></table>"
        if obs_rows
        else "<em class='muted small'>no expression observations</em>"
    )
    return f"""
    <div class="method-card">
      <div class="method-head">
        {_badge(m.get('method_family', '—'), 'blue')}
        {_badge(m.get('method_subclass', '—'), 'blue')}
        {_badge('perm: ' + str(m.get('permeabilization', '—')), 'gray')}
        {_badge('system: ' + str(m.get('expression_system', '—')), 'gray')}
        {_badge(m.get('accessibility_relevance', '—'), _RELEVANCE_KIND.get(m.get('accessibility_relevance') or '', 'gray'))}
        {_badge('claim: ' + str(m.get('surface_claim_type', '—')), 'amber')}
      </div>
      <div class="abs">{abs_html or "<em class='muted small'>no antibodies recorded</em>"}</div>
      <div class="obs">{obs_table}</div>
      <div class="citations">{_evi_chip_row(m.get('cited_evidence_ids') or [])}</div>
    </div>
    """


def _render_nse(nse: dict[str, Any]) -> str:
    return (
        f"<tr>"
        f"<td>{html.escape(nse.get('context', '—'))}</td>"
        f"<td>{_badge(nse.get('sample_type', '—'), 'gray')}</td>"
        f"<td>{_badge(nse.get('measurement_type', '—'), 'lavender')}</td>"
        f"<td>{_badge(nse.get('level', '—'), _PRESENCE_KIND.get(nse.get('level') or '', 'gray'))}</td>"
        f"<td>{_evi_chip_row(nse.get('cited_evidence_ids') or [])}</td>"
        f"</tr>"
    )


def _render_te(te: dict[str, Any] | None) -> str:
    if te is None:
        return "<em class='muted'>no therapeutic engagement evidence</em>"
    desc = html.escape(te.get("description") or "—")
    rat = html.escape(te.get("surface_form_rationale") or "—")
    return f"""
    <div class="te-card">
      <div class="te-head">
        {_badge('stage: ' + str(te.get('highest_stage', '—')), 'amber')}
      </div>
      <div class="quote-label">description</div>
      <div class="prose-block">{desc}</div>
      <div class="quote-label">surface-form rationale</div>
      <div class="prose-block">{rat}</div>
      <div class="citations">{_evi_chip_row(te.get('cited_evidence_ids') or [])}</div>
    </div>
    """


def _render_contradiction(c: dict[str, Any]) -> str:
    return f"""
    <div class="contra-card">
      <div class="contra-head">
        {_badge(c.get('contradiction_type', '—'), 'red')}
        {_badge('severity: ' + str(c.get('severity_for_surface_accessibility', '—')),
                _SEVERITY_KIND.get(c.get('severity_for_surface_accessibility') or '', 'gray'))}
      </div>
      <div class="prose-block">{html.escape(c.get('claim') or '—')}</div>
      {f"<div class='quote-label'>likely explanation</div><div class='prose-block'>{html.escape(c.get('likely_explanation') or '')}</div>" if c.get('likely_explanation') else ''}
      <div class="citations">{_evi_chip_row(c.get('cited_evidence_ids') or [])}</div>
    </div>
    """


def _render_surface_evidence(record: dict[str, Any]) -> str:
    se = record.get("surface_evidence") or {}
    grade = se.get("evidence_grade") or "—"
    rationale = html.escape(se.get("grade_rationale") or "—")
    methods = se.get("methods") or []
    nse = se.get("non_surface_expression") or []
    te = se.get("therapeutic_engagement")
    contras = se.get("contradicting_evidence") or []

    methods_html = (
        "".join(_render_method_card(m) for m in methods)
        if methods
        else "<em class='muted'>no method observations</em>"
    )
    nse_table = (
        "<table class='compact'><thead><tr><th>context</th><th>sample</th>"
        "<th>measurement</th><th>level</th><th>cites</th></tr></thead><tbody>"
        + "".join(_render_nse(n) for n in nse)
        + "</tbody></table>"
        if nse
        else "<em class='muted'>no non-surface expression rows</em>"
    )
    contras_html = (
        "".join(_render_contradiction(c) for c in contras)
        if contras
        else "<em class='muted'>no contradictions recorded</em>"
    )

    return f"""
    <section class="block">
      <h2>Section 1 — Surface evidence</h2>
      <div class="sub-grid">
        <div class="sub">
          <div class="sub-label">evidence grade</div>
          <div class="sub-val">{_badge(grade, _GRADE_KIND.get(grade, 'gray'))}</div>
        </div>
        <div class="sub wide">
          <div class="sub-label">grade rationale</div>
          <div class="sub-val">{rationale}</div>
        </div>
      </div>

      <h3>Methods ({len(methods)})</h3>
      {methods_html}

      <h3>Non-surface expression ({len(nse)})</h3>
      <div class="muted small">RNA / bulk-protein / non-fractionated observations — held
      separately so expression isn't read as accessibility.</div>
      {nse_table}

      <h3>Therapeutic engagement</h3>
      {_render_te(te)}

      <h3>Contradicting evidence ({len(contras)})</h3>
      {contras_html}
    </section>
    """


# ---------------------------------------------------------------------------
# Section 2 — Biological context
# ---------------------------------------------------------------------------


def _render_tissue(t: dict[str, Any]) -> str:
    cell_types = ", ".join(t.get("cell_types") or [])
    cell_states = ", ".join(t.get("cell_states") or [])
    return (
        f"<tr>"
        f"<td><strong>{html.escape(t.get('tissue', '—'))}</strong></td>"
        f"<td>{_badge(t.get('present', '—'), _PRESENCE_KIND.get(t.get('present') or '', 'gray'))}</td>"
        f"<td>{_badge(t.get('disease_context', '—'), 'gray')}</td>"
        f"<td class='small'>{html.escape(cell_types)}</td>"
        f"<td class='small'>{html.escape(cell_states)}</td>"
        f"<td>{_evi_chip_row(t.get('cited_evidence_ids') or [])}</td>"
        f"</tr>"
    )


def _render_cell_type(c: dict[str, Any]) -> str:
    tissues = ", ".join(c.get("present_in_tissues") or [])
    return (
        f"<tr>"
        f"<td><strong>{html.escape(c.get('cell_type', '—'))}</strong></td>"
        f"<td><code>{html.escape(c.get('ontology_id') or '—')}</code></td>"
        f"<td class='small'>{html.escape(tissues)}</td>"
        f"<td>{_evi_chip_row(c.get('cited_evidence_ids') or [])}</td>"
        f"</tr>"
    )


def _render_subcellular(s: dict[str, Any]) -> str:
    primary = s.get("primary_compartment") or "—"
    dual = s.get("dual_localization") or []
    subdomains = s.get("membrane_subdomains") or []
    dual_html = "".join(
        f"<li>{html.escape(d.get('compartment', '—'))}"
        + (f" — {html.escape(d.get('condition'))}" if d.get('condition') else '')
        + (f" (fraction ~{d.get('fraction_estimate')})" if d.get('fraction_estimate') is not None else '')
        + f" {_evi_chip_row(d.get('cited_evidence_ids') or [])}</li>"
        for d in dual
    ) or "<li class='muted small'>none</li>"
    sub_html = "".join(
        f"<li>{html.escape(sd.get('subdomain', '—'))} "
        + f"{_evi_chip_row(sd.get('cited_evidence_ids') or [])}</li>"
        for sd in subdomains
    ) or "<li class='muted small'>none</li>"
    return f"""
    <div class="sub-grid">
      <div class="sub">
        <div class="sub-label">primary compartment</div>
        <div class="sub-val">{_badge(primary, 'green' if primary == 'plasma_membrane' else 'amber')}</div>
      </div>
      <div class="sub wide">
        <div class="sub-label">dual localization</div>
        <ul class="compact-list">{dual_html}</ul>
      </div>
      <div class="sub wide">
        <div class="sub-label">membrane subdomains</div>
        <ul class="compact-list">{sub_html}</ul>
      </div>
    </div>
    """


def _render_anat(a: dict[str, Any]) -> str:
    return f"""
    <div class="anat-card">
      <div class="anat-head">
        {_badge(a.get('orientation', '—'), 'blue')}
        {_badge('access: ' + str(a.get('accessibility_implication', '—')),
                _ACC_KIND.get(a.get('accessibility_implication') or '', 'gray'))}
      </div>
      <div class="prose-block"><strong>context:</strong> {html.escape(a.get('context') or '—')}</div>
      <div class="prose-block">{html.escape(a.get('rationale') or '—')}</div>
      <div class="citations">{_evi_chip_row(a.get('cited_evidence_ids') or [])}</div>
    </div>
    """


def _render_modulation(m: dict[str, Any]) -> str:
    category = m.get("category") or "—"
    sub_chips: list[str] = []
    if m.get("category_other_label"):
        sub_chips.append(_badge("other: " + m["category_other_label"], "gray"))
    if m.get("cell_state_trigger"):
        sub_chips.append(_badge("trigger: " + m["cell_state_trigger"], "lavender"))
    if m.get("restricted_lineage"):
        sub_chips.append(_badge("lineage: " + m["restricted_lineage"], "blue"))
    if m.get("dual_loc_partner_compartment"):
        sub_chips.append(_badge("partner: " + m["dual_loc_partner_compartment"], "amber"))
    return f"""
    <div class="mod-card">
      <div class="mod-head">
        {_badge(category, _MODULATION_KIND.get(category, 'gray'))}
        {''.join(sub_chips)}
      </div>
      <div class="mod-states">
        <div class="state-cell">
          <div class="state-label">baseline</div>
          <div class="state-val">{html.escape(m.get('baseline_context') or '—')}</div>
        </div>
        <div class="state-arrow">→</div>
        <div class="state-cell">
          <div class="state-label">modulating state</div>
          <div class="state-val">{html.escape(m.get('modulating_state') or '—')}</div>
        </div>
      </div>
      <div class="quote-label">change</div>
      <div class="prose-block">{html.escape(m.get('change') or '—')}</div>
      <div class="quote-label">accessibility implication</div>
      <div class="prose-block">{html.escape(m.get('accessibility_implication') or '—')}</div>
      <div class="citations">{_evi_chip_row(m.get('cited_evidence_ids') or [])}</div>
    </div>
    """


def _render_biological_context(record: dict[str, Any]) -> str:
    bc = record.get("biological_context") or {}
    tissues = bc.get("tissues") or []
    cell_types = bc.get("cell_types") or []
    cell_states = bc.get("cell_states") or []
    sub = bc.get("subcellular_localization") or {}
    anat = bc.get("anatomical_accessibility") or []
    mods = bc.get("accessibility_modulation") or []

    tissues_html = (
        "<table class='compact'><thead><tr><th>tissue</th><th>presence</th>"
        "<th>disease</th><th>cell types</th><th>cell states</th><th>cites</th>"
        "</tr></thead><tbody>" + "".join(_render_tissue(t) for t in tissues) + "</tbody></table>"
        if tissues
        else "<em class='muted'>no tissue rows</em>"
    )
    cell_types_html = (
        "<table class='compact'><thead><tr><th>cell type</th><th>ontology</th>"
        "<th>in tissues</th><th>cites</th></tr></thead><tbody>"
        + "".join(_render_cell_type(c) for c in cell_types) + "</tbody></table>"
        if cell_types
        else "<em class='muted'>no cell-type rows</em>"
    )
    cell_states_html = (
        "<ul class='compact-list'>"
        + "".join(
            f"<li><strong>{html.escape(s.get('state', '—'))}</strong>: "
            f"{html.escape(s.get('descriptor', '—'))} "
            f"{_evi_chip_row(s.get('cited_evidence_ids') or [])}</li>"
            for s in cell_states
        )
        + "</ul>"
        if cell_states
        else "<em class='muted'>no cell-state rows</em>"
    )
    anat_html = (
        "".join(_render_anat(a) for a in anat)
        if anat
        else "<em class='muted'>no anatomical-accessibility observations</em>"
    )
    mods_html = (
        "".join(_render_modulation(m) for m in mods)
        if mods
        else "<em class='muted'>no accessibility-modulation observations</em>"
    )

    return f"""
    <section class="block">
      <h2>Section 2 — Biological context</h2>

      <h3>Tissues ({len(tissues)})</h3>
      {tissues_html}

      <h3>Cell types ({len(cell_types)})</h3>
      {cell_types_html}

      <h3>Cell states ({len(cell_states)})</h3>
      {cell_states_html}

      <h3>Subcellular localization</h3>
      {_render_subcellular(sub)}

      <h3>Anatomical accessibility ({len(anat)})</h3>
      {anat_html}

      <h3>Accessibility modulation ({len(mods)})</h3>
      {mods_html}
    </section>
    """


# ---------------------------------------------------------------------------
# Section 3 — Deterministic features
# ---------------------------------------------------------------------------


def _render_deterministic(record: dict[str, Any]) -> str:
    det = record.get("deterministic_features") or {}
    ct = det.get("canonical_topology") or {}
    struct = det.get("structure") or {}
    paralogs = det.get("paralogs") or []
    orthos = det.get("orthologs") or {}
    o_counts = {
        sp: len(orthos.get(sp) or []) for sp in ("mouse", "rat", "cynomolgus")
    }
    return f"""
    <section class="block">
      <h2>Section 3 — Deterministic features</h2>
      <div class="sub-grid">
        <div class="sub">
          <div class="sub-label">TM helix count</div>
          <div class="sub-val big">{ct.get('tm_helix_count', '—')}</div>
        </div>
        <div class="sub">
          <div class="sub-label">ECD length (aa)</div>
          <div class="sub-val big">{ct.get('ecd_length_residues', '—')}</div>
        </div>
        <div class="sub">
          <div class="sub-label">ICD length (aa)</div>
          <div class="sub-val big">{ct.get('icd_length_residues', '—')}</div>
        </div>
        <div class="sub">
          <div class="sub-label">N / C terminus</div>
          <div class="sub-val">
            {html.escape(ct.get('n_terminal_orientation', '—'))} /
            {html.escape(ct.get('c_terminal_orientation', '—'))}
          </div>
        </div>
        <div class="sub">
          <div class="sub-label">AFDB structure</div>
          <div class="sub-val">{html.escape(struct.get('afdb_id') or '—')}</div>
          <div class="sub-sub">
            mean pLDDT {struct.get('ecd_mean_plddt', '—')} ·
            disorder {struct.get('ecd_disordered_fraction', '—')}
          </div>
        </div>
        <div class="sub">
          <div class="sub-label">orthologs (m / r / c)</div>
          <div class="sub-val">{o_counts['mouse']} / {o_counts['rat']} / {o_counts['cynomolgus']}</div>
        </div>
        <div class="sub">
          <div class="sub-label">paralogs</div>
          <div class="sub-val big">{len(paralogs)}</div>
        </div>
      </div>
    </section>
    """


# ---------------------------------------------------------------------------
# Section 4 — Filters
# ---------------------------------------------------------------------------


def _render_filters(record: dict[str, Any]) -> str:
    f = record.get("filters") or {}

    def _kv(k: str, v: Any, kind: str = "gray") -> str:
        return (
            f'<div class="filter-row">'
            f'<span class="filter-key">{html.escape(k)}</span>'
            f'{_badge(str(v) if v is not None else "—", kind)}'
            f"</div>"
        )

    rows = [
        _kv("surface_accessibility", f.get("surface_accessibility"),
            _ACC_KIND.get(f.get("surface_accessibility") or "", "gray")),
        _kv("evidence_grade", f.get("evidence_grade"),
            _GRADE_KIND.get(f.get("evidence_grade") or "", "gray")),
        _kv("confidence", f.get("confidence"),
            _CONFIDENCE_KIND.get(f.get("confidence") or "", "gray")),
        _kv("subcategory", f.get("subcategory")),
        _kv("expression_level", f.get("expression_level")),
        _kv("expression_breadth", f.get("expression_breadth")),
        _kv("surface_specificity", f.get("surface_specificity")),
        _kv("evidence_density", f.get("evidence_density")),
        _kv("ecd_accessibility_class", f.get("ecd_accessibility_class")),
        _kv("has_shed_form", f.get("has_shed_form")),
        _kv("has_secreted_form", f.get("has_secreted_form")),
        _kv("has_restricted_subdomain", f.get("has_restricted_subdomain")),
        _kv("has_epitope_masking", f.get("has_epitope_masking")),
        _kv("requires_coreceptor", f.get("requires_coreceptor_for_expression")),
        _kv("n-term extracellular", f.get("n_term_extracellular")),
        _kv("c-term extracellular", f.get("c_term_extracellular")),
        _kv("mouse ECD %id", f.get("mouse_ortholog_ecd_pct_identity")),
        _kv("cyno ECD %id", f.get("cyno_ortholog_ecd_pct_identity")),
        _kv("max paralog ECD %id", f.get("max_paralog_ecd_pct_identity")),
    ]
    return f"""
    <section class="block">
      <h2>Section 4 — Filters (catalog rollups)</h2>
      <div class="filters-grid">{''.join(rows)}</div>
    </section>
    """


# ---------------------------------------------------------------------------
# Section 5 — Accessibility risks
# ---------------------------------------------------------------------------


def _render_risks(record: dict[str, Any]) -> str:
    r = record.get("accessibility_risks") or {}

    def _present_chip(rec: dict[str, Any], label: str) -> str:
        present = rec.get("present")
        sev = rec.get("severity") or "unclear"
        strength = rec.get("evidence_strength") or "unknown"
        kind = "red" if present else "gray"
        return (
            f"<div class='risk-row'>"
            f"<div class='risk-label'>{label}</div>"
            f"{_badge('present' if present else 'absent', kind)}"
            f"{_badge('severity: ' + sev, _SEVERITY_KIND.get(sev, 'gray'))}"
            f"{_badge('strength: ' + strength, 'gray')}"
            f"</div>"
            + (f"<div class='risk-detail'>{html.escape(rec.get('mechanism') or '')}</div>"
               if rec.get('mechanism') else '')
            + (f"<div class='risk-detail'>sheddase: {html.escape(rec.get('sheddase_if_known') or '')}</div>"
               if rec.get('sheddase_if_known') else '')
            + f"<div class='citations'>{_evi_chip_row(rec.get('cited_evidence_ids') or [])}</div>"
        )

    co = r.get("co_receptor_requirements") or {}
    co_html = (
        f"<div class='risk-row'>"
        f"<div class='risk-label'>co-receptor</div>"
        f"{_badge(co.get('surface_expression_dependency', '—'), 'amber')}"
        f"{_badge('basis: ' + str(co.get('evidence_basis', '—')), 'gray')}"
        f"</div>"
        f"<div class='risk-detail'>partners: {html.escape(', '.join(co.get('partners') or []) or '—')}</div>"
        f"<div class='risk-detail'>{html.escape(co.get('rationale') or '—')}</div>"
        f"<div class='citations'>{_evi_chip_row(co.get('cited_evidence_ids') or [])}</div>"
    )

    em = r.get("epitope_masking") or {}
    em_html = (
        f"<div class='risk-row'>"
        f"<div class='risk-label'>epitope masking</div>"
        f"{_badge('present' if em.get('present') else 'absent', 'red' if em.get('present') else 'gray')}"
        f"{_badge('mechanism: ' + str(em.get('mechanism_type', '—')), 'amber')}"
        f"{_badge('severity: ' + str(em.get('severity', '—')), _SEVERITY_KIND.get(em.get('severity') or '', 'gray'))}"
        f"</div>"
        + (f"<div class='risk-detail'>{html.escape(em.get('description') or '')}</div>"
           if em.get('description') else '')
        + f"<div class='citations'>{_evi_chip_row(em.get('cited_evidence_ids') or [])}</div>"
    )

    rs = r.get("restricted_subdomain") or {}
    rs_html = (
        f"<div class='risk-row'>"
        f"<div class='risk-label'>restricted subdomain</div>"
        f"{_badge('present' if rs.get('present') else 'absent', 'red' if rs.get('present') else 'gray')}"
        f"{_badge('domain: ' + str(rs.get('domain', '—')), 'amber')}"
        f"{_badge('severity: ' + str(rs.get('severity', '—')), _SEVERITY_KIND.get(rs.get('severity') or '', 'gray'))}"
        f"</div>"
        + (f"<div class='risk-detail'>{html.escape(rs.get('rationale') or '')}</div>"
           if rs.get('rationale') else '')
        + f"<div class='citations'>{_evi_chip_row(rs.get('cited_evidence_ids') or [])}</div>"
    )

    ecd = r.get("ecd_size_assessment") or {}
    ecd_html = (
        f"<div class='risk-row'>"
        f"<div class='risk-label'>ECD size assessment</div>"
        f"{_badge(ecd.get('class') or '—', 'blue')}"
        f"</div>"
        + (f"<div class='risk-detail'>{html.escape(ecd.get('rationale') or '')}</div>"
           if ecd.get('rationale') else '')
    )

    return f"""
    <section class="block">
      <h2>Section 5 — Accessibility risks</h2>
      <div class="risks-grid">
        <div class="risk-card">{_present_chip(r.get('shed_form') or {}, 'shed form')}</div>
        <div class="risk-card">{_present_chip(r.get('secreted_form') or {}, 'secreted form')}</div>
        <div class="risk-card">{em_html}</div>
        <div class="risk-card">{rs_html}</div>
        <div class="risk-card">{co_html}</div>
        <div class="risk-card">{ecd_html}</div>
      </div>
    </section>
    """


# ---------------------------------------------------------------------------
# Section 6 — Evidence ledger
# ---------------------------------------------------------------------------


def _render_evidence_card(e: dict[str, Any], bundle: dict[str, Any] | None) -> str:
    """Render one promoted Evidence row.

    Post-promotion the verbatim quote(s) live under ``spans[]`` —
    ``EvidenceSpan`` objects with ``quote``, ``source.source_id``,
    ``section``, ``figure_or_table_id``. Most rows carry one span;
    multi-span Evidence (when one claim is anchored to multiple
    passages) gets each span rendered as its own quote block.
    """

    safe_id = html.escape(e.get("evidence_id", "—"))
    anchored = e.get("entailment_verified")
    anchored_badge = (
        _badge("anchored", "green") if anchored else _badge("UNANCHORED", "red")
    )
    badges = "".join([
        _badge(e.get("claim_type", "—"), "blue"),
        _badge(e.get("evidence_type", "—"), "lavender"),
        _badge(e.get("evidence_tier", "—"),
               _TIER_KIND.get(e.get("evidence_tier") or "", "gray")),
        _badge(e.get("direction", "—"),
               _DIRECTION_KIND.get(e.get("direction") or "", "gray")),
        _badge("conf: " + str(e.get("confidence", "—")),
               _CONFIDENCE_KIND.get(e.get("confidence") or "", "gray")),
        anchored_badge,
    ])

    spans = e.get("spans") or []
    if not spans:
        # Defensive: surface the missing-span case explicitly rather than
        # silently rendering an empty quote block. Shouldn't happen post-
        # promote_claim, but check makes a broken record visible at QC time.
        spans_html = (
            "<div class='quote-label'>verbatim quote</div>"
            "<blockquote class='quote'><em>"
            "(no spans on this Evidence row — promote_claim may have "
            "produced an unanchored record)"
            "</em></blockquote>"
        )
        src_chip = (
            f"<span class='src'>{html.escape(str(e.get('source_id') or '—'))}</span>"
        )
        section_chip = html.escape(e.get("section") or "—")
    else:
        # One header chip per source — usually one, but allow multi-source.
        seen_sources: list[str] = []
        for sp in spans:
            sid = (sp.get("source") or {}).get("source_id") or "—"
            if sid not in seen_sources:
                seen_sources.append(sid)
        src_chip = " ".join(
            _src_link(sid, bundle=bundle) for sid in seen_sources
        )
        # Section / figure tag (use the first span's; rare to differ across spans).
        first = spans[0]
        section = first.get("section") or "—"
        figure = first.get("figure_or_table_id")
        section_chip = (
            html.escape(section)
            + (f' · <code>{html.escape(str(figure))}</code>' if figure else '')
        )
        # Render each span as its own quote block (most Evidence has one).
        block_pieces: list[str] = []
        for i, sp in enumerate(spans, start=1):
            quote = html.escape(sp.get("quote") or "")
            label = (
                f"verbatim quote {i}/{len(spans)}"
                if len(spans) > 1 else "verbatim quote"
            )
            block_pieces.append(
                f"<div class='quote-label'>{label}</div>"
                f"<blockquote class='quote'>{quote}</blockquote>"
            )
        spans_html = "\n".join(block_pieces)

    return f"""
    <article class="evidence-card" id="{safe_id}">
      <header class="evi-header">
        <div class="evi-id-row">
          <span class="evi-id">{safe_id}</span>
          {src_chip}
          <span class="section">{section_chip}</span>
        </div>
        <div class="badges">{badges}</div>
      </header>
      {spans_html}
      <div class="quote-label">agent's claim</div>
      <p class="claim-text">{html.escape(e.get("claim") or '—')}</p>
    </article>
    """


def _render_evidence_section(record: dict[str, Any]) -> str:
    evidence = record.get("evidence") or []
    bundle_proxy = record.get("gene") or {}  # for HPA URL bundle keys
    bundle = {
        "ensembl_gene": bundle_proxy.get("ensembl_gene"),
        "hgnc_symbol": bundle_proxy.get("hgnc_symbol"),
    }
    if not evidence:
        return "<section class='block'><h2>Section 6 — Evidence ledger</h2><em class='muted'>no evidence</em></section>"
    cards = "\n".join(_render_evidence_card(e, bundle) for e in evidence)
    return f"""
    <section class="block">
      <h2>Section 6 — Evidence ledger ({len(evidence)})</h2>
      {cards}
    </section>
    """


# ---------------------------------------------------------------------------
# CSS
# ---------------------------------------------------------------------------

_CSS = r"""
:root {
  --bg: #fafaf7;
  --bg-card: #ffffff;
  --bg-muted: #f1f0eb;
  --fg: #222;
  --fg-muted: #6b6b6b;
  --border: #e2e0d8;
  --accent: #7a1d3f;
  --accent-soft: #f3e2e8;
  --quote-bg: #f7f4ee;
  --quote-border: #c8a35e;
  --ok: #2c6e4b; --ok-bg: #e0f0e6;
  --warn: #8a5a00; --warn-bg: #fbeed1;
  --bad: #8a1d1d; --bad-bg: #f7d8d8;
  --info: #1d4f8a; --info-bg: #d8e6f7;
  --gray: #555; --gray-bg: #e8e8e3;
  --lav: #4e3c8a; --lav-bg: #e5dcf7;
}
* { box-sizing: border-box; }
body {
  font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
  background: var(--bg); color: var(--fg);
  margin: 0; padding: 1.5rem; line-height: 1.5;
}
main { max-width: 1200px; margin: 0 auto; }

/* ---- Banner ---- */
.record-banner {
  background: var(--bg-card); border: 1px solid var(--border);
  border-radius: 8px; padding: 1.25rem 1.5rem; margin-bottom: 1.5rem;
}
.record-banner h1 { font-size: 2rem; margin: 0; color: var(--accent); }
.id-row {
  display: flex; flex-wrap: wrap; gap: 1rem;
  margin: 0.5rem 0 1rem; font-size: 0.88rem; color: var(--fg-muted);
}
.id-key {
  color: var(--fg-muted); font-size: 0.72rem;
  text-transform: uppercase; letter-spacing: 0.05em; margin-right: 0.3rem;
}
.id { font-family: ui-monospace, "SF Mono", Menlo, monospace; }
.verdict-row {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(140px, 1fr));
  gap: 1rem; padding-top: 0.75rem; border-top: 1px solid var(--border);
}
.verdict .verdict-label {
  font-size: 0.72rem; text-transform: uppercase; letter-spacing: 0.05em;
  color: var(--fg-muted); margin-bottom: 0.25rem;
}
.verdict .verdict-val { font-size: 0.95rem; }
.verdict .verdict-val.big { font-size: 1.5rem; font-weight: 600; }
.verdict .verdict-val.small { font-size: 0.82rem; }
.verdict .verdict-sub {
  font-size: 0.74rem; color: var(--fg-muted); margin-top: 0.2rem;
}

/* ---- Section block ---- */
section.block {
  background: var(--bg-card); border: 1px solid var(--border);
  border-radius: 8px; padding: 1rem 1.5rem 1.5rem; margin-bottom: 1.25rem;
}
section.block > h2 {
  font-size: 1.2rem; color: var(--accent); margin: 0.5rem 0 1rem;
  padding-bottom: 0.4rem; border-bottom: 2px solid var(--accent-soft);
}
section.block > h3 {
  font-size: 1rem; margin: 1.25rem 0 0.5rem;
  color: var(--fg); font-weight: 600;
}

/* ---- Generic badge ---- */
.badge {
  display: inline-block;
  font-size: 0.74rem; padding: 0.1rem 0.5rem;
  border-radius: 3px; font-weight: 500;
  font-family: ui-monospace, "SF Mono", Menlo, monospace;
}
.badge-green { background: var(--ok-bg); color: var(--ok); }
.badge-amber { background: var(--warn-bg); color: var(--warn); }
.badge-red { background: var(--bad-bg); color: var(--bad); }
.badge-blue { background: var(--info-bg); color: var(--info); }
.badge-gray { background: var(--gray-bg); color: var(--gray); }
.badge-lavender { background: var(--lav-bg); color: var(--lav); }

/* ---- Sub-grid (used in multiple sections) ---- */
.sub-grid {
  display: grid; grid-template-columns: repeat(auto-fit, minmax(220px, 1fr));
  gap: 0.75rem; margin-bottom: 1rem;
}
.sub.wide { grid-column: span 2; }
.sub-label, .verdict-label {
  font-size: 0.72rem; text-transform: uppercase; letter-spacing: 0.05em;
  color: var(--fg-muted); margin-bottom: 0.25rem;
}
.sub-val { font-size: 0.95rem; }
.sub-val.big { font-size: 1.4rem; font-weight: 600; }
.sub-sub { font-size: 0.78rem; color: var(--fg-muted); margin-top: 0.2rem; }

/* ---- Prose block ---- */
.prose-block {
  background: var(--bg-muted); padding: 0.6rem 0.9rem;
  border-radius: 4px; font-size: 0.92rem; margin: 0.3rem 0;
}
.prose-block .reasoning { margin-left: 0.5rem; }
.quote-label {
  font-size: 0.72rem; text-transform: uppercase; letter-spacing: 0.05em;
  color: var(--fg-muted); margin: 0.5rem 0 0.2rem;
}
blockquote.quote {
  margin: 0; padding: 0.6rem 0.9rem;
  background: var(--quote-bg); border-left: 3px solid var(--quote-border);
  border-radius: 0 4px 4px 0;
  font-family: Georgia, "Times New Roman", serif;
  font-size: 0.94rem; white-space: pre-wrap; word-wrap: break-word;
}
.claim-text { margin: 0.3rem 0 0; }

/* ---- Tables ---- */
table.compact {
  width: 100%; border-collapse: collapse;
  background: var(--bg-card); border: 1px solid var(--border);
  border-radius: 4px; overflow: hidden;
  font-size: 0.86rem; margin: 0.5rem 0;
}
table.compact th, table.compact td {
  text-align: left; padding: 0.4rem 0.6rem;
  border-bottom: 1px solid var(--border); vertical-align: top;
}
table.compact th {
  background: var(--bg-muted); font-weight: 600;
  font-size: 0.74rem; text-transform: uppercase;
  letter-spacing: 0.04em; color: var(--fg-muted);
}
table.compact tbody tr:last-child td { border-bottom: 0; }
table.compact td.small, td.small { font-size: 0.82rem; color: var(--fg-muted); }
.compact-list { margin: 0.3rem 0 0; padding-left: 1.2rem; }
.compact-list li { font-size: 0.88rem; margin-bottom: 0.25rem; }

/* ---- Method cards ---- */
.method-card {
  background: var(--bg-card); border: 1px solid var(--border);
  border-left: 4px solid var(--info); border-radius: 4px;
  padding: 0.75rem 1rem; margin-bottom: 0.75rem;
}
.method-head, .te-head, .contra-head, .anat-head, .mod-head {
  display: flex; flex-wrap: wrap; gap: 0.4rem; margin-bottom: 0.6rem;
}
.abs { margin: 0.5rem 0; }
.ab {
  font-size: 0.85rem; padding: 0.3rem 0.5rem;
  background: var(--bg-muted); border-radius: 3px;
  margin-bottom: 0.25rem;
}
.obs { margin: 0.4rem 0; }
.te-card {
  background: var(--bg-card); border: 1px solid var(--border);
  border-left: 4px solid var(--warn); border-radius: 4px;
  padding: 0.75rem 1rem; margin: 0.5rem 0;
}
.contra-card {
  background: var(--bg-card); border: 1px solid var(--border);
  border-left: 4px solid var(--bad); border-radius: 4px;
  padding: 0.75rem 1rem; margin-bottom: 0.5rem;
}
.anat-card {
  background: var(--bg-card); border: 1px solid var(--border);
  border-left: 4px solid var(--info); border-radius: 4px;
  padding: 0.75rem 1rem; margin-bottom: 0.5rem;
}
.mod-card {
  background: var(--bg-card); border: 1px solid var(--border);
  border-left: 4px solid var(--lav); border-radius: 4px;
  padding: 0.75rem 1rem; margin-bottom: 0.75rem;
}
.mod-states {
  display: grid;
  grid-template-columns: 1fr auto 1fr;
  align-items: center; gap: 0.6rem; margin: 0.5rem 0;
}
.state-cell {
  background: var(--bg-muted); padding: 0.45rem 0.7rem; border-radius: 4px;
}
.state-label {
  font-size: 0.7rem; text-transform: uppercase; letter-spacing: 0.05em;
  color: var(--fg-muted); margin-bottom: 0.2rem;
}
.state-val { font-size: 0.88rem; }
.state-arrow { font-size: 1.5rem; color: var(--accent); text-align: center; }

/* ---- Filters ---- */
.filters-grid {
  display: grid; grid-template-columns: repeat(auto-fit, minmax(260px, 1fr));
  gap: 0.4rem 1rem;
}
.filter-row {
  display: flex; justify-content: space-between;
  padding: 0.3rem 0.5rem;
  border-bottom: 1px dashed var(--border); align-items: center;
  font-size: 0.85rem;
}
.filter-key { color: var(--fg-muted); font-family: ui-monospace, monospace; }

/* ---- Risks ---- */
.risks-grid {
  display: grid; grid-template-columns: repeat(auto-fit, minmax(280px, 1fr));
  gap: 0.75rem;
}
.risk-card {
  background: var(--bg-muted); border-radius: 4px;
  padding: 0.75rem 1rem;
}
.risk-row {
  display: flex; flex-wrap: wrap; gap: 0.4rem; align-items: center;
  margin-bottom: 0.4rem;
}
.risk-label { font-weight: 600; font-size: 0.92rem; }
.risk-detail {
  font-size: 0.82rem; color: var(--fg); margin: 0.3rem 0;
}

/* ---- Evidence cards ---- */
.evidence-card {
  background: var(--bg-card); border: 1px solid var(--border);
  border-left: 4px solid var(--accent); border-radius: 6px;
  padding: 0.9rem 1.2rem; margin-bottom: 1rem;
  scroll-margin-top: 1.5rem;
}
.evi-header { display: flex; flex-direction: column; gap: 0.4rem; margin-bottom: 0.6rem; }
.evi-id-row {
  display: flex; flex-wrap: wrap; gap: 0.5rem;
  align-items: center; font-size: 0.9rem;
}
.evi-id {
  font-family: ui-monospace, monospace; font-weight: 600;
  background: var(--accent-soft); color: var(--accent);
  padding: 0.1rem 0.4rem; border-radius: 3px; font-size: 0.85rem;
}
.section {
  color: var(--fg-muted); font-size: 0.83rem; font-style: italic;
}
.section code { font-style: normal; font-family: ui-monospace, monospace; }
.badges { display: flex; flex-wrap: wrap; gap: 0.3rem; }
a.src {
  text-decoration: none; color: var(--accent);
  font-family: ui-monospace, monospace; font-size: 0.85rem;
}
a.src:hover { text-decoration: underline; }
span.src {
  font-family: ui-monospace, monospace; font-size: 0.85rem;
  color: var(--fg-muted);
}

/* ---- Citation chips ---- */
.evi-chips { display: inline-flex; flex-wrap: wrap; gap: 0.2rem; }
a.evi-chip {
  background: var(--accent-soft); color: var(--accent);
  font-family: ui-monospace, monospace; font-size: 0.74rem;
  padding: 0.05rem 0.35rem; border-radius: 3px;
  text-decoration: none;
}
a.evi-chip:hover { background: var(--accent); color: white; }
.citations { margin-top: 0.4rem; }
.muted { color: var(--fg-muted); }
.muted.small, .small { font-size: 0.82rem; }

/* ---- Risks list ---- */
ul.risks { margin: 0.3rem 0 0; padding-left: 1.2rem; }
ul.risks li { font-size: 0.88rem; margin-bottom: 0.2rem; }

/* ---- Timing section ---- */
.timing-bar {
  display: flex; width: 100%; height: 28px;
  border-radius: 4px; overflow: hidden;
  background: var(--bg-muted);
  border: 1px solid var(--border);
  margin: 0.5rem 0 0.4rem;
}
.bar-seg { height: 100%; }
.bar-legend-row {
  display: flex; flex-wrap: wrap; gap: 0.6rem 1rem;
  margin-bottom: 0.4rem;
  align-items: center;
}
.bar-legend { display: inline-flex; align-items: center; gap: 0.3rem; }
details.timing-detail { margin-top: 0.5rem; }
details.timing-detail summary {
  cursor: pointer; color: var(--fg-muted);
  font-size: 0.86rem; padding: 0.3rem 0;
}
table.timing-table td.num, table.timing-table th.num {
  text-align: right; font-variant-numeric: tabular-nums;
}
table.timing-table code {
  font-family: ui-monospace, monospace; font-size: 0.78rem;
}

footer {
  margin-top: 2rem; padding-top: 1rem;
  border-top: 1px solid var(--border);
  color: var(--fg-muted); font-size: 0.78rem; text-align: center;
}
"""


# ---------------------------------------------------------------------------
# Top-level render
# ---------------------------------------------------------------------------


def render_html(record: dict[str, Any]) -> str:
    gene = record.get("gene") or {}
    title = f"surfaceome_v2 · {gene.get('hgnc_symbol', '?')}"
    body = "\n".join([
        _render_banner(record),
        _render_executive_summary(record),
        _render_confidence(record),
        _render_timing_section(record),
        _render_surface_evidence(record),
        _render_biological_context(record),
        _render_deterministic(record),
        _render_filters(record),
        _render_risks(record),
        _render_evidence_section(record),
    ])
    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <title>{html.escape(title)}</title>
  <style>{_CSS}</style>
</head>
<body>
<main>
  {body}
  <footer>
    surfaceome_v2 QC viewer · schema {html.escape(record.get("schema_version", "—"))} ·
    {len(record.get("evidence") or [])} evidence rows
  </footer>
</main>
</body>
</html>
"""


def main(argv: list[str] | None = None) -> int:
    args = sys.argv[1:] if argv is None else argv
    if not args:
        print(
            "usage: python -m accessible_surfaceome.agents.surfaceome_v2.render_html "
            "<surfaceome_v2_record.json> [<out.html>]",
            file=sys.stderr,
        )
        return 2
    in_path = Path(args[0])
    if not in_path.exists():
        print(f"input not found: {in_path}", file=sys.stderr)
        return 1
    out_path = Path(args[1]) if len(args) > 1 else in_path.with_suffix(".html")
    record = json.loads(in_path.read_text())
    out_path.write_text(render_html(record))
    print(f"wrote {out_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
