"""Run the triage agent over a benchmark, sub-bench, or arbitrary gene list.

The triage agent answers a single binary question — is this protein
plausibly cell-surface in the way most therapeutics care about? — under
4 prompt variants:

  1. naive      — system_naive.md         (no resolver, no tools)
  2. ncbi       — system.md               (resolver only, no tools)
  3. web_naive  — system_web_naive.md     (web_search, no resolver)
  4. web_ncbi   — system_web.md           (web_search + resolver)

This script runs all (variant × model × gene × replicate) cells in
parallel and streams results both to per-cell JSON on disk and to D1's
``triage_run`` via :class:`D1RunSink`.

Input modes (mutually exclusive):

  * ``--bench benchmark`` (default) — 147-row labeled mainbench at
    ``data/eval/triage_benchmark_v1.tsv`` (the source of truth for
    the cost-vs-accuracy figures).
  * ``--gene-list <path>`` — arbitrary TSV with a ``gene_symbol``
    column. Used for genome-scale sweeps (e.g.
    ``data/processed/whole_genome_minus_m1.tsv``).

The 17-row sub-bench was retired on 2026-05-16 — the bench TSV +
output tree (``data/eval/triage_subbench_v1*``) were dropped from
the repo. The 4-variant × 3-model matrix that made the sub-bench
useful is now exercised against the 147-row mainbench instead.

CANONICAL PRODUCTION SWEEP: ``run_id=genome_full_sonnet_ncbi_v2``,
``model=claude-sonnet-4-6``, ``variant=ncbi``. This is the sweep that
backs the catalog's triage column and feeds the v2 deep-dive's
``_load_triage_record`` input — i.e., what "the triage" means when
the production pipeline refers to it. The constants
:data:`CANONICAL_TRIAGE_MODEL` and :data:`CANONICAL_TRIAGE_RUN_ID`
below are the single grep target for that attribution. The triage
agent is NOT a Managed Agent: this runner invokes the model directly
via :class:`anthropic.Anthropic`'s ``messages.create`` with prompts
loaded from :data:`PROMPTS_DIR`.

USAGE — note this script does NOT auto-execute. Invoke directly:

    # Production-shape run (single model, canonical variant):
    uv run python scripts/triage_runner.py --model claude-sonnet-4-6 --variants ncbi --replicates 1

    # Single model, cheap-tier sanity check:
    uv run python scripts/triage_runner.py --model claude-haiku-4-5 --replicates 2

    # All three model tiers in one shot (shared thread pool, single cost report):
    uv run python scripts/triage_runner.py \\
        --model claude-sonnet-4-6 claude-haiku-4-5 claude-opus-4-7 --replicates 2

For a smoke test of one variant on one gene:

    uv run python scripts/triage_runner.py \\
        --model claude-sonnet-4-6 --replicates 1 \\
        --variants naive --genes HSPA1A

CANONICAL BENCH SCOPE (run_id=mainbench_canonical_v1, bench_version
fc7ddee89155, replicate 1). The model × variant matrix is intentionally
ragged — not every model runs every variant:

  * claude-sonnet-4-6 — naive, ncbi, web_ncbi, pubmed_ncbi (the
    headline model; full variant spread; matches production triage).
  * claude-haiku-4-5  — naive, ncbi, web_ncbi, pubmed_ncbi (the
    cheap-model comparison).
  * claude-opus-4-7 / claude-opus-4-8 — naive + ncbi ONLY, by design.
    Opus is the accuracy ceiling probe; the web/pubmed-augmented
    variants exist to lift *weaker* models toward Opus-without-tools,
    so running them on Opus would be redundant and (at $15/$75 per MTok)
    not worth the spend. Extend deliberately if that changes.

To extend or gap-fill an existing run without drifting its
bench_version, pin the bench content with --bench-tsv (see below).
"""

from __future__ import annotations

import argparse
import csv
import json
import logging
import threading
import time
import uuid as _uuid
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from anthropic import Anthropic

from accessible_surfaceome.agents._support import client as _client_module
from accessible_surfaceome.agents.surface_triage.task import render_task as _render_task
from accessible_surfaceome.env import load_env
from accessible_surfaceome.tools._shared.http import open_default_client
from accessible_surfaceome.tools.gene_lookup import resolve, resolve_by_hgnc_id

