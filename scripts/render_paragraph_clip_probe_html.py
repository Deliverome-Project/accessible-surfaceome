"""Render per-paper HTML for the paragraph clip + Haiku keep/drop probe.

Reads ``.runs/paragraph_clip_probe_<gene>.json`` (from
``paragraph_clip_probe.py``) and writes one HTML per source showing every
clip color-coded by keep/drop, with the Haiku-provided reason inline.

The goal is a fast visual scan for "did Haiku keep the right paragraphs?"
— green border = kept, red border = dropped, target-mention badge in the
header. Each clip's section + length + id are visible at a glance.

Usage:

    uv run python scripts/render_paragraph_clip_probe_html.py GPR75
    open .runs/paragraph_clip_probe_GPR75_html/index.html
"""

from __future__ import annotations

import argparse
import html
import json
import sys
from pathlib import Path


CSS = """
:root {
  --bg: #fafafa;
  --fg: #222;
  --muted: #777;
  --card: #fff;
  --border: #e2e2e2;
  --keep-bg: #e8f5e9;
  --keep-bd: #66bb6a;
  --drop-bg: #f5f5f5;
  --drop-bd: #cfcfcf;
  --target-bd: #1565c0;
}
body {
  background: var(--bg);
  color: var(--fg);
  font: 15px/1.55 -apple-system, BlinkMacSystemFont, system-ui, sans-serif;
  margin: 0; padding: 24px;
  max-width: 1150px; margin-inline: auto;
}
h1 { font-size: 22px; margin: 0 0 6px; }
.meta { color: var(--muted); font-size: 13px; margin-bottom: 18px; }
.meta a { color: #1565c0; text-decoration: none; }
.legend { font-size: 12px; color: var(--muted); margin-bottom: 18px; }
.swatch { display: inline-block; width: 12px; height: 12px; vertical-align: middle; margin-right: 4px; border-radius: 2px; border: 1px solid; }
.section-bar {
  display: flex; gap: 6px; flex-wrap: wrap;
  font-size: 12px;
  margin-bottom: 18px;
  color: var(--muted);
}
.section-stat {
  background: var(--card); border: 1px solid var(--border); border-radius: 4px;
  padding: 4px 10px;
}
.clip {
  background: var(--card);
  border: 1px solid var(--border);
  border-left: 4px solid var(--drop-bd);
  border-radius: 4px;
  padding: 10px 14px;
  margin-bottom: 12px;
  white-space: pre-wrap;
  position: relative;
}
.clip.keep { border-left-color: var(--keep-bd); background: var(--keep-bg); }
.clip.target { box-shadow: inset 3px 0 0 var(--target-bd); }
.clip-head {
  font: 600 12px/1.4 ui-monospace, "SF Mono", Menlo, monospace;
  color: var(--muted);
  margin-bottom: 6px;
  display: flex; gap: 10px; align-items: center; flex-wrap: wrap;
}
.badge {
  display: inline-block;
  font-size: 10px;
  font-weight: 700;
  padding: 1px 6px;
  border-radius: 3px;
  letter-spacing: 0.05em;
  text-transform: uppercase;
}
.badge-keep { background: var(--keep-bd); color: white; }
.badge-drop { background: #ababab; color: white; }
.badge-target { background: var(--target-bd); color: white; }
.badge-section { background: #ede7f6; color: #4527a0; }
.reason {
  font-size: 12px;
  color: #2e7d32;
  font-style: italic;
  margin-top: 6px;
  border-top: 1px dashed #c5e1a5;
  padding-top: 6px;
}
.clip-body {
  font: 13.5px/1.55 -apple-system, BlinkMacSystemFont, system-ui, sans-serif;
  color: var(--fg);
}
ul.index { padding-left: 18px; }
ul.index li { margin-bottom: 6px; }
"""


def _build_paper_html(gene: str, paper: dict) -> str:
    clips: list[dict] = paper["clips"]
    decisions = paper.get("haiku_decisions") or {}
    keep_list = decisions.get("keep") or []
    keep_map: dict[str, str] = {}
    for entry in keep_list:
        if isinstance(entry, dict):
            cid = entry.get("clip_id")
            reason = entry.get("reason", "")
            if cid:
                keep_map[cid] = reason
        elif isinstance(entry, str):
            keep_map[entry] = ""

    n_kept = sum(1 for c in clips if c["clip_id"] in keep_map)
    n_target = sum(1 for c in clips if c["has_target_mention"])

    section_counts: dict[str, list[int]] = {}
    for c in clips:
        bucket = section_counts.setdefault(c["section"], [0, 0])
        bucket[0] += 1
        if c["clip_id"] in keep_map:
            bucket[1] += 1
    section_bar_html = "".join(
        f'<span class="section-stat">{html.escape(name)}: <b>{kept}</b>/{total} kept</span>'
        for name, (total, kept) in section_counts.items()
    )

    clip_html: list[str] = []
    for c in clips:
        cid = c["clip_id"]
        is_keep = cid in keep_map
        target_cls = " target" if c["has_target_mention"] else ""
        keep_cls = " keep" if is_keep else ""
        badge = (
            '<span class="badge badge-keep">keep</span>'
            if is_keep
            else '<span class="badge badge-drop">drop</span>'
        )
        target_badge = (
            '<span class="badge badge-target">target</span>'
            if c["has_target_mention"]
            else ""
        )
        reason_html = (
            f'<div class="reason">↳ {html.escape(keep_map[cid])}</div>'
            if is_keep and keep_map[cid]
            else ""
        )
        clip_html.append(
            f"""<div class="clip{keep_cls}{target_cls}">
  <div class="clip-head">
    <span>{html.escape(cid)}</span>
    <span class="badge badge-section">{html.escape(c['section'])}</span>
    {badge}
    {target_badge}
    <span style="margin-left:auto">{c['char_len']} chars</span>
  </div>
  <div class="clip-body">{html.escape(c['text'])}</div>
  {reason_html}
</div>"""
        )

    pmcid = paper["source_id"].split(":", 1)[-1]
    external = f"https://europepmc.org/article/PMC/{pmcid}"
    return f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<title>{html.escape(paper['source_id'])} — paragraph clip probe</title>
