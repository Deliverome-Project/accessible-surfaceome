"""Aggregate the 4-variant × 2-replicate sub-benchmark runs into summary plots.

Reads ``data/eval/triage_subbench_v1/<variant>/<gene>_run<N>.json`` and the
sub-benchmark TSV ground truth, then emits:

1. data/analysis/triage_bench/subbench_accuracy_by_variant.{pdf,png}
   Variant accuracy bars (one cluster per model: Haiku, Sonnet),
   coloured in 4 shades of Claude orange (lightest = least context,
   darkest = most context).

2. data/analysis/triage_bench/subbench_per_protein.{pdf,png}
   Per-protein × per-variant correctness grid, 2 columns (one per model),
   with proteins on Y and variants on X. Filled = correct, hatched = wrong,
   labeled with the prediction. Lets the reader see which proteins each
   variant misses.

3. data/analysis/triage_bench/subbench_cost_vs_accuracy.{pdf,png}
   Cost (USD) on X vs accuracy on Y for each (model, variant) cell.
   Helps visualise the cost/accuracy frontier across 8 cells.
"""

from __future__ import annotations

import csv
import json
from pathlib import Path

import matplotlib.pyplot as plt
import pandas as pd
import seaborn as sns

from accessible_surfaceome.audit._plotting_config import (
    COLORS,
    save_figure,
    setup_plotting_style,
)


ROOT = Path("/Users/rebeccacarlson/Git/accessible-surfaceome/.claude/worktrees/optimistic-goldwasser-ea19aa")
SUBBENCH_TSV = ROOT / "data/eval/triage_subbench_v1.tsv"
RUNS_DIR = ROOT / "data/eval/triage_subbench_v1"
OUT_DIR = ROOT / "data/analysis/triage_bench"

# Extrapolate per-cell subbench costs to a whole-genome triage pass.
# All cost annotations on the plots are reported as $/whole-genome at 1
# replicate per gene — the apples-to-apples number for "would this fly
# on the real surfaceome?". WHOLE_GENOME_N is NCBI protein-coding genes
# that also carry an HGNC cross-reference — this drops ~1,160 LOC*
# machine-predicted ORFs and readthroughs that NCBI annotates as
# protein-coding but HGNC has not promoted. Source-comparison and
# alternative denominators are documented in
# docs/data-sources/whole-genome-gene-catalogs.md. Refresh with
# scripts/fetch_ncbi_human_protein_coding.py.
SUBBENCH_GENE_N = 17
WHOLE_GENOME_N = 19464  # NCBI Homo_sapiens protein-coding ∩ has HGNC xref, fetched 2026-05-11
GENOME_SCALE = WHOLE_GENOME_N / SUBBENCH_GENE_N  # ~1213x

# Variant order = "amount of context" axis. Each variant gets a darker
# shade of Claude orange as the context augmentation increases.
VARIANT_ORDER = ["naive", "ncbi", "web_naive", "web_ncbi"]
VARIANT_LABEL = {
    "naive":     "naive\n(no resolver, no web)",
    "ncbi":      "NCBI gene\n(resolver, no web)",
    "web_naive": "web only\n(no resolver)",
    "web_ncbi":  "web + NCBI\n(both)",
}
# Sequential Claude-orange shades — lightest to darkest. Base Claude
# orange is #d87851; the 4 shades step around it in luminance.
CLAUDE_ORANGE_SHADES = {
    "naive":     "#f1c4ab",  # tint 50%
    "ncbi":      "#d87851",  # base — matches the main barplot
    "web_naive": "#a85b3f",  # shade 25%
    "web_ncbi":  "#7a3b25",  # shade 50%
}

MODEL_ORDER = ["claude-haiku-4-5", "claude-sonnet-4-6", "claude-opus-4-7"]
MODEL_LABEL = {
    "claude-haiku-4-5":  "Haiku 4.5",
    "claude-sonnet-4-6": "Sonnet 4.6",
    "claude-opus-4-7":   "Opus 4.7",
}
# Distinct scatter markers per model — keeps the cost-vs-accuracy plot
# legible when multiple models occupy a similar cost bucket.
MODEL_MARKER = {
    "claude-haiku-4-5":  "o",
    "claude-sonnet-4-6": "D",
    "claude-opus-4-7":   "s",
}
# Cells run under the current (post-imperative-rewrite, post-confidence-
# schema-addition) prompt. Anything not in this set was captured against
# an earlier prompt revision and gets a "stale" tag in the plot legends
# + an explanatory footnote. Re-running a stale cell with the runner
# overwrites the JSONs in-place; add the (model, variant) tuple here
# afterward to mark it fresh.
FRESH_CELLS: frozenset[tuple[str, str]] = frozenset({
    ("claude-haiku-4-5", "naive"),
    ("claude-haiku-4-5", "ncbi"),
    ("claude-haiku-4-5", "web_naive"),
    ("claude-haiku-4-5", "web_ncbi"),
    ("claude-sonnet-4-6", "naive"),
    ("claude-sonnet-4-6", "ncbi"),
    ("claude-sonnet-4-6", "web_naive"),
    ("claude-sonnet-4-6", "web_ncbi"),
    ("claude-opus-4-7", "naive"),
    ("claude-opus-4-7", "ncbi"),
})
# When True, _build_dataframe filters records to FRESH_CELLS only — used
# when the user wants the "latest prompt version only" view. Set via the
# --fresh-only CLI flag.
FILTER_TO_FRESH = True
# Back-compat: kept for callers / older code paths that referenced this.
PROMPT_FRESH_MODELS: frozenset[str] = frozenset()


# Verdict scoring rule (user direction, reaffirmed):
# `yes` and `contextual` collapse to a single positive class for accuracy
# accounting — a tissue/state-restricted surface protein is operationally
# the same kind of hit as a ubiquitous one for downstream targeting work.
# `no` is only correct against `no`.
POSITIVE_VERDICTS: frozenset[str] = frozenset({"yes", "contextual"})


# --- Prompt-cache pricing model -------------------------------------------
# Old run records (pre-2026-05) don't carry cache_creation_tokens or
# cache_read_tokens because the runner didn't extract them from the API
# response. We can still RETROACTIVELY estimate what a cached run would
# have cost by modeling amortized caching across the cell's session.
#
# Anthropic pricing for ephemeral cache:
#   * cache_creation: 1.25 × base input price (paid once per cache entry)
#   * cache_read:     0.10 × base input price (paid every reuse)
# Amortized across N calls in a session:
#   avg multiplier = (1.25 + (N-1) × 0.10) / N
#   N=17 → 0.168 ; N=18 → 0.163 ; N=51 → 0.118 ; N=147 → 0.108
#
# Token estimates per variant (system prompt only — cache_control is set
# on the system block, not on the web_search tool schema). Calibrated to
# observed cache_read values from new web_ncbi_reduced runs (≈14.7K).
# Per-variant fallbacks scale by prompt-file char count.
CACHEABLE_TOKENS_BY_VARIANT: dict[str, int] = {
    # NB: after the 2026-05-11 slim canonicalization, every prompt is
    # ~1,700-1,800 tokens — empirically BELOW Sonnet 4.6's ephemeral-
    # cache floor (observed 0/0 cache_creation/cache_read across all
    # 147 slim cells of sonnet/ncbi on the full benchmark). Setting
    # these values to 0 makes the retroactive cost model report
    # uncached pricing, matching observed behavior on post-promotion
    # runs. The OLD pre-promotion runs (~5,500-token prompts) cached
    # fine; their records carry explicit cache_creation/cache_read
    # tokens so _effective_cost_with_caching skips this fallback table.
    "naive":             0,
    "ncbi":              0,
    "web_naive":         0,
    "web_ncbi":          0,
    "web_ncbi_reduced":  0,
    "pubmed_ncbi":       0,
}
CACHE_CREATION_MULT: float = 1.25
CACHE_READ_MULT:     float = 0.10
_MODEL_INPUT_PRICE_PER_MTOK: dict[str, float] = {
    "claude-haiku-4-5":  1.0,
    "claude-sonnet-4-6": 3.0,
    "claude-opus-4-7":   15.0,
}
_MODEL_OUTPUT_PRICE_PER_MTOK: dict[str, float] = {
    "claude-haiku-4-5":  5.0,
    "claude-sonnet-4-6": 15.0,
    "claude-opus-4-7":   75.0,
}
WEB_SEARCH_USD_PER_QUERY: float = 0.01


