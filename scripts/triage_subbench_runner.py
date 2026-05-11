"""Run the 4-variant × N-replicate triage sub-benchmark.

Tests the 17-protein hard-case sub-benchmark across 4 prompt variants:

  1. naive      — system_naive.md         (no resolver, no tools)
  2. ncbi       — system.md               (resolver only, no tools)
  3. web_naive  — system_web_naive.md     (web_search, no resolver)
  4. web_ncbi   — system_web.md           (web_search + resolver)

For each (variant × gene × replicate) cell, writes a per-run record at
``data/eval/triage_subbench_v1/<variant>/<gene>_run<N>.json`` with the
parsed verdict, reason, full verdict_reasoning prose, token counts,
web-search count, latency, and dollar cost (computed from the model
pricing table).

USAGE — note this script does NOT auto-execute. Invoke directly:

    uv run python scripts/triage_subbench_runner.py --model claude-haiku-4-5 --replicates 2
    uv run python scripts/triage_subbench_runner.py --model claude-sonnet-4-6 --replicates 2

For a smoke test of one variant on one gene:

    uv run python scripts/triage_subbench_runner.py \\
        --model claude-haiku-4-5 --replicates 1 \\
        --variants naive --genes HSPA1A
"""

from __future__ import annotations

import argparse
import csv
import json
import logging
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from anthropic import Anthropic

from accessible_surfaceome.agents._support import client as _client_module
from accessible_surfaceome.agents.surface_triage.orchestrator import _render_task
from accessible_surfaceome.tools._shared.http import open_default_client
from accessible_surfaceome.tools.gene_lookup import resolve

logger = logging.getLogger(__name__)
ROOT = Path("/Users/rebeccacarlson/Git/accessible-surfaceome/.claude/worktrees/optimistic-goldwasser-ea19aa")
SUBBENCH_TSV = ROOT / "data/eval/triage_subbench_v1.tsv"
OUT_ROOT = ROOT / "data/eval/triage_subbench_v1"
PROMPTS_DIR = ROOT / "src/accessible_surfaceome/agents/surface_triage/prompts"

# Per-million-token list pricing for input + output. Update as Anthropic
# adjusts. Web search is billed separately at $10 / 1000 searches across
# all Claude models.
MODEL_PRICING: dict[str, tuple[float, float]] = {
    "claude-haiku-4-5":  (1.0, 5.0),
    "claude-sonnet-4-6": (3.0, 15.0),
    "claude-opus-4-7":   (15.0, 75.0),
}
WEB_SEARCH_USD_PER_QUERY = 0.01  # $10 / 1000 searches

# Web search tool block — Anthropic builtin. The exact `type` slug rolls
# forward periodically; update if the API returns a `tool_use_id` you can't
# match. As of 2025-Q4 the supported variant is "web_search_20250305".
WEB_SEARCH_TOOL: dict[str, Any] = {
    "type": "web_search_20250305",
    "name": "web_search",
    "max_uses": 4,
}

VARIANTS = {
    "naive":     {"prompt": "system_naive.md",     "resolver": False, "web_search": False},
    "ncbi":      {"prompt": "system.md",            "resolver": True,  "web_search": False},
    "web_naive": {"prompt": "system_web_naive.md", "resolver": False, "web_search": True},
    "web_ncbi":  {"prompt": "system_web.md",        "resolver": True,  "web_search": True},
}


@dataclass
class RunRecord:
    variant: str
    model: str
    gene_symbol: str
    replicate: int
    truth_verdict: str
    truth_class: str
    predicted_verdict: str | None
    predicted_reason: str | None
    verdict_reasoning: str
    correct: bool
    prompt_tokens: int
    completion_tokens: int
    n_web_searches: int
    cost_usd: float
    latency_s: float
    error: str | None = None
    raw_text: str = ""


_thread_local = threading.local()


def _client() -> Anthropic:
    if not hasattr(_thread_local, "client"):
        _thread_local.client = _client_module.get_client()
    return _thread_local.client


def _http():
    if not hasattr(_thread_local, "http"):
        _thread_local.http = open_default_client()
    return _thread_local.http


def _load_prompt(name: str) -> str:
    return (PROMPTS_DIR / name).read_text()


def _resolve_task_text(gene: str) -> str:
    """Use the orchestrator's _render_task to format the task message
    with HGNC + UniProt + NCBI + gene-group + CD designation context."""
    bundle = resolve(gene, http=_http())
    return _render_task(bundle)


def _parse_json_response(text: str) -> dict[str, Any] | None:
    """Pull a single JSON object out of the model's text response.

    Tolerates: bare JSON, JSON inside ```json fences, JSON with leading
    prose. Returns None on parse failure.
    """
    import re
    fenced = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", text, re.DOTALL)
    if fenced:
        try:
            return json.loads(fenced.group(1))
        except json.JSONDecodeError:
            pass
    # Try to find a top-level {…} block.
    start = text.find("{")
    while start != -1:
        depth = 0
        for i in range(start, len(text)):
            if text[i] == "{":
                depth += 1
            elif text[i] == "}":
                depth -= 1
                if depth == 0:
                    snippet = text[start : i + 1]
                    try:
                        return json.loads(snippet)
                    except json.JSONDecodeError:
                        break
        start = text.find("{", start + 1)
    return None


