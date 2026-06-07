"""Render a plan-trim-select run JSON as a single self-contained QC HTML.

Usage:

    uv run python -m accessible_surfaceome.agents.plan_trim_select.render_html \\
        .runs/plan_trim_select_HGNC:4526_a1.json

Writes ``<input>.html`` next to the input JSON. No external assets — open
it straight in a browser.

The viewer is organized for hand QC of the per-agent ledger:

* Top banner with run identity (gene, agent_focus, model spend).
* Per-claim cards: the verbatim quote pinned to the clip pool, the
  agent's interpretive ``claim`` prose underneath, classifications as
  badges, deep-link to the source paper.
* Iteration trace: planner output, search log, per-iteration trim+select
  stats, selector notes, any additional_searches the selector requested.
* Warnings + raw selector response below the fold.

The goal is to make every classification (``claim_type``,
``evidence_type``, ``evidence_tier``, ``direction``, ``confidence``)
visible at a glance so a human reviewer can spot mistags, missing
buckets, or selector behavior that wandered off-focus.
"""

from __future__ import annotations

import html
import json
import sys
from pathlib import Path
from typing import Any


# ---------------------------------------------------------------------------
# Source-id → external URL
# ---------------------------------------------------------------------------


def _source_url(
    source_id: str, *, bundle: dict[str, Any] | None = None
) -> str | None:
    """Best-effort URL for a SourceRef id.

    ``bundle`` (the gene's IdentifierBundle dump) lets us construct
    identifier-shaped URLs for sources that need more than the
    source-id payload: HPA's gene page is
    ``proteinatlas.org/{ensembl_gene}-{hgnc_symbol}`` and needs both
    the Ensembl gene ID and the symbol; passing the bundle keeps the
    renderer source-agnostic. Falls back to a search-keyed URL when
    the bundle is missing or incomplete.
    """

    if source_id.startswith("PMID:"):
        return f"https://pubmed.ncbi.nlm.nih.gov/{source_id[5:].strip()}/"
    if source_id.startswith("PMC:"):
        # NCBI PMC's path requires the ``PMC`` prefix on the accession;
        # source_ids come in two flavors (``PMC:PMC12345`` and
        # ``PMC:12345``) so normalize before formatting. Linking to
        # ncbi.nlm.nih.gov rather than europepmc.org because the latter
        # has had availability issues.
        accession = source_id[4:].strip()
        if not accession.upper().startswith("PMC"):
            accession = f"PMC{accession}"
        return f"https://www.ncbi.nlm.nih.gov/pmc/articles/{accession}/"
    if source_id.startswith("HPA:"):
        # Prefer the canonical {ensembl_gene}-{symbol} gene-page URL when
        # we have the resolved identifiers; the source_id's tail is just
        # the gene symbol (e.g. ``HPA:GPR75``) and isn't enough on its
        # own. Fall back to a symbol-keyed search URL.
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


# ---------------------------------------------------------------------------
# Classification → badge color
# ---------------------------------------------------------------------------


def _badge(text: str | None, kind: str) -> str:
    if text is None:
        text = "—"
    return (
        f'<span class="badge badge-{html.escape(kind)}">'
        f"{html.escape(str(text))}</span>"
    )


_DIRECTION_KIND = {
    "supports": "green",
    "refutes": "red",
    "ambiguous": "amber",
}

_TIER_KIND = {
    "primary": "green",
    "secondary": "amber",
}

_CONFIDENCE_KIND = {
    "strong": "green",
    "moderate": "amber",
    "weak": "red",
}

# A1 vs A2 vs cross-bucket — colored so mistags pop visually.
_A1_CLAIM_TYPES = {
    "surface_expression",
    "topology",
    "methodological",
    "contradictory",
    "epitope_masking",
}
_A2_CLAIM_TYPES = {
    "tissue_expression",
    "cell_state",
    "subcellular_localization",
    "anatomical_accessibility",
    "accessibility_modulation",
}