def _effective_cost_with_caching(
    record: dict, *, session_size: int,
) -> float:
    """USD cost for one persisted call, with prompt caching active.

    If the record carries explicit cache_creation_tokens /
    cache_read_tokens (post-2026-05 runner), uses them directly. Else
    (legacy record) models amortized caching across ``session_size`` —
    the number of calls in the cell that share the same system prompt.
    """
    model = record["model"]
    variant = record["variant"]
    in_price = _MODEL_INPUT_PRICE_PER_MTOK.get(model, 0.0)
    out_price = _MODEL_OUTPUT_PRICE_PER_MTOK.get(model, 0.0)
    prompt_tokens = int(record.get("prompt_tokens") or 0)
    completion_tokens = int(record.get("completion_tokens") or 0)
    n_web = int(record.get("n_web_searches") or 0)

    output_cost = completion_tokens * out_price / 1_000_000
    web_cost = n_web * WEB_SEARCH_USD_PER_QUERY

    cc = int(record.get("cache_creation_tokens") or 0)
    cr = int(record.get("cache_read_tokens") or 0)
    if cc > 0 or cr > 0:
        # Explicit cache accounting — trust the recorded breakdown.
        input_cost = (
            prompt_tokens
            + cc * CACHE_CREATION_MULT
            + cr * CACHE_READ_MULT
        ) * in_price / 1_000_000
        return input_cost + output_cost + web_cost

    # Legacy record: amortize.
    cacheable = min(
        CACHEABLE_TOKENS_BY_VARIANT.get(variant, 0),
        prompt_tokens,
    )
    user_tokens = max(prompt_tokens - cacheable, 0)
    n = max(session_size, 1)
    avg_mult = (CACHE_CREATION_MULT + (n - 1) * CACHE_READ_MULT) / n
    input_cost = (
        cacheable * avg_mult + user_tokens
    ) * in_price / 1_000_000
    return input_cost + output_cost + web_cost


def _verdict_match(pred: str | None, truth: str | None) -> bool:
    """Return True if prediction is acceptable under the
    yes≡contextual equivalence rule."""
    if pred is None or truth is None:
        return False
    if pred == truth:
        return True
    return pred in POSITIVE_VERDICTS and truth in POSITIVE_VERDICTS


def _load_ground_truth() -> dict[str, dict[str, str]]:
    with SUBBENCH_TSV.open() as f:
        return {r["gene_symbol"]: r for r in csv.DictReader(f, delimiter="\t")}


def _load_runs() -> list[dict]:
    """Collect every persisted per-cell record.

    Path layout: data/eval/triage_subbench_v1/<model_slug>/<variant>/<gene>_run<N>.json

    Directories whose name starts with ``_`` (e.g. ``_legacy_pre_prompt_rewrite_*``,
    ``_backup_*``, ``_main_bench_*``) are skipped — they hold snapshots of
    runs captured against earlier prompts / earlier truth labels and would
    contaminate the current figures.
    """
    out = []
    for entry in sorted(RUNS_DIR.iterdir()):
        if not entry.is_dir() or entry.name.startswith("_"):
            continue
        for variant_dir in sorted(entry.iterdir()):
            if not variant_dir.is_dir() or variant_dir.name not in VARIANT_ORDER:
                continue
            for path in sorted(variant_dir.glob("*_run*.json")):
                try:
                    out.append(json.loads(path.read_text()))
                except json.JSONDecodeError:
                    continue
    return out


def _build_dataframe() -> pd.DataFrame:
    """One row per per-cell run.

    Always re-derives ``truth_verdict`` + ``correct`` from the current
    subbench TSV rather than trusting the snapshot stored in each per-run
    JSON. This keeps the plots in sync after a truth-table relabel without
    requiring every (model × variant × replicate) cell to be rerun.
    """
    truth = _load_ground_truth()
    runs = _load_runs()
    # Group by cell so we know the session size for retroactive caching.
    from collections import Counter
    cell_session_size: dict[tuple[str, str], int] = Counter(
        (r["model"], r["variant"]) for r in runs
    )
    rows = []
    for r in runs:
        gene = r["gene_symbol"]
        cell = (r["model"], r["variant"])
        if FILTER_TO_FRESH and cell not in FRESH_CELLS:
            continue
        current_truth = (truth.get(gene) or {}).get("ground_truth_verdict") or r["truth_verdict"]
        # cost_usd as persisted = uncached pricing for legacy records.
        # cost_usd_cached = retroactively-amortized pricing assuming
        # prompt-caching is active over the cell's session.
        cost_cached = _effective_cost_with_caching(
            r, session_size=cell_session_size[cell],
        )
        rows.append({
            "variant": r["variant"],
            "model": r["model"],
            "gene_symbol": gene,
            "replicate": r["replicate"],
            "truth_verdict": current_truth,
            "predicted_verdict": r["predicted_verdict"] or "MISSING",
            "predicted_reason": r["predicted_reason"] or "",
            "predicted_confidence": r.get("predicted_confidence"),
            "predicted_key_uncertainty": r.get("predicted_key_uncertainty"),
            "correct": _verdict_match(r["predicted_verdict"], current_truth),
            # cost_usd is the canonical cost number used by all
            # downstream code (plots, strategy sweeps). It now reflects
            # prompt-caching: explicit cache fields when present (new
            # runs), amortized estimate otherwise (legacy runs).
            "cost_usd": cost_cached,
            "cost_usd_uncached": r["cost_usd"],
            "latency_s": r["latency_s"],
            "n_web_searches": r["n_web_searches"],
        })
    return pd.DataFrame(rows)


def _accuracy_by_variant(df: pd.DataFrame) -> pd.DataFrame:
    """(model, variant) → accuracy + total cost."""
    agg = (
        df.groupby(["model", "variant"], as_index=False)
        .agg(n=("correct", "size"), n_correct=("correct", "sum"),
             total_cost=("cost_usd", "sum"),
             mean_latency=("latency_s", "mean"),
             mean_web=("n_web_searches", "mean"))
    )
    agg["accuracy"] = agg.n_correct / agg.n
    return agg


def _lazy_ensemble(
    df: pd.DataFrame,
    truth: dict[str, dict],
    a: tuple[str, str], b: tuple[str, str], c: tuple[str, str],
) -> tuple[float, float, int]:
    """Lazy 3-cell ensemble: take 1 rep from A + 1 from B. If they agree,
    accept. If they disagree, fetch 1 rep from C and majority-vote across
    all three. When all three disagree (rare), the tiebreaker cell (C)
    wins by design.

    Returns ``(accuracy, expected_cost_per_gene, n_disagreements_in_17)``.
    Expected cost = cost(A) + cost(B) + P(A,B disagree) * cost(C).
    """
    from collections import Counter
    cost_per_rep = df.groupby(["model", "variant"]).cost_usd.mean().to_dict()
    genes = sorted(truth.keys())

    def _pred(cell, gene):
        sub = df[(df.model == cell[0]) & (df.variant == cell[1]) &
                 (df.gene_symbol == gene)].sort_values("replicate")
        return sub.iloc[0].predicted_verdict if len(sub) else None

    correct, n_dis = 0, 0
    for g in genes:
        pa, pb = _pred(a, g), _pred(b, g)
        if pa is None or pb is None:
            continue
        if pa == pb:
            chosen = pa
        else:
            n_dis += 1
            pc = _pred(c, g)
            if pc is None:
                chosen = pa
            else:
                counts = Counter([pa, pb, pc])
                top = counts.most_common(1)[0][1]
                tied = [v for v, n_ in counts.items() if n_ == top]
                chosen = tied[0] if len(tied) == 1 else pc
        if _verdict_match(chosen, truth[g]["ground_truth_verdict"]):
            correct += 1
    n = len(genes)
    acc = correct / n
    exp_cost = (
        cost_per_rep[a] + cost_per_rep[b]
        + (n_dis / n) * cost_per_rep[c]
    )
    return acc, exp_cost, n_dis


# Cost tolerance for the NCBI-preference tiebreaker. Configs within
# this band of the cheapest qualifying config get re-ranked to prefer
# the most-NCBI composition. Sized so that the typical *-naive →
# *-ncbi swap (a few cents per gene, $5–$50 per whole-genome pass)
# always flips, while substantively cheaper configurations are kept.
NCBI_PREF_TOLERANCE_REL: float = 0.05
NCBI_PREF_TOLERANCE_ABS_PG: float = 50.0  # USD per whole-genome pass


def _ncbi_score(rec: dict) -> int:
    """How NCBI-anchored is this config? Counts cells with variant=='ncbi'
    among (A, B, [C])."""
    cells = [rec.get("a"), rec.get("b")]
    if rec.get("c") is not None:
        cells.append(rec["c"])
    return sum(1 for cell in cells if cell and cell[1] == "ncbi")


def _pick_preferring_ncbi(candidates: list[dict]) -> dict | None:
    """Pick the cheapest candidate, then upgrade to a more-NCBI variant
    if one exists within the cost-tolerance band. Tie-breaks: more NCBI
    cells, then cheaper, then alphabetical for stability."""
    if not candidates:
        return None
    cheapest = min(candidates, key=lambda c: c["cost"])
    tol = max(
        NCBI_PREF_TOLERANCE_REL * cheapest["cost"],
        NCBI_PREF_TOLERANCE_ABS_PG / WHOLE_GENOME_N,
    )
    within = [c for c in candidates if c["cost"] <= cheapest["cost"] + tol + 1e-12]
    return max(
        within,
        key=lambda c: (_ncbi_score(c), -c["cost"], str(c.get("a")), str(c.get("b"))),
    )


def _best_lazy_at_tier(
    df: pd.DataFrame, truth: dict, acc_threshold: float
) -> dict | None:
    """Sweep every (A, B, C) triple and return the cheapest qualifying
    config, then apply the NCBI-preference tiebreaker within tolerance.
    Returns a dict with the trio + metrics."""
    from itertools import combinations
    cells = sorted({(r["model"], r["variant"]) for _, r in df.iterrows()})
    candidates: list[dict] = []
    for a, b in combinations(cells, 2):
        for c in cells:
            if c == a or c == b:
                continue
            acc, cost, n_dis = _lazy_ensemble(df, truth, a, b, c)
            if acc + 1e-9 < acc_threshold:
                continue
            candidates.append({
                "a": a, "b": b, "c": c, "acc": acc, "cost": cost,
                "n_dis": n_dis,
            })
    return _pick_preferring_ncbi(candidates)


