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
    ("claude-sonnet-4-6", "naive"),
    ("claude-sonnet-4-6", "ncbi"),
    ("claude-opus-4-7", "naive"),
})
# When True, _build_dataframe filters records to FRESH_CELLS only — used
# when the user wants the "latest prompt version only" view. Set via the
# --fresh-only CLI flag.
FILTER_TO_FRESH = True
# Back-compat: kept for callers / older code paths that referenced this.
PROMPT_FRESH_MODELS: frozenset[str] = frozenset()


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
    rows = []
    for r in runs:
        gene = r["gene_symbol"]
        cell = (r["model"], r["variant"])
        if FILTER_TO_FRESH and cell not in FRESH_CELLS:
            continue
        current_truth = (truth.get(gene) or {}).get("ground_truth_verdict") or r["truth_verdict"]
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
            "correct": (r["predicted_verdict"] or "") == current_truth,
            "cost_usd": r["cost_usd"],
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
        if chosen == truth[g]["ground_truth_verdict"]:
            correct += 1
    n = len(genes)
    acc = correct / n
    exp_cost = (
        cost_per_rep[a] + cost_per_rep[b]
        + (n_dis / n) * cost_per_rep[c]
    )
    return acc, exp_cost, n_dis


def _best_lazy_at_tier(
    df: pd.DataFrame, truth: dict, acc_threshold: float
) -> dict | None:
    """Sweep every (A, B, C) triple and return the cheapest configuration
    meeting ``acc_threshold``. Returns a dict with the trio + metrics."""
    from itertools import combinations
    cells = sorted({(r["model"], r["variant"]) for _, r in df.iterrows()})
    best = None
    for a, b in combinations(cells, 2):
        for c in cells:
            if c == a or c == b:
                continue
            acc, cost, n_dis = _lazy_ensemble(df, truth, a, b, c)
            if acc + 1e-9 < acc_threshold:
                continue
            if best is None or cost < best["cost"]:
                best = {"a": a, "b": b, "c": c, "acc": acc, "cost": cost,
                        "n_dis": n_dis}
    return best


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
        if chosen == truth[g]["ground_truth_verdict"]:
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
    the cheapest configuration that meets ``acc_threshold``."""
    pred = ESCALATE_PREDICATES[predicate_name]
    cells = sorted({(r["model"], r["variant"]) for _, r in df.iterrows()})
    best: dict | None = None
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
                    if best is None or cost < best["cost"]:
                        best = {
                            "a": a, "b": b, "c": c,
                            "acc": acc, "cost": cost,
                            "n_to_b": nb, "n_to_c": nc,
                            "with_lazy": True,
                            "predicate": predicate_name,
                        }
            else:
                acc, cost, nb, _ = _cascade(df, truth, a, b, None, pred)
                if acc + 1e-9 < acc_threshold:
                    continue
                if best is None or cost < best["cost"]:
                    best = {
                        "a": a, "b": b, "c": None,
                        "acc": acc, "cost": cost,
                        "n_to_b": nb, "n_to_c": 0,
                        "with_lazy": False,
                        "predicate": predicate_name,
                    }
    return best


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
    best_by_tier: dict[str, dict | None] = {}
    for tier_name in ("≥100%", "≥94%"):
        candidates = [s for s in summary if s["tier"] == tier_name and s["rec"]]
        candidates.sort(key=lambda s: s["rec"]["cost"])
        best_by_tier[tier_name] = candidates[0] if candidates else None
    any_combos = any(best_by_tier.values())

    # Two-bar combo group: brand them as best-overall winners. Use the
    # familiar teal/sage palette so the combo bars stay visually distinct
    # from the orange per-cell bars.
    COMBO_HI = COLORS["secondary"]   # teal — best @ ≥100%
    COMBO_LO = "#7eafa4"             # sage — best @ ≥94%
    if any_combos:
        n_models = len(models)
        bar_w = 0.34
        group_center = n_models
        tier_entries = [(t, best_by_tier[t]) for t in ("≥100%", "≥94%")]
        tier_entries = [(t, r) for t, r in tier_entries if r]
        n_t = len(tier_entries)
        offsets = [(i - (n_t - 1) / 2) * (bar_w + 0.04) for i in range(n_t)]
        bar_colors = [COMBO_HI, COMBO_LO][:n_t]
        for (tier_name, entry), off, fc in zip(tier_entries, offsets, bar_colors):
            rec = entry["rec"]
            x_pos = group_center + off
            ax.bar(x_pos, rec["acc"], width=bar_w, color=fc,
                   edgecolor="none", zorder=2)
            cost_per_genome = rec["cost"] * WHOLE_GENOME_N
            n_b = rec.get("n_to_b", rec.get("n_dis", 0))
            n_c = rec.get("n_to_c", 0)
            esc = f"{n_b}→B"
            if rec.get("c") is not None and not entry["is_pure_lazy"]:
                esc += f", {n_c}→C"
            elif entry["is_pure_lazy"]:
                esc = f"{rec.get('n_dis', 0)}/17 tied"
            ax.text(
                x_pos, rec["acc"] + 0.018,
                f"{tier_name}\n${cost_per_genome:,.0f}\n{esc}",
                ha="center", va="bottom",
                fontsize=8, color=COLORS["dark"],
                linespacing=1.2, fontweight="bold",
            )
            comp = (
                f"{entry['strategy']}\n"
                f"{_short(rec['a'])}"
                + (f"\n→ {_short(rec['b'])}" if rec.get('b') else "")
                + (f"\n→ {_short(rec['c'])}" if rec.get('c') else "")
            )
            ax.text(
                x_pos, rec["acc"] / 2, comp,
                ha="center", va="center",
                fontsize=7, color="white", linespacing=1.2,
                style="italic",
            )

    ax.set_xlabel("")
    ax.set_ylabel("Verdict accuracy on 17-protein sub-benchmark")
    ax.set_title(
        "Triage sub-benchmark: variant × model accuracy  ·  "
        f"costs extrapolated to a {WHOLE_GENOME_N:,}-gene whole-genome pass "
        "(NCBI protein-coding, 1 rep/gene)  ·  "
        "Combo bars = cheapest config across 11 strategies "
        "(pure lazy / conf=low / conf≤med / verdict=no / unions / +lazy)"
    )
    n_combo_groups = 1 if any_combos else 0
    xtick_positions = list(range(len(models))) + (
        [len(models)] if any_combos else []
    )
    xtick_labels = [MODEL_LABEL[m] for m in models] + (
        ["Best\ncombination"] if any_combos else []
    )
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

    # Lazy-ensemble Combined points — same teal-on-teal colour scheme as
    # the accuracy_by_variant plot, distinctive star markers to set them
    # apart from the per-cell points.
    truth_rows = _load_ground_truth()
    combined_tiers = [
        ("≥100%", _best_lazy_at_tier(df, truth_rows, 0.999), COLORS["secondary"]),
        ("≥94%",  _best_lazy_at_tier(df, truth_rows, 0.94),  "#7eafa4"),
    ]
    combined_tiers = [(lbl, r, c) for lbl, r, c in combined_tiers if r]

    def _short(cell):
        m_, v_ = cell
        return f"{m_.replace('claude-', '').split('-')[0]}/{v_}"

    for label, rec, fc in combined_tiers:
        gc = rec["cost"] * WHOLE_GENOME_N
        ax.scatter(
            gc, rec["acc"],
            s=380, color=fc, marker="*",
            edgecolor=COLORS["dark"], linewidth=1.2, zorder=5,
        )
        combo_label = (
            f"Lazy-disagree {label}\n"
            f"{_short(rec['a'])} + {_short(rec['b'])} → {_short(rec['c'])}"
        )
        ax.annotate(
            combo_label, (gc, rec["acc"]),
            xytext=(10, -8), textcoords="offset points", fontsize=8.5,
            color=COLORS["dark"], fontweight="bold",
        )

    # Cascade-strategy winners — sweep every entry in STRATEGIES and plot
    # the cheapest config at each tier as a labeled marker. Marker shape
    # encodes the predicate family; fill darkness encodes the tier.
    summary = _summarize_strategies(df, truth_rows)
    # Skip "Pure lazy" here — it's drawn separately as the star above.
    cascade_summary = [s for s in summary if not s["is_pure_lazy"] and s["rec"]]
    # Marker per predicate family.
    PREDICATE_MARKER = {
        "conf_low":         "D",   # diamond
        "conf_low_or_med":  "D",
        "resp_no":          "v",   # downward triangle
        "conf_low|resp_no": "P",   # filled plus
        "conf_lm|resp_no":  "P",
    }
    # Slight color shift by predicate family for visual grouping.
    PREDICATE_COLOR_HI = {
        "conf_low":         "#6c3e92",
        "conf_low_or_med":  "#4b2b66",
        "resp_no":          "#1f7a87",
        "conf_low|resp_no": "#9b4a2f",
        "conf_lm|resp_no":  "#6b3220",
    }
    PREDICATE_COLOR_LO = {
        "conf_low":         "#a07cc1",
        "conf_low_or_med":  "#7d619a",
        "resp_no":          "#6cb3bc",
        "conf_low|resp_no": "#d28968",
        "conf_lm|resp_no":  "#a8745b",
    }
    # Only annotate the *Pareto-optimal* cascade winners so the plot
    # doesn't drown in 20 overlapping labels.
    cascade_points: list[tuple[float, float, str, str, dict]] = []
    for entry in cascade_summary:
        rec = entry["rec"]
        gc = rec["cost"] * WHOLE_GENOME_N
        cascade_points.append((gc, rec["acc"], entry["tier"], entry["strategy"], entry))
    # Plot each marker (small, low alpha for the non-winners).
    pareto_cascade = set()  # set of (cost, acc) pareto-optimal cascade points
    if cascade_points:
        sorted_pts = sorted(cascade_points, key=lambda p: p[0])
        best = -1.0
        for gc, acc, _, _, _ in sorted_pts:
            if acc > best + 1e-9:
                pareto_cascade.add((round(gc, 6), round(acc, 6)))
                best = acc
    for gc, acc, tier, strat, entry in cascade_points:
        pred = entry["predicate"]
        fc = (PREDICATE_COLOR_HI if tier == "≥100%" else PREDICATE_COLOR_LO)[pred]
        marker = PREDICATE_MARKER[pred]
        is_pareto = (round(gc, 6), round(acc, 6)) in pareto_cascade
        alpha = 1.0 if is_pareto else 0.35
        size = 220 if is_pareto else 110
        ax.scatter(
            gc, acc, s=size, color=fc, marker=marker,
            edgecolor=COLORS["dark"], linewidth=1.0 if is_pareto else 0.5,
            zorder=5 if is_pareto else 3, alpha=alpha,
        )
        if is_pareto:
            rec = entry["rec"]
            comp = f"{_short(rec['a'])} → {_short(rec['b'])}"
            if rec.get("c") is not None:
                comp += f" → {_short(rec['c'])}"
            ax.annotate(
                f"{strat} {tier}\n{comp}",
                (gc, acc),
                xytext=(10, 6 if tier == "≥100%" else -18),
                textcoords="offset points",
                fontsize=7.5, color=fc, fontweight="bold",
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
        (rec["cost"] * WHOLE_GENOME_N, rec["acc"], f"Lazy-disagree {label}")
        for label, rec, _ in combined_tiers
    ] + [
        (gc, acc, f"{strat} {tier}")
        for gc, acc, tier, strat, _ in cascade_points
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
        f"Cost vs accuracy frontier: {n_cells} per-cell points (replicates averaged) "
        "+ lazy-ensemble stars + cascade-strategy winners at ≥100% / ≥94% tiers "
        "(faded markers = Pareto-dominated)"
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
        [
            Line2D([], [], marker="*", color="w", markerfacecolor=COLORS["secondary"],
                   markersize=15, markeredgecolor=COLORS["dark"],
                   label="Lazy-disagree ≥100%"),
            Line2D([], [], marker="*", color="w", markerfacecolor="#7eafa4",
                   markersize=15, markeredgecolor=COLORS["dark"],
                   label="Lazy-disagree ≥94%"),
        ]
        if combined_tiers else []
    ) + (
        # One legend entry per predicate family (marker shape), with a
        # single representative color (the ≥100% shade). The ≥94% shade
        # is implied — same marker, lighter fill on the plot.
        [
            Line2D([], [], marker="D", color="w",
                   markerfacecolor=PREDICATE_COLOR_HI["conf_low"],
                   markersize=11, markeredgecolor=COLORS["dark"],
                   label="Conf-routed (low / ≤med)"),
            Line2D([], [], marker="v", color="w",
                   markerfacecolor=PREDICATE_COLOR_HI["resp_no"],
                   markersize=11, markeredgecolor=COLORS["dark"],
                   label="Response-routed (verdict=no)"),
            Line2D([], [], marker="P", color="w",
                   markerfacecolor=PREDICATE_COLOR_HI["conf_low|resp_no"],
                   markersize=11, markeredgecolor=COLORS["dark"],
                   label="Conf | resp routed (union)"),
            Line2D([], [], marker="s", color="w", markerfacecolor="white",
                   markersize=11, markeredgecolor=COLORS["dark"],
                   label="Dark fill = ≥100%, light = ≥94%"),
            Line2D([], [], marker="s", color="w", markerfacecolor="white",
                   markersize=11, markeredgecolor=COLORS["dark"], alpha=0.4,
                   label="Faded = Pareto-dominated combo"),
        ]
        if cascade_points else []
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
    print(f"\nWrote 4 plots to {OUT_DIR}")


if __name__ == "__main__":
    main()