logger = logging.getLogger(__name__)
# Repo root, derived from this file's location (scripts/triage_runner.py →
# parents[1]). Must NOT be a hardcoded absolute path: the runner is invoked
# from agent-created worktrees, and a pinned path silently read the bench
# TSV + prompts + wrote outputs into a *different* worktree.
ROOT = Path(__file__).resolve().parents[1]
BENCH_TSV_BY_NAME = {
    "benchmark": (ROOT / "data/eval/triage_benchmark_v1.tsv", ROOT / "data/eval/triage_bench_v1"),
}
# Defaults — overridable via --bench or --gene-list. Module-level globals
# because _persist() reads OUT_ROOT and we want a single source of truth.
BENCH_TSV = BENCH_TSV_BY_NAME["benchmark"][0]
OUT_ROOT = BENCH_TSV_BY_NAME["benchmark"][1]
PROMPTS_DIR = ROOT / "src/accessible_surfaceome/agents/surface_triage/prompts"

# Canonical production triage attribution. Single grep target — used by
# downstream scripts (audit_v2_deterministic_coverage.py, build_universe_v2,
# zero_db_rescues_by_triage, etc.) and referenced from CLAUDE.md. Bump when
# the production sweep moves; the surface_triage docstring + the prompt-
# review HTML's "Prereq" card both rely on this being correct.
CANONICAL_TRIAGE_MODEL = "claude-sonnet-4-6"
CANONICAL_TRIAGE_RUN_ID = "genome_full_sonnet_ncbi_v2"