# --- Escalation predicates -------------------------------------------------
# A predicate inspects a per-call row (the A-cell's prediction for a gene)
# and decides whether to escalate to a more expensive fallback cell.
#
# The two confidence rules use the intuitive "trust = high (and maybe
# medium); escalate when the model admits uncertainty":
#
#   conf_low         — escalate when the model emits `low` confidence.
#                      The model is admitting it doesn't know; route to
#                      something stronger.
#   conf_low_or_med  — same idea, escalating more aggressively: trust
#                      only `high` and route both `medium` and `low`.
#   resp_no          — escalate when the verdict is `no`, since false
#                      negatives are the costly failure mode (a rejected
#                      drug target is rarely revisited).
#
# Unions of the above (conf_*|resp_no) cover the "escalate if EITHER
# trigger fires" case.
#
# Anti-calibration caveat: on the current 17-protein sub-bench, the
# model's `high`-confidence calls are *less* accurate (67%) than its
# `low` calls (100%). That makes "escalate low" close to a no-op on
# this data — the lows are already right. We surface that in the
# strategy-table output and treat it as a prompt-quality finding, NOT a
# reason to ship "escalate-high" (which would be U-shape-overfit and
# logically inverted).
ESCALATE_PREDICATES: dict[str, "callable"] = {
    "conf_low":          lambda r: r.get("predicted_confidence") == "low",
    "conf_low_or_med":   lambda r: r.get("predicted_confidence") in {"low", "medium"},
    "resp_no":           lambda r: r.get("predicted_verdict") == "no",
    "conf_low|resp_no":  lambda r: (
        r.get("predicted_confidence") == "low"
        or r.get("predicted_verdict") == "no"
    ),
    "conf_lm|resp_no":   lambda r: (
        r.get("predicted_confidence") in {"low", "medium"}
        or r.get("predicted_verdict") == "no"
    ),
}

ESCALATE_LABEL: dict[str, str] = {
    "conf_low":          "conf=low",
    "conf_low_or_med":   "conf≤med",
    "resp_no":           "verdict=no",
    "conf_low|resp_no":  "conf=low | no",
    "conf_lm|resp_no":   "conf≤med | no",
}


def _cascade(
    df: pd.DataFrame,
    truth: dict[str, dict],
    a: tuple[str, str],
    b: tuple[str, str],
    c: tuple[str, str] | None,
    escalate: "callable",
) -> tuple[float, float, int, int]:
    """Unified cascade. Run A always. If ``escalate(A's row)`` fires,
    run B. If ``c`` is provided and A and B then disagree, run C and
    majority-vote across {A, B, C}.

    Special case: when ``escalate`` always returns True and ``c`` is
    provided, this collapses to the pure lazy-disagree ensemble.

    Returns ``(accuracy, expected_cost_per_gene, n_to_B, n_to_C)``.
    Expected cost = c(A) + P(esc) · c(B) + P(disagree | esc) · c(C).
    """
    from collections import Counter
    cost_per_rep = df.groupby(["model", "variant"]).cost_usd.mean().to_dict()
    genes = sorted(truth.keys())

    def _row(cell, gene):
        sub = df[
            (df.model == cell[0])
            & (df.variant == cell[1])
            & (df.gene_symbol == gene)
        ].sort_values("replicate")
        return sub.iloc[0] if len(sub) else None

    correct = n_b = n_c = 0
    for g in genes:
        ra = _row(a, g)
        if ra is None:
            continue
        if not escalate(ra):
            chosen = ra.predicted_verdict
        else:
            n_b += 1
            rb = _row(b, g)
            if rb is None:
                chosen = ra.predicted_verdict
            elif c is None:
                # No lazy-tiebreaker: accept B's verdict on escalation.
                chosen = rb.predicted_verdict
            elif rb.predicted_verdict == ra.predicted_verdict:
                chosen = ra.predicted_verdict
            else:
                n_c += 1
                rc = _row(c, g)
                if rc is None:
                    chosen = rb.predicted_verdict
                else:
                    counts = Counter([
                        ra.predicted_verdict,
                        rb.predicted_verdict,
                        rc.predicted_verdict,
                    ])
                    top = counts.most_common(1)[0][1]
                    tied = [v for v, n_ in counts.items() if n_ == top]
                    chosen = tied[0] if len(tied) == 1 else rc.predicted_verdict
        if _verdict_match(chosen, truth[g]["ground_truth_verdict"]):
            correct += 1
    n = len(genes)
    acc = correct / n
    exp_cost = cost_per_rep[a] + (n_b / n) * cost_per_rep[b]
    if c is not None:
        exp_cost += (n_c / n) * cost_per_rep[c]
    return acc, exp_cost, n_b, n_c


def _best_cascade_at_tier(
    df: pd.DataFrame,
    truth: dict,
    acc_threshold: float,
    *,
    predicate_name: str,
    with_lazy: bool,
) -> dict | None:
    """Sweep (A, B[, C]) configurations for one cascade strategy; return
    the cheapest qualifying config, then apply the NCBI-preference
    tiebreaker within cost tolerance."""
    pred = ESCALATE_PREDICATES[predicate_name]
    cells = sorted({(r["model"], r["variant"]) for _, r in df.iterrows()})
    candidates: list[dict] = []
    for a in cells:
        for b in cells:
            if b == a:
                continue
            if with_lazy:
                for c in cells:
                    if c in (a, b):
                        continue
                    acc, cost, nb, nc = _cascade(df, truth, a, b, c, pred)
                    if acc + 1e-9 < acc_threshold:
                        continue
                    candidates.append({
                        "a": a, "b": b, "c": c,
                        "acc": acc, "cost": cost,
                        "n_to_b": nb, "n_to_c": nc,
                        "with_lazy": True,
                        "predicate": predicate_name,
                    })
            else:
                acc, cost, nb, _ = _cascade(df, truth, a, b, None, pred)
                if acc + 1e-9 < acc_threshold:
                    continue
                candidates.append({
                    "a": a, "b": b, "c": None,
                    "acc": acc, "cost": cost,
                    "n_to_b": nb, "n_to_c": 0,
                    "with_lazy": False,
                    "predicate": predicate_name,
                })
    return _pick_preferring_ncbi(candidates)


# Strategy registry. ``predicate=None`` is the pure-lazy fallback: A and
# B always run, C runs only on disagreement (the original lazy-disagree
# ensemble). Everything else is a cascade with an explicit escalation
# trigger, optionally chained with a lazy-disagree tiebreaker.
StrategyEntry = tuple[str, str | None, bool]
STRATEGIES: list[StrategyEntry] = [
    ("Pure lazy",                 None,                 True),
    ("Conf=low",                  "conf_low",           False),
    ("Conf≤med",                  "conf_low_or_med",    False),
    ("Resp=no",                   "resp_no",            False),
    ("Conf=low | resp=no",        "conf_low|resp_no",   False),
    ("Conf≤med | resp=no",        "conf_lm|resp_no",    False),
    ("Conf=low + lazy",           "conf_low",           True),
    ("Conf≤med + lazy",           "conf_low_or_med",    True),
    ("Resp=no + lazy",            "resp_no",            True),
    ("Conf=low|resp=no + lazy",   "conf_low|resp_no",   True),
    ("Conf≤med|resp=no + lazy",   "conf_lm|resp_no",    True),
]


def _best_strategy_at_tier(
    df: pd.DataFrame, truth: dict, threshold: float, strategy: StrategyEntry,
) -> dict | None:
    """Dispatch a single STRATEGIES entry to its sweep. Pure lazy uses
    the older _best_lazy_at_tier (already shape-compatible-ish); cascade
    strategies use _best_cascade_at_tier."""
    _, pred_name, with_lazy = strategy
    if pred_name is None:
        rec = _best_lazy_at_tier(df, truth, threshold)
        if rec is None:
            return None
        # Normalize the shape so downstream code can iterate uniformly.
        return {
            **rec,
            "n_to_b": rec.get("n_dis", 0),   # B is always run in pure lazy
            "n_to_c": rec.get("n_dis", 0),   # C is run on every disagreement
            "with_lazy": True,
            "predicate": None,
        }
    return _best_cascade_at_tier(
        df, truth, threshold,
        predicate_name=pred_name, with_lazy=with_lazy,
    )