def _claim_type_badge(claim_type: str, agent_focus: str) -> str:
    """Color claim_type by whether it fits the agent's declared focus."""

    if agent_focus == "a1":
        kind = "green" if claim_type in _A1_CLAIM_TYPES else "red"
    elif agent_focus == "a2":
        kind = "green" if claim_type in _A2_CLAIM_TYPES else "red"
    else:
        raise ValueError(
            f"unknown agent_focus={agent_focus!r}; expected 'a1' or 'a2'"
        )
    return _badge(claim_type, kind)


# ---------------------------------------------------------------------------
# Per-claim card
# ---------------------------------------------------------------------------


def _render_assay_context(ac: dict[str, Any]) -> str:
    if not ac:
        return ""
    items: list[str] = []
    for key, val in ac.items():
        if val is None or val == "" or val == []:
            continue
        if isinstance(val, list):
            val_str = ", ".join(str(v) for v in val)
        else:
            val_str = str(val)
        items.append(
            f'<div class="ac-item"><span class="ac-key">{html.escape(key)}</span>'
            f'<span class="ac-val">{html.escape(val_str)}</span></div>'
        )
    if not items:
        return ""
    return f'<div class="assay-context">{"".join(items)}</div>'


def _render_claim(
    claim: dict[str, Any],
    agent_focus: str,
    *,
    bundle: dict[str, Any] | None = None,
) -> str:
    section = claim.get("section") or "—"
    figure = claim.get("figure_or_table_id")
    figure_html = (
        f' · <span class="fig">{html.escape(str(figure))}</span>' if figure else ""
    )

    badges = "".join(
        [
            _claim_type_badge(claim.get("claim_type", "—"), agent_focus),
            _badge(claim.get("evidence_type", "—"), "blue"),
            _badge(
                claim.get("evidence_tier", "—"),
                _TIER_KIND.get(claim.get("evidence_tier") or "", "gray"),
            ),
            _badge(
                claim.get("direction", "—"),
                _DIRECTION_KIND.get(claim.get("direction") or "", "gray"),
            ),
            _badge(
                f"conf: {claim.get('confidence', '—')}",
                _CONFIDENCE_KIND.get(claim.get("confidence") or "", "gray"),
            ),
        ]
    )

    quote = html.escape(claim.get("quote") or "")
    claim_text = html.escape(claim.get("claim") or "")

    return f"""
    <article class="claim">
      <header class="claim-header">
        <div class="claim-id-row">
          <span class="evidence-id">{html.escape(claim.get("evidence_id", "—"))}</span>
          {_src_link(claim.get("source_id", "—"), bundle=bundle)}
          <span class="section">{html.escape(section)}{figure_html}</span>
        </div>
        <div class="badges">{badges}</div>
      </header>

      <section class="quote-block">
        <div class="quote-label">verbatim quote (anchored to source body):</div>
        <blockquote class="quote">{quote}</blockquote>
      </section>

      <section class="agent-claim">
        <div class="quote-label">agent's interpretive claim:</div>
        <p class="claim-text">{claim_text}</p>
      </section>

      {_render_assay_context(claim.get("assay_context") or {})}
    </article>
    """


# ---------------------------------------------------------------------------
# Plan + search log + iteration trace
# ---------------------------------------------------------------------------


def _render_plan(plan: dict[str, Any] | None) -> str:
    if not plan:
        return '<p class="muted">no plan recorded</p>'
    rationale = html.escape(plan.get("rationale", "") or "(no rationale)")
    rows: list[str] = []
    for i, req in enumerate(plan.get("searches", []), start=1):
        params = ", ".join(
            f"{k}={v!r}"
            for k, v in req.items()
            if k not in ("tool", "intent") and v is not None
        )
        rows.append(
            f"<tr>"
            f"<td class='num'>{i}</td>"
            f"<td><code>{html.escape(req.get('tool', '—'))}</code></td>"
            f"<td><code>{html.escape(params)}</code></td>"
            f"<td class='intent'>{html.escape(req.get('intent', ''))}</td>"
            f"</tr>"
        )
    return (
        f'<p class="muted plan-rationale">{rationale}</p>'
        f'<table class="searches">'
        f"<thead><tr><th>#</th><th>tool</th><th>params</th><th>intent</th></tr></thead>"
        f'<tbody>{"".join(rows)}</tbody></table>'
    )