# Per-million-token list pricing for input + output. Update as Anthropic
# adjusts. Web search is billed separately at $10 / 1000 searches across
# all Claude models. Ordered with the canonical production model first so
# a reader scanning the dict sees the right answer up top.
MODEL_PRICING: dict[str, tuple[float, float]] = {
    "claude-sonnet-4-6": (3.0, 15.0),   # canonical production triage model
    "claude-haiku-4-5":  (1.0, 5.0),
    "claude-opus-4-7":   (15.0, 75.0),
    "claude-opus-4-8":   (15.0, 75.0),  # same list price as 4-7
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
    # All 5 variants now use the slim-style prompt body — same verdict
    # logic, same reason enums, same Pre-`no` framing. They only differ
    # in the per-variant "tools / context" paragraph at the top of each
    # prompt. The pre-2026-05 long-form prompts were promoted to the
    # slim style on 2026-05-11 (commit `next` — see git log).
    "naive":     {"prompt": "system_naive.md",     "resolver": False, "web_search": False},
    "ncbi":      {"prompt": "system.md",            "resolver": True,  "web_search": False},
    "web_naive": {"prompt": "system_web_naive.md", "resolver": False, "web_search": True},
    "web_ncbi":  {"prompt": "system_web.md",        "resolver": True,  "web_search": True},
    # Cost-reduced variant of web_ncbi. Same prompt (system_web.md) as
    # web_ncbi — only API-level knobs change:
    #   * max_uses=2 on the web_search tool (hard cap, was 4).
    #   * max_tokens=2048 per turn (was 4096) to bound runaway output.
    # Prompt is intentionally unmodified so the comparison isolates the
    # effect of the API caps alone.
    "web_ncbi_reduced": {
        "prompt": "system_web.md",
        "resolver": True, "web_search": True,
        "max_tokens": 2048, "web_max_uses": 2,
    },
    # PubMed evidence variant: NCBI resolver + relevance-ranked PubMed
    # esearch (gene × surface terms) + efetch abstracts, sentence-filtered
    # to those mentioning both the gene and a surface keyword. No
    # web_search tool — all literature evidence is pre-fetched and
    # injected into the task message before the LLM call.
    "pubmed_ncbi": {
        "prompt": "system_pubmed.md",
        "resolver": True, "web_search": False,
        "pubmed_evidence": True,
    },
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
    # Provenance — full inputs the agent saw. SHA-versioning happens at
    # upload time (see triage_upload._intern_resolver_context).
    user_message: str = ""
    # Decoding params — record explicitly so a future runner-default
    # tweak doesn't silently change historical comparability.
    temperature: float | None = None
    top_p: float | None = None
    max_tokens: int | None = None
    # Anthropic API response metadata.
    api_response_id: str | None = None
    api_stop_reason: str | None = None
    api_model: str | None = None
    # One entry per tool call (web_search / pubmed_lookup / etc.):
    # {"step_index": int, "tool": str, "query": str|None,
    #  "n_results": int|None, "top_results": list[dict]|None}
    search_log: list[dict] = field(default_factory=list)


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


def _resolve_task_text(
    gene: str,
    hgnc_id: str | None = None,
    uniprot_acc: str | None = None,
) -> str:
    """Use the orchestrator's _render_task to format the task message
    with HGNC + UniProt + NCBI + gene-group + CD designation context.

    Stable-identifier-keyed only. Symbol fallback was removed in
    resolver v3 — the legacy symbol-keyed path silently returned
    wrong-protein context for ~0.2% of cohort genes (see CLAUDE.md
    "Gene identifier resolution").

    Argument priority (most stable → least stable):
      1. **hgnc_id** — preferred. Cohort TSVs carry it for every
         row (100% coverage).
      2. **uniprot_acc** — used when hgnc_id is absent. Benchmark
         TSVs (`triage_benchmark_v1.tsv` etc.) historically carry
         uniprot_acc, not hgnc_id, so this path keeps bench reruns
         working without re-shaping their input TSV.

    Raises LookupError when neither identifier is supplied. Cohort
    rows missing hgnc_id usually indicate a stale cohort TSV — the
    fix is to regenerate the cohort, not to fall back to symbol
    search.
    """
    if hgnc_id:
        bundle = resolve_by_hgnc_id(hgnc_id, http=_http())
        return _render_task(bundle)
    if uniprot_acc:
        bundle = resolve(uniprot_acc, http=_http())
        return _render_task(bundle)
    raise LookupError(
        f"_resolve_task_text({gene!r}) called without hgnc_id OR uniprot_acc — "
        "symbol-only resolution was removed in resolver v3. The input row "
        "must supply at least one stable identifier; if a bench TSV is "
        "missing both, regenerate it from a stable-ID source."
    )


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


def _extract_text(response: Any) -> tuple[str, int, list[dict]]:
    """Collect text content, count web_search tool uses, AND assemble a
    structured search log from interleaved server_tool_use and
    web_search_tool_result blocks.

    Anthropic streams these as a paired sequence:

        ... server_tool_use(name=web_search, input={"query": ...}) ...
        ... web_search_tool_result(content=[{title, url, page_age, ...}, ...]) ...

    We collect them in order and pair adjacent (use, result) blocks.
    The result content is truncated per-entry to keep persisted records
    compact (~1KB per entry: title + URL + 240-char snippet).
    """
    parts: list[str] = []
    n_searches = 0
    search_uses: list[dict] = []
    last_use_idx: int | None = None

    for block in getattr(response, "content", []) or []:
        btype = getattr(block, "type", None)
        if btype == "text":
            txt = getattr(block, "text", None)
            if isinstance(txt, str):
                parts.append(txt)
        elif btype == "server_tool_use":
            tool_name = getattr(block, "name", "") or ""
            if tool_name == "web_search":
                n_searches += 1
                inp = getattr(block, "input", None) or {}
                if not isinstance(inp, dict):
                    inp = {}
                search_uses.append({
                    "step_index": len(search_uses),
                    "tool": "web_search",
                    "query": inp.get("query"),
                    "n_results": None,
                    "top_results": None,
                })
                last_use_idx = len(search_uses) - 1
        elif btype == "web_search_tool_result" and last_use_idx is not None:
            results = getattr(block, "content", []) or []
            normed: list[dict] = []
            try:
                iterable = results if isinstance(results, list) else []
            except Exception:  # noqa: BLE001
                iterable = []
            for r in iterable[:5]:  # cap at 5 results / search to bound row size
                title = getattr(r, "title", None) or (r.get("title") if isinstance(r, dict) else None)
                url = getattr(r, "url", None) or (r.get("url") if isinstance(r, dict) else None)
                text = getattr(r, "encrypted_content", None) or getattr(r, "snippet", None)
                if text is None and isinstance(r, dict):
                    text = r.get("snippet") or r.get("encrypted_content")
                if isinstance(text, str) and len(text) > 240:
                    text = text[:240] + "…"
                normed.append({"title": title, "url": url, "snippet": text})
            search_uses[last_use_idx]["n_results"] = len(normed)
            search_uses[last_use_idx]["top_results"] = normed
            last_use_idx = None

    return "\n".join(parts), n_searches, search_uses


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
    hgnc_id: str | None = None,
    uniprot_acc: str | None = None,
) -> RunRecord:
    cfg = VARIANTS[variant]
    system_prompt = _load_prompt(cfg["prompt"])

    if cfg["resolver"]:
        try:
            user_message = _resolve_task_text(
                gene_symbol, hgnc_id=hgnc_id, uniprot_acc=uniprot_acc,
            )
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

    # Pre-fetch and inject surface-context literature evidence for the
    # `pubmed_ncbi` variant. Quiet on failure — the agent still has the
    # resolver context and its trained knowledge to fall back on.
    if cfg.get("pubmed_evidence"):
        from accessible_surfaceome.tools.pubmed_lookup import (
            get_surface_evidence, render_evidence_block,
        )
        try:
            records = get_surface_evidence(gene_symbol, max_results=8)
            if records:
                user_message = (
                    user_message.rstrip()
                    + "\n\n"
                    + render_evidence_block(records)
                )
        except Exception as exc:  # noqa: BLE001
            logging.warning("pubmed evidence fetch failed for %s: %s", gene_symbol, exc)

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
        # Per-variant override for cost-reduced runs (e.g. web_ncbi_reduced
        # halves the per-turn output budget to 2048 to cut the dominant
        # output-token cost on Sonnet/Opus).
        "max_tokens": cfg.get("max_tokens", 4096),
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
        # Per-variant override for max_uses (hard ceiling on web search
        # calls; the prompt also asks for at most 1, but the API enforces).
        web_tool = dict(WEB_SEARCH_TOOL)
        if "web_max_uses" in cfg:
            web_tool["max_uses"] = cfg["web_max_uses"]
        create_kwargs["tools"] = [web_tool]
    # Snapshot the decoding params we'll send so they land in the
    # persisted record even on the error path below.
    decode_params = {
        "temperature": create_kwargs.get("temperature"),
        "top_p": create_kwargs.get("top_p"),
        "max_tokens": create_kwargs.get("max_tokens"),
    }
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
            user_message=user_message, **decode_params,
        )
    latency = time.monotonic() - started

    raw_text, n_searches, search_log = _extract_text(response)
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

    # Anthropic response metadata — small, durable, joinable.
    api_meta = {
        "api_response_id": getattr(response, "id", None),
        "api_stop_reason": getattr(response, "stop_reason", None),
        "api_model":       getattr(response, "model", None),
    }

    parsed = _parse_json_response(raw_text)
    if parsed is None:
        return RunRecord(
            variant=variant, model=model, gene_symbol=gene_symbol,
            replicate=replicate, truth_verdict=truth_verdict, truth_class=truth_class,
            predicted_verdict=None, predicted_reason=None, verdict_reasoning="",
            correct=False, prompt_tokens=prompt_tokens, completion_tokens=completion_tokens,
            n_web_searches=n_searches, cost_usd=cost, latency_s=latency,
            error="could not parse JSON from response", raw_text=raw_text[:1000],
            user_message=user_message, search_log=search_log,
            cache_creation_tokens=cache_creation_tokens,
            cache_read_tokens=cache_read_tokens,
            **decode_params, **api_meta,
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
        user_message=user_message, search_log=search_log,
        **decode_params, **api_meta,
    )