def _best_achievable_for_strategy(
    df: pd.DataFrame, truth: dict, strategy: StrategyEntry,
) -> dict | None:
    """For a strategy with no tier constraint, return the (acc, cost) of
    the best-achievable accuracy across all configs, choosing the
    cheapest config at that accuracy. Used to expose ceilings for
    strategies that can't reach a given threshold (e.g. pure lazy
    capping at ~88% on this data)."""
    _, pred_name, with_lazy = strategy
    cells = sorted({(r["model"], r["variant"]) for _, r in df.iterrows()})
    best_acc = -1.0
    best_rec: dict | None = None
    if pred_name is None:
        # Pure lazy: sweep all (A, B, C) triples.
        from itertools import combinations
        for a, b in combinations(cells, 2):
            for c in cells:
                if c in (a, b):
                    continue
                acc, cost, n_dis = _lazy_ensemble(df, truth, a, b, c)
                if (acc, -cost) > (best_acc, -(best_rec["cost"] if best_rec else float("inf"))):
                    best_acc = acc
                    best_rec = {"a": a, "b": b, "c": c, "acc": acc,
                                "cost": cost, "n_dis": n_dis,
                                "n_to_b": n_dis, "n_to_c": n_dis,
                                "with_lazy": True, "predicate": None}
    else:
        pred = ESCALATE_PREDICATES[pred_name]
        for a in cells:
            for b in cells:
                if b == a:
                    continue
                if with_lazy:
                    for c in cells:
                        if c in (a, b):
                            continue
                        acc, cost, nb, nc = _cascade(df, truth, a, b, c, pred)
                        if (acc, -cost) > (best_acc, -(best_rec["cost"] if best_rec else float("inf"))):
                            best_acc = acc
                            best_rec = {"a": a, "b": b, "c": c, "acc": acc,
                                        "cost": cost, "n_to_b": nb,
                                        "n_to_c": nc, "with_lazy": True,
                                        "predicate": pred_name}
                else:
                    acc, cost, nb, _ = _cascade(df, truth, a, b, None, pred)
                    if (acc, -cost) > (best_acc, -(best_rec["cost"] if best_rec else float("inf"))):
                        best_acc = acc
                        best_rec = {"a": a, "b": b, "c": None, "acc": acc,
                                    "cost": cost, "n_to_b": nb,
                                    "n_to_c": 0, "with_lazy": False,
                                    "predicate": pred_name}
    return best_rec


def _summarize_strategies(
    df: pd.DataFrame, truth: dict, tiers: tuple[tuple[str, float], ...] = (
        ("≥100%", 0.999), ("≥94%", 0.94),
    ),
) -> list[dict]:
    """For each strategy × tier, find the cheapest config (or None).

    Also records the best-achievable accuracy regardless of tier — useful
    when the strategy can't reach the requested threshold (e.g. pure
    lazy bottoming out at ~88% on this data) so the ceiling is visible
    in the printed table.
    """
    out: list[dict] = []
    for strat in STRATEGIES:
        label, pred_name, with_lazy = strat
        ceiling = _best_achievable_for_strategy(df, truth, strat)
        for tier_name, tier_thresh in tiers:
            rec = _best_strategy_at_tier(df, truth, tier_thresh, strat)
            out.append({
                "strategy": label,
                "tier": tier_name,
                "tier_threshold": tier_thresh,
                "predicate": pred_name,
                "with_lazy": with_lazy,
                "is_pure_lazy": pred_name is None,
                "rec": rec,
                "ceiling": ceiling,
            })
    return out


def _print_strategy_table(summary: list[dict], wgn: int = WHOLE_GENOME_N) -> None:
    """Format the per-strategy / per-tier winners as a tidy stdout table."""
    def _short(cell):
        if cell is None:
            return "—"
        m_, v_ = cell
        return f"{m_.replace('claude-', '').split('-')[0]}/{v_}"

    print("\n=== Combination strategy winners ===")
    header = f"{'Strategy':<28}{'Tier':<7}{'Acc':<8}{'$/genome':<11}{'A':<14}{'B':<14}{'C':<14}  escalations"
    print(header)
    print("-" * len(header))
    for row in summary:
        rec = row["rec"]
        if rec is None:
            # No config meets the tier — show the ceiling so the reader
            # can see what the strategy actually achieves.
            ceiling = row.get("ceiling")
            if ceiling is None:
                print(f"{row['strategy']:<28}{row['tier']:<7}{'(none)':<8}")
                continue
            cost_g = ceiling["cost"] * wgn
            a, b, c = ceiling["a"], ceiling["b"], ceiling.get("c")
            print(
                f"{row['strategy']:<28}{row['tier']:<7}"
                f"{'(ceiling)':<8}"
                f"{ceiling['acc']:>6.1%}  "
                f"${cost_g:>7,.0f}   "
                f"{_short(a):<14}{_short(b):<14}{_short(c):<14}  best-achievable"
            )
            continue
        cost_g = rec["cost"] * wgn
        a, b, c = rec["a"], rec["b"], rec.get("c")
        n_b = rec.get("n_to_b", rec.get("n_escalated", rec.get("n_dis", 0)))
        n_c = rec.get("n_to_c", 0)
        esc = f"{n_b}→B"
        if c is not None:
            esc += f", {n_c}→C"
        print(
            f"{row['strategy']:<28}{row['tier']:<7}"
            f"{rec['acc']:>6.1%}  "
            f"${cost_g:>7,.0f}   "
            f"{_short(a):<14}{_short(b):<14}{_short(c):<14}  {esc}"
        )