def _render_search_log(search_log: list[dict[str, Any]]) -> str:
    if not search_log:
        return '<p class="muted">no searches executed</p>'
    rows: list[str] = []
    for i, entry in enumerate(search_log, start=1):
        err = entry.get("error")
        cls = " row-error" if err else ""
        err_html = (
            f"<div class='err-msg'>{html.escape(err)}</div>" if err else ""
        )
        params_str = ", ".join(
            f"{k}={v!r}" for k, v in (entry.get("params") or {}).items()
        )
        rows.append(
            f"<tr class='{cls.strip()}'>"
            f"<td class='num'>{i}</td>"
            f"<td><code>{html.escape(entry.get('tool', '—'))}</code></td>"
            f"<td><code>{html.escape(params_str)}</code></td>"
            f"<td class='num'>{entry.get('n_drafts', 0)}</td>"
            f"<td class='num'>{entry.get('n_papers', 0)}</td>"
            f"<td class='num'>{entry.get('elapsed_s', 0):.2f}s</td>"
            f"<td class='intent'>{html.escape(entry.get('intent', ''))}"
            f"{err_html}</td>"
            f"</tr>"
        )
    return (
        f'<table class="search-log"><thead>'
        f"<tr><th>#</th><th>tool</th><th>params</th>"
        f"<th>drafts</th><th>papers</th><th>elapsed</th><th>intent / error</th></tr>"
        f'</thead><tbody>{"".join(rows)}</tbody></table>'
    )


def _render_iteration_log(iteration_log: list[dict[str, Any]]) -> str:
    if not iteration_log:
        return '<p class="muted">no iterations recorded</p>'
    rows: list[str] = []
    for e in iteration_log:
        more = (
            '<span class="badge badge-amber">YES</span>'
            if e.get("needs_more_searches")
            else '<span class="badge badge-gray">no</span>'
        )
        rows.append(
            f"<tr>"
            f"<td class='num'>{e.get('iteration', 0)}</td>"
            f"<td class='num'>+{e.get('new_searches', 0)}</td>"
            f"<td class='num'>+{e.get('new_drafts', 0)}</td>"
            f"<td class='num'>{e.get('n_drafts_after', 0)}</td>"
            f"<td class='num'>{e.get('n_papers_after', 0)}</td>"
            f"<td class='num'>{e.get('n_kept_after_trim', 0)}</td>"
            f"<td class='num'>{e.get('n_selections', 0)}</td>"
            f"<td>{more}</td>"
            f"</tr>"
        )
    return (
        f'<table class="iter-log"><thead>'
        f"<tr><th>iter</th><th>+searches</th><th>+drafts</th>"
        f"<th>pool drafts</th><th>pool papers</th>"
        f"<th>trim kept</th><th>selected</th><th>more?</th></tr>"
        f'</thead><tbody>{"".join(rows)}</tbody></table>'
    )


def _render_selector_followups(selection_response: dict[str, Any] | None) -> str:
    if not selection_response:
        return ""
    notes = selection_response.get("notes") or ""
    needs_more = selection_response.get("needs_more_searches", False)
    additional = selection_response.get("additional_searches") or []
    parts: list[str] = []
    if notes:
        parts.append(
            f'<div class="selector-notes"><div class="quote-label">selector notes:</div>'
            f'<p>{html.escape(notes)}</p></div>'
        )
    if needs_more and additional:
        rows = []
        for i, req in enumerate(additional, start=1):
            params = ", ".join(
                f"{k}={v!r}"
                for k, v in req.items()
                if k not in ("tool", "intent") and v is not None
            )
            rows.append(
                f"<tr><td class='num'>{i}</td>"
                f"<td><code>{html.escape(req.get('tool', '—'))}</code></td>"
                f"<td><code>{html.escape(params)}</code></td>"
                f"<td class='intent'>{html.escape(req.get('intent', ''))}</td></tr>"
            )
        parts.append(
            f'<div class="additional-searches">'
            f"<div class='quote-label'>final iteration's requested additional searches:</div>"
            f'<table class="searches">'
            f"<thead><tr><th>#</th><th>tool</th><th>params</th><th>intent</th></tr></thead>"
            f'<tbody>{"".join(rows)}</tbody></table></div>'
        )
    return "".join(parts)


