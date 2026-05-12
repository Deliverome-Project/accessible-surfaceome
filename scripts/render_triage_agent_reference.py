"""Generate docs/eval/triage_agent_reference.html.

Self-contained HTML reference for the surface_triage agent. Renders:

- All 4 prompt variants as tabbed sections (default, naive, web, web+naive)
- A representative per-gene task message (B2M)
- The relevant Pydantic classes (extracted in source order from models.py)
- The auto-generated JSON schema for `TriageRecordDraft`
- One example agent output (B2M, persisted at data/triage/B2M.json)
- The current benchmark TSV as a sortable table

Run after editing a prompt, the schema, the example record, or the
benchmark. Keeping the renderer dumb-but-deterministic prevents the HTML
from drifting.

Usage:
    uv run python scripts/render_triage_agent_reference.py
"""

from __future__ import annotations

import csv
import json
import re

from accessible_surfaceome.paths import REPO_ROOT
from accessible_surfaceome.tools._shared.models import TriageRecordDraft

PROMPTS_DIR = (
    REPO_ROOT / "src" / "accessible_surfaceome" / "agents" / "surface_triage" / "prompts"
)
MODELS_PATH = REPO_ROOT / "src" / "accessible_surfaceome" / "tools" / "_shared" / "models.py"
EXAMPLE_PATH = REPO_ROOT / "data" / "triage" / "B2M.json"
BENCHMARK_PATH = REPO_ROOT / "data" / "eval" / "triage_benchmark_v1.tsv"
SUBBENCH_PATH = REPO_ROOT / "data" / "eval" / "triage_subbench_v1.tsv"
SUBBENCH_RUNS_DIR = REPO_ROOT / "data" / "eval" / "triage_subbench_v1"
OUTPUT_HTML = REPO_ROOT / "docs" / "eval" / "triage_agent_reference.html"

SUBBENCH_MODELS: list[str] = ["haiku-4-5", "sonnet-4-6", "opus-4-7"]
# All 4 variants the runner exposes. Cells without run data render as
# 0/0 (the grid builder degrades gracefully on missing directories).
SUBBENCH_VARIANTS = ["naive", "ncbi", "web_naive", "web_ncbi"]

# (slug, filename, display label, blurb)
PROMPT_VARIANTS = [
    (
        "default",
        "system.md",
        "Default (NCBI + HGNC resolver, no web)",
        "Active production prompt. Orchestrator pre-resolves HGNC + UniProt + NCBI + gene-group + CD designation and injects them into the task message. No tools.",
    ),
    (
        "naive",
        "system_naive.md",
        "Naive (no resolver, no web)",
        "Pure-model baseline. Agent receives only the gene symbol in the task message — no resolver context, no tools. Measures what trained knowledge alone can do.",
    ),
    (
        "web_ncbi",
        "system_web.md",
        "Web search + NCBI resolver",
        "Adds the `web_search` builtin tool on top of the default prompt. Agent uses the resolver context as a baseline and queries the web for proteins where its trained knowledge is uncertain.",
    ),
    (
        "web_naive",
        "system_web_naive.md",
        "Web search alone (no resolver)",
        "`web_search` tool with no resolver context — agent builds its own context from the web given just the gene symbol. Measures whether the resolver injection or the web tool dominates.",
    ),
    (
        "slim",
        "system_slim.md",
        "Slim (NCBI + HGNC resolver, streamlined)",
        "Streamlined sibling of the default. Same resolver context and task message; system prompt is 63% shorter (5,506 → 2,017 tokens) — recruitment-test logic merged into the enum definitions, contextual subtype prose consolidated, opening pMHC framing removed (the `pmhc_only_intracellular` enum already covers it), and the 8-probe `Pre-no` checklist collapsed to 2 explicit patterns. Drops probes that re-tell the agent to use resolver context. See the diff section below.",
    ),
]


_PYDANTIC_NAMES = [
    "GeneIdentifier",
    "TRIAGE_SCHEMA_VERSION",
    "TriageVerdict",
    "TriageModelPath",
    "YesReason",
    "ContextualReason",
    "NoReason",
    "TriageReason",
    "_YES_REASONS",
    "_CONTEXTUAL_REASONS",
    "_NO_REASONS",
    "_REASONS_BY_VERDICT",
    "TriageRecordDraft",
    "TriageRecord",
]


def _extract_pydantic_source(models_text: str, names: list[str]) -> str:
    """Pull selected class / type-alias blocks out of models.py in source order."""
    lines = models_text.splitlines()
    spans: dict[str, tuple[int, int]] = {}

    class_starts: dict[str, int] = {}
    for i, line in enumerate(lines):
        m = re.match(r"^class (\w+)\(", line)
        if m and m.group(1) in names:
            class_starts[m.group(1)] = i

    for name, start in class_starts.items():
        end = len(lines) - 1
        for j in range(start + 1, len(lines)):
            stripped = lines[j].lstrip()
            if not lines[j].strip():
                continue
            indent = len(lines[j]) - len(stripped)
            if indent == 0 and not stripped.startswith("#"):
                end = j - 1
                break
        while end > start and not lines[end].strip():
            end -= 1
        spans[name] = (start, end)

    for i, line in enumerate(lines):
        m = re.match(r"^(\w+)\s*[:=]", line)
        if m and m.group(1) in names and m.group(1) not in spans:
            end = i
            if "[" in line and "]" not in line:
                for j in range(i + 1, len(lines)):
                    if "]" in lines[j]:
                        end = j
                        break
            elif "(" in line and ")" not in line:
                for j in range(i + 1, len(lines)):
                    if ")" in lines[j] and "(" not in lines[j]:
                        end = j
                        break
            elif "{" in line and "}" not in line:
                for j in range(i + 1, len(lines)):
                    if "}" in lines[j] and "{" not in lines[j]:
                        end = j
                        break
            spans[m.group(1)] = (i, end)

    ordered = sorted(spans.values())
    blocks: list[str] = []
    for start, end in ordered:
        blocks.append("\n".join(lines[start : end + 1]))
    return "\n\n\n".join(blocks)