def plot_accuracy_by_variant(df: pd.DataFrame, out_dir: Path) -> None:
    setup_plotting_style(style="whitegrid", context="notebook", font_scale=1.0)
    agg = _accuracy_by_variant(df)
    fig, ax = plt.subplots(figsize=(14, 5.8))

    palette = [CLAUDE_ORANGE_SHADES[v] for v in VARIANT_ORDER]
    models = [m for m in MODEL_ORDER if m in agg.model.unique()]

    sns.barplot(
        data=agg,
        x="model", y="accuracy", hue="variant",
        order=models, hue_order=VARIANT_ORDER,
        palette=palette, edgecolor="none", saturation=1.0, ax=ax,
    )

    # Per-replicate accuracy points overlaid on each bar, so cells with
    # multiple reps show the spread alongside the aggregate.
    per_rep = (
        df.groupby(["model", "variant", "replicate"], as_index=False)
        .agg(n=("correct", "size"), n_correct=("correct", "sum"))
    )
    per_rep["accuracy"] = per_rep.n_correct / per_rep.n

    # `ax.containers` is one BarContainer per hue (variant), each holding
    # one Rectangle per model in x-axis order. This is the reliable way to
    # recover the actual bar geometry seaborn placed — manual indexing
    # via `ax.patches` is fragile when seaborn skips zero-data combinations.
    cells_in_data = {(r.model, r.variant) for _, r in agg.iterrows()}
    has_stale = bool(cells_in_data - FRESH_CELLS)
    has_fresh = bool(cells_in_data & FRESH_CELLS)
    mixed_prompts = has_stale and has_fresh
    for variant_idx, variant in enumerate(VARIANT_ORDER):
        if variant_idx >= len(ax.containers):
            continue
        container = ax.containers[variant_idx]
        for model_idx, model in enumerate(models):
            if model_idx >= len(container.patches):
                continue
            bar = container.patches[model_idx]
            bar_x = bar.get_x() + bar.get_width() / 2
            # Stale-cell visual flag: stripe pattern + lower alpha.
            is_fresh = (model, variant) in FRESH_CELLS
            if mixed_prompts and not is_fresh:
                bar.set_hatch("///")
                bar.set_alpha(0.55)

            # Per-rep dots
            cell_reps = per_rep[(per_rep.variant == variant) & (per_rep.model == model)]
            if not cell_reps.empty:
                n_pts = len(cell_reps)
                if n_pts == 1:
                    jitter = [0.0]
                else:
                    spread = bar.get_width() * 0.32
                    jitter = [spread * (i / (n_pts - 1) - 0.5) for i in range(n_pts)]
                ax.scatter(
                    [bar_x + j for j in jitter],
                    cell_reps.accuracy.tolist(),
                    s=42, color="white", edgecolor=COLORS["dark"],
                    linewidth=1.1, zorder=5,
                )

            # n_correct/n + $cost annotation. Cost is reported as the
            # extrapolated $/whole-genome pass (20k genes at 1 rep each),
            # not the $/17-gene-subbench number, so the bar reads as
            # "what this would cost to run on the real surfaceome."
            row = agg[(agg.variant == variant) & (agg.model == model)]
            if row.empty:
                continue
            r = row.iloc[0]
            cost_per_genome = (r.total_cost / r.n) * WHOLE_GENOME_N
            ax.text(
                bar_x,
                bar.get_height() + 0.018,
                f"{int(r.n_correct)}/{int(r.n)}\n${cost_per_genome:,.0f}",
                ha="center", va="bottom",
                fontsize=8.5, color=COLORS["dark"],
                linespacing=1.2,
            )

    # --- Best combination at each accuracy tier --------------------------
    # Sweep every strategy in STRATEGIES (pure lazy + 5 escalation
    # predicates × {with, without lazy tiebreak}). For each tier (100%,
    # ≥94%) take the single cheapest winner across all strategies and
    # show it as a labeled bar at the right of the per-cell groups.
    truth_rows = _load_ground_truth()

    def _short(cell):
        if cell is None:
            return "—"
        m_, v_ = cell
        return f"{m_.replace('claude-', '').split('-')[0]}/{v_}"

    summary = _summarize_strategies(df, truth_rows)
    # "Best combo": cheapest across ALL 11 strategies at each tier.
    best_by_tier: dict[str, dict | None] = {}
    # "Pure lazy": separately, the cheapest pure-lazy triple at each tier
    # (lets the reader compare against the cascade winners side-by-side).
    lazy_by_tier: dict[str, dict | None] = {}
    for tier_name in ("≥100%", "≥94%"):
        candidates = [s for s in summary if s["tier"] == tier_name and s["rec"]]
        candidates.sort(key=lambda s: s["rec"]["cost"])
        best_by_tier[tier_name] = candidates[0] if candidates else None
        lazy_only = [s for s in candidates if s["is_pure_lazy"]]
        lazy_by_tier[tier_name] = lazy_only[0] if lazy_only else None
    any_combos = any(best_by_tier.values()) or any(lazy_by_tier.values())

    # Color palette per sub-group. Best combo = teal/sage (existing);
    # Pure lazy = purple/lavender so it's visually adjacent but distinct.
    COMBO_HI = COLORS["secondary"]   # teal — best combo @ ≥100%
    COMBO_LO = "#7eafa4"             # sage — best combo @ ≥94%
    LAZY_HI = "#6c3e92"              # purple — pure lazy @ ≥100%
    LAZY_LO = "#a07cc1"              # lavender — pure lazy @ ≥94%

    def _draw_combo_subgroup(group_x_center: float, label: str,
                             entries: list[tuple[str, dict | None]],
                             colors: tuple[str, str]) -> None:
        """Render one combo sub-group at ``group_x_center`` with one bar
        per tier (filled = qualifying winner, hatched = ceiling-only
        when no config meets the tier)."""
        bar_w = 0.34
        entries_present = [(t, e) for t, e in entries if e]
        n_t = len(entries_present)
        if n_t == 0:
            return
        offsets = [(i - (n_t - 1) / 2) * (bar_w + 0.04) for i in range(n_t)]
        for (tier_name, entry), off, fc in zip(entries_present, offsets, colors):
            rec = entry["rec"]
            x_pos = group_x_center + off
            ax.bar(x_pos, rec["acc"], width=bar_w, color=fc,
                   edgecolor="none", zorder=2)
            cost_per_genome = rec["cost"] * WHOLE_GENOME_N
            n_b = rec.get("n_to_b", rec.get("n_dis", 0))
            n_c = rec.get("n_to_c", 0)
            if entry["is_pure_lazy"]:
                esc = f"{rec.get('n_dis', 0)}/17 tied"
            else:
                esc = f"{n_b}→B"
                if rec.get("c") is not None:
                    esc += f", {n_c}→C"
            ax.text(
                x_pos, rec["acc"] + 0.018,
                f"{tier_name}\n${cost_per_genome:,.0f}\n{esc}",
                ha="center", va="bottom",
                fontsize=8, color=COLORS["dark"],
                linespacing=1.2, fontweight="bold",
            )
            # Composition notation:
            #  * Pure lazy: "A + B → C" — A and B vote, C is the tiebreaker.
            #  * Cascade (no lazy):     "A → B"     — B fires on A's escalation.
            #  * Cascade + lazy:        "A → B → C" — B fires on escalation,
            #    C fires on the A/B disagreement after that.
            comp_lines = [entry["strategy"], _short(rec["a"])]
            if rec.get("b"):
                sep = "+" if entry["is_pure_lazy"] else "→"
                comp_lines.append(f"{sep} {_short(rec['b'])}")
            if rec.get("c"):
                comp_lines.append(f"→ {_short(rec['c'])}")
            ax.text(
                x_pos, rec["acc"] / 2, "\n".join(comp_lines),
                ha="center", va="center",
                fontsize=6.8, color="white", linespacing=1.2,
                style="italic",
            )

    # Lay out two sub-groups: "Best combo" then "Pure lazy".
    n_models = len(models)
    n_combo_groups = 0
    if any_combos:
        # Best combo (any strategy)
        _draw_combo_subgroup(
            n_models,
            "Best combo",
            [("≥100%", best_by_tier["≥100%"]), ("≥94%", best_by_tier["≥94%"])],
            (COMBO_HI, COMBO_LO),
        )
        n_combo_groups += 1
        # Pure lazy (separate)
        if any(lazy_by_tier.values()):
            _draw_combo_subgroup(
                n_models + 1,
                "Pure lazy",
                [("≥100%", lazy_by_tier["≥100%"]), ("≥94%", lazy_by_tier["≥94%"])],
                (LAZY_HI, LAZY_LO),
            )
            n_combo_groups += 1

    ax.set_xlabel("")
    ax.set_ylabel("Verdict accuracy on 17-protein sub-benchmark")
    # Wrapped title — three lines for legibility on narrow renderings.
    ax.set_title(
        "Triage sub-benchmark: variant × model accuracy\n"
        f"costs extrapolated to a {WHOLE_GENOME_N:,}-gene whole-genome pass "
        "(NCBI protein-coding, 1 rep/gene)\n"
        "Best combo = cheapest across 11 strategies (cascade + lazy)  ·  "
        "Pure lazy = cheapest A+B → C tiebreak  ·  "
        "ties within ~5% prefer NCBI-anchored cells",
        fontsize=11, linespacing=1.3,
    )
    xtick_positions = list(range(len(models))) + (
        [n_models + i for i in range(n_combo_groups)] if any_combos else []
    )
    combo_xtick_labels = ["Best combo", "Pure lazy"][:n_combo_groups]
    xtick_labels = [MODEL_LABEL[m] for m in models] + combo_xtick_labels
    ax.set_xticks(xtick_positions)
    ax.set_xticklabels(xtick_labels)
    if any_combos:
        ax.set_xlim(-0.6, len(models) + n_combo_groups - 0.4)
    ax.set_ylim(0, 1.22)
    # Build the legend from coloured Patch swatches so each variant's shade
    # is visible in the legend (the default barplot legend renders as
    # outline-only lines when we override the labels).
    from matplotlib.lines import Line2D
    from matplotlib.patches import Patch
    legend_handles = [
        Patch(facecolor=CLAUDE_ORANGE_SHADES[v], edgecolor="none", label=VARIANT_LABEL[v])
        for v in VARIANT_ORDER
    ] + [
        Line2D(
            [], [], marker="o", color="w", markerfacecolor="white",
            markeredgecolor=COLORS["dark"], markeredgewidth=1.1,
            markersize=8, label="One replicate",
        )
    ] + (
        [
            Patch(facecolor=COMBO_HI, edgecolor="none",
                  label="Best combo ≥ 100%"),
            Patch(facecolor=COMBO_LO, edgecolor="none",
                  label="Best combo ≥ 94%"),
        ]
        if any_combos else []
    ) + (
        [
            Patch(facecolor=LAZY_HI, edgecolor="none",
                  label="Pure lazy ≥ 100%"),
            Patch(facecolor=LAZY_LO, edgecolor="none",
                  label="Pure lazy ≥ 94%"),
        ]
        if any(lazy_by_tier.values()) else []
    )
    ax.legend(
        handles=legend_handles,
        title="Prompt variant",
        loc="upper left", bbox_to_anchor=(1.02, 1.0),
        frameon=False, borderaxespad=0.0,
    )
    sns.despine(ax=ax, top=True, right=True)

    if mixed_prompts:
        stale_cells = sorted(cells_in_data - FRESH_CELLS)
        fresh_cells = sorted(cells_in_data & FRESH_CELLS)
        fresh_labels = ", ".join(
            f"{m.replace('claude-', '').split('-')[0]}/{v}" for m, v in fresh_cells
        )
        stale_summary = ", ".join(
            f"{m.replace('claude-', '').split('-')[0]}/{v}" for m, v in stale_cells
        )
        fig.text(
            0.5, 0.005,
            f"Hatched bars = stale: captured under earlier prompt revisions ({stale_summary}). "
            f"Solid bars = current prompt: {fresh_labels}.",
            ha="center", va="bottom", fontsize=8,
            color=COLORS["neutral"], style="italic",
        )
        fig.subplots_adjust(bottom=0.12)

    out_dir.mkdir(parents=True, exist_ok=True)
    save_figure(
        fig, filename="subbench_accuracy_by_variant",
        output_dir=str(out_dir), formats=["pdf", "png"],
    )
    plt.close(fig)


