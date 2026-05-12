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

    # Single model:
    uv run python scripts/triage_subbench_runner.py --model claude-haiku-4-5 --replicates 2

    # All three models in one shot (shared thread pool, single cost report):
    uv run python scripts/triage_subbench_runner.py \\
        --model claude-haiku-4-5 claude-sonnet-4-6 claude-opus-4-7 --replicates 2

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
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from anthropic import Anthropic

from accessible_surfaceome.agents._support import client as _client_module
from accessible_surfaceome.agents.surface_triage.orchestrator import _render_task
from accessible_surfaceome.env import load_env
from accessible_surfaceome.tools._shared.http import open_default_client
from accessible_surfaceome.tools.gene_lookup import resolve

logger = logging.getLogger(__name__)
ROOT = Path("/Users/rebeccacarlson/Git/accessible-surfaceome/.claude/worktrees/optimistic-goldwasser-ea19aa")
BENCH_TSV_BY_NAME = {
    "subbench": (ROOT / "data/eval/triage_subbench_v1.tsv", ROOT / "data/eval/triage_subbench_v1"),
    "benchmark": (ROOT / "data/eval/triage_benchmark_v1.tsv", ROOT / "data/eval/triage_bench_v1"),
}
# Defaults — overridable via --bench. Kept as module-level globals because
# _persist() reads OUT_ROOT and we want a single source of truth.
SUBBENCH_TSV = BENCH_TSV_BY_NAME["subbench"][0]
OUT_ROOT = BENCH_TSV_BY_NAME["subbench"][1]
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
    predicted_confidence: str | None = None
    predicted_key_uncertainty: str | None = None
    cache_creation_tokens: int = 0
    cache_read_tokens: int = 0
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