SAMPLE_TASK = (
    "Triage the human gene **B2M**.\n\n"
    "Canonical identifiers and gene summary (machine-resolved from HGNC and NCBI; "
    "no further lookups available — judge from the context below plus your trained knowledge):\n\n"
    "- HGNC approved name: beta-2-microglobulin\n"
    "- HGNC symbol: B2M\n"
    "- UniProt accession: P61769\n"
    "- Aliases: AMYLD6, IMD43, MHC1D4\n"
    "- Previous symbols: (none)\n"
    "- HGNC gene-group memberships: C1-set domain containing\n"
    "- CD nomenclature: (none assigned)\n"
    "- NCBI summary: This gene encodes a serum protein found in association with the major "
    "histocompatibility complex (MHC) class I heavy chain on the surface of nearly all nucleated "
    "cells. The protein has a predominantly beta-pleated sheet structure that can form amyloid "
    "fibrils in some pathological conditions. The encoded antimicrobial protein displays "
    "antibacterial activity in amniotic fluid. A mutation in this gene has been shown to result "
    "in hypercatabolic hypoproteinemia.[provided by RefSeq, Aug 2014]\n\n"
    "Emit one JSON object matching the `TriageRecordDraft` schema as your **entire** response — "
    "no prose around it, no markdown code fences, no commentary. Required keys: `verdict`, "
    "`verdict_reasoning`, `reason`.\n"
)


def _load_prompt_variants() -> list[dict]:
    out = []
    for slug, fname, label, blurb in PROMPT_VARIANTS:
        path = PROMPTS_DIR / fname
        if not path.exists():
            continue
        text = path.read_text()
        out.append({
            "slug": slug,
            "label": label,
            "blurb": blurb,
            "filename": fname,
            "n_lines": len(text.splitlines()),
            "source": text,
        })
    return out


def _render_slim_diff_html() -> str:
    """Render a unified diff of system.md → system_slim.md as inline HTML.

    Pre-escapes ``<`` / ``>`` / ``&`` and wraps each line in a ``<span>``
    with a class that the dedicated CSS colours according to whether the
    line is added (``+``), removed (``-``), context (` `), or a hunk
    header (``@@``). Skips the leading ``---`` / ``+++`` file headers
    since the section heading already says which two files are being
    compared.
    """
    import difflib
    import html as _html

    old_path = PROMPTS_DIR / "system.md"
    new_path = PROMPTS_DIR / "system_slim.md"
    if not (old_path.exists() and new_path.exists()):
        return "<p><em>Slim variant not present; diff section omitted.</em></p>"

    old_lines = old_path.read_text().splitlines(keepends=False)
    new_lines = new_path.read_text().splitlines(keepends=False)

    diff = difflib.unified_diff(
        old_lines, new_lines,
        fromfile="system.md", tofile="system_slim.md",
        lineterm="", n=3,
    )

    parts: list[str] = ["<pre class=\"diff\"><code>"]
    n_add = n_del = 0
    for raw in diff:
        if raw.startswith("---") or raw.startswith("+++"):
            continue
        if raw.startswith("@@"):
            cls = "hunk"
        elif raw.startswith("+"):
            cls = "add"
            n_add += 1
        elif raw.startswith("-"):
            cls = "del"
            n_del += 1
        else:
            cls = "ctx"
        # difflib emits each diff line WITHOUT a trailing newline. Render
        # one <span> per line; the ``white-space: pre`` on the parent
        # preserves indentation.
        parts.append(
            f'<span class="diff-line diff-{cls}">'
            f'{_html.escape(raw)}'
            f'</span>\n'
        )
    parts.append("</code></pre>")
    summary = (
        f'<p class="diff-stats"><span class="diff-add-pill">+{n_add}</span>'
        f' <span class="diff-del-pill">−{n_del}</span> '
        f'<span class="diff-meta">'
        f'{len(old_lines):,} → {len(new_lines):,} lines · '
        f'{old_path.stat().st_size:,} → {new_path.stat().st_size:,} bytes'
        f'</span></p>'
    )
    return summary + "".join(parts)


def _load_benchmark() -> list[dict[str, str]]:
    with BENCHMARK_PATH.open() as f:
        return list(csv.DictReader(f, delimiter="\t"))


def _load_subbench() -> list[dict[str, str]]:
    if not SUBBENCH_PATH.exists():
        return []
    with SUBBENCH_PATH.open() as f:
        return list(csv.DictReader(f, delimiter="\t"))