def plot_per_protein(df: pd.DataFrame, out_dir: Path) -> None:
    """Per-protein × variant grid, one column per model.

    Each cell shows the prediction (yes/contextual/no) with a filled
    background when correct and a striped/light background when wrong.
    """
    setup_plotting_style(style="white", context="notebook", font_scale=0.85)

    truth = _load_ground_truth()
    genes = list(truth.keys())  # preserve TSV order
    n_genes = len(genes)
    models = [m for m in MODEL_ORDER if m in df.model.unique()]

    # Use a representative replicate per (gene, variant, model): pick the
    # majority prediction across replicates, breaking ties toward the
    # truth-correct one.
    cell_view: dict[tuple[str, str, str], dict] = {}
    for (gene, variant, model), group in df.groupby(["gene_symbol", "variant", "model"]):
        preds = group.predicted_verdict.value_counts()
        # Majority pred; in tie, prefer one matching truth.
        truth_v = truth.get(gene, {}).get("ground_truth_verdict", "?")
        if truth_v in preds.index and preds.get(truth_v, 0) == preds.max():
            pred = truth_v
        else:
            pred = preds.index[0]
        # Did at least one replicate get it right?
        any_correct = bool(group["correct"].any())
        cell_view[(gene, variant, model)] = {
            "pred": pred, "any_correct": any_correct, "truth": truth_v,
        }

    fig, axes = plt.subplots(
        1, len(models), figsize=(2 + 2.5 * len(models), 0.32 * n_genes + 1.6),
        sharey=True,
    )
    if len(models) == 1:
        axes = [axes]
    for ax, model in zip(axes, models):
        for var_idx, variant in enumerate(VARIANT_ORDER):
            color = CLAUDE_ORANGE_SHADES[variant]
            for gene_idx, gene in enumerate(genes):
                cell = cell_view.get((gene, variant, model))
                if cell is None:
                    continue
                # Cell background: filled with the variant's shade when
                # correct in ANY replicate; light-grey wash when always wrong.
                if cell["any_correct"]:
                    ax.add_patch(plt.Rectangle(
                        (var_idx - 0.45, gene_idx - 0.45), 0.9, 0.9,
                        color=color, alpha=0.85,
                    ))
                else:
                    ax.add_patch(plt.Rectangle(
                        (var_idx - 0.45, gene_idx - 0.45), 0.9, 0.9,
                        color="#e4dcd5", alpha=0.6,
                    ))
                # Print the prediction abbreviation.
                pred_abbrev = {"yes": "Y", "contextual": "C", "no": "N",
                               "MISSING": "—"}.get(cell["pred"], cell["pred"][:1])
                ax.text(
                    var_idx, gene_idx, pred_abbrev,
                    ha="center", va="center",
                    fontsize=10, fontweight="bold",
                    color="white" if cell["any_correct"] else COLORS["neutral"],
                )
        ax.set_xlim(-0.6, len(VARIANT_ORDER) - 0.4)
        ax.set_ylim(n_genes - 0.5, -0.5)
        ax.set_xticks(range(len(VARIANT_ORDER)))
        ax.set_xticklabels(
            [VARIANT_LABEL[v].replace("\n", "\n") for v in VARIANT_ORDER],
            rotation=30, ha="right", fontsize=9,
        )
        ax.set_yticks(range(n_genes))
        truth_labels = [
            f"{g} ({truth[g]['ground_truth_verdict'][:3]})" for g in genes
        ]
        ax.set_yticklabels(truth_labels, fontsize=9)
        ax.set_title(MODEL_LABEL[model], fontsize=12)
        ax.tick_params(length=0)
        for spine in ax.spines.values():
            spine.set_visible(False)

    fig.suptitle(
        "Sub-benchmark per-protein correctness  ·  Y=yes / C=contextual / N=no  ·  "
        "colored cell = correct in ≥1 replicate, grey = always wrong",
        y=1.02, fontsize=10,
    )
    fig.tight_layout()

    out_dir.mkdir(parents=True, exist_ok=True)
    save_figure(
        fig, filename="subbench_per_protein",
        output_dir=str(out_dir), formats=["pdf", "png"],
    )
    plt.close(fig)


def plot_cost_vs_accuracy(df: pd.DataFrame, out_dir: Path) -> None:
    setup_plotting_style(style="whitegrid", context="notebook", font_scale=1.0)
    # One point per (model, variant) — replicates averaged. Per-rep
    # variance is already shown on the accuracy-by-variant figure; this
    # plot is the Pareto-frontier view, so we want a single point per cell.
    per_cell = (
        df.groupby(["model", "variant"], as_index=False)
        .agg(
            n=("correct", "size"),
            n_correct=("correct", "sum"),
            n_reps=("replicate", "nunique"),
            cost_per_rep_mean=("cost_usd", "mean"),
        )
    )
    per_cell["accuracy"] = per_cell.n_correct / per_cell.n
    # Mean per-cell cost × WHOLE_GENOME_N == cost of one production pass.
    per_cell["genome_cost"] = per_cell.cost_per_rep_mean * WHOLE_GENOME_N

    fig, ax = plt.subplots(figsize=(9.0, 5.8))
    cells_in_data = {(r.model, r.variant) for _, r in per_cell.iterrows()}
    has_stale = bool(cells_in_data - FRESH_CELLS)
    has_fresh = bool(cells_in_data & FRESH_CELLS)
    mixed_prompts = has_stale and has_fresh

    for model in MODEL_ORDER:
        sub = per_cell[per_cell.model == model]
        if sub.empty:
            continue
        marker = MODEL_MARKER.get(model, "o")
        for _, row in sub.iterrows():
            is_fresh = (row.model, row.variant) in FRESH_CELLS
            ax.scatter(
                row.genome_cost, row.accuracy,
                s=220,
                color=CLAUDE_ORANGE_SHADES[row.variant] if is_fresh else "white",
                marker=marker,
                edgecolor=CLAUDE_ORANGE_SHADES[row.variant] if not is_fresh else COLORS["dark"],
                linewidth=1.3 if not is_fresh else 1.0,
                alpha=0.55 if not is_fresh else 1.0,
                zorder=3,
            )
            label = row.variant + ("†" if mixed_prompts and not is_fresh else "")
            ax.annotate(
                label, (row.genome_cost, row.accuracy),
                xytext=(8, 4), textcoords="offset points", fontsize=9,
                color=COLORS["neutral"],
                alpha=0.7 if not is_fresh else 1.0,
            )

    # Headline winners — exactly four points, matching the variant
    # barplot's combo group: best cascade @ ≥100% / ≥94% (teal/sage
    # diamonds) and best pure-lazy triple @ ≥100% / ≥94% (purple/
    # lavender stars). Composition notation:
    #   * cascade:   A → B  (or  A → B → C  for "+ lazy" cascades).
    #   * pure lazy: A + B → C  (A and B vote, C is the tiebreaker).
    truth_rows = _load_ground_truth()

    def _short(cell):
        m_, v_ = cell
        return f"{m_.replace('claude-', '').split('-')[0]}/{v_}"

    summary = _summarize_strategies(df, truth_rows)

    def _cheapest_at(tier_name, *, pure_lazy: bool):
        cand = [
            s for s in summary
            if s["tier"] == tier_name and s["rec"]
            and (s["is_pure_lazy"] == pure_lazy)
        ]
        cand.sort(key=lambda s: s["rec"]["cost"])
        return cand[0] if cand else None

    # Match the variant-plot palette so the two figures tell the same story.
    BEST_HI = COLORS["secondary"]   # teal
    BEST_LO = "#7eafa4"             # sage
    LAZY_HI = "#6c3e92"             # purple
    LAZY_LO = "#a07cc1"             # lavender

    headline = [
        ("Best combo ≥100%", _cheapest_at("≥100%", pure_lazy=False),
         "D", BEST_HI),
        ("Best combo ≥94%",  _cheapest_at("≥94%",  pure_lazy=False),
         "D", BEST_LO),
        ("Pure lazy ≥100%",  _cheapest_at("≥100%", pure_lazy=True),
         "*", LAZY_HI),
        ("Pure lazy ≥94%",   _cheapest_at("≥94%",  pure_lazy=True),
         "*", LAZY_LO),
    ]
    combined_tiers = [
        (lbl, e["rec"], color)
        for lbl, e, _, color in headline
        if e is not None and not lbl.startswith("Pure")
    ]  # used downstream for legend conditioning
    pure_lazy_present = any(
        e is not None for lbl, e, _, _ in headline if lbl.startswith("Pure")
    )

    for label, entry, marker, fc in headline:
        if entry is None:
            continue
        rec = entry["rec"]
        gc = rec["cost"] * WHOLE_GENOME_N
        ax.scatter(
            gc, rec["acc"],
            s=420 if marker == "*" else 320,
            color=fc, marker=marker,
            edgecolor=COLORS["dark"], linewidth=1.3, zorder=5,
        )
        # Build the composition string with the right separator.
        is_lazy = entry["is_pure_lazy"]
        parts = [_short(rec["a"])]
        if rec.get("b"):
            sep = "+" if is_lazy else "→"
            parts.append(f"{sep} {_short(rec['b'])}")
        if rec.get("c"):
            parts.append(f"→ {_short(rec['c'])}")
        comp = " ".join(parts)
        # ≥100% labels go above the marker; ≥94% labels go below so
        # they don't collide on the log-x axis.
        is_hi = "≥100%" in label
        ax.annotate(
            f"{label}\n{entry['strategy']}: {comp}",
            (gc, rec["acc"]),
            xytext=(10, 10 if is_hi else -22),
            textcoords="offset points",
            fontsize=8.5, color=COLORS["dark"], fontweight="bold",
        )

    # --- Pareto frontier ----------------------------------------------
    # Walk all points (per-cell + cascade winners + pure-lazy) in
    # cost-ascending order; keep a point only when its accuracy strictly
    # exceeds the previous best. Draw a step curve through the survivors
    # so the flattening / knee of the cost/accuracy curve is visible.
    frontier_points = [
        (row.genome_cost, row.accuracy, f"{row.model}/{row.variant}")
        for _, row in per_cell.iterrows()
    ] + [
        (entry["rec"]["cost"] * WHOLE_GENOME_N, entry["rec"]["acc"], label)
        for label, entry, _, _ in headline
        if entry is not None
    ]
    frontier_points.sort(key=lambda p: p[0])
    pareto = []
    best_acc = -1.0
    for cost, acc, label in frontier_points:
        if acc > best_acc + 1e-9:
            pareto.append((cost, acc, label))
            best_acc = acc
    if len(pareto) >= 2:
        # Step curve: at each frontier point, jump up to new accuracy,
        # then extend right to the next point's cost. This makes the
        # plateau between successive frontier points explicit.
        step_x = []
        step_y = []
        for i, (c, a, _) in enumerate(pareto):
            if i == 0:
                step_x.append(c)
                step_y.append(a)
            else:
                # horizontal segment from previous (cost, prev_acc) up to
                # (this cost, prev_acc), then vertical up to (this cost,
                # this_acc).
                prev_c, prev_a, _ = pareto[i - 1]
                step_x.extend([c, c])
                step_y.extend([prev_a, a])
        ax.plot(
            step_x, step_y,
            color=COLORS["dark"], linewidth=1.6,
            linestyle="--", alpha=0.55, zorder=2,
        )
        # Annotate the knee — first plateau point — so the reader sees
        # where additional spend stops buying meaningful accuracy.
        # The knee is the cheapest point at the second-to-last accuracy.
        # For our data this should be the Combined ≥94% star.
        knee = pareto[-2] if len(pareto) >= 2 else None
        if knee and knee[1] >= 0.9:
            ax.annotate(
                "knee:\nlowest cost\nat 90 %+ acc",
                xy=(knee[0], knee[1]),
                xytext=(-90, -28), textcoords="offset points",
                fontsize=8.5, color=COLORS["neutral"], style="italic",
                arrowprops=dict(arrowstyle="->", color=COLORS["neutral"],
                                lw=0.8, alpha=0.6),
            )

    ax.set_xlabel(
        f"Cost per whole-genome triage pass ({WHOLE_GENOME_N:,} NCBI "
        "protein-coding genes × 1 rep, USD)"
    )
    ax.set_ylabel("Verdict accuracy on 17-protein sub-benchmark")
    n_cells = int(per_cell.shape[0])
    ax.set_title(
        f"Cost vs accuracy: {n_cells} per-cell points (replicates averaged)\n"
        "+ four headline winners (best combo / pure lazy, each at ≥100% / ≥94%)  ·  "
        "matches variant-plot combo bars",
        fontsize=11, linespacing=1.3,
    )
    ax.set_ylim(0, 1.07)
    ax.set_xscale("log")
    # Legend: shade-by-variant, marker-by-model, star for Combined.
    from matplotlib.lines import Line2D
    models_present = [m for m in MODEL_ORDER if m in per_cell.model.unique()]
    handles = [
        Line2D([], [], marker="o", color="w", markerfacecolor=CLAUDE_ORANGE_SHADES[v],
               markersize=11, markeredgecolor=COLORS["dark"], label=VARIANT_LABEL[v].replace("\n", " "))
        for v in VARIANT_ORDER
    ] + [
        Line2D(
            [], [], marker=MODEL_MARKER[m], color="w",
            markerfacecolor=COLORS["neutral"], markersize=10,
            markeredgecolor=COLORS["dark"],
            label=MODEL_LABEL[m] + ("*" if mixed_prompts and m in PROMPT_FRESH_MODELS else ""),
        )
        for m in models_present
    ] + (
        # Four headline winners — same color/shape mapping as the
        # variant barplot's combo bars so the two figures tell the same
        # story at a glance.
        [
            Line2D([], [], marker="D", color="w", markerfacecolor=BEST_HI,
                   markersize=12, markeredgecolor=COLORS["dark"],
                   label="Best combo ≥100% (cascade)"),
            Line2D([], [], marker="D", color="w", markerfacecolor=BEST_LO,
                   markersize=12, markeredgecolor=COLORS["dark"],
                   label="Best combo ≥94% (cascade)"),
            Line2D([], [], marker="*", color="w", markerfacecolor=LAZY_HI,
                   markersize=16, markeredgecolor=COLORS["dark"],
                   label="Pure lazy ≥100% (A+B → C)"),
            Line2D([], [], marker="*", color="w", markerfacecolor=LAZY_LO,
                   markersize=16, markeredgecolor=COLORS["dark"],
                   label="Pure lazy ≥94% (A+B → C)"),
        ]
        if combined_tiers or pure_lazy_present else []
    ) + (
        [Line2D([], [], color=COLORS["dark"], linewidth=1.6,
                linestyle="--", alpha=0.6, label="Pareto frontier")]
        if len(pareto) >= 2 else []
    )
    ax.legend(handles=handles, loc="upper left", bbox_to_anchor=(1.02, 1.0),
              frameon=False, borderaxespad=0.0)
    sns.despine(ax=ax, top=True, right=True)

    if mixed_prompts:
        stale_cells = sorted(cells_in_data - FRESH_CELLS)
        fresh_cells = sorted(cells_in_data & FRESH_CELLS)
        fresh_labels = ", ".join(
            f"{m.replace('claude-', '').split('-')[0]}/{v}" for m, v in fresh_cells
        )
        stale_summary = ", ".join(
            f"{m.replace('claude-', '').split('-')[0]}/{v}" for m, v in stale_cells
        )
        fig.text(
            0.5, 0.005,
            f"†Hollow markers = stale: captured under earlier prompt revisions ({stale_summary}). "
            f"Filled markers = current prompt: {fresh_labels}.",
            ha="center", va="bottom", fontsize=8,
            color=COLORS["neutral"], style="italic",
        )
        fig.subplots_adjust(bottom=0.14)

    out_dir.mkdir(parents=True, exist_ok=True)
    save_figure(
        fig, filename="subbench_cost_vs_accuracy",
        output_dir=str(out_dir), formats=["pdf", "png"],
    )
    plt.close(fig)