# Error substrings that indicate a transient or retryable failure.
# When ``_run_one`` returns a record whose ``error`` field matches any
# of these AND ``predicted_verdict`` is null, the wrapper tries the
# call once more before giving up. Catches:
#   * stochastic JSON malformations the parser couldn't recover from
#   * resolver 404s that the resolver's own symbol-search fallback
#     might race against an upstream rate-limit window
#   * generic API errors (rate limits, transient network)
_RETRYABLE_ERROR_PATTERNS: tuple[str, ...] = (
    "could not parse JSON from response",
    "404 Not Found",
    "resolver failed:",
    "messages.create:",
)

# Resolver-LookupError sub-pattern: when the resolver raises with
# "out of study scope", the gene symbol fundamentally has no human
# reviewed UniProt entry (deprecated HGNC symbol, withdrawn entry,
# etc.). These are NOT transient — retrying just wastes UniProt
# round-trips. Carve this out of the generic ``resolver failed:``
# bucket so the wrapper short-circuits to a NULL D1 row in one shot.
_RESOLVER_NONRETRYABLE_PATTERN = "out of study scope"

# Schema validity: each verdict literal allows a small set of `reason`
# literals. Mirrors ``_REASONS_BY_VERDICT`` in
# accessible_surfaceome.tools._shared.models.TriageRecordDraft —
# duplicated here so the runner can reject mismatched emissions before
# they reach D1, and trigger an automatic retry. Keep in sync with the
# Pydantic schema; the prompt-parity test catches the most common
# drift by fingerprinting each reason enum line.
_VALID_VERDICTS: frozenset[str] = frozenset({"yes", "contextual", "no"})
_REASONS_BY_VERDICT: dict[str, frozenset[str]] = {
    "yes": frozenset({
        "classical_surface_receptor", "gpi_anchored",
        "multipass_with_exposed_loops", "extracellular_face_protein",
        "stable_complex_partner", "other",
    }),
    "contextual": frozenset({
        "cell_state_induced", "tissue_restricted_surface",
        "lysosomal_exocytosis", "dual_localization",
        "stable_surface_attachment", "other",
    }),
    "no": frozenset({
        "cytoplasmic", "nuclear", "mitochondrial_internal",
        "endomembrane_resident", "nuclear_envelope",
        "inner_leaflet_anchored", "secreted_only",
        "pmhc_only_intracellular", "other",
    }),
}