# ---------------------------------------------------------------------------
# Top-of-page summary
# ---------------------------------------------------------------------------


def _render_summary(result: dict[str, Any]) -> str:
    gene = html.escape(result.get("gene", "—"))
    focus = result.get("agent_focus") or "—"
    focus_kind = "green" if focus == "a1" else "lavender" if focus == "a2" else "gray"
    uniprot = result.get("uniprot_acc") or "(unresolved)"
    pct_anchored = result.get("pct_anchored")
    anchored_kind = (
        "green"
        if pct_anchored is not None and pct_anchored >= 95.0
        else "red"
        if pct_anchored is not None and pct_anchored < 80.0
        else "amber"
    )
    anchored_text = (
        f"{result.get('n_anchored', 0)}/{result.get('n_claims', 0)}"
        f" ({pct_anchored:.1f}%)" if pct_anchored is not None else "—"
    )
    usage = result.get("usage") or {}
    total_cost = usage.get("total_cost_usd", 0.0)
    plan_c = (usage.get("plan") or {}).get("cost_usd", 0.0)
    trim_c = (usage.get("trim") or {}).get("cost_usd", 0.0)
    sel_c = (usage.get("select") or {}).get("cost_usd", 0.0)

    # Source-spread chip row.
    bundle = result.get("bundle")
    sources: dict[str, int] = {}
    for c in result.get("claims") or []:
        sid = c.get("source_id") or "?"
        sources[sid] = sources.get(sid, 0) + 1
    source_chips = "".join(
        f'<span class="src-chip">{_src_link(sid, bundle=bundle)}'
        f' <span class="count">×{n}</span></span>'
        for sid, n in sorted(sources.items(), key=lambda kv: -kv[1])
    )

    return f"""
    <header class="summary">
      <h1>{gene} <span class="uniprot">→ {html.escape(uniprot)}</span></h1>
      <div class="summary-row">
        <div class="stat">
          <div class="stat-label">focus</div>
          <div class="stat-val">{_badge(focus, focus_kind)}</div>
        </div>
        <div class="stat">
          <div class="stat-label">claims</div>
          <div class="stat-val big">{result.get("n_claims", 0)}</div>
        </div>
        <div class="stat">
          <div class="stat-label">anchored</div>
          <div class="stat-val">{_badge(anchored_text, anchored_kind)}</div>
        </div>
        <div class="stat">
          <div class="stat-label">iterations</div>
          <div class="stat-val big">{result.get("n_iterations_run", 0)}</div>
        </div>
        <div class="stat">
          <div class="stat-label">drafts pooled</div>
          <div class="stat-val big">{result.get("n_drafts_total", 0)}</div>
          <div class="stat-sub">across {result.get("n_papers_total", 0)} papers</div>
        </div>
        <div class="stat">
          <div class="stat-label">trim kept (final)</div>
          <div class="stat-val big">{result.get("n_kept_after_trim", 0)}</div>
        </div>
        <div class="stat">
          <div class="stat-label">elapsed</div>
          <div class="stat-val big">{result.get("elapsed_s", 0):.0f}s</div>
        </div>
        <div class="stat">
          <div class="stat-label">spend (info only)</div>
          <div class="stat-val big">${total_cost:.4f}</div>
          <div class="stat-sub">
            plan ${plan_c:.4f} · trim ${trim_c:.4f} · select ${sel_c:.4f}
          </div>
        </div>
      </div>
      <div class="sources-row">
        <div class="stat-label">sources used:</div>
        <div class="src-chips">{source_chips or "<em>none</em>"}</div>
      </div>
    </header>
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
  --accent: #7a1d3f;        /* maroon */
  --accent-soft: #f3e2e8;
  --quote-bg: #f7f4ee;
  --quote-border: #c8a35e;  /* amber */
  --ok: #2c6e4b;
  --ok-bg: #e0f0e6;
  --warn: #8a5a00;
  --warn-bg: #fbeed1;
  --bad: #8a1d1d;
  --bad-bg: #f7d8d8;
  --info: #1d4f8a;
  --info-bg: #d8e6f7;
  --gray: #555;
  --gray-bg: #e8e8e3;
  --lav: #4e3c8a;
  --lav-bg: #e5dcf7;
}

* { box-sizing: border-box; }

body {
  font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
  background: var(--bg);
  color: var(--fg);
  margin: 0;
  padding: 1.5rem;
  line-height: 1.5;
}

main { max-width: 1100px; margin: 0 auto; }

header.summary {
  background: var(--bg-card);
  border: 1px solid var(--border);
  border-radius: 8px;
  padding: 1.25rem 1.5rem;
  margin-bottom: 1.5rem;
}
header.summary h1 {
  font-size: 1.5rem;
  margin: 0 0 0.5rem;
  color: var(--accent);
}
header.summary .uniprot {
  color: var(--fg-muted);
  font-weight: 400;
  font-size: 1rem;
  font-family: ui-monospace, "SF Mono", Menlo, monospace;
}
.summary-row {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(120px, 1fr));
  gap: 1rem;
  margin-top: 0.5rem;
}
.stat .stat-label {
  font-size: 0.72rem;
  text-transform: uppercase;
  letter-spacing: 0.05em;
  color: var(--fg-muted);
  margin-bottom: 0.2rem;
}
.stat .stat-val { font-size: 1rem; }
.stat .stat-val.big { font-size: 1.4rem; font-weight: 600; }
.stat .stat-sub {
  font-size: 0.75rem;
  color: var(--fg-muted);
  margin-top: 0.15rem;
}
.sources-row {
  margin-top: 1rem;
  padding-top: 0.75rem;
  border-top: 1px solid var(--border);
}
.src-chips { margin-top: 0.4rem; display: flex; flex-wrap: wrap; gap: 0.5rem; }
.src-chip {
  display: inline-flex;
  align-items: center;
  gap: 0.3rem;
  background: var(--bg-muted);
  padding: 0.15rem 0.5rem;
  border-radius: 4px;
  font-size: 0.85rem;
}
.src-chip .count { color: var(--fg-muted); font-size: 0.8rem; }
.src-chip-shared { background: var(--ok-bg); }
.src-chip-a1     { background: var(--accent-soft); }
.src-chip-a2     { background: var(--lav-bg); }

h2 {
  font-size: 1.15rem;
  color: var(--accent);
  margin: 1.5rem 0 0.5rem;
  padding-bottom: 0.25rem;
  border-bottom: 2px solid var(--accent-soft);
}

article.claim {
  background: var(--bg-card);
  border: 1px solid var(--border);
  border-left: 4px solid var(--accent);
  border-radius: 6px;
  padding: 1rem 1.25rem;
  margin-bottom: 1rem;
}
.claim-header {
  display: flex;
  flex-direction: column;
  gap: 0.4rem;
  margin-bottom: 0.75rem;
}
.claim-id-row {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 0.6rem;
  font-size: 0.9rem;
}
.evidence-id {
  font-family: ui-monospace, "SF Mono", Menlo, monospace;
  font-weight: 600;
  background: var(--accent-soft);
  color: var(--accent);
  padding: 0.1rem 0.4rem;
  border-radius: 3px;
  font-size: 0.85rem;
}
.section {
  color: var(--fg-muted);
  font-size: 0.85rem;
  font-style: italic;
}
.fig { font-style: normal; font-family: ui-monospace, monospace; }
.badges { display: flex; flex-wrap: wrap; gap: 0.35rem; }
.badge {
  font-size: 0.74rem;
  padding: 0.1rem 0.5rem;
  border-radius: 3px;
  font-weight: 500;
  font-family: ui-monospace, "SF Mono", Menlo, monospace;
}
.badge-green   { background: var(--ok-bg);   color: var(--ok); }
.badge-amber   { background: var(--warn-bg); color: var(--warn); }
.badge-red     { background: var(--bad-bg);  color: var(--bad); }
.badge-blue    { background: var(--info-bg); color: var(--info); }
.badge-gray    { background: var(--gray-bg); color: var(--gray); }
.badge-lavender{ background: var(--lav-bg);  color: var(--lav); }

.quote-label {
  font-size: 0.72rem;
  text-transform: uppercase;
  letter-spacing: 0.05em;
  color: var(--fg-muted);
  margin-bottom: 0.3rem;
}
.quote-block { margin: 0.6rem 0; }
blockquote.quote {
  margin: 0;
  padding: 0.6rem 0.9rem;
  background: var(--quote-bg);
  border-left: 3px solid var(--quote-border);
  border-radius: 0 4px 4px 0;
  font-family: Georgia, "Times New Roman", serif;
  font-size: 0.95rem;
  white-space: pre-wrap;
  word-wrap: break-word;
}
.agent-claim { margin: 0.6rem 0; }
.claim-text {
  margin: 0;
  padding: 0.6rem 0.9rem;
  background: var(--bg-muted);
  border-radius: 4px;
  font-size: 0.95rem;
}
.assay-context {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(220px, 1fr));
  gap: 0.4rem;
  margin-top: 0.75rem;
  padding-top: 0.75rem;
  border-top: 1px dashed var(--border);
}
.ac-item {
  display: flex;
  gap: 0.5rem;
  font-size: 0.82rem;
  font-family: ui-monospace, monospace;
}
.ac-key { color: var(--fg-muted); }
.ac-val { color: var(--fg); }

a.src {
  text-decoration: none;
  color: var(--accent);
  font-family: ui-monospace, monospace;
  font-size: 0.85rem;
}
a.src:hover { text-decoration: underline; }
span.src {
  font-family: ui-monospace, monospace;
  font-size: 0.85rem;
  color: var(--fg-muted);
}

table {
  width: 100%;
  border-collapse: collapse;
  background: var(--bg-card);
  border: 1px solid var(--border);
  border-radius: 4px;
  overflow: hidden;
  font-size: 0.88rem;
}
table th, table td {
  text-align: left;
  padding: 0.45rem 0.65rem;
  border-bottom: 1px solid var(--border);
  vertical-align: top;
}
table th {
  background: var(--bg-muted);
  font-weight: 600;
  font-size: 0.78rem;
  text-transform: uppercase;
  letter-spacing: 0.04em;
  color: var(--fg-muted);
}
table td.num { text-align: right; font-variant-numeric: tabular-nums; }
table td code { font-size: 0.82rem; }
table tbody tr:last-child td { border-bottom: 0; }
tr.row-error td { background: var(--bad-bg); }
.err-msg {
  margin-top: 0.3rem;
  color: var(--bad);
  font-family: ui-monospace, monospace;
  font-size: 0.78rem;
}
td.intent { color: var(--fg-muted); font-size: 0.82rem; }

details {
  margin: 1rem 0;
  background: var(--bg-card);
  border: 1px solid var(--border);
  border-radius: 6px;
  padding: 0.5rem 1rem;
}
details summary {
  cursor: pointer;
  font-weight: 600;
  color: var(--accent);
  padding: 0.3rem 0;
}
details[open] { padding-bottom: 1rem; }

.plan-rationale { font-size: 0.88rem; margin-top: 0.4rem; }
.muted { color: var(--fg-muted); }

.selector-notes, .additional-searches { margin-top: 1rem; }
.selector-notes p {
  margin: 0.3rem 0 0;
  padding: 0.6rem 0.9rem;
  background: var(--bg-muted);
  border-radius: 4px;
}

.warnings {
  background: var(--warn-bg);
  border: 1px solid var(--warn);
  color: var(--warn);
  padding: 0.75rem 1rem;
  border-radius: 4px;
  margin: 1rem 0;
}
.warnings ul { margin: 0.3rem 0 0; padding-left: 1.5rem; }

footer {
  margin-top: 2rem;
  padding-top: 1rem;
  border-top: 1px solid var(--border);
  color: var(--fg-muted);
  font-size: 0.78rem;
  text-align: center;
}
"""


