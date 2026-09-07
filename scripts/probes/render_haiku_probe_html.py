"""Render per-source HTML for the Haiku paraphrase-repair probe.

Reads ``.runs/haiku_repair_probe_<gene>.json`` (produced by
``haiku_paraphrase_repair_probe.py``), re-fetches each unique source body
from the Europe PMC cache, and writes one HTML file per source showing:

* the original paraphrase(s) the agent emitted
* the verbatim text Haiku returned as a repair
* the full source body with the Haiku-picked span highlighted in context
* for non-anchored repairs, the longest prefix that DID match (highlighted
  in yellow) + a red marker where the divergence begins, so you can see
  visually where the model went off the source

Output: one HTML per source under ``.runs/haiku_repair_probe_<gene>_html/``
plus an ``index.html`` linking them.

Usage:

    uv run python scripts/render_haiku_probe_html.py GPR75
    open .runs/haiku_repair_probe_GPR75_html/index.html
"""

from __future__ import annotations

import argparse
import html
import json
import logging
import sys
from collections import defaultdict
from pathlib import Path

from accessible_surfaceome.env import load_env
from accessible_surfaceome.tools._shared.europepmc import (
    europepmc_search,
    fetch_fulltext,
    paper_from_europepmc,
)
from accessible_surfaceome.tools._shared.http import open_default_client
from accessible_surfaceome.tools._shared.normalize import (
    normalize_for_quote_matching,
)
from accessible_surfaceome.tools._shared.retraction_watch import (
    empty as _empty_retraction_index,
)


logger = logging.getLogger(__name__)


CSS = """
:root {
  --bg: #fafafa;
  --fg: #222;
  --muted: #777;
  --card: #fff;
  --border: #e2e2e2;
  --paraphrase-bg: #f0f0f0;
  --paraphrase-fg: #555;
  --repair-ok-bg: #e8f5e9;
  --repair-ok-bd: #66bb6a;
  --repair-fail-bg: #fde8e6;
  --repair-fail-bd: #ef5350;
  --highlight-bg: #fff3a3;
  --highlight-partial-bg: #fff3a3;
  --divergence-marker: #d32f2f;
}
body {
  background: var(--bg);
  color: var(--fg);
  font: 15px/1.55 -apple-system, BlinkMacSystemFont, system-ui, sans-serif;
  margin: 0;
  padding: 24px;
  max-width: 1100px;
  margin-inline: auto;
}
h1 {
  font-size: 22px;
  margin: 0 0 6px;
}
.meta {
  color: var(--muted);
  font-size: 13px;
  margin-bottom: 24px;
}
.meta a { color: #1565c0; text-decoration: none; }
.meta a:hover { text-decoration: underline; }
.row {
  background: var(--card);
  border: 1px solid var(--border);
  border-radius: 6px;
  padding: 14px 18px;
  margin-bottom: 18px;
}
.row h3 {
  margin: 0 0 10px;
  font-size: 15px;
  font-weight: 600;
}
.badge {
  display: inline-block;
  font-size: 11px;
  font-weight: 600;
  padding: 2px 7px;
  border-radius: 3px;
  margin-left: 8px;
  vertical-align: middle;
  letter-spacing: 0.04em;
  text-transform: uppercase;
}
.badge-ok { background: var(--repair-ok-bd); color: white; }
.badge-fail { background: var(--repair-fail-bd); color: white; }
.label {
  display: inline-block;
  font-size: 11px;
  font-weight: 600;
  text-transform: uppercase;
  letter-spacing: 0.05em;
  color: var(--muted);
  margin-top: 8px;
  margin-bottom: 4px;
}
.paraphrase {
  background: var(--paraphrase-bg);
  color: var(--paraphrase-fg);
  border-left: 3px solid #bbb;
  padding: 8px 12px;
  font-style: italic;
  white-space: pre-wrap;
}
.repair {
  border-radius: 4px;
  padding: 8px 12px;
  border-left-style: solid;
  border-left-width: 3px;
  white-space: pre-wrap;
}
.repair-ok {
  background: var(--repair-ok-bg);
  border-left-color: var(--repair-ok-bd);
}
.repair-fail {
  background: var(--repair-fail-bg);
  border-left-color: var(--repair-fail-bd);
}
.stats {
  font-size: 12px;
  color: var(--muted);
  margin-top: 6px;
}
.body-block {
  background: var(--card);
  border: 1px solid var(--border);
  border-radius: 6px;
  padding: 18px;
  margin-top: 24px;
  white-space: pre-wrap;
  font: 13.5px/1.6 ui-monospace, "SF Mono", Menlo, monospace;
  word-break: break-word;
  max-height: 70vh;
  overflow-y: auto;
}
.body-block h2 {
  font: 600 15px/1 -apple-system, BlinkMacSystemFont, system-ui, sans-serif;
  color: var(--muted);
  margin: 0 0 12px;
  text-transform: uppercase;
  letter-spacing: 0.06em;
}
mark {
  background: var(--highlight-bg);
  padding: 1px 0;
  border-radius: 2px;
}
mark.partial {
  background: var(--highlight-partial-bg);
  position: relative;
}
.divergence-marker {
  display: inline-block;
  color: var(--divergence-marker);
  font-weight: 700;
  background: #ffebee;
  border-radius: 2px;
  padding: 0 4px;
  margin: 0 2px;
  font-family: ui-monospace, monospace;
  font-size: 0.9em;
}
.legend {
  font-size: 12px;
  color: var(--muted);
  margin-bottom: 16px;
}
.legend .swatch {
  display: inline-block;
  width: 12px;
  height: 12px;
  vertical-align: middle;
  margin-right: 4px;
  border-radius: 2px;
}
hr {
  border: none;
  border-top: 1px solid var(--border);
  margin: 12px 0;
}
ul.index { padding-left: 18px; }
ul.index li { margin-bottom: 6px; }
"""