def _score_subbench(subbench_rows: list[dict[str, str]]) -> dict:
    """Walk data/eval/triage_subbench_v1/<model>/<variant>/<gene>_run*.json and
    score each model x variant combination against ground_truth_verdict /
    ground_truth_reason. Returns a nested dict suitable for rendering.

    A run is correct on verdict if predicted_verdict == ground_truth_verdict;
    correct on reason if (verdict-correct AND predicted_reason ==
    ground_truth_reason). Missing runs are skipped silently.
    """
    truth_by_gene: dict[str, tuple[str, str]] = {
        r["gene_symbol"]: (
            r["ground_truth_verdict"],
            r["ground_truth_reason"],
        )
        for r in subbench_rows
    }

    grid: dict[str, dict[str, dict[str, object]]] = {}
    per_gene: dict[str, dict[str, dict[str, object]]] = {}
    for model in SUBBENCH_MODELS:
        grid[model] = {}
        for variant in SUBBENCH_VARIANTS:
            run_dir = SUBBENCH_RUNS_DIR / model / variant
            if not run_dir.exists():
                grid[model][variant] = {
                    "n_runs": 0,
                    "n_verdict_correct": 0,
                    "n_reason_correct": 0,
                }
                continue
            n_runs = 0
            n_v = 0
            n_r = 0
            for path in sorted(run_dir.glob("*.json")):
                try:
                    data = json.loads(path.read_text())
                except json.JSONDecodeError:
                    continue
                gene = (
                    data.get("gene_symbol")
                    or path.stem.split("_run")[0]
                )
                tv, tr = truth_by_gene.get(gene, (None, None))
                if tv is None:
                    continue
                pv = data.get("predicted_verdict") or data.get("verdict")
                pr = data.get("predicted_reason") or data.get("reason")
                n_runs += 1
                # yes/contextual are interchangeable for verdict accuracy
                # (mirrors the runner's correctness rule); reason match is
                # still strict.
                v_ok = pv is not None and (
                    pv == tv or (pv in ("yes", "contextual") and tv in ("yes", "contextual"))
                )
                r_ok = v_ok and pr == tr
                n_v += int(v_ok)
                n_r += int(r_ok)
                bucket = per_gene.setdefault(gene, {}).setdefault(model, {}).setdefault(
                    variant, {"runs": [], "n_v": 0, "n_r": 0}
                )
                bucket["runs"].append({
                    "run_id": path.stem,
                    "predicted_verdict": pv,
                    "predicted_reason": pr,
                    "verdict_correct": v_ok,
                    "reason_correct": r_ok,
                })
                bucket["n_v"] = int(bucket["n_v"]) + int(v_ok)
                bucket["n_r"] = int(bucket["n_r"]) + int(r_ok)
            grid[model][variant] = {
                "n_runs": n_runs,
                "n_verdict_correct": n_v,
                "n_reason_correct": n_r,
            }

    return {"grid": grid, "per_gene": per_gene}