# ---------------------------------------------------------------------------
# Top-level render
# ---------------------------------------------------------------------------


def render_dual_html(dual: dict[str, Any]) -> str:
    """Render a DualPlanTrimSelectResult JSON dump as a single QC HTML
    showing A1 + A2 ledgers stacked, with a combined summary banner up
    top.

    The JSON shape is the one ``scripts/plan_trim_select_dual_run.py``
    emits: ``{gene, bundle, total_*, a1: {...}, a2: {...}}`` where each
    sub-object matches the single-focus result shape ``render_html``
    expects.
    """

    gene = html.escape(dual.get("gene", "—"))
    uniprot = html.escape(dual.get("uniprot_acc") or "(unresolved)")
    bundle = dual.get("bundle")
    pct = dual.get("pct_anchored")
    pct_kind = (
        "green"
        if pct is not None and pct >= 95.0
        else "red"
        if pct is not None and pct < 80.0
        else "amber"
    )
    pct_text = (
        f"{dual.get('total_anchored', 0)}/{dual.get('total_claims', 0)}"
        f" ({pct:.1f}%)" if pct is not None else "—"
    )
    total_cost = dual.get("total_cost_usd", 0.0)
    a1 = dual.get("a1") or {}
    a2 = dual.get("a2") or {}
    a1_cost = (a1.get("usage") or {}).get("total_cost_usd", 0.0)
    a2_cost = (a2.get("usage") or {}).get("total_cost_usd", 0.0)

    # Shared-source view: which sources did BOTH agents pick from?
    a1_sources = {c.get("source_id") for c in (a1.get("claims") or [])}
    a2_sources = {c.get("source_id") for c in (a2.get("claims") or [])}
    a1_only = a1_sources - a2_sources
    a2_only = a2_sources - a1_sources
    shared = a1_sources & a2_sources

    def _source_chip_row(sids: set, css_kind: str) -> str:
        if not sids:
            return '<em class="muted">none</em>'
        return "".join(
            f'<span class="src-chip src-chip-{css_kind}">{_src_link(sid, bundle=bundle)}</span>'
            for sid in sorted(s for s in sids if s)
        )

    a1_html = "\n".join(
        _render_claim(c, "a1", bundle=bundle) for c in (a1.get("claims") or [])
    ) or '<p class="muted">A1 selected no claims</p>'
    a2_html = "\n".join(
        _render_claim(c, "a2", bundle=bundle) for c in (a2.get("claims") or [])
    ) or '<p class="muted">A2 selected no claims</p>'

    a1_pct = a1.get("pct_anchored")
    a1_pct_text = f"{a1_pct:.0f}%" if a1_pct is not None else "n/a"
    a2_pct = a2.get("pct_anchored")
    a2_pct_text = f"{a2_pct:.0f}%" if a2_pct is not None else "n/a"

    raw_json = html.escape(json.dumps(dual, indent=2))

    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <title>plan-trim-select dual QC · {gene}</title>
  <style>{_CSS}</style>