def _clean_title(raw: str) -> str:
    """EuropePMC titles arrive pre-escaped (``&lt;i&gt;GPR75&lt;/i&gt;``).
    Decode once so the markup either renders or, more often, just strips
    cleanly when re-escaped for HTML output."""
    decoded = html.unescape(raw)
    # Strip simple JATS-style inline markup (we re-escape for HTML output
    # so leaving raw tags would just display them literally).
    import re as _re
    return _re.sub(r"<[^>]+>", "", decoded).strip()


def _strip_source_prefix(source_id: str) -> tuple[str, str]:
    if ":" not in source_id:
        return "", source_id
    prefix, bare = source_id.split(":", 1)
    return prefix, bare


def _fetch_source(source_id: str, http) -> tuple[str, str, str | None]:
    """Return (title, body, external_url) for a source.

    Body is title + abstract + (sections joined by \n\n) for PMC.
    For PMID-only sources, body is title + abstract.
    """
    prefix, bare = _strip_source_prefix(source_id)
    retraction = _empty_retraction_index()
    if prefix == "PMC":
        paper = fetch_fulltext(http=http, pmcid=bare, retraction_index=retraction)
        parts = []
        if paper.abstract:
            parts.append(paper.abstract)
        parts.extend(s.text for s in paper.sections)
        return (
            _clean_title(paper.title or "(no title)"),
            "\n\n".join(p for p in parts if p),
            f"https://europepmc.org/article/PMC/{bare}",
        )
    if prefix == "PMID":
        payload = europepmc_search(
            http=http, query=f"EXT_ID:{bare} AND SRC:MED", page_size=1
        )
        hits = (payload.get("resultList") or {}).get("result") or []
        if not hits:
            raise LookupError(f"PMID:{bare} not found in Europe PMC")
        paper = paper_from_europepmc(hits[0], retraction_index=retraction)
        return (
            _clean_title(paper.title or "(no title)"),
            paper.abstract or "",
            f"https://europepmc.org/article/MED/{bare}",
        )
    raise ValueError(f"unrecognized source_id: {source_id!r}")


def _longest_prefix_in(text: str, body: str) -> int:
    """Length of the longest prefix of ``text`` (after the orchestrator's
    quote-normalizer) that is a substring of the normalized ``body``.

    Returns 0 if no prefix matches; ``len(text)`` if the whole text matches.
    """

    n_text = normalize_for_quote_matching(text)
    n_body = normalize_for_quote_matching(body)
    if not n_text or not n_body:
        return 0
    # Bisect on the prefix length, against the normalized forms — that's
    # what the orchestrator uses at promotion.
    lo, hi = 0, len(n_text)
    while lo + 1 < hi:
        mid = (lo + hi) // 2
        if n_text[:mid] in n_body:
            lo = mid
        else:
            hi = mid
    return lo if n_text[:lo] in n_body else 0