def _extract_text(response: Any) -> tuple[str, int]:
    """Collect all text content from a non-tool-use response, plus
    count web_search tool uses in the message history."""
    parts: list[str] = []
    n_searches = 0
    for block in getattr(response, "content", []) or []:
        if getattr(block, "type", None) == "text":
            txt = getattr(block, "text", None)
            if isinstance(txt, str):
                parts.append(txt)
        elif getattr(block, "type", None) == "server_tool_use":
            # Anthropic's web_search is a server_tool_use; counts as one search.
            if getattr(block, "name", "") == "web_search":
                n_searches += 1
    return "\n".join(parts), n_searches


def _cost(model: str, prompt_tokens: int, completion_tokens: int, n_web_searches: int) -> float:
    in_price, out_price = MODEL_PRICING.get(model, (0.0, 0.0))
    token_cost = (prompt_tokens * in_price + completion_tokens * out_price) / 1_000_000
    search_cost = n_web_searches * WEB_SEARCH_USD_PER_QUERY
    return token_cost + search_cost


def _run_one(
    *,
    variant: str,
    model: str,
    gene_symbol: str,
    replicate: int,
    truth_verdict: str,
    truth_class: str,
) -> RunRecord:
    cfg = VARIANTS[variant]
    system_prompt = _load_prompt(cfg["prompt"])

    if cfg["resolver"]:
        try:
            user_message = _resolve_task_text(gene_symbol)
        except Exception as exc:  # noqa: BLE001
            return RunRecord(
                variant=variant, model=model, gene_symbol=gene_symbol,
                replicate=replicate, truth_verdict=truth_verdict, truth_class=truth_class,
                predicted_verdict=None, predicted_reason=None, verdict_reasoning="",
                correct=False, prompt_tokens=0, completion_tokens=0, n_web_searches=0,
                cost_usd=0.0, latency_s=0.0, error=f"resolver failed: {exc}",
            )
    else:
        # Naive variants get only the bare gene symbol. No NCBI summary,
        # no HGNC family, no aliases.
        user_message = (
            f"Triage the human gene `{gene_symbol}`. Emit one "
            f"`TriageRecordDraft` JSON block as your final response. "
            f"You have {'one tool: web_search.' if cfg['web_search'] else 'no tools.'} "
            f"Reason from {'web evidence + your trained knowledge' if cfg['web_search'] else 'your trained knowledge'} "
            f"of this protein's biology."
        )

    started = time.monotonic()
    # Build kwargs; omit `tools` entirely for no-tool variants — the API
    # rejects `tools=None` with "Input should be a valid array".
    create_kwargs: dict[str, Any] = {
        "model": model,
        "max_tokens": 4096,
        "system": system_prompt,
        "messages": [{"role": "user", "content": user_message}],
    }
    if cfg["web_search"]:
        create_kwargs["tools"] = [WEB_SEARCH_TOOL]
    try:
        response = _client().messages.create(**create_kwargs)
    except Exception as exc:  # noqa: BLE001
        latency = time.monotonic() - started
        return RunRecord(
            variant=variant, model=model, gene_symbol=gene_symbol,
            replicate=replicate, truth_verdict=truth_verdict, truth_class=truth_class,
            predicted_verdict=None, predicted_reason=None, verdict_reasoning="",
            correct=False, prompt_tokens=0, completion_tokens=0, n_web_searches=0,
            cost_usd=0.0, latency_s=latency, error=f"messages.create: {exc}",
        )
    latency = time.monotonic() - started

    raw_text, n_searches = _extract_text(response)
    usage = getattr(response, "usage", None)
    prompt_tokens = getattr(usage, "input_tokens", 0) or 0
    completion_tokens = getattr(usage, "output_tokens", 0) or 0
    cost = _cost(model, prompt_tokens, completion_tokens, n_searches)

    parsed = _parse_json_response(raw_text)
    if parsed is None:
        return RunRecord(
            variant=variant, model=model, gene_symbol=gene_symbol,
            replicate=replicate, truth_verdict=truth_verdict, truth_class=truth_class,
            predicted_verdict=None, predicted_reason=None, verdict_reasoning="",
            correct=False, prompt_tokens=prompt_tokens, completion_tokens=completion_tokens,
            n_web_searches=n_searches, cost_usd=cost, latency_s=latency,
            error="could not parse JSON from response", raw_text=raw_text[:1000],
        )
    pred_v = parsed.get("verdict")
    pred_r = parsed.get("reason")
    reasoning = parsed.get("verdict_reasoning", "")
    correct = pred_v == truth_verdict
    return RunRecord(
        variant=variant, model=model, gene_symbol=gene_symbol,
        replicate=replicate, truth_verdict=truth_verdict, truth_class=truth_class,
        predicted_verdict=pred_v, predicted_reason=pred_r, verdict_reasoning=reasoning,
        correct=correct, prompt_tokens=prompt_tokens, completion_tokens=completion_tokens,
        n_web_searches=n_searches, cost_usd=cost, latency_s=latency,
    )