</head>
<body>
<main>
  <header class="summary">
    <h1>{gene} <span class="uniprot">→ {uniprot}</span> · DUAL (A1 + A2)</h1>
    <div class="summary-row">
      <div class="stat">
        <div class="stat-label">total claims</div>
        <div class="stat-val big">{dual.get("total_claims", 0)}</div>
        <div class="stat-sub">A1: {a1.get("n_claims", 0)} · A2: {a2.get("n_claims", 0)}</div>
      </div>
      <div class="stat">
        <div class="stat-label">anchored</div>
        <div class="stat-val">{_badge(pct_text, pct_kind)}</div>
      </div>
      <div class="stat">
        <div class="stat-label">elapsed</div>
        <div class="stat-val big">{dual.get("elapsed_s", 0):.0f}s</div>
        <div class="stat-sub">
          A1 {a1.get("elapsed_s", 0):.0f}s · A2 {a2.get("elapsed_s", 0):.0f}s
        </div>
      </div>
      <div class="stat">
        <div class="stat-label">spend (info only)</div>
        <div class="stat-val big">${total_cost:.4f}</div>
        <div class="stat-sub">A1 ${a1_cost:.4f} · A2 ${a2_cost:.4f}</div>
      </div>
    </div>
    <div class="sources-row">
      <div class="stat-label">shared sources (both agents cited):</div>
      <div class="src-chips">{_source_chip_row(shared, "shared")}</div>
    </div>
    <div class="sources-row">
      <div class="stat-label">A1-only sources:</div>
      <div class="src-chips">{_source_chip_row(a1_only, "a1")}</div>
    </div>
    <div class="sources-row">
      <div class="stat-label">A2-only sources:</div>
      <div class="src-chips">{_source_chip_row(a2_only, "a2")}</div>
    </div>
  </header>

  <h2>A1 · Surface Evidence ({a1.get("n_claims", 0)} claims, {a1_pct_text} anchored)</h2>
  {a1_html}

  <h2>A2 · Biological Context ({a2.get("n_claims", 0)} claims, {a2_pct_text} anchored)</h2>
  {a2_html}

  <details>
    <summary>A1 iteration trace</summary>
    {_render_iteration_log(a1.get("iteration_log") or [])}
  </details>

  <details>
    <summary>A2 iteration trace</summary>
    {_render_iteration_log(a2.get("iteration_log") or [])}
  </details>

  <details>
    <summary>Raw dual JSON</summary>
    <pre><code>{raw_json}</code></pre>
  </details>

  <footer>
    plan-trim-select dual QC viewer · gene <code>{gene}</code> ·
    sequential A1 then A2, shared HTTP cache
  </footer>