def _find_in_raw_body(
    repair_text: str, body: str, prefix_len_normalized: int
) -> tuple[int, int] | None:
    """Locate the Haiku-repair span in the *raw* body (so we can highlight
    in HTML preserving the original characters).

    Walks tokens of the repair forward through the body, returns (start, end)
    of the longest contiguous match found. ``prefix_len_normalized`` bounds
    how many characters into ``repair_text`` we try to follow (so for non-
    anchored rows we only highlight the matched prefix, not the divergent
    suffix).

    Strategy: take the first 60 chars of repair, find that exact text in
    body; then extend matching forward as long as both sides agree
    character-for-character (ignoring whitespace differences). Light,
    deterministic, no NLP.
    """

    candidate = repair_text[: max(60, prefix_len_normalized // 2)]
    head = candidate.strip()
    if not head:
        return None
    # First try an exact substring match on the raw body for the head.
    start = body.find(head[:60])
    if start < 0:
        # Try a slightly broader window for the anchor — strip leading
        # whitespace and special characters.
        head_clean = head.lstrip(" \n\r\t-—\"'(")[:60]
        if not head_clean:
            return None
        start = body.find(head_clean)
        if start < 0:
            return None
    # Extend forward through the body matching the rest of the repair
    # character by character, tolerating whitespace differences.
    bi = start + len(head[:60].rstrip())  # body cursor
    ri = len(head[:60].rstrip())  # repair cursor
    last_good_bi = bi
    while ri < len(repair_text) and bi < len(body):
        rc, bc = repair_text[ri], body[bi]
        if rc == bc:
            bi += 1
            ri += 1
            last_good_bi = bi
            continue
        # Tolerate whitespace differences: skip whitespace on either side.
        if rc.isspace() and bc.isspace():
            bi += 1
            ri += 1
            last_good_bi = bi
            continue
        if rc.isspace():
            ri += 1
            continue
        if bc.isspace():
            bi += 1
            continue
        break  # genuine divergence
    return (start, last_good_bi)


def _render_body_with_highlights(
    body: str, spans: list[tuple[int, int, bool]]
) -> str:
    """Render ``body`` with HTML escaping, wrapping each (start, end, is_full)
    span in a <mark> tag (with class ``partial`` when is_full is False).

    Inserts a small red divergence marker at the end of any partial span.
    Spans should be non-overlapping; if they overlap, later spans win.
    """

    if not spans:
        return html.escape(body)
    # Sort by start, drop overlaps (keep first).
    spans = sorted(spans, key=lambda s: s[0])
    cleaned: list[tuple[int, int, bool]] = []
    last_end = -1
    for s in spans:
        if s[0] >= last_end:
            cleaned.append(s)
            last_end = s[1]
    out: list[str] = []
    cursor = 0
    for start, end, is_full in cleaned:
        if start < cursor:
            continue
        out.append(html.escape(body[cursor:start]))
        cls = "mark" if is_full else "mark partial"
        out.append(f'<mark class="{cls}">')
        out.append(html.escape(body[start:end]))
        out.append("</mark>")
        if not is_full:
            out.append(
                '<span class="divergence-marker" title="Haiku reply diverges from source past this point">↯ DIVERGES HERE</span>'
            )
        cursor = end
    out.append(html.escape(body[cursor:]))
    return "".join(out)


def _build_source_html(
    *,
    source_id: str,
    title: str,
    external_url: str | None,
    body: str,
    rows: list[dict],
) -> str:
    """Build one HTML page for a single source.

    ``rows`` are the probe rows that cite this source.
    """

    spans: list[tuple[int, int, bool]] = []
    row_html: list[str] = []
    for r in rows:
        repair = r["haiku_repair"]
        anchored = bool(r["anchored"])
        prefix_len = (
            len(normalize_for_quote_matching(repair))
            if anchored
            else _longest_prefix_in(repair, body)
        )
        span = _find_in_raw_body(repair, body, prefix_len)
        if span is not None and span[1] - span[0] > 20:
            spans.append((span[0], span[1], anchored))

        badge = (
            '<span class="badge badge-ok">anchored ✓</span>'
            if anchored
            else '<span class="badge badge-fail">diverged ✗</span>'
        )
        repair_cls = "repair repair-ok" if anchored else "repair repair-fail"
        prefix_note = (
            ""
            if anchored
            else f' (matches first {prefix_len} chars of {len(normalize_for_quote_matching(repair))} after normalization)'
        )
        row_html.append(
            f"""
<div class="row">
  <h3>{html.escape(r['evidence_id'])} {badge}</h3>
  <div class="label">Paraphrase emitted by the agent ({len(r['paraphrase'])} chars)</div>
  <div class="paraphrase">{html.escape(r['paraphrase'])}</div>
  <div class="label">Haiku repair ({len(repair)} chars{prefix_note})</div>
  <div class="{repair_cls}">{html.escape(repair)}</div>
  <div class="stats">cost ${r['cost_usd']:.4f} · latency {r['latency_s']:.1f}s · body length {r['body_len']:,} chars</div>
</div>"""
        )

    body_html = _render_body_with_highlights(body, spans)
    external_link = (
        f'· <a href="{external_url}" target="_blank">open on Europe PMC →</a>'
        if external_url
        else ""
    )
    return f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<title>{html.escape(source_id)} — Haiku probe</title>
<style>{CSS}</style>
</head>
<body>
<h1>{html.escape(source_id)}</h1>
<div class="meta">{html.escape(title)} {external_link}</div>
<div class="legend">
  <span class="swatch" style="background:#fff3a3"></span>matched verbatim span ·
  <span class="swatch" style="background:#fde8e6;border:1px solid #ef5350"></span>repair diverged from source ·
  <span class="divergence-marker">↯ DIVERGES HERE</span>
</div>
{''.join(row_html)}
<div class="body-block">
<h2>Source body ({len(body):,} chars)</h2>
{body_html}
</div>
</body>
</html>"""


def _build_index_html(gene: str, sources: list[dict]) -> str:
    rows = "\n".join(
        f'  <li><a href="{html.escape(s["filename"])}">{html.escape(s["source_id"])}</a> '
        f'<span style="color:#777;font-size:13px">— {html.escape(s["title"][:120])} '
        f'({s["n_rows"]} repair attempt{"s" if s["n_rows"] != 1 else ""}, '
        f'{s["n_anchored"]}/{s["n_rows"]} anchored)</span></li>'
        for s in sources
    )
    return f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<title>{html.escape(gene)} — Haiku probe index</title>
<style>{CSS}</style>
</head>
<body>
<h1>{html.escape(gene)} — Haiku paraphrase-repair probe</h1>
<div class="meta">One page per unique source cited in the unanchored rows. Each page shows the agent's paraphrase, Haiku's verbatim repair, and the source body with the matched span highlighted in place.</div>
<ul class="index">
{rows}
</ul>
</body>
</html>"""


def main(argv: list[str] | None = None) -> int:
    load_env()
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s — %(message)s",
    )
    parser = argparse.ArgumentParser()
    parser.add_argument("gene", help="Gene symbol (matches .runs/haiku_repair_probe_<GENE>.json)")
    args = parser.parse_args(argv)

    probe_path = Path(f".runs/haiku_repair_probe_{args.gene}.json")
    if not probe_path.exists():
        print(f"no probe data at {probe_path}", file=sys.stderr)
        return 1
    data = json.loads(probe_path.read_text())
    rows = data.get("rows", [])
    if not rows:
        print("probe JSON has no rows", file=sys.stderr)
        return 1

    out_dir = Path(f".runs/haiku_repair_probe_{args.gene}_html")
    out_dir.mkdir(parents=True, exist_ok=True)

    # Group by source_id (one HTML per source, even if cited by multiple rows).
    by_source: dict[str, list[dict]] = defaultdict(list)
    for r in rows:
        sid = r.get("source_id") or "UNKNOWN"
        by_source[sid].append(r)

    http = open_default_client()
    index_entries: list[dict] = []
    try:
        for source_id, source_rows in sorted(by_source.items()):
            print(f"rendering {source_id} ({len(source_rows)} row(s))")
            try:
                title, body, url = _fetch_source(source_id, http)
            except Exception as exc:  # noqa: BLE001 — render-level robustness
                print(f"  FETCH FAILED: {type(exc).__name__}: {exc}")
                continue
            html_text = _build_source_html(
                source_id=source_id,
                title=title,
                external_url=url,
                body=body,
                rows=source_rows,
            )
            filename = source_id.replace(":", "_") + ".html"
            (out_dir / filename).write_text(html_text)
            index_entries.append(
                {
                    "source_id": source_id,
                    "title": title,
                    "filename": filename,
                    "n_rows": len(source_rows),
                    "n_anchored": sum(1 for r in source_rows if r["anchored"]),
                }
            )
    finally:
        http.close()

    (out_dir / "index.html").write_text(_build_index_html(args.gene, index_entries))
    print(f"\nwrote {len(index_entries)} source page(s) → {out_dir}")
    print(f"open {out_dir / 'index.html'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