<style>{CSS}</style>
</head>
<body>
<h1>{html.escape(paper['source_id'])}</h1>
<div class="meta">{html.escape(paper.get('title','(no title)'))} · <a href="{external}" target="_blank">open on Europe PMC →</a></div>
<div class="meta">
  <b>{len(clips)}</b> paragraph clips · <b>{n_kept}</b> kept by Haiku ({100*n_kept/max(1,len(clips)):.0f}%) ·
  <b>{n_target}</b> mention {html.escape(gene)} ({100*n_target/max(1,len(clips)):.0f}%) ·
  Haiku cost ${paper.get('haiku_cost_usd', 0):.4f}, latency {paper.get('haiku_latency_s', 0):.1f}s
</div>
<div class="section-bar">{section_bar_html}</div>
<div class="legend">
  <span class="swatch" style="background:var(--keep-bg);border-color:var(--keep-bd)"></span>kept by Haiku ·
  <span class="swatch" style="background:var(--drop-bg);border-color:var(--drop-bd)"></span>dropped ·
  <span class="swatch" style="background:white;border-color:var(--target-bd);box-shadow:inset 3px 0 0 var(--target-bd)"></span>contains a {html.escape(gene)} mention
</div>
{''.join(clip_html)}
</body>
</html>"""


def _build_index_html(gene: str, papers: list[dict]) -> str:
    rows = "\n".join(
        f'  <li><a href="{html.escape(p["filename"])}">{html.escape(p["source_id"])}</a> '
        f'<span style="color:#777;font-size:13px">— {html.escape(p["title"][:120])} '
        f'({p["n_kept"]}/{p["n_clips"]} kept, ${p.get("cost",0):.4f})</span></li>'
        for p in papers
    )
    total_clips = sum(p["n_clips"] for p in papers)
    total_kept = sum(p["n_kept"] for p in papers)
    total_cost = sum(p.get("cost", 0) for p in papers)
    return f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<title>{html.escape(gene)} — paragraph clip probe</title>
<style>{CSS}</style>
</head>
<body>
<h1>{html.escape(gene)} — paragraph clip + Haiku keep/drop probe</h1>
<div class="meta">Per-paper breakdown of paragraph extraction + Haiku's keep/drop call under the clip-and-judge design.</div>
<div class="meta">
  <b>{len(papers)}</b> papers · <b>{total_clips}</b> total clips ·
  <b>{total_kept}</b> kept ({100*total_kept/max(1,total_clips):.0f}%) ·
  total Haiku cost <b>${total_cost:.4f}</b>
</div>
<ul class="index">
{rows}
</ul>
</body>
</html>"""


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("gene")
    args = parser.parse_args(argv)
    probe_path = Path(f".runs/paragraph_clip_probe_{args.gene}.json")
    if not probe_path.exists():
        print(f"no probe data at {probe_path}", file=sys.stderr)
        return 1
    data = json.loads(probe_path.read_text())

    out_dir = Path(f".runs/paragraph_clip_probe_{args.gene}_html")
    out_dir.mkdir(parents=True, exist_ok=True)

    index_entries: list[dict] = []
    for paper in data.get("papers", []):
        filename = paper["source_id"].replace(":", "_") + ".html"
        (out_dir / filename).write_text(_build_paper_html(args.gene, paper))
        index_entries.append(
            {
                "source_id": paper["source_id"],
                "title": paper.get("title", ""),
                "filename": filename,
                "n_clips": paper["n_clips"],
                "n_kept": len((paper.get("haiku_decisions") or {}).get("keep") or []),
                "cost": paper.get("haiku_cost_usd", 0),
            }
        )

    (out_dir / "index.html").write_text(_build_index_html(args.gene, index_entries))
    print(f"wrote {len(index_entries)} paper page(s) → {out_dir}")
    print(f"open {out_dir / 'index.html'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