def _best_of_k_accuracy(
    df: pd.DataFrame, model: str, variant: str, k: int, strategy: str = "majority"
) -> float | None:
    """Compute per-gene ensemble accuracy at fixed K reps.

    Two strategies:

    * ``majority`` — for each gene, pick the verdict with the most votes
      across the first K reps. Tie-break by truth-match (gives the ensemble
      the benefit of the doubt on hung juries; this is the standard
      "consensus with oracle tiebreak" used in the per-protein grid).
    * ``oracle`` — gene counts correct if ANY of the K reps got it right;
      upper-bound ensemble (assuming you could perfectly route to the
      right rep).

    Returns ``None`` when fewer than K reps exist for some gene in this
    cell (i.e. the plot point isn't well-defined).
    """
    cell = df[(df.model == model) & (df.variant == variant)]
    if cell.empty:
        return None

    per_gene_correct = []
    for gene, group in cell.groupby("gene_symbol"):
        if len(group) < k:
            return None  # ragged — skip this K for this cell
        # Take the first K reps in replicate-order (sorting so the result
        # is deterministic across runs).
        sub = group.sort_values("replicate").head(k)
        truth = sub.truth_verdict.iloc[0]
        if strategy == "oracle":
            per_gene_correct.append(bool(sub["correct"].any()))
        else:  # majority
            counts = sub.predicted_verdict.value_counts()
            top = counts.max()
            top_preds = counts[counts == top].index.tolist()
            # Oracle tiebreak: if truth is among the tied top, pick it.
            chosen = truth if truth in top_preds else top_preds[0]
            per_gene_correct.append(chosen == truth)
    return sum(per_gene_correct) / len(per_gene_correct)


def plot_best_of_k(df: pd.DataFrame, out_dir: Path) -> None:
    """Best-of-K ensemble accuracy as a function of replicate budget K.

    For each (model, variant), draws a line of majority-vote accuracy vs
    K (with oracle-tiebreak on hung juries), plus a dashed "oracle" line
    showing the any-correct ceiling. Annotates the K at which majority
    accuracy first hits 100% or plateaus (≤ 1/N improvement vs previous K).
    """
    setup_plotting_style(style="whitegrid", context="notebook", font_scale=1.0)

    models = [m for m in MODEL_ORDER if m in df.model.unique()]
    fig, axes = plt.subplots(
        1, len(models), figsize=(4.5 * len(models) + 1.0, 5.5), sharey=True,
    )
    if len(models) == 1:
        axes = [axes]

    # Truth-table row count drives the "plateau" threshold: any K-to-K+1
    # change < 1 / n_genes is essentially a single-gene swing.
    n_genes = df.gene_symbol.nunique()
    plateau_eps = 1.0 / max(n_genes, 1)

    for ax, model in zip(axes, models):
        cell_rep_counts = (
            df[df.model == model]
            .groupby(["variant", "gene_symbol"])
            .size()
            .groupby("variant")
            .min()
        )
        # Max K we can plot for this model = min reps per gene across variants.
        max_k_per_variant = {v: int(n) for v, n in cell_rep_counts.items()}

        for variant in VARIANT_ORDER:
            max_k = max_k_per_variant.get(variant, 0)
            if max_k < 1:
                continue
            ks = list(range(1, max_k + 1))
            maj_acc = [_best_of_k_accuracy(df, model, variant, k, "majority") for k in ks]
            orc_acc = [_best_of_k_accuracy(df, model, variant, k, "oracle") for k in ks]
            color = CLAUDE_ORANGE_SHADES[variant]
            # Majority-vote line — solid
            ax.plot(ks, maj_acc, marker="o", markersize=8, color=color,
                    linewidth=2.0, label=VARIANT_LABEL[variant], zorder=4)
            # Oracle ceiling — dashed, slightly transparent
            ax.plot(ks, orc_acc, marker="^", markersize=6, color=color,
                    linewidth=1.0, linestyle="--", alpha=0.55, zorder=3)

            # Annotate plateau / 100% point on the majority curve.
            for i, k in enumerate(ks):
                if maj_acc[i] is None:
                    continue
                hit_100 = maj_acc[i] >= 1.0 - 1e-9
                stalled = (
                    i > 0 and maj_acc[i - 1] is not None
                    and abs(maj_acc[i] - maj_acc[i - 1]) <= plateau_eps
                )
                if hit_100 or (stalled and i == len(ks) - 1):
                    ax.scatter([k], [maj_acc[i]], s=180, marker="o",
                               facecolor="none", edgecolor=color,
                               linewidth=2.4, zorder=5)
                    ax.annotate(
                        f"K={k}\n{maj_acc[i]:.0%}",
                        (k, maj_acc[i]), xytext=(8, -4),
                        textcoords="offset points", fontsize=8.5,
                        color=color,
                    )
                    break

        ax.set_title(MODEL_LABEL[model], fontsize=12)
        ax.set_xlabel("Reps combined (K)")
        ax.set_xticks(range(1, max(max_k_per_variant.values(), default=1) + 1))
        ax.set_ylim(0, 1.05)
        ax.grid(True, axis="y", linestyle=":", alpha=0.4)

    axes[0].set_ylabel("Verdict accuracy on 17-protein sub-benchmark")

    # Shared legend below the row of subplots.
    from matplotlib.lines import Line2D
    handles = [
        Line2D([], [], marker="o", color=CLAUDE_ORANGE_SHADES[v],
               markersize=8, linewidth=2.0, label=VARIANT_LABEL[v].replace("\n", " "))
        for v in VARIANT_ORDER
    ] + [
        Line2D([], [], marker="^", color=COLORS["neutral"], markersize=6,
               linewidth=1.0, linestyle="--", alpha=0.7,
               label="Oracle ceiling (any rep correct)"),
        Line2D([], [], marker="o", color="white",
               markerfacecolor="none", markeredgecolor=COLORS["dark"],
               markersize=12, markeredgewidth=2.0, linewidth=0,
               label="Plateau / 100% marker"),
    ]
    fig.legend(
        handles=handles, loc="lower center",
        bbox_to_anchor=(0.5, -0.02), ncol=3, frameon=False, fontsize=9,
    )
    fig.suptitle(
        "Best-of-K ensemble accuracy across prompt variants  ·  "
        "solid = majority vote with oracle tiebreak  ·  dashed = oracle ceiling",
        fontsize=11, y=1.005,
    )
    fig.tight_layout(rect=(0, 0.06, 1, 0.98))

    out_dir.mkdir(parents=True, exist_ok=True)
    save_figure(
        fig, filename="subbench_best_of_k",
        output_dir=str(out_dir), formats=["pdf", "png"],
    )
    plt.close(fig)


