#!/usr/bin/env python3
"""Review HTML: full prompt md shown always, with the diff vs main highlighted inline."""
from __future__ import annotations
import html
import re
import subprocess
import typing
from pathlib import Path

from accessible_surfaceome.agents.plan_trim_select.kickoff_templates import (
    build_a1_kickoff, build_a2_kickoff,
)
from accessible_surfaceome.tools._shared import models as _models
from accessible_surfaceome.tools.gene_literature import _TOPIC_TERMS

NEW_ANCHORS = {"tox_normal_tissue", "surface_reachability",
               "partner_dependency", "membrane_subdomain"}
GATED = {"surface_reachability", "partner_dependency", "membrane_subdomain"}


def render_kickoff(label, sub, plan):
    cats = [s.category for s in plan.searches if s.tool == "evidence_retrieval"]
    modes = [s.mode for s in plan.searches
             if s.tool == "gene_literature" and s.mode in ("gene2pubmed", "recent_corpus")]
    topics = [s for s in plan.searches
              if s.tool == "gene_literature" and s.mode == "topic_search"]
    catrow = "".join(f'<span class="catchip">{html.escape(c)}</span>' for c in cats)
    moderow = "".join(f'<span class="catchip mode">{html.escape(m)}</span>' for m in modes)
    rows = []
    for s in topics:
        anc = s.anchors or []
        badge = ""
        for a in anc:
            if a in NEW_ANCHORS:
                badge += f'<span class="b new">new{"·gated" if a in GATED else ""}</span>'
        terms = sorted({t for a in anc for t in _TOPIC_TERMS.get(a, [])})
        rows.append(
            f'<div class="trow"><div class="tanc"><code>{" + ".join(anc)}</code>{badge}</div>'
            f'<div class="tterms">{", ".join(html.escape(t) for t in terms)}</div></div>'
        )
    return f"""<div class="kcol">
      <h3>{label} <span class="kn">{len(plan.searches)} searches · {sub}</span></h3>
      <div class="ksub">evidence_retrieval — methodology categories</div>
      <div class="catrow">{catrow}{moderow}</div>
      <div class="ksub">gene_literature — topic_search keyword groups</div>
      {''.join(rows)}
    </div>"""


def kickoff_section():
    a1 = render_kickoff("A1", "surface evidence", build_a1_kickoff(1, 600))
    a2 = render_kickoff("A2", "biological context", build_a2_kickoff(1, 600))
    return f"""<section class="kick">
      <h2>Retrieval — search terms feeding each agent</h2>
      <p class="sub2">Deterministic kickoff (no LLM planner). <span class="b new">new</span> = added in this PR;
      <code>·gated</code> = emitted only for membrane+ECD (or unknown) topology. The <code>flow_cytometry</code>
      category query also gained host-agnostic OE terms (<i>transfected / ectopic / heterologous / overexpressing /
      stably&nbsp;expressing</i>, no "wild-type"), and <code>shedding</code> gained serum/plasma/circulating terms.</p>
      <div class="kgrid">{a1}{a2}</div>
    </section>"""


# ---- Closed-enum reference -------------------------------------------------
# The structured-output options the model must choose from, introspected live
# from models.py so the review never drifts from the shipped schema. Each
# (EnumName, json-path) is rendered as a chip row; the masking mechanism gets
# the homo / hetero / other axis annotated.
ENUM_GROUPS = [
    ("Accessibility risks", [
        ("EpitopeMaskingMechanism", "epitope_masking.mechanism[]"),
        ("EpitopeMaskingSeverity", "epitope_masking.severity"),
        ("CoreceptorDependency", "co_receptor_requirements.surface_expression_dependency"),
        ("CoreceptorEvidenceBasis", "co_receptor_requirements.evidence_basis"),
        ("SecretedFormSource", "secreted_form.source"),
        ("ECDAccessibilityClass", "ecd_size_assessment.ecd_accessibility_class"),
        ("RestrictedSubdomainName", "restricted_subdomain.domain"),
        ("RiskSeverity", "shed/secreted/restricted severity"),
        ("EvidenceStrength", "every risk · evidence_strength"),
    ]),
    ("Executive summary", [
        ("HeadlineRisk", "executive_summary.headline_risks[]"),
    ]),
]

# homo / hetero / other axis for the masking mechanism options.
MASK_AXIS = {
    "oligomerization": ("homo", "the protein's OWN homodimer / homo-oligomer interface buries the epitope"),
    "partner": ("hetero", "a DIFFERENT protein in a complex covers the epitope"),
    "glycan": ("other", "glycocalyx / glycan shielding"),
    "conformational": ("other", "monomer closed/open occlusion"),
    "cleaved": ("other", "proteolytic removal of the epitope"),
    "none": ("", "no masking documented"),
}