HTML_TEMPLATE = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<title>surface_triage agent — reference</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Manrope:wght@300;400;500;600;700;800&family=Playfair+Display:ital,wght@0,400..700;1,400..600&display=swap" rel="stylesheet">
<link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/highlight.js/11.9.0/styles/atom-one-light.min.css">
<script src="https://cdnjs.cloudflare.com/ajax/libs/marked/12.0.0/marked.min.js"></script>
<script src="https://cdnjs.cloudflare.com/ajax/libs/highlight.js/11.9.0/highlight.min.js"></script>
<style>
:root { --primary: #BC3C4C; --secondary: #3D6B60; --accent: #F4AA28;
  --bg: #FBF7F2; --bg-warm: #F3ECE5; --ink: #1F1718; --line: #E6DAD4; --neutral: #6F5D5A;
  --code-bg: #F5EFE8; --code-line: #E6DAD4; --claude-orange: #d87851; }
* { box-sizing: border-box; }
html, body { margin: 0; padding: 0; background: var(--bg); }
body { font-family: "Manrope", -apple-system, BlinkMacSystemFont, system-ui, sans-serif;
  font-size: 15.5px; line-height: 1.6; color: var(--ink); font-weight: 400; }
header { background: linear-gradient(135deg, #F3ECE5 0%, #FBF7F2 100%);
  border-bottom: 1px solid var(--line); padding: 36px 48px 28px; }
header .eyebrow { font-size: 11px; font-weight: 700; letter-spacing: 0.12em;
  text-transform: uppercase; color: var(--primary); margin: 0 0 8px 0; }
header h1 { font-family: "Playfair Display", Georgia, serif; font-weight: 600;
  font-size: 34px; letter-spacing: -0.02em; margin: 0 0 12px 0; color: var(--ink); }
header .meta-row { display: flex; flex-wrap: wrap; gap: 12px; font-size: 13px; }
header .meta-row .chip { display: inline-flex; align-items: center; gap: 6px;
  background: white; border: 1px solid var(--line); padding: 4px 12px;
  border-radius: 999px; color: var(--neutral); font-weight: 500; }
header .meta-row .chip strong { color: var(--ink); font-weight: 600; }
nav { position: sticky; top: 0; background: rgba(251, 247, 242, 0.95);
  backdrop-filter: blur(8px); -webkit-backdrop-filter: blur(8px);
  border-bottom: 1px solid var(--line); padding: 14px 48px;
  display: flex; gap: 8px; z-index: 10; }
nav a { color: var(--neutral); text-decoration: none; font-size: 13.5px;
  font-weight: 500; padding: 6px 14px; border-radius: 999px; transition: all 0.15s ease; }
nav a:hover { background: var(--bg-warm); color: var(--primary); }
main { max-width: 1100px; margin: 0 auto; padding: 40px 48px 96px; }
section { margin-bottom: 64px; }
section h2 { font-family: "Playfair Display", Georgia, serif; font-weight: 600;
  font-size: 26px; letter-spacing: -0.015em; margin: 0 0 8px 0; color: var(--ink); }
section h2 .pill { display: inline-block; vertical-align: middle; margin-left: 12px;
  font-family: "Manrope", sans-serif; font-size: 11px; font-weight: 700;
  letter-spacing: 0.08em; text-transform: uppercase; color: var(--primary);
  background: white; border: 1px solid var(--line); padding: 3px 10px; border-radius: 999px; }
section .lede { color: var(--neutral); font-size: 14.5px; margin: 4px 0 24px 0; }
.prompt-rendered { background: white; border: 1px solid var(--line); border-radius: 10px;
  padding: 28px 32px; }
.prompt-rendered h1 { font-family: "Playfair Display", Georgia, serif; font-weight: 600;
  font-size: 24px; margin: 0 0 14px 0; color: var(--ink); }
.prompt-rendered h2 { font-family: "Manrope", sans-serif; font-weight: 700;
  font-size: 16px; letter-spacing: -0.005em; margin: 28px 0 10px 0;
  color: var(--primary); text-transform: none; }
.prompt-rendered h3 { font-family: "Manrope", sans-serif; font-weight: 700;
  font-size: 14.5px; margin: 22px 0 8px 0; color: var(--ink); }
.prompt-rendered p { margin: 0 0 12px 0; }
.prompt-rendered ul, .prompt-rendered ol { margin: 0 0 12px 0; padding-left: 22px; }
.prompt-rendered li { margin-bottom: 6px; }
.prompt-rendered hr { border: none; border-top: 1px solid var(--line); margin: 28px 0; }
.prompt-rendered code { background: var(--code-bg); border: 1px solid var(--code-line);
  border-radius: 4px; padding: 1px 6px; font-family: ui-monospace, SFMono-Regular, Menlo, monospace;
  font-size: 13.5px; color: var(--ink); }
.prompt-rendered pre { background: var(--code-bg); border: 1px solid var(--code-line);
  border-radius: 8px; padding: 16px 20px; overflow-x: auto; margin: 12px 0; }
.prompt-rendered pre code { background: transparent; border: none; padding: 0; font-size: 13px; }
.prompt-rendered strong { font-weight: 700; color: var(--ink); }
.prompt-rendered blockquote { border-left: 3px solid var(--accent); margin: 12px 0;
  padding: 4px 16px; color: var(--neutral); background: var(--bg-warm); border-radius: 0 8px 8px 0; }
.task-rendered.prompt-rendered { background: white; border: 1px solid var(--line); }
pre { background: var(--code-bg); border: 1px solid var(--code-line); border-radius: 10px;
  padding: 20px 24px; overflow-x: auto; font-size: 13.5px; line-height: 1.55;
  font-family: ui-monospace, SFMono-Regular, Menlo, monospace; }
details { background: white; border: 1px solid var(--line); border-radius: 10px;
  padding: 14px 20px; margin-top: 16px; }
details summary { cursor: pointer; color: var(--neutral); font-weight: 600; font-size: 13.5px; }
details[open] summary { margin-bottom: 12px; }

/* Tabs for prompt variants */
.tabs { display: flex; flex-wrap: wrap; gap: 6px; margin-bottom: 18px;
  border-bottom: 1px solid var(--line); padding-bottom: 0; }
.tab-button { background: none; border: 1px solid transparent; border-bottom: none;
  padding: 10px 18px; cursor: pointer; font-family: "Manrope", sans-serif;
  font-size: 13px; font-weight: 600; color: var(--neutral); border-radius: 8px 8px 0 0;
  margin-bottom: -1px; transition: all 0.15s ease; }
.tab-button:hover { color: var(--primary); background: var(--bg-warm); }
.tab-button.active { color: var(--primary); background: white;
  border-color: var(--line); border-bottom-color: white; }
.tab-content { display: none; }
.tab-content.active { display: block; }
.tab-blurb { color: var(--neutral); font-size: 14px; font-style: italic;
  margin: 0 0 16px 4px; }

/* system.md → system_slim.md unified diff */
.diff { background: var(--code-bg); border: 1px solid var(--code-line);
  border-radius: 8px; padding: 14px 16px; overflow-x: auto;
  font-family: "JetBrains Mono", Menlo, Consolas, monospace; font-size: 12.5px;
  line-height: 1.55; color: var(--ink); }
.diff code { background: transparent; border: none; padding: 0; }
.diff-line { display: block; white-space: pre; padding: 0 4px;
  border-left: 3px solid transparent; }
.diff-add { background: #ecfdf5; color: #065f46; border-left-color: #10b981; }
.diff-del { background: #fef2f2; color: #991b1b; border-left-color: #ef4444; }
.diff-hunk { background: #f3f4f6; color: var(--neutral); font-style: italic;
  margin: 6px 0; padding: 2px 4px; border-left-color: var(--neutral); }
.diff-ctx { color: var(--neutral); }
.diff-stats { font-size: 13px; color: var(--neutral); margin: 0 0 12px 0;
  display: flex; gap: 10px; align-items: center; flex-wrap: wrap; }
.diff-add-pill { background: #ecfdf5; color: #065f46; padding: 2px 10px;
  border-radius: 999px; font-weight: 700; font-family: "JetBrains Mono", monospace; }
.diff-del-pill { background: #fef2f2; color: #991b1b; padding: 2px 10px;
  border-radius: 999px; font-weight: 700; font-family: "JetBrains Mono", monospace; }
.diff-meta { font-family: "JetBrains Mono", monospace; }

/* Benchmark table */
.benchmark-controls { display: flex; gap: 12px; flex-wrap: wrap; align-items: center;
  margin-bottom: 18px; }
.benchmark-search { flex: 1; min-width: 220px; padding: 9px 14px; border: 1px solid var(--line);
  border-radius: 8px; font-family: inherit; font-size: 13.5px; background: white;
  color: var(--ink); }
.benchmark-filter { padding: 9px 14px; border: 1px solid var(--line); border-radius: 8px;
  font-family: inherit; font-size: 13.5px; background: white; color: var(--ink); }
.benchmark-stats { font-size: 13px; color: var(--neutral); }
.benchmark-stats strong { color: var(--ink); font-weight: 700; }
.benchmark-table { width: 100%; border-collapse: collapse; background: white;
  border: 1px solid var(--line); border-radius: 10px; overflow: hidden; font-size: 13px; }
.benchmark-table th { background: var(--bg-warm); color: var(--ink); font-weight: 700;
  text-align: left; padding: 10px 12px; border-bottom: 1px solid var(--line);
  font-size: 11.5px; text-transform: uppercase; letter-spacing: 0.05em;
  cursor: pointer; user-select: none; }
.benchmark-table th:hover { background: var(--line); }
.benchmark-table td { padding: 9px 12px; border-bottom: 1px solid var(--line);
  vertical-align: top; }
.benchmark-table tr:last-child td { border-bottom: none; }
.benchmark-table tr:hover td { background: var(--bg-warm); }
.benchmark-table td.gene { font-weight: 700; color: var(--ink); font-family: ui-monospace, Menlo, monospace; }
.benchmark-table td.acc { font-family: ui-monospace, Menlo, monospace; color: var(--neutral); font-size: 12px; }
.benchmark-table td.rationale { color: var(--neutral); font-size: 12.5px; max-width: 420px; }
.verdict-pill { display: inline-block; padding: 2px 10px; border-radius: 999px;
  font-size: 11px; font-weight: 700; text-transform: uppercase; letter-spacing: 0.05em; }
.verdict-pill.yes { background: #E8F0E5; color: #3D6B60; }
.verdict-pill.contextual { background: #FCEDD3; color: #C68A1B; }
.verdict-pill.no { background: #F7D9D6; color: var(--primary); }
.reason-tag { display: inline-block; background: var(--bg-warm); color: var(--ink);
  padding: 2px 8px; border-radius: 6px; font-family: ui-monospace, Menlo, monospace;
  font-size: 11.5px; }

/* Subbench score grid */
.subbench-grid { width: 100%; border-collapse: collapse; background: white;
  border: 1px solid var(--line); border-radius: 10px; overflow: hidden;
  font-size: 13px; margin-bottom: 28px; }
.subbench-grid th, .subbench-grid td { padding: 9px 12px;
  border-bottom: 1px solid var(--line); text-align: left; }
.subbench-grid th { background: var(--bg-warm); color: var(--ink);
  font-weight: 700; font-size: 11.5px; text-transform: uppercase;
  letter-spacing: 0.05em; }
.subbench-grid tr:last-child td { border-bottom: none; }
.subbench-grid td.model { font-weight: 700; font-family: ui-monospace, Menlo, monospace; }
.subbench-grid td.score { font-family: ui-monospace, Menlo, monospace;
  text-align: center; }
.subbench-grid td.score .pct { display: block; font-weight: 700; color: var(--ink); }
.subbench-grid td.score .frac { font-size: 11.5px; color: var(--neutral); }
.subbench-grid td.score.weak .pct { color: var(--primary); }
.subbench-grid td.score.mid .pct { color: #C68A1B; }
.subbench-grid td.score.strong .pct { color: var(--secondary); }
.subbench-note { font-size: 12.5px; color: var(--neutral); margin: 4px 0 16px 0; }
.subbench-history { color: var(--neutral); font-size: 12px; font-style: italic; }
</style>
</head>
<body>

<header>
  <div class="eyebrow">Agent reference</div>
  <h1>surface_triage agent</h1>
  <div class="meta-row">
    <span class="chip"><strong>Schema</strong> <code>TriageRecordDraft</code></span>
    <span class="chip"><strong>Version</strong> __SCHEMA_VERSION__</span>
    <span class="chip"><strong>Default model</strong> haiku_only</span>
    <span class="chip"><strong>Benchmark</strong> __BENCH_N__ proteins</span>
  </div>
</header>

<nav>
  <a href="#prompt-variants">Prompt variants</a>
  <a href="#slim-diff">Slim diff</a>
  <a href="#task-context">Task context</a>
  <a href="#pydantic">Pydantic schema</a>
  <a href="#jsonschema">JSON schema</a>
  <a href="#example">Example output</a>
  <a href="#benchmark">Benchmark</a>
  <a href="#subbench">17-gene subbench</a>
</nav>

<main>

<section id="prompt-variants">
  <h2>Prompt variants <span class="pill">__N_VARIANTS__ versions</span></h2>
  <p class="lede">Four prompt variants for A/B comparison. The <em>Default</em> is the active production prompt. The others measure ablations: removing the resolver context, adding web search, or both.</p>
  <div class="tabs" id="prompt-tabs"></div>
  <div id="prompt-tab-contents"></div>
</section>

<section id="slim-diff">
  <h2>Slim diff <span class="pill">system.md → system_slim.md</span></h2>
  <p class="lede">Unified diff of the streamlined sibling variant. The slim prompt trades 3,489 tokens (63%) for a tighter call: cardinal-rule logic absorbed into the <code>secreted_only</code> / <code>stable_surface_attachment</code> enum definitions; contextual subtype prose consolidated; opening pMHC framing removed (the <code>pmhc_only_intracellular</code> enum already covers it); the 8-probe <code>Pre-no</code> checklist collapsed to 2 patterns; probes that re-tell the agent to use HGNC / NCBI resolver context dropped (the task message already carries it). Same accuracy story to be measured.</p>
  __SLIM_DIFF_HTML__
</section>

<section id="task-context">
  <h2>Task context (per-gene) <span class="pill">B2M sample</span></h2>
  <p class="lede">For prompt variants that use the resolver, every run gets a per-gene <strong>task message</strong> populated by the orchestrator from a live <code>resolve()</code> call: HGNC approved name + symbol, UniProt accession, aliases / previous symbols, HGNC gene-group memberships, CD nomenclature (when assigned), and the NCBI gene summary.</p>
  <div class="task-rendered prompt-rendered" id="task-rendered-content"></div>
</section>

<section id="pydantic">
  <h2>Pydantic schema</h2>
  <p class="lede">The agent emits a <code>TriageRecordDraft</code> JSON; the orchestrator fills in <code>gene</code> / <code>schema_version</code> / <code>model_path</code>, validates against this schema, and persists the canonical <code>TriageRecord</code>. A <code>model_validator</code> enforces <code>reason ∈ allowed-reasons-for-verdict</code>.</p>
  <pre><code class="language-python" id="pydantic-src"></code></pre>
</section>

<section id="jsonschema">
  <h2>JSON schema</h2>
  <p class="lede">Auto-generated from <code>TriageRecordDraft.model_json_schema()</code>.</p>
  <pre><code class="language-json" id="json-schema"></code></pre>
</section>

<section id="example">
  <h2>Example output <span class="pill">B2M · Haiku 4.5</span></h2>
  <p class="lede">Persisted at <code>data/triage/B2M.json</code>.</p>
  <pre><code class="language-json" id="example-output"></code></pre>
</section>

<section id="benchmark">
  <h2>Benchmark <span class="pill">__BENCH_N__ proteins</span></h2>
  <p class="lede">Current curated benchmark at <code>data/eval/triage_benchmark_v1.tsv</code>. Every entry is in the "DB-disagreement" zone — no 5/5 positives and no 0/5 negatives. Click column headers to sort. Use the search box and verdict filter to scope.</p>
  <div class="benchmark-controls">
    <input class="benchmark-search" id="bench-search" placeholder="Search gene, class, rationale…" type="text">
    <select class="benchmark-filter" id="bench-verdict-filter">
      <option value="">All verdicts</option>
      <option value="yes">yes</option>
      <option value="contextual">contextual</option>
      <option value="no">no</option>
    </select>
    <span class="benchmark-stats" id="bench-stats"></span>
  </div>
  <table class="benchmark-table" id="bench-table">
    <thead>
      <tr>
        <th data-key="gene_symbol">Gene</th>
        <th data-key="uniprot_acc">UniProt</th>
        <th data-key="class">Class</th>
        <th data-key="ground_truth_verdict">Verdict</th>
        <th data-key="ground_truth_signal">Signal</th>
        <th data-key="ground_truth_reason">Reason</th>
        <th data-key="rationale">Rationale</th>
      </tr>
    </thead>
    <tbody id="bench-tbody"></tbody>
  </table>
</section>

<section id="subbench">
  <h2>17-gene subbench <span class="pill">__SUBBENCH_N__ genes</span></h2>
  <p class="lede">Persistent-error subset at <code>data/eval/triage_subbench_v1.tsv</code> — every entry was missed at least once by a non-Haiku cell, or twice across the two Haiku cells, on the most recent full-benchmark sweep. Used for rapid prompt-iteration cycles. Score grid below shows verdict accuracy (V) and verdict+reason accuracy (R) for each (model, prompt-variant) pair.</p>

  <table class="subbench-grid" id="subbench-grid-table" hidden>
    <thead>
      <tr>
        <th>Model</th>
        __SUBBENCH_VARIANT_HEADERS__
      </tr>
    </thead>
    <tbody id="subbench-grid-tbody"></tbody>
  </table>
  <p class="subbench-note" id="subbench-grid-note" hidden>V = correct verdict; R = correct verdict <em>and</em> correct reason. Each cell shows percent (top) and absolute fraction (bottom). Colour: red &lt; 50%, amber 50–75%, green ≥ 75%.</p>

  <table class="benchmark-table" id="subbench-table">
    <thead>
      <tr>
        <th data-key="gene_symbol">Gene</th>
        <th data-key="uniprot_acc">UniProt</th>
        <th data-key="class">Class</th>
        <th data-key="ground_truth_verdict">Verdict</th>
        <th data-key="ground_truth_signal">Signal</th>
        <th data-key="ground_truth_reason">Reason</th>
        <th data-key="rationale">Rationale</th>
        <th data-key="error_history">Error history</th>
      </tr>
    </thead>
    <tbody id="subbench-tbody"></tbody>
  </table>
</section>

</main>

<script>
const promptVariants = __PROMPT_VARIANTS_JSON__;
const taskSource = __TASK_JSON__;
const benchmark = __BENCHMARK_JSON__;
const subbench = __SUBBENCH_JSON__;
const subbenchScores = __SUBBENCH_SCORES_JSON__;
const subbenchModels = __SUBBENCH_MODELS_JSON__;
const subbenchVariants = __SUBBENCH_VARIANTS_JSON__;

// Tab UI for prompt variants.
const tabs = document.getElementById("prompt-tabs");
const contents = document.getElementById("prompt-tab-contents");
promptVariants.forEach((v, idx) => {
  const btn = document.createElement("button");
  btn.className = "tab-button" + (idx === 0 ? " active" : "");
  btn.textContent = v.label;
  btn.dataset.slug = v.slug;
  btn.addEventListener("click", () => {
    document.querySelectorAll(".tab-button").forEach(b => b.classList.remove("active"));
    document.querySelectorAll(".tab-content").forEach(c => c.classList.remove("active"));
    btn.classList.add("active");
    document.getElementById("prompt-content-" + v.slug).classList.add("active");
  });
  tabs.appendChild(btn);

  const div = document.createElement("div");
  div.className = "tab-content" + (idx === 0 ? " active" : "");
  div.id = "prompt-content-" + v.slug;
  const blurb = document.createElement("p");
  blurb.className = "tab-blurb";
  blurb.innerHTML = "<strong>" + v.filename + "</strong> &mdash; " + v.blurb + " <em>(" + v.n_lines + " lines)</em>";
  div.appendChild(blurb);
  const rendered = document.createElement("div");
  rendered.className = "prompt-rendered";
  rendered.innerHTML = marked.parse(v.source);
  div.appendChild(rendered);
  const raw = document.createElement("details");
  raw.innerHTML = "<summary>Raw markdown source</summary><div><pre><code class=\\"language-markdown\\"></code></pre></div>";
  raw.querySelector("code").textContent = v.source;
  div.appendChild(raw);
  contents.appendChild(div);
});

document.getElementById("task-rendered-content").innerHTML = marked.parse(taskSource);
document.getElementById("pydantic-src").textContent = __PYDANTIC_JSON__;
document.getElementById("json-schema").textContent = __JSONSCHEMA_JSON__;
document.getElementById("example-output").textContent = __EXAMPLE_JSON__;

// Benchmark table — render, search, filter, sort.
const tbody = document.getElementById("bench-tbody");
const search = document.getElementById("bench-search");
const verdictFilter = document.getElementById("bench-verdict-filter");
const stats = document.getElementById("bench-stats");
let sortKey = "gene_symbol";
let sortDir = 1;

function renderTable() {
  const q = search.value.trim().toLowerCase();
  const vf = verdictFilter.value;
  const filtered = benchmark.filter(r => {
    if (vf && r.ground_truth_verdict !== vf) return false;
    if (!q) return true;
    return (
      r.gene_symbol.toLowerCase().includes(q) ||
      r.class.toLowerCase().includes(q) ||
      (r.rationale || "").toLowerCase().includes(q) ||
      (r.ground_truth_reason || "").toLowerCase().includes(q)
    );
  });
  filtered.sort((a, b) => {
    const av = (a[sortKey] || "").toString();
    const bv = (b[sortKey] || "").toString();
    if (av < bv) return -1 * sortDir;
    if (av > bv) return 1 * sortDir;
    return 0;
  });
  tbody.innerHTML = filtered.map(r => `
    <tr>
      <td class="gene">${r.gene_symbol}</td>
      <td class="acc">${r.uniprot_acc}</td>
      <td>${r.class.replaceAll("_", " ")}</td>
      <td><span class="verdict-pill ${r.ground_truth_verdict}">${r.ground_truth_verdict}</span></td>
      <td>${r.ground_truth_signal.replaceAll("_", " ")}</td>
      <td><span class="reason-tag">${r.ground_truth_reason}</span></td>
      <td class="rationale">${r.rationale}</td>
    </tr>
  `).join("");
  const counts = {yes: 0, contextual: 0, no: 0};
  filtered.forEach(r => { counts[r.ground_truth_verdict] = (counts[r.ground_truth_verdict] || 0) + 1; });
  stats.innerHTML = `<strong>${filtered.length}</strong> of ${benchmark.length} &nbsp;·&nbsp; yes: <strong>${counts.yes}</strong> &nbsp;·&nbsp; contextual: <strong>${counts.contextual}</strong> &nbsp;·&nbsp; no: <strong>${counts.no}</strong>`;
}

document.querySelectorAll(".benchmark-table th").forEach(th => {
  th.addEventListener("click", () => {
    const key = th.dataset.key;
    if (key === sortKey) sortDir = -sortDir;
    else { sortKey = key; sortDir = 1; }
    renderTable();
  });
});
search.addEventListener("input", renderTable);
verdictFilter.addEventListener("change", renderTable);
renderTable();

// Subbench score grid (model rows × variant columns; each cell shows V/R).
function scoreBucket(pct) {
  if (pct >= 75) return "strong";
  if (pct >= 50) return "mid";
  return "weak";
}
const subbenchTbody = document.getElementById("subbench-grid-tbody");
if (subbenchTbody && subbenchModels.length) {
  document.getElementById("subbench-grid-table").hidden = false;
  document.getElementById("subbench-grid-note").hidden = false;
  const rows = subbenchModels.map(model => {
    const cells = subbenchVariants.map(variant => {
      const cell = (subbenchScores[model] || {})[variant] || {n_runs: 0, n_verdict_correct: 0, n_reason_correct: 0};
      const n = cell.n_runs;
      if (!n) return `<td class="score">—</td>`;
      const vPct = Math.round((cell.n_verdict_correct / n) * 100);
      const rPct = Math.round((cell.n_reason_correct / n) * 100);
      const vClass = scoreBucket(vPct);
      const rClass = scoreBucket(rPct);
      return `<td class="score ${vClass}"><span class="pct">V ${vPct}%</span><span class="frac">${cell.n_verdict_correct}/${n}</span></td>
              <td class="score ${rClass}"><span class="pct">R ${rPct}%</span><span class="frac">${cell.n_reason_correct}/${n}</span></td>`;
    }).join("");
    return `<tr><td class="model">${model}</td>${cells}</tr>`;
  });
  subbenchTbody.innerHTML = rows.join("");
}

// Subbench detail table (reuses the .benchmark-table style).
const subbenchDetailTbody = document.getElementById("subbench-tbody");
if (subbenchDetailTbody) {
  subbenchDetailTbody.innerHTML = subbench.map(r => `
    <tr>
      <td class="gene">${r.gene_symbol}</td>
      <td class="acc">${r.uniprot_acc}</td>
      <td>${(r.class || "").replaceAll("_", " ")}</td>
      <td><span class="verdict-pill ${r.ground_truth_verdict}">${r.ground_truth_verdict}</span></td>
      <td>${(r.ground_truth_signal || "").replaceAll("_", " ")}</td>
      <td><span class="reason-tag">${r.ground_truth_reason || ""}</span></td>
      <td class="rationale">${r.rationale || ""}</td>
      <td class="subbench-history">${r.error_history || ""}</td>
    </tr>
  `).join("");
}

hljs.highlightAll();
</script>
</body>
</html>
"""


def main() -> None:
    variants = _load_prompt_variants()
    benchmark = _load_benchmark()
    subbench = _load_subbench()
    subbench_scored = _score_subbench(subbench)
    models_text = MODELS_PATH.read_text()
    pydantic_src = _extract_pydantic_source(models_text, _PYDANTIC_NAMES)
    json_schema = json.dumps(
        TriageRecordDraft.model_json_schema(), indent=2, sort_keys=True
    )
    example_record = EXAMPLE_PATH.read_text()
    schema_version_match = re.search(
        r'TRIAGE_SCHEMA_VERSION\s*=\s*"([^"]+)"', models_text
    )
    schema_version = schema_version_match.group(1) if schema_version_match else "?"

    # Build the <th> header row for the subbench grid: one (V, R) pair per variant.
    subbench_variant_headers = "".join(
        f'<th colspan="2">{v.replace("_", " ")}</th>' for v in SUBBENCH_VARIANTS
    )

    slim_diff_html = _render_slim_diff_html()

    rendered = (
        HTML_TEMPLATE.replace("__SCHEMA_VERSION__", schema_version)
        .replace("__N_VARIANTS__", str(len(variants)))
        .replace("__BENCH_N__", str(len(benchmark)))
        .replace("__SUBBENCH_N__", str(len(subbench)))
        .replace("__SUBBENCH_VARIANT_HEADERS__", subbench_variant_headers)
        .replace("__SLIM_DIFF_HTML__", slim_diff_html)
        .replace("__PROMPT_VARIANTS_JSON__", json.dumps(variants))
        .replace("__TASK_JSON__", json.dumps(SAMPLE_TASK))
        .replace("__PYDANTIC_JSON__", json.dumps(pydantic_src))
        .replace("__JSONSCHEMA_JSON__", json.dumps(json_schema))
        .replace("__EXAMPLE_JSON__", json.dumps(example_record))
        .replace("__BENCHMARK_JSON__", json.dumps(benchmark))
        .replace("__SUBBENCH_JSON__", json.dumps(subbench))
        .replace("__SUBBENCH_SCORES_JSON__", json.dumps(subbench_scored["grid"]))
        .replace("__SUBBENCH_MODELS_JSON__", json.dumps(SUBBENCH_MODELS))
        .replace("__SUBBENCH_VARIANTS_JSON__", json.dumps(SUBBENCH_VARIANTS))
    )

    OUTPUT_HTML.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_HTML.write_text(rendered, encoding="utf-8")
    print(
        f"wrote {OUTPUT_HTML.relative_to(REPO_ROOT)} "
        f"({len(rendered):,} chars, {len(variants)} prompt variants, "
        f"{len(benchmark)} benchmark rows, {len(subbench)} subbench rows)"
    )


if __name__ == "__main__":
    main()