</main>
</body>
</html>
"""


def render_html(result: dict[str, Any]) -> str:
    agent_focus = result.get("agent_focus") or "a1"
    gene = result.get("gene", "?")
    title = f"plan-trim-select QC · {gene} · {agent_focus}"

    bundle = result.get("bundle")
    claims = result.get("claims") or []
    claim_cards = (
        "\n".join(_render_claim(c, agent_focus, bundle=bundle) for c in claims)
        if claims
        else '<p class="muted">no claims selected</p>'
    )

    warnings = result.get("warnings") or []
    warnings_html = ""
    if warnings:
        items = "".join(f"<li>{html.escape(w)}</li>" for w in warnings)
        warnings_html = (
            f'<section class="warnings"><strong>warnings:</strong>'
            f"<ul>{items}</ul></section>"
        )

    raw_json = html.escape(json.dumps(result, indent=2))

    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <title>{html.escape(title)}</title>
  <style>{_CSS}</style>
</head>
<body>
<main>
  {_render_summary(result)}
  {warnings_html}

  <h2>Claims ({len(claims)})</h2>
  {claim_cards}

  <h2>Iteration trace</h2>
  {_render_iteration_log(result.get("iteration_log") or [])}

  <details>
    <summary>Initial search plan ({len((result.get("plan") or {}).get("searches") or [])} requests)</summary>
    {_render_plan(result.get("plan"))}
  </details>

  <details>
    <summary>Full search log ({len(result.get("search_log") or [])} dispatched)</summary>
    {_render_search_log(result.get("search_log") or [])}
  </details>

  <details>
    <summary>Final selector response (notes + last-iteration additional_searches)</summary>
    {_render_selector_followups(result.get("selection_response"))}
  </details>

  <details>
    <summary>Raw result JSON</summary>
    <pre><code>{raw_json}</code></pre>
  </details>

  <footer>
    plan-trim-select QC viewer · generated from
    <code>{html.escape(result.get("gene", "?"))}</code> ·
    focus=<code>{html.escape(str(agent_focus))}</code>
  </footer>
</main>
</body>
</html>
"""


def main(argv: list[str] | None = None) -> int:
    args = sys.argv[1:] if argv is None else argv
    if not args:
        print(
            "usage: python -m accessible_surfaceome.agents.plan_trim_select.render_html "
            "<result.json> [<out.html>]",
            file=sys.stderr,
        )
        return 2
    in_path = Path(args[0])
    if not in_path.exists():
        print(f"input not found: {in_path}", file=sys.stderr)
        return 1
    out_path = Path(args[1]) if len(args) > 1 else in_path.with_suffix(".html")

    result = json.loads(in_path.read_text())
    # Auto-detect dual vs single: dual JSON has ``a1`` + ``a2`` sub-objects.
    if "a1" in result and "a2" in result:
        out_path.write_text(render_dual_html(result))
        print(f"wrote (dual) {out_path}")
    else:
        out_path.write_text(render_html(result))
        print(f"wrote {out_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