def _is_schema_valid(verdict: str | None, reason: str | None) -> bool:
    """Mirror of TriageRecordDraft._check_reason_matches_verdict."""
    if verdict not in _VALID_VERDICTS:
        return False
    return reason in _REASONS_BY_VERDICT[verdict]


def _is_retryable(rec: "RunRecord") -> bool:
    """A record is retryable if:
      (a) ``predicted_verdict`` is null AND ``error`` matches a known
          transient pattern (parse failure, resolver 404, API error), OR
      (b) ``predicted_verdict`` is set but the ``(verdict, reason)``
          combo violates the Pydantic schema's per-verdict reason
          enumeration. A fresh model sample often emits a self-
          consistent combo on the second try.

    Refusal-stop-reason records are NOT retried — those are stable
    safety-classifier blocks (see CTXN1/FBRS on
    genome_full_sonnet_ncbi_v1) and another sample just refuses again.
    """
    # Schema mismatch: model emitted a valid-looking record that
    # violates the Pydantic verdict↔reason constraint.
    if rec.predicted_verdict is not None and not _is_schema_valid(
        rec.predicted_verdict, rec.predicted_reason
    ):
        return True

    # Null verdict: only retry on known transient error patterns.
    if rec.predicted_verdict is None:
        err = rec.error or ""
        # Resolver-out-of-study-scope is a stable, structural miss —
        # the symbol has no reviewed human UniProt entry and never
        # will under the current resolver. Don't burn retries on it.
        if _RESOLVER_NONRETRYABLE_PATTERN in err:
            return False
        if any(pat in err for pat in _RETRYABLE_ERROR_PATTERNS):
            return True

    return False