def enum_chip(enum_name: str, val: str) -> str:
    if enum_name == "EpitopeMaskingMechanism":
        axis, desc = MASK_AXIS.get(val, ("", ""))
        if axis:
            return (f'<span class="evchip ev-{axis}" title="{html.escape(axis.upper())} — {html.escape(desc)}">'
                    f'{html.escape(val)}<span class="evaxis">{html.escape(axis)}</span></span>')
    return f'<span class="evchip">{html.escape(val)}</span>'


def enum_section() -> str:
    groups = []
    for title, entries in ENUM_GROUPS:
        rows = []
        for enum_name, field in entries:
            obj = getattr(_models, enum_name, None)
            if obj is None:
                continue
            chips = "".join(enum_chip(enum_name, v) for v in typing.get_args(obj))
            rows.append(
                f'<div class="evrow"><div class="evmeta"><code>{html.escape(field)}</code>'
                f'<span class="evname">{html.escape(enum_name)}</span></div>'
                f'<div class="evchips">{chips}</div></div>'
            )
        groups.append(f'<div class="evgroup"><h3>{html.escape(title)}</h3>{"".join(rows)}</div>')
    return f"""<section class="enums">
      <h2>Closed enums — the options the model must choose from</h2>
      <p class="sub2">Introspected live from <code>models.py</code> (the structured-output schema), so this
      never drifts from what ships. For <code>epitope_masking.mechanism</code> the
      <span class="evaxis ax-homo">homo</span> / <span class="evaxis ax-hetero">hetero</span> axis is annotated
      (everything else is monomer-level / other).</p>
      {''.join(groups)}
    </section>"""


REPO = Path(
    subprocess.run(["git", "rev-parse", "--show-toplevel"],
                   capture_output=True, text=True).stdout.strip() or "."
)
# Diff base = where this branch forked from main (PR base). Falls back to main.
BASE = (
    subprocess.run(["git", "merge-base", "origin/main", "HEAD"],
                   cwd=REPO, capture_output=True, text=True).stdout.strip()
    or "main"
)
HEAD = "HEAD"
GLOB = "src/accessible_surfaceome/agents/**/prompts/*.md"
HUNK = re.compile(r"@@ -\d+(?:,\d+)? \+(\d+)")
SKIP = ("diff --git", "index ", "--- ", "+++ ", "new file", "deleted file", "similarity", "rename ")


def git(*a: str) -> str:
    return subprocess.run(["git", *a], cwd=REPO, capture_output=True, text=True).stdout


# Wholesale-removed deprecated v1 Managed-Agent prompts — excluded so the
# review stays focused on the live v2 deep-dive prompts the colleague works on.
EXCLUDE = ("biology_compiler/", "surface_evidence_compiler/")


def changed():
    out = git("diff", "--name-status", f"{BASE}...{HEAD}", "--", GLOB).strip()
    rows = [(ln.split("\t")[0], ln.split("\t")[-1]) for ln in out.splitlines()]
    return [(st, p) for st, p in rows if not any(x in p for x in EXCLUDE)]


def full_diff(path: str) -> str:
    # -U100000 → whole file as one hunk: every line is context, changes inline.
    return git("diff", "--no-color", "-U100000", BASE, HEAD, "--", path)


def counts(diff: str):
    a = sum(1 for ln in diff.splitlines() if ln.startswith("+") and not ln.startswith("+++"))
    r = sum(1 for ln in diff.splitlines() if ln.startswith("-") and not ln.startswith("---"))
    return a, r


def render(diff: str) -> str:
    rows, newno = [], 0
    for ln in diff.splitlines():
        if ln.startswith(SKIP):
            continue
        m = HUNK.match(ln)
        if m:
            newno = int(m.group(1))
            continue  # hide hunk header — full file is shown
        if ln.startswith("+"):
            cls, num, txt = "add", str(newno), ln[1:]
            newno += 1
        elif ln.startswith("-"):
            cls, num, txt = "del", "−", ln[1:]
        else:
            cls, num, txt = "ctx", str(newno), (ln[1:] if ln.startswith(" ") else ln)
            newno += 1
        rows.append(
            f'<div class="ln {cls}"><span class="num">{num}</span>'
            f'<span class="tx">{html.escape(txt) or "&nbsp;"}</span></div>'
        )
    return "".join(rows)


BADGE = {"M": ("modified", "mod"), "A": ("new", "new"), "D": ("deleted", "del")}