def _model_slug(model: str) -> str:
    return model.replace("claude-", "").replace("anthropic-", "")


def _persist(rec: RunRecord) -> Path:
    # Per-cell records are isolated by model so concurrent Haiku + Sonnet
    # runs don't clobber each other.
    out_dir = OUT_ROOT / _model_slug(rec.model) / rec.variant
    out_dir.mkdir(parents=True, exist_ok=True)
    path = out_dir / f"{rec.gene_symbol}_run{rec.replicate}.json"
    path.write_text(json.dumps(rec.__dict__, indent=2) + "\n")
    return path


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--model", default="claude-haiku-4-5",
                    choices=list(MODEL_PRICING.keys()),
                    help="Anthropic model id.")
    ap.add_argument("--replicates", type=int, default=2,
                    help="How many times to run each (variant, gene) cell.")
    ap.add_argument("--variants", nargs="+", default=list(VARIANTS.keys()),
                    choices=list(VARIANTS.keys()),
                    help="Which variants to run (default: all 4).")
    ap.add_argument("--genes", nargs="*", default=None,
                    help="Optional gene-symbol subset (default: full sub-benchmark).")
    ap.add_argument("--concurrency", type=int, default=8,
                    help="ThreadPoolExecutor workers.")
    ap.add_argument("--dry-run", action="store_true",
                    help="Print the planned cells and exit without API calls.")
    args = ap.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(message)s")

    with SUBBENCH_TSV.open() as f:
        rows = list(csv.DictReader(f, delimiter="\t"))
    if args.genes:
        rows = [r for r in rows if r["gene_symbol"] in set(args.genes)]
        if not rows:
            raise SystemExit(f"--genes {args.genes!r} matched no sub-benchmark rows")

    cells: list[tuple[str, dict, int]] = []
    for variant in args.variants:
        for row in rows:
            for rep in range(1, args.replicates + 1):
                cells.append((variant, row, rep))

    print(f"Sub-benchmark: {len(rows)} proteins × {len(args.variants)} variants × "
          f"{args.replicates} replicates = {len(cells)} cells")
    print(f"Model: {args.model}")
    print(f"Output: {OUT_ROOT}")
    print()

    if args.dry_run:
        print("DRY RUN — printing planned cells, not calling API.")
        for variant, row, rep in cells[:20]:
            print(f"  {variant:10s}  {row['gene_symbol']:10s}  run{rep}")
        if len(cells) > 20:
            print(f"  ... + {len(cells) - 20} more")
        return

    results: list[RunRecord] = []
    start = time.monotonic()
    with ThreadPoolExecutor(max_workers=args.concurrency) as ex:
        futures = {
            ex.submit(
                _run_one,
                variant=v, model=args.model, gene_symbol=row["gene_symbol"],
                replicate=rep, truth_verdict=row["ground_truth_verdict"],
                truth_class=row["class"],
            ): (v, row["gene_symbol"], rep)
            for (v, row, rep) in cells
        }
        for i, fut in enumerate(as_completed(futures), start=1):
            rec = fut.result()
            _persist(rec)
            results.append(rec)
            marker = "✓" if rec.correct else ("✗" if rec.error is None else "!")
            err = f"  ERR={rec.error}" if rec.error else ""
            print(f"  [{i:3d}/{len(cells)}] {marker} {rec.variant:10s}  {rec.gene_symbol:10s}  "
                  f"r{rec.replicate}  truth={rec.truth_verdict:11s}  pred={rec.predicted_verdict or '—':12s}  "
                  f"reason={rec.predicted_reason or '—':30s}  ${rec.cost_usd:.4f}  {rec.latency_s:5.1f}s{err}")
    wall = time.monotonic() - start
    print(f"\nWallclock: {wall:.1f}s")
    print()

    # Per-variant summary.
    print(f"{'variant':12s}  {'n':4s}  {'acc':8s}  {'cost':10s}  {'mean_lat':10s}  {'mean_web':10s}")
    print("-" * 70)
    for variant in args.variants:
        sub = [r for r in results if r.variant == variant]
        if not sub:
            continue
        n = len(sub)
        acc = sum(1 for r in sub if r.correct) / n
        cost = sum(r.cost_usd for r in sub)
        lat = sum(r.latency_s for r in sub) / n
        wsearch = sum(r.n_web_searches for r in sub) / n
        print(f"  {variant:10s}  {n:4d}  {acc:6.1%}  ${cost:8.3f}  {lat:7.1f}s    {wsearch:5.1f}")

    print()
    print(f"TOTAL COST: ${sum(r.cost_usd for r in results):.3f}")


if __name__ == "__main__":
    main()