def _run_one_with_retry(
    *,
    variant: str,
    model: str,
    gene_symbol: str,
    replicate: int,
    truth_verdict: str,
    truth_class: str,
    hgnc_id: str | None = None,
    uniprot_acc: str | None = None,
) -> RunRecord:
    """``_run_one`` with one automatic retry for transient failures
    or schema-mismatch emissions, plus a refusal-fallback to the
    ``naive`` variant.

    Three retry / fallback triggers:
      * **Null verdict + transient error** (parse failure, resolver
        404, generic API error) → re-issue with the same variant.
      * **Schema-mismatch emission** (verdict/reason combo violates
        the Pydantic constraint, e.g. ``no + multipass_with_exposed_loops``)
        → re-issue with the same variant. A fresh sample usually
        emits a self-consistent combo.
      * **Anthropic refusal** (``stop_reason='refusal'``) on a
        resolver-context variant → fall back to the ``naive``
        variant. Empirically (CTXN1, FBRS in the 2026-05 genome-wide
        sweep), the refusal trigger lives in the resolver-injected
        task message; the naive prompt's bare gene symbol routes
        around it. The returned record carries ``variant='naive'``
        so audit queries can identify cells where the fallback fired.

    Refusals on the naive variant are NOT further retried — those
    really do refuse on the symbol alone.
    """

    first = _run_one(
        variant=variant, model=model, gene_symbol=gene_symbol,
        replicate=replicate, truth_verdict=truth_verdict, truth_class=truth_class,
        hgnc_id=hgnc_id, uniprot_acc=uniprot_acc,
    )

    # Refusal fallback: when a resolver-context variant gets refused,
    # try the naive variant whose bare-symbol prompt doesn't trip the
    # safety classifier.
    if first.api_stop_reason == "refusal" and variant != "naive":
        naive_attempt = _run_one(
            variant="naive", model=model, gene_symbol=gene_symbol,
            replicate=replicate, truth_verdict=truth_verdict, truth_class=truth_class,
            hgnc_id=hgnc_id, uniprot_acc=uniprot_acc,
        )
        if naive_attempt.predicted_verdict is not None:
            return naive_attempt
        # Naive also failed — return the original refusal record so
        # the persisted artifact reflects the user-requested variant.
        return first

    if not _is_retryable(first):
        return first
    second = _run_one(
        variant=variant, model=model, gene_symbol=gene_symbol,
        replicate=replicate, truth_verdict=truth_verdict, truth_class=truth_class,
        hgnc_id=hgnc_id, uniprot_acc=uniprot_acc,
    )
    # Persistent schema mismatch — the retry sample is ALSO invalid.
    # Null out the predicted fields and stamp a schema-mismatch error
    # rather than persisting an invalid (verdict, reason) combo to D1.
    # The original 2026-05-12 mainbench sweep wrote 15 rows to D1 past
    # this point (one Sonnet, fourteen Haiku); the Pydantic validator
    # at TriageRecord can't catch them because the runner never
    # constructs a TriageRecord — it operates on raw dict + RunRecord.
    # This null-out is the canonical enforcement leg for the runner
    # path. The D1RunSink belt-and-suspenders is at
    # cloud/triage_upload.py.
    if second.predicted_verdict is not None and not _is_schema_valid(
        second.predicted_verdict, second.predicted_reason
    ):
        second.error = (
            f"schema mismatch after retry: verdict="
            f"{second.predicted_verdict!r} reason={second.predicted_reason!r}"
        )
        second.predicted_verdict = None
        second.predicted_reason = None
    return second


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