def plot_lazy_ensemble_landscape(df: pd.DataFrame, out_dir: Path) -> None:
    """Dedicated panel: what does pure lazy actually achieve?

    For every (A, B, C) triple, plot (expected $/genome, accuracy) as a
    scatter point. Marker color encodes the tiebreaker cell (C), which
    is what differentiates triples that share an (A, B) pair.
    Annotate the cheapest triple at each unique accuracy level so the
    structural ceiling is obvious.

    Companion to plot_cost_vs_accuracy, which folds lazy into a
    one-dot-per-strategy view. This plot exists so the reader can see
    the *full* lazy-ensemble landscape — where lazy can and cannot
    reach, independent of cascade strategies.
    """
    from itertools import combinations

    setup_plotting_style(style="whitegrid", context="notebook", font_scale=1.0)
    truth = _load_ground_truth()
    cells = sorted({(r["model"], r["variant"]) for _, r in df.iterrows()})

    def _short(cell):
        m_, v_ = cell
        return f"{m_.replace('claude-', '').split('-')[0]}/{v_}"

    # Sweep every (A, B, C) triple. A and B are unordered; C is the
    # tiebreaker. Record (cost, acc, A, B, C, n_dis).
    triples: list[dict] = []
    for a, b in combinations(cells, 2):
        for c in cells:
            if c in (a, b):
                continue
            acc, cost, n_dis = _lazy_ensemble(df, truth, a, b, c)
            triples.append({
                "a": a, "b": b, "c": c,
                "acc": acc, "cost_per_genome": cost * WHOLE_GENOME_N,
                "n_dis": n_dis,
            })
    if not triples:
        return

    fig, ax = plt.subplots(figsize=(11, 6))

    # Build a deterministic color per tiebreaker cell. Use a categorical
    # palette so the legend stays readable.
    c_cells = sorted({t["c"] for t in triples})
    palette = sns.color_palette("Set2", n_colors=len(c_cells))
    color_for_c = dict(zip(c_cells, palette))

    # Marker per (A, B) PAIR — we use shape to encode "which two cells
    # do the voting". Pick from a stable list.
    pair_markers = ["o", "s", "D", "^", "v", "P", "X", "*", "h", "<"]
    pair_keys = sorted({(t["a"], t["b"]) for t in triples})
    marker_for_pair = {
        pair: pair_markers[i % len(pair_markers)]
        for i, pair in enumerate(pair_keys)
    }

    # Plot each triple. Slight horizontal jitter on overlapping points
    # is unnecessary at log-x because cost spreads naturally.
    for t in triples:
        ax.scatter(
            t["cost_per_genome"], t["acc"],
            s=110, color=color_for_c[t["c"]],
            marker=marker_for_pair[(t["a"], t["b"])],
            edgecolor=COLORS["dark"], linewidth=0.9, alpha=0.85, zorder=3,
        )

    # Horizontal ceiling line at the max-achievable accuracy.
    max_acc = max(t["acc"] for t in triples)
    ax.axhline(max_acc, color=COLORS["dark"], linestyle="--",
               linewidth=1.2, alpha=0.6, zorder=2)
    ax.text(
        ax.get_xlim()[1] * 0.99, max_acc + 0.005,
        f"  lazy ceiling: {max_acc:.1%}",
        ha="right", va="bottom",
        color=COLORS["dark"], fontsize=10, fontweight="bold",
        style="italic",
    )

    # Annotate the cheapest triple at each unique accuracy level.
    by_acc: dict[float, dict] = {}
    for t in triples:
        ak = round(t["acc"], 4)
        if ak not in by_acc or t["cost_per_genome"] < by_acc[ak]["cost_per_genome"]:
            by_acc[ak] = t
    for ak, t in sorted(by_acc.items()):
        label = (
            f"{_short(t['a'])} + {_short(t['b'])}\n"
            f"→ {_short(t['c'])}*  ({t['n_dis']}/17 tied)"
        )
        ax.annotate(
            label,
            (t["cost_per_genome"], t["acc"]),
            xytext=(8, 6), textcoords="offset points",
            fontsize=7.8, color=COLORS["dark"],
            arrowprops=dict(arrowstyle="-", color=COLORS["dark"],
                            lw=0.6, alpha=0.4),
        )

    ax.set_xlabel(
        f"Expected cost per whole-genome triage pass "
        f"({WHOLE_GENOME_N:,} NCBI protein-coding genes × 1 rep, USD)"
    )
    ax.set_ylabel("Verdict accuracy on 17-protein sub-benchmark")
    ax.set_title(
        f"Lazy-ensemble landscape: {len(triples)} (A, B, C) triples  ·  "
        "A + B → C tiebreaker on disagreement  ·  "
        "yes≡contextual scoring  ·  expected cost = c(A) + c(B) + P(A,B disagree) · c(C)"
    )
    ax.set_xscale("log")
    ax.set_ylim(0, 1.05)
    sns.despine(ax=ax, top=True, right=True)

    # Legend: tiebreaker color + (A, B) marker shape.
    from matplotlib.lines import Line2D
    color_handles = [
        Line2D([], [], marker="o", color="w",
               markerfacecolor=color_for_c[c],
               markeredgecolor=COLORS["dark"], markersize=10,
               label=f"tiebreaker C = {_short(c)}")
        for c in c_cells
    ]
    shape_handles = [
        Line2D([], [], marker=marker_for_pair[pair], color="w",
               markerfacecolor="white", markeredgecolor=COLORS["dark"],
               markersize=9,
               label=f"A+B = {_short(pair[0])} + {_short(pair[1])}")
        for pair in pair_keys
    ]
    legend1 = ax.legend(
        handles=color_handles, title="Tiebreaker (color)",
        loc="upper left", bbox_to_anchor=(1.02, 1.0),
        frameon=False, fontsize=8,
    )
    ax.add_artist(legend1)
    ax.legend(
        handles=shape_handles, title="A + B pair (shape)",
        loc="lower left", bbox_to_anchor=(1.02, 0.0),
        frameon=False, fontsize=8,
    )

    out_dir.mkdir(parents=True, exist_ok=True)
    save_figure(
        fig, filename="subbench_lazy_landscape",
        output_dir=str(out_dir), formats=["pdf", "png"],
    )
    plt.close(fig)


def main() -> None:
    df = _build_dataframe()
    if df.empty:
        raise SystemExit(
            f"No sub-bench run records found under {RUNS_DIR}. "
            f"Run scripts/triage_subbench_runner.py first."
        )
    print(f"Loaded {len(df)} run records")
    print(df.groupby(["model", "variant"]).size().to_string())
    truth = _load_ground_truth()
    _print_strategy_table(_summarize_strategies(df, truth))
    plot_accuracy_by_variant(df, OUT_DIR)
    plot_per_protein(df, OUT_DIR)
    plot_cost_vs_accuracy(df, OUT_DIR)
    plot_best_of_k(df, OUT_DIR)
    plot_lazy_ensemble_landscape(df, OUT_DIR)
    print(f"\nWrote 5 plots to {OUT_DIR}")


if __name__ == "__main__":
    main()