def _cost(
    model: str,
    prompt_tokens: int,
    completion_tokens: int,
    n_web_searches: int,
    cache_creation_tokens: int = 0,
    cache_read_tokens: int = 0,
) -> float:
    """Total $ cost for one API call.

    Anthropic prompt caching pricing (as of 2026-Q1):
      * `cache_creation_input_tokens` — billed at 1.25× the base input rate
        (the system prompt being written to the cache).
      * `cache_read_input_tokens` — billed at 0.10× the base input rate
        (cache hits — every call after the first within the 5-min TTL).
      * `input_tokens` (what the SDK calls just "input") excludes both
        cache fields, so we add them as separate weighted components.
    """
    in_price, out_price = MODEL_PRICING.get(model, (0.0, 0.0))
    uncached_in = prompt_tokens * in_price
    cache_write = cache_creation_tokens * in_price * 1.25
    cache_read = cache_read_tokens * in_price * 0.10
    output = completion_tokens * out_price
    token_cost = (uncached_in + cache_write + cache_read + output) / 1_000_000
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
    #
    # Prompt caching: mark the system prompt as ephemeral so it's billed
    # at 1.25× input on first call but 0.10× input on subsequent calls
    # within the 5-minute cache TTL. For our sweeps (147+ calls landing
    # within seconds of each other), every call after the first reads
    # the cached 1.8-2K-token system prompt at a 90% discount. Also
    # helps inside multi-turn tool-use loops (web_search variants),
    # which re-include the system prompt on every turn.
    #
    # Per Anthropic's pricing, cache hits on Sonnet save ~$0.005 per
    # call; Haiku saves ~$0.0008. Free, no behaviour change.
    create_kwargs: dict[str, Any] = {
        "model": model,
        "max_tokens": 4096,
        "system": [
            {
                "type": "text",
                "text": system_prompt,
                "cache_control": {"type": "ephemeral"},
            }
        ],
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
    # Prompt-caching fields — non-zero only when the request marks
    # parts of the prompt with cache_control. `input_tokens` excludes
    # both cache fields, so we count them separately at their tier rates.
    cache_creation_tokens = getattr(usage, "cache_creation_input_tokens", 0) or 0
    cache_read_tokens = getattr(usage, "cache_read_input_tokens", 0) or 0
    cost = _cost(
        model, prompt_tokens, completion_tokens, n_searches,
        cache_creation_tokens=cache_creation_tokens,
        cache_read_tokens=cache_read_tokens,
    )

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
    pred_c = parsed.get("confidence")
    pred_ku = parsed.get("key_uncertainty")
    reasoning = parsed.get("verdict_reasoning", "")
    # yes/contextual are equivalent for accuracy accounting (a
    # tissue/state-restricted hit is operationally the same as a
    # ubiquitous one); `no` is only correct against `no`. A missing
    # prediction is never correct, even if truth is also missing —
    # otherwise a parse failure on a None-truth gene would silently
    # score as a hit.
    _POSITIVE = {"yes", "contextual"}
    correct = (
        pred_v is not None
        and truth_verdict is not None
        and (
            pred_v == truth_verdict
            or (pred_v in _POSITIVE and truth_verdict in _POSITIVE)
        )
    )
    return RunRecord(
        variant=variant, model=model, gene_symbol=gene_symbol,
        replicate=replicate, truth_verdict=truth_verdict, truth_class=truth_class,
        predicted_verdict=pred_v, predicted_reason=pred_r,
        predicted_confidence=pred_c, predicted_key_uncertainty=pred_ku,
        verdict_reasoning=reasoning,
        correct=correct, prompt_tokens=prompt_tokens, completion_tokens=completion_tokens,
        n_web_searches=n_searches, cost_usd=cost, latency_s=latency,
        cache_creation_tokens=cache_creation_tokens,
        cache_read_tokens=cache_read_tokens,
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


def _commit_record(rec: RunRecord, sink: Any | None) -> str:
    """Persist a completed run record.

    Two modes:

    * **No D1 sink** — write the per-cell JSON under ``OUT_ROOT/`` as
      before. Returns "".

    * **D1 sink configured** — write to D1 first. On success, skip the
      local JSON write (D1 is canonical; local copies are clutter at
      genome-wide scale — 13,918 cells × ~3KB = ~42MB of throwaway files).
      On D1 failure, fall back to local JSON so we don't lose the cell —
      the batch uploader can replay it later. Returns ``"  d1=✓"`` or
      ``"  d1=✗(local-fallback)"``.

    Trade-off: under happy-path --d1 you can't grep the local JSON tree
    for results; everything lives in D1. That's the design intent —
    query via ``SELECT ... FROM triage_run``, not ``find data/eval/``.
    """
    if sink is None:
        _persist(rec)
        return ""
    ok = sink.insert(rec.__dict__)
    if ok:
        return "  d1=✓"
    # D1 hiccup — preserve the cell locally so it can be re-uploaded.
    _persist(rec)
    return "  d1=✗(local-fallback)"


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--model", nargs="+", default=["claude-haiku-4-5"],
                    choices=list(MODEL_PRICING.keys()),
                    help="Anthropic model id(s). Pass multiple to run all in one "
                         "invocation under a shared thread pool — outputs separate "
                         "per-model directories under data/eval/triage_subbench_v1/.")
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
    ap.add_argument("--bench", choices=list(BENCH_TSV_BY_NAME.keys()), default="subbench",
                    help="Which benchmark to run: 'subbench' (17 persistent-error genes) "
                         "or 'benchmark' (full 147-gene triage_benchmark_v1). Ignored "
                         "when --gene-list is provided.")
    ap.add_argument("--gene-list", default=None,
                    help="Path to a TSV with at least a 'gene_symbol' column — runs "
                         "the triage agent on every gene listed, with no ground truth. "
                         "Use for genome-wide / unlabeled sweeps (e.g. "
                         "data/processed/whole_genome_minus_m1.tsv). Overrides --bench. "
                         "When set, --out-root defaults to "
                         "data/eval/triage_<basename>_v1/ unless explicitly overridden.")
    ap.add_argument("--out-root", default=None,
                    help="Directory for per-cell JSON records. Default: derived from "
                         "--bench or --gene-list.")
    ap.add_argument("--d1", action="store_true",
                    help="Stream each completed cell to the surfaceome_agents D1 "
                         "database in real time. Requires CLOUDFLARE_* env vars in "
                         ".env (see cloudflare/README.md). The JSON write under "
                         "data/eval/triage_*_v1/ remains the canonical record; "
                         "the D1 mirror is for live dashboards + dropping the "
                         "batch-upload step.")
    ap.add_argument("--run-id", default=None,
                    help="Tag for this sweep in D1's triage_run.run_id column. "
                         "Default: a fresh uuid. Only meaningful with --d1.")
    args = ap.parse_args()

    global SUBBENCH_TSV, OUT_ROOT
    if args.gene_list:
        # Unlabeled sweep — the "input TSV" is the gene-list itself.
        SUBBENCH_TSV = Path(args.gene_list)
        if not SUBBENCH_TSV.exists():
            raise SystemExit(f"--gene-list path does not exist: {SUBBENCH_TSV}")
        # Derive out-root from the gene-list filename (drop .tsv suffix).
        default_out = ROOT / "data" / "eval" / f"triage_{SUBBENCH_TSV.stem}_v1"
        OUT_ROOT = Path(args.out_root) if args.out_root else default_out
    else:
        SUBBENCH_TSV, OUT_ROOT = BENCH_TSV_BY_NAME[args.bench]
        if args.out_root:
            OUT_ROOT = Path(args.out_root)

    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(message)s")
    # Pull ANTHROPIC_API_KEY (and NCBI_API_KEY if present) from repo-root
    # .env so a freshly-bootstrapped worktree picks them up without a shell
    # export. Same precedence rules as the main CLI — see env.py.
    load_env()

    with SUBBENCH_TSV.open() as f:
        rows = list(csv.DictReader(f, delimiter="\t"))
    if not rows:
        raise SystemExit(f"{SUBBENCH_TSV} has no data rows")
    if "gene_symbol" not in rows[0]:
        raise SystemExit(f"{SUBBENCH_TSV} missing required 'gene_symbol' column")
    if args.genes:
        rows = [r for r in rows if r["gene_symbol"] in set(args.genes)]
        if not rows:
            raise SystemExit(f"--genes {args.genes!r} matched no input rows")

    # Gene-list inputs don't have truth fields; default to empty strings so
    # _run_one's signature is happy and `correct` resolves to False (no
    # truth to match against).
    for r in rows:
        r.setdefault("ground_truth_verdict", "")
        r.setdefault("class", "")

    cells: list[tuple[str, str, dict, int]] = []
    for model in args.model:
        for variant in args.variants:
            for row in rows:
                for rep in range(1, args.replicates + 1):
                    cells.append((variant, model, row, rep))

    sweep_label = "Gene-list" if args.gene_list else f"{args.bench.capitalize()} bench"
    print(f"{sweep_label}: {len(rows)} proteins × {len(args.variants)} variants × "
          f"{args.replicates} replicates × {len(args.model)} model(s) = {len(cells)} cells")
    print(f"Input:   {SUBBENCH_TSV}")
    print(f"Models:  {', '.join(args.model)}")
    print(f"Output:  {OUT_ROOT}")
    if args.gene_list:
        print("Note:    unlabeled sweep — `correct` will be False for every cell")
    print()

    if args.dry_run:
        print("DRY RUN — printing planned cells, not calling API.")
        for variant, model, row, rep in cells[:20]:
            print(f"  {model:18s}  {variant:10s}  {row['gene_symbol']:10s}  run{rep}")
        if len(cells) > 20:
            print(f"  ... + {len(cells) - 20} more")
        return

    # Optional D1 streaming sink — initialized once before the worker
    # pool so prompts + benchmark snapshot are interned exactly once.
    d1_sink = None
    if args.d1:
        import uuid as _uuid
        from accessible_surfaceome.cloud.triage_upload import D1RunSink
        run_id = args.run_id or f"{datetime.now(UTC).strftime('%Y-%m-%dT%H%M%SZ')}_{_uuid.uuid4().hex[:8]}"
        d1_sink = D1RunSink(run_id=run_id, bench_tsv=SUBBENCH_TSV)
        print(f"D1 streaming enabled: run_id={d1_sink.run_id}  bench_version={d1_sink.bench_version}")
        print()

    results: list[RunRecord] = []
    start = time.monotonic()
    with ThreadPoolExecutor(max_workers=args.concurrency) as ex:
        futures = {
            ex.submit(
                _run_one,
                variant=v, model=m, gene_symbol=row["gene_symbol"],
                replicate=rep, truth_verdict=row["ground_truth_verdict"],
                truth_class=row["class"],
            ): (v, m, row["gene_symbol"], rep)
            for (v, m, row, rep) in cells
        }
        for i, fut in enumerate(as_completed(futures), start=1):
            rec = fut.result()
            d1_tag = _commit_record(rec, d1_sink)
            results.append(rec)
            marker = "✓" if rec.correct else ("✗" if rec.error is None else "!")
            err = f"  ERR={rec.error}" if rec.error else ""
            print(f"  [{i:3d}/{len(cells)}] {marker} {_model_slug(rec.model):14s} {rec.variant:10s}  {rec.gene_symbol:10s}  "
                  f"r{rec.replicate}  truth={rec.truth_verdict:11s}  pred={rec.predicted_verdict or '—':12s}  "
                  f"reason={rec.predicted_reason or '—':30s}  ${rec.cost_usd:.4f}  {rec.latency_s:5.1f}s{d1_tag}{err}")

    if d1_sink is not None:
        d1_sink.close()
    wall = time.monotonic() - start
    print(f"\nWallclock: {wall:.1f}s")
    print()

    # Per-(model, variant) summary.
    print(f"{'model':16s} {'variant':12s}  {'n':4s}  {'acc':8s}  {'cost':10s}  {'mean_lat':10s}  {'mean_web':10s}")
    print("-" * 90)
    for model in args.model:
        for variant in args.variants:
            sub = [r for r in results if r.variant == variant and r.model == model]
            if not sub:
                continue
            n = len(sub)
            acc = sum(1 for r in sub if r.correct) / n
            cost = sum(r.cost_usd for r in sub)
            lat = sum(r.latency_s for r in sub) / n
            wsearch = sum(r.n_web_searches for r in sub) / n
            print(f"  {_model_slug(model):14s} {variant:10s}  {n:4d}  {acc:6.1%}  ${cost:8.3f}  {lat:7.1f}s    {wsearch:5.1f}")

    # Per-model totals.
    print()
    for model in args.model:
        sub = [r for r in results if r.model == model]
        if not sub:
            continue
        print(f"  {_model_slug(model):14s} total: ${sum(r.cost_usd for r in sub):.3f}  "
              f"(n={len(sub)}, {sum(1 for r in sub if r.correct)/len(sub):.1%} verdict-correct)")

    print()
    print(f"GRAND TOTAL COST: ${sum(r.cost_usd for r in results):.3f}")


if __name__ == "__main__":
    main()