def main():
    files = changed()
    nm = sum(s == "M" for s, _ in files)
    nn = sum(s == "A" for s, _ in files)
    nd = sum(s == "D" for s, _ in files)
    nav, secs = [], []
    for i, (st, path) in enumerate(files):
        label, badge = BADGE[st]
        name = path.split("/prompts/")[-1]
        grp = ("synthesizer" if "surfaceome_synthesizer" in path
               else "plan_trim_select" if "plan_trim_select" in path else "v2 builders")
        d = full_diff(path)
        a, r = counts(d)
        nav.append(
            f'<a class="navitem" href="#f{i}"><span class="b {badge}">{label}</span>'
            f'<span class="nm">{html.escape(name)}</span><span class="grp">{grp}</span>'
            f'<span class="cnt"><span class="plus">+{a}</span> <span class="minus">−{r}</span></span></a>'
        )
        note = " · deleted prompt (shown struck-through)" if st == "D" else (
            " · new prompt (all lines added)" if st == "A" else "")
        secs.append(f"""
        <section class="card" id="f{i}">
          <div class="card-h"><span class="b {badge}">{label}</span>
            <code class="path">{html.escape(path)}</code>
            <span class="cnt"><span class="plus">+{a}</span> <span class="minus">−{r}</span></span></div>
          <div class="meta">Full prompt below; <span class="k add">added</span> /
            <span class="k del">removed</span> lines highlighted inline{note}.</div>
          <div class="doc">{render(d)}</div>
        </section>""")

    out = f"""<!doctype html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Deep-dive prompt review — PR #54</title><style>
:root{{--bg:#0f1115;--panel:#171a21;--line:#262b36;--ink:#dfe4ee;--mut:#7e8696;
--add:#16361f;--addbar:#2ea043;--del:#3a1c20;--delbar:#f85149;--acc:#6aa3ff;--gut:#11141a;}}
*{{box-sizing:border-box}}body{{margin:0;background:var(--bg);color:var(--ink);
font:14px/1.5 -apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,sans-serif}}
.wrap{{max-width:1080px;margin:0 auto;padding:24px}}
h1{{font-size:22px;margin:0 0 4px}}.sub{{color:var(--mut);margin:0 0 18px}}
.chips{{display:flex;gap:8px;flex-wrap:wrap;margin:0 0 22px}}
.chip{{background:var(--panel);border:1px solid var(--line);border-radius:20px;padding:4px 12px;font-size:12px;color:var(--mut)}}
.chip b{{color:var(--ink)}}
.nav{{display:grid;gap:6px;margin:0 0 28px}}
.navitem{{display:grid;grid-template-columns:74px 1fr auto auto;gap:10px;align-items:center;text-decoration:none;
color:var(--ink);background:var(--panel);border:1px solid var(--line);border-radius:8px;padding:8px 12px}}
.navitem:hover{{border-color:var(--acc)}}.navitem .nm{{font-family:ui-monospace,Menlo,monospace;font-size:12.5px}}
.navitem .grp{{color:var(--mut);font-size:11px}}
.b{{font-size:10.5px;text-transform:uppercase;letter-spacing:.04em;border-radius:5px;padding:2px 7px;font-weight:600;text-align:center}}
.b.mod{{background:#1f2a44;color:#8fb4ff}}.b.new{{background:#143226;color:#56d364}}.b.del{{background:#3a1d22;color:#ff9a9a}}
.cnt{{font-family:ui-monospace,monospace;font-size:12px;white-space:nowrap}}.plus{{color:var(--addbar)}}.minus{{color:var(--delbar)}}
.card{{background:var(--panel);border:1px solid var(--line);border-radius:10px;margin:0 0 20px;overflow:hidden;scroll-margin-top:14px}}
.card-h{{display:flex;align-items:center;gap:12px;padding:12px 14px;border-bottom:1px solid var(--line);flex-wrap:wrap}}
.path{{font-family:ui-monospace,monospace;font-size:12.5px;flex:1;word-break:break-all}}
.meta{{color:var(--mut);font-size:11.5px;padding:8px 14px;border-bottom:1px solid var(--line)}}
.meta .k{{padding:0 5px;border-radius:3px}}.meta .k.add{{background:var(--add);color:#7ee2a8}}.meta .k.del{{background:var(--del);color:#ff9a9a}}
.doc{{font-family:ui-monospace,SFMono-Regular,Menlo,monospace;font-size:12.5px}}
.ln{{display:grid;grid-template-columns:46px 1fr;border-left:3px solid transparent}}
.ln .num{{background:var(--gut);color:#4b5263;text-align:right;padding:1px 8px;user-select:none;font-size:11px}}
.ln .tx{{padding:1px 12px;white-space:pre-wrap;word-break:break-word}}
.ln.ctx .tx{{color:var(--ink)}}
.ln.add{{background:var(--add);border-left-color:var(--addbar)}}.ln.add .tx{{color:#c8f0d6}}
.ln.del{{background:var(--del);border-left-color:var(--delbar)}}.ln.del .tx{{color:#f0b3b6;text-decoration:line-through;text-decoration-color:#a04a4f}}
.ln.del .num{{color:var(--delbar)}}
.kick{{margin:0 0 30px}}.kick h2{{font-size:17px;margin:0 0 4px}}
.sub2{{color:var(--mut);font-size:12px;margin:0 0 14px;line-height:1.5}}
.kgrid{{display:grid;grid-template-columns:1fr 1fr;gap:14px}}
@media(max-width:760px){{.kgrid{{grid-template-columns:1fr}}}}
.kcol{{background:var(--panel);border:1px solid var(--line);border-radius:10px;padding:14px}}
.kcol h3{{margin:0 0 6px;font-size:14px}}.kn{{color:var(--mut);font-weight:400;font-size:11.5px}}
.ksub{{color:var(--mut);font-size:10.5px;text-transform:uppercase;letter-spacing:.05em;margin:12px 0 6px}}
.catrow{{display:flex;flex-wrap:wrap;gap:5px}}
.catchip{{background:#1b2230;border:1px solid var(--line);border-radius:5px;padding:2px 8px;font-family:ui-monospace,monospace;font-size:11px;color:#bcd0f0}}
.catchip.mode{{color:#cdb6f0}}
.trow{{padding:6px 0;border-top:1px solid var(--line)}}
.tanc{{font-size:11.5px;margin-bottom:2px}}.tanc code{{color:#8fb4ff}}
.tterms{{color:var(--ink);font-size:11.5px;line-height:1.45}}
footer{{color:var(--mut);font-size:12px;margin:28px 0 0;border-top:1px solid var(--line);padding-top:14px}}a{{color:var(--acc)}}
.enums{{margin:0 0 30px}}.enums h2{{font-size:17px;margin:0 0 4px}}
.evgroup{{background:var(--panel);border:1px solid var(--line);border-radius:10px;padding:12px 14px;margin:0 0 12px}}
.evgroup h3{{margin:0 0 8px;font-size:13px;color:var(--mut);text-transform:uppercase;letter-spacing:.05em}}
.evrow{{display:grid;grid-template-columns:280px 1fr;gap:12px;align-items:start;padding:7px 0;border-top:1px solid var(--line)}}
.evrow:first-of-type{{border-top:none}}
@media(max-width:680px){{.evrow{{grid-template-columns:1fr}}}}
.evmeta code{{font-family:ui-monospace,monospace;font-size:11.5px;color:#8fb4ff;display:block}}
.evmeta .evname{{color:var(--mut);font-size:10.5px}}
.evchips{{display:flex;flex-wrap:wrap;gap:5px}}
.evchip{{background:#1b2230;border:1px solid var(--line);border-radius:5px;padding:2px 8px;font-family:ui-monospace,monospace;font-size:11px;color:#cfd8ea;display:inline-flex;align-items:center;gap:6px}}
.evchip.ev-homo{{border-color:#2ea043;color:#7ee2a8}}.evchip.ev-hetero{{border-color:#6aa3ff;color:#a9c8ff}}
.evaxis{{font-size:9px;text-transform:uppercase;letter-spacing:.04em;border-radius:3px;padding:1px 4px;background:#0d1014;color:var(--mut)}}
.ev-homo .evaxis{{background:#143226;color:#56d364}}.ev-hetero .evaxis{{background:#142544;color:#8fb4ff}}
.evaxis.ax-homo{{background:#143226;color:#56d364}}.evaxis.ax-hetero{{background:#142544;color:#8fb4ff}}
</style></head><body><div class="wrap">
<h1>Deep-dive prompt review</h1>
<p class="sub">PR&nbsp;#54 — full prompt text with the diff vs <b>main</b> (<code>{BASE[:7]}</code>) highlighted inline · {len(files)} files</p>
<div class="chips"><span class="chip"><b>{nm}</b> modified</span><span class="chip"><b>{nn}</b> new</span><span class="chip"><b>{nd}</b> deleted</span></div>
{kickoff_section()}
{enum_section()}
<h2 style="font-size:17px;margin:0 0 12px">Prompts</h2>
<nav class="nav">{''.join(nav)}</nav>
{''.join(secs)}
<footer>Each prompt shown in full (the verbatim system prompt the model receives), rendered from <code>git diff -U100000 {BASE[:7]}…HEAD</code>. Unchanged lines are plain; added=green, removed=struck red.</footer>
</div></body></html>"""
    dest = REPO / "docs" / "prompt_review.html"
    dest.write_text(out)
    print(f"wrote {dest}  ({len(files)} files, {len(out)//1024} KB)")


if __name__ == "__main__":
    main()