def _smoke_routing(*, bench: str, gene_list: str | None) -> tuple[Path, str]:
    """Compute ``(out_root, run_id)`` for a ``--smoke`` invocation.

    The point of ``--smoke`` is operator-error prevention: when set, the
    runner writes per-cell JSON into ``data/eval/_smoke/...`` and tags
    the D1 ``run_id`` with the ``smoke_`` prefix, so a test invocation
    can't overwrite canonical artifacts the way today's HSPA1A loss did.

    Both paths are derived from a single timestamp (UTC, second-grained)
    so a sweep that finishes inside one second still gets a distinct
    directory thanks to the uuid8 suffix on ``run_id``. The
    ``data/eval/_smoke/`` prefix is gitignored.
    """

    timestamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    stem = Path(gene_list).stem if gene_list else bench
    smoke_dir = ROOT / "data" / "eval" / "_smoke" / f"{stem}_{timestamp}"
    run_id = f"smoke_{timestamp}_{_uuid.uuid4().hex[:8]}"
    return smoke_dir, run_id


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--model", nargs="+", default=["claude-haiku-4-5"],
                    choices=list(MODEL_PRICING.keys()),
                    help="Anthropic model id(s). Pass multiple to run all in one "
                         "invocation under a shared thread pool — outputs separate "
                         "per-model directories under the configured --out-root.")
    ap.add_argument("--replicates", type=int, default=2,
                    help="How many times to run each (variant, gene) cell.")
    ap.add_argument("--variants", nargs="+", default=list(VARIANTS.keys()),
                    choices=list(VARIANTS.keys()),
                    help="Which variants to run (default: all 4).")
    ap.add_argument("--genes", nargs="*", default=None,
                    help="Optional gene-symbol subset (default: every row in the input).")
    ap.add_argument("--concurrency", type=int, default=8,
                    help="ThreadPoolExecutor workers.")
    ap.add_argument("--dry-run", action="store_true",
                    help="Print the planned cells and exit without API calls.")
    ap.add_argument("--bench", choices=list(BENCH_TSV_BY_NAME.keys()), default="benchmark",
                    help="Which benchmark to run. Currently only 'benchmark' (the "
                         "147-gene triage_benchmark_v1) is wired up; the 17-row "
                         "sub-bench was retired 2026-05-16. Ignored when "
                         "--gene-list is provided.")
    ap.add_argument("--gene-list", default=None,
                    help="Path to a TSV with at least a 'gene_symbol' column — runs "
                         "the triage agent on every gene listed, with no ground truth. "
                         "Use for genome-wide / unlabeled sweeps (e.g. "
                         "data/processed/whole_genome_minus_m1.tsv). Overrides --bench. "
                         "When set, --out-root defaults to "
                         "data/eval/triage_<basename>_v1/ unless explicitly overridden.")
    ap.add_argument("--bench-tsv", default=None,
                    help="Read the labeled benchmark from an explicit TSV path instead "
                         "of the --bench default. Unlike --gene-list, ground-truth "
                         "columns are preserved (so `correct` is scored). Use this to "
                         "pin a sweep to a specific bench content SHA — e.g. extending "
                         "or gap-filling an existing run_id whose bench_version "
                         "(=sha256(tsv)[:12]) must stay stable. Mutually exclusive with "
                         "--gene-list.")
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
    ap.add_argument("--publish-public", action="store_true",
                    help="With --d1, ALSO write each cell to the public mirror "
                         "(triage_run_public) live, whitelisted (no raw_text / "
                         "private-only columns). Lands results in public as the "
                         "sweep runs — no separate sync_public_d1.py step. Private "
                         "D1 stays the full-fidelity source of truth.")
    ap.add_argument("--run-id", default=None,
                    help="Tag for this sweep in D1's triage_run.run_id column. "
                         "Default: a fresh uuid. Only meaningful with --d1.")
    ap.add_argument("--smoke", action="store_true",
                    help="Sandbox mode. Routes --out-root to "
                         "data/eval/_smoke/<bench-or-list>_<timestamp>/ "
                         "and --run-id to smoke_<timestamp>_<uuid8> so a "
                         "smoke test can't clobber canonical run artifacts "
                         "(today's HSPA1A loss exhibit A). Mutually "
                         "exclusive with explicit --out-root.")
    args = ap.parse_args()

    # Resolve --smoke routing BEFORE the per-bench --out-root defaulting
    # below, so the smoke path wins. Explicit --out-root is mutually
    # exclusive with --smoke (the flag's whole point is to refuse the
    # foot-gun, not enable a creative version of it).
    if args.smoke:
        if args.out_root:
            raise SystemExit(
                "--smoke and --out-root are mutually exclusive; --smoke "
                "pins out-root to data/eval/_smoke/... by design."
            )
        smoke_dir, smoke_run_id = _smoke_routing(
            bench=args.bench, gene_list=args.gene_list,
        )
        args.out_root = str(smoke_dir)
        if not args.run_id:
            args.run_id = smoke_run_id
        print(f"🔒 SMOKE MODE — out_root={smoke_dir.relative_to(ROOT)}  run_id={args.run_id}")
        print()

    global BENCH_TSV, OUT_ROOT
    if args.gene_list and args.bench_tsv:
        raise SystemExit("--gene-list and --bench-tsv are mutually exclusive.")
    if args.gene_list:
        # Unlabeled sweep — the "input TSV" is the gene-list itself.
        BENCH_TSV = Path(args.gene_list)
        if not BENCH_TSV.exists():
            raise SystemExit(f"--gene-list path does not exist: {BENCH_TSV}")
        # Derive out-root from the gene-list filename (drop .tsv suffix).
        default_out = ROOT / "data" / "eval" / f"triage_{BENCH_TSV.stem}_v1"
        OUT_ROOT = Path(args.out_root) if args.out_root else default_out
    elif args.bench_tsv:
        # Labeled bench from an explicit TSV path — ground-truth columns
        # preserved (csv.DictReader keeps them; the setdefault below only
        # fills genuinely-absent truth fields). Lets a gap-fill / extend
        # run pin bench_version=sha256(tsv)[:12] to an existing run's SHA.
        BENCH_TSV = Path(args.bench_tsv)
        if not BENCH_TSV.exists():
            raise SystemExit(f"--bench-tsv path does not exist: {BENCH_TSV}")
        OUT_ROOT = Path(args.out_root) if args.out_root else BENCH_TSV_BY_NAME["benchmark"][1]
    else:
        BENCH_TSV, OUT_ROOT = BENCH_TSV_BY_NAME[args.bench]
        if args.out_root:
            OUT_ROOT = Path(args.out_root)

    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(message)s")
    # Pull ANTHROPIC_API_KEY (and NCBI_API_KEYS / NCBI_API_KEY if present)
    # from repo-root
    # .env so a freshly-bootstrapped worktree picks them up without a shell
    # export. Same precedence rules as the main CLI — see env.py.
    load_env()

    with BENCH_TSV.open() as f:
        rows = list(csv.DictReader(f, delimiter="\t"))
    if not rows:
        raise SystemExit(f"{BENCH_TSV} has no data rows")
    if "gene_symbol" not in rows[0]:
        raise SystemExit(f"{BENCH_TSV} missing required 'gene_symbol' column")
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
    print(f"Input:   {BENCH_TSV}")
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
        d1_sink = D1RunSink(run_id=run_id, bench_tsv=BENCH_TSV,
                            publish_public=args.publish_public)
        print(f"D1 streaming enabled: run_id={d1_sink.run_id}  bench_version={d1_sink.bench_version}"
              + ("  +PUBLIC-DIRECT" if args.publish_public else ""))
        print()

    # Resume semantics: when an explicit --run-id is reused and the sink
    # already has cells under it, skip those before submitting to the
    # worker pool. The sink's insert-side dedupe would catch them too,
    # but only after paying for the API call — for a 13k-gene sweep
    # that's the difference between a 5-second restart and a $500 one.
    if d1_sink is not None and args.run_id:
        before = len(cells)
        cells = [
            (v, m, row, rep)
            for (v, m, row, rep) in cells
            if not d1_sink.already_done(
                gene_symbol=row["gene_symbol"], model=m, variant=v, replicate=rep,
            )
        ]
        skipped = before - len(cells)
        if skipped:
            print(f"Resume: skipping {skipped}/{before} cells already in D1 under run_id={args.run_id}")
            print()

    if not cells:
        print("Nothing to do — all planned cells already exist in D1.")
        if d1_sink is not None:
            d1_sink.close()
        return

    results: list[RunRecord] = []
    start = time.monotonic()
    with ThreadPoolExecutor(max_workers=args.concurrency) as ex:
        futures = {
            ex.submit(
                _run_one_with_retry,
                variant=v, model=m, gene_symbol=row["gene_symbol"],
                replicate=rep, truth_verdict=row["ground_truth_verdict"],
                truth_class=row["class"],
                # Pass-throughs to the resolver. Stable-identifier
                # priority per CLAUDE.md "Gene identifier resolution":
                # hgnc_id (cohort path) > uniprot_acc (bench TSV
                # path) > raise. Symbol-only resolution was removed
                # in resolver v3.
                hgnc_id=(row.get("hgnc_id") or None),
                uniprot_acc=(row.get("uniprot_acc") or None),
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

    # ── Post-sweep completeness assertion ──────────────────────────────
    # The original 2026-05-12 mainbench sweep silently shipped a holey
    # matrix: 16 (gene × model × variant) cells never produced a valid
    # verdict (15 dropped without a row, 1 unparsed-JSON error), and it
    # went unnoticed because the headline sonnet/ncbi cell was complete
    # (issue #48). This check makes a holey sweep fail LOUDLY — every cell
    # this invocation executed must carry a non-null predicted_verdict, or
    # we exit non-zero with the offenders listed.
    #
    # Scope note: only cells run *this* invocation are checked. Resume-
    # skipped cells (already in D1 under --run-id) were validated by the
    # run that inserted them — re-validating them would require a network
    # read we deliberately avoid here.
    holes = [
        (r.model, r.variant, r.gene_symbol, r.replicate, r.error or "null verdict")
        for r in results
        if r.predicted_verdict is None
    ]
    if holes:
        print()
        print(f"❌ COMPLETENESS FAILURE: {len(holes)}/{len(results)} executed cells "
              "produced no valid verdict:")
        for model, variant, gene, rep, why in sorted(holes):
            print(f"   {_model_slug(model):14s} {variant:12s} {gene:10s} r{rep}  — {why}")
        print("Re-run with the same --run-id to gap-fill (idempotent on the "
              "natural key); a persisted error row must be deleted first.")
        raise SystemExit(1)
    print(f"✓ Completeness: all {len(results)} executed cells carry a valid verdict.")


if __name__ == "__main__":
    main()
