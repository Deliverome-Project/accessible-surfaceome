"""Per-class caller-correctness barplot — 5 M1 surface DBs + 5 LLM cells.

For each ground-truth class (`yes`, `contextual`, `no`), shows the
fraction of benchmark proteins each caller correctly classifies.
Callers covered:

* **5 M1 surface databases** — UniProt, GO CC, HPA, SURFY, CSPA — from
  the boolean flag columns in ``candidate_universe.tsv``.
* **4 LLM cells** — haiku/naive, haiku/ncbi, sonnet/naive, sonnet/ncbi
  — from per-gene run JSONs under
  ``data/eval/triage_bench_v1/<model>/<variant>/``.
* **1 routed LLM cell** — ``haiku/ncbi → sonnet/ncbi``: accept haiku's
  verdict when ``confidence == "high"``, otherwise escalate to
  sonnet/ncbi. Mirrors the lazy-ensemble Combined column in the
  subbench by-variant plot.

Correctness convention (binary: surface vs not-surface):

* truth = `yes`        → caller correct iff vote = True
* truth = `contextual` → caller correct iff vote = True
* truth = `no`         → caller correct iff vote = False

LLM vote = True iff the emitted verdict is ``yes`` or ``contextual``
(yes/contextual interchangeable for surface accessibility).

Outputs (PDF + PNG via the brand plotting config):

* ``data/analysis/triage_bench/db_correctness_by_class.{pdf,png}``
* ``data/analysis/triage_bench/db_correctness_overall.{pdf,png}``
"""

from __future__ import annotations

import csv
import json
from collections import defaultdict
from pathlib import Path

import matplotlib.pyplot as plt
import pandas as pd
import seaborn as sns

from accessible_surfaceome.audit._plotting_config import (
    CATEGORICAL_PALETTE,
    COLORS,
    save_figure,
    setup_plotting_style,
)


DB_FLAGS_5: list[tuple[str, str]] = [
    ("uniprot_surface_flag", "UniProt"),
    ("go_surface_flag", "GO CC"),
    ("hpa_surface_flag", "HPA"),
    ("surfy_surface_flag", "SURFY"),
    ("cspa_surface_flag", "CSPA"),
]

# LLM cells run under the v0.9.0 prompts. Each entry maps a vote-key →
# (model, variant) directory under data/eval/triage_bench_v1/. The
# vote-key carries through the per-protein votes dict alongside the DB
# flags so the per-class correctness logic can treat them uniformly.
LLM_CELLS: list[tuple[str, str, str]] = [
    # (vote_key, model_slug, variant)
    ("_llm_haiku_naive",        "haiku-4-5",  "naive"),
    ("_llm_haiku_ncbi",         "haiku-4-5",  "ncbi"),
    ("_llm_haiku_web_ncbi",     "haiku-4-5",  "web_ncbi"),
    ("_llm_sonnet_naive",       "sonnet-4-6", "naive"),
    ("_llm_sonnet_ncbi",        "sonnet-4-6", "ncbi"),
    ("_llm_sonnet_pubmed_ncbi", "sonnet-4-6", "pubmed_ncbi"),
    ("_llm_sonnet_web_ncbi",    "sonnet-4-6", "web_ncbi"),
    ("_llm_opus_ncbi",          "opus-4-7",   "ncbi"),
]
LLM_LABEL = {
    "_llm_haiku_naive":        "Haiku (naive)",
    "_llm_haiku_ncbi":         "Haiku (+ NCBI)",
    "_llm_haiku_web_ncbi":     "Haiku (+ NCBI + web)",
    "_llm_sonnet_naive":       "Sonnet (naive)",
    "_llm_sonnet_ncbi":        "Sonnet (+ NCBI)",
    "_llm_sonnet_pubmed_ncbi": "Sonnet (+ NCBI + PubMed)",
    "_llm_sonnet_web_ncbi":    "Sonnet (+ NCBI + web)",
    "_llm_opus_ncbi":          "Opus (+ NCBI)",
    "_llm_combined":           "Combined (Haiku→Sonnet)",
}

# Combined cell: confidence-routed Haiku+NCBI → Sonnet+NCBI. Accept
# Haiku when it emits `confidence == "high"`, otherwise escalate to
# Sonnet. Mirrors the subbench by-variant Combined group.
COMBINED_KEY = "_llm_combined"
COMBINED_PRIMARY = ("_llm_haiku_ncbi", "_llm_sonnet_ncbi")  # (cheap, escalation)

LLM_KEYS = [k for k, _, _ in LLM_CELLS] + [COMBINED_KEY]

# Palette — DBs use the brand categorical palette (5 distinct colors).
# LLM cells get a sequential Claude-orange walk: lighter = less context /
# smaller model, darker = more context / larger model. Same family as the
# subbench by-variant plot. Base Claude orange is #d87851.
DB_PALETTE = {label: CATEGORICAL_PALETTE[i] for i, (_, label) in enumerate(DB_FLAGS_5)}
LLM_PALETTE = {
    "_llm_haiku_naive":        "#f7d8c4",   # tint 65%
    "_llm_haiku_ncbi":         "#f1c4ab",   # tint 50%
    "_llm_haiku_web_ncbi":     "#ec9e7d",   # tint 38%
    "_llm_sonnet_naive":       "#e3a07d",   # tint 25%
    "_llm_sonnet_ncbi":        "#d87851",   # base Claude
    "_llm_sonnet_pubmed_ncbi": "#cb6f4a",   # base+, sits between ncbi and web
    "_llm_sonnet_web_ncbi":    "#c46139",   # shade 12%
    "_llm_opus_ncbi":          "#a85b3f",   # shade 25%
    "_llm_combined":           "#7a3b25",   # shade 50%
}

VERDICT_ORDER = ["yes", "contextual", "no"]
VERDICT_LABEL = {
    "yes": "yes",
    "contextual": "contextual\n(yes-vote = correct)",
    "no": "no",
}

ROOT = Path(__file__).resolve().parents[1]
BENCH_TSV = ROOT / "data/eval/triage_benchmark_v1.tsv"
CAND_TSV = ROOT / "data/processed/candidate_universe/candidate_universe.tsv"
LLM_RUNS_DIR = ROOT / "data/eval/triage_bench_v1"


def _load_llm_predictions(model: str, variant: str) -> dict[str, dict]:
    """Return {gene_symbol: run_record_dict} for one cell."""
    out: dict[str, dict] = {}
    run_dir = LLM_RUNS_DIR / model / variant
    if not run_dir.exists():
        return out
    for path in run_dir.glob("*_run1.json"):
        try:
            data = json.loads(path.read_text())
        except json.JSONDecodeError:
            continue
        gene = data.get("gene_symbol") or path.stem.split("_run")[0]
        out[gene] = data
    return out


def _surface_vote(verdict: str | None) -> bool:
    """LLM 'surface' vote = True iff verdict is yes or contextual."""
    return verdict in ("yes", "contextual")


def _route_combined(haiku_rec: dict | None, sonnet_rec: dict | None) -> tuple[str | None, dict | None]:
    """Return (chosen_verdict, source_record) under the
    confidence-routing rule: accept Haiku when confidence == 'high',
    else escalate to Sonnet (fall back to Haiku if Sonnet is missing)."""
    if haiku_rec is None:
        return None, None
    hv = haiku_rec.get("predicted_verdict")
    hconf = haiku_rec.get("predicted_confidence") or haiku_rec.get("confidence")
    if hconf == "high":
        return hv, haiku_rec
    if sonnet_rec is None:
        return hv, haiku_rec
    return sonnet_rec.get("predicted_verdict"), sonnet_rec


def load_benchmark_with_votes() -> list[dict[str, object]]:
    bench = []
    with BENCH_TSV.open() as fh:
        for r in csv.DictReader(fh, delimiter="\t"):
            bench.append(r)

    votes_by_acc: dict[str, dict[str, bool]] = {}
    with CAND_TSV.open() as fh:
        for r in csv.DictReader(fh, delimiter="\t"):
            acc = r["uniprot_accession"]
            votes_by_acc[acc] = {flag: (r.get(flag, "0") == "1") for flag, _ in DB_FLAGS_5}

    llm_runs_by_cell = {
        vote_key: _load_llm_predictions(model, variant)
        for vote_key, model, variant in LLM_CELLS
    }
    haiku_ncbi_runs = llm_runs_by_cell.get(COMBINED_PRIMARY[0], {})
    sonnet_ncbi_runs = llm_runs_by_cell.get(COMBINED_PRIMARY[1], {})

    out = []
    n_escalated = 0
    for r in bench:
        acc = r["uniprot_acc"]
        gene = r["gene_symbol"]
        votes = votes_by_acc.get(acc, {flag: False for flag, _ in DB_FLAGS_5}).copy()
        for vote_key, _, _ in LLM_CELLS:
            rec = llm_runs_by_cell[vote_key].get(gene)
            votes[vote_key] = _surface_vote((rec or {}).get("predicted_verdict"))
        # Routed Combined cell
        h_rec = haiku_ncbi_runs.get(gene)
        s_rec = sonnet_ncbi_runs.get(gene)
        routed_verdict, source_rec = _route_combined(h_rec, s_rec)
        votes[COMBINED_KEY] = _surface_vote(routed_verdict)
        if source_rec is s_rec and s_rec is not None:
            n_escalated += 1
        out.append({
            "gene": gene,
            "uniprot_acc": acc,
            "verdict": r["ground_truth_verdict"],
            "votes": votes,
            "in_m1": acc in votes_by_acc,
        })
    out_meta = {"n_escalated": n_escalated, "n_total": len(out)}
    return out, out_meta  # type: ignore[return-value]


def _all_callers() -> list[tuple[str, str]]:
    """Vote-key + display-label for every caller in plot order:
    LLM cells first (canonical light-to-dark order), then DBs in raw
    declaration order. The routed Combined cell is computed by
    :func:`_route_combined` but excluded from the displayed callers —
    keep the route's tally available for downstream cost analysis
    without crowding the per-class barplot. For display, callers should
    be reordered via :func:`_display_order` to put DBs in descending
    overall-accuracy."""
    out: list[tuple[str, str]] = []
    for vote_key, _, _ in LLM_CELLS:
        out.append((vote_key, LLM_LABEL[vote_key]))
    out.extend(DB_FLAGS_5)
    return out


def _display_order(overall: dict[str, float]) -> list[tuple[str, str]]:
    """Return the (vote_key, label) caller list in display order:
    LLM cells in canonical light-to-dark order, then DBs sorted by
    overall accuracy on this benchmark (descending)."""
    callers = _all_callers()
    n_llm = len(LLM_CELLS)
    llm_part = callers[:n_llm]
    db_part = sorted(callers[n_llm:], key=lambda kv: -overall[kv[1]])
    return llm_part + db_part


def _caller_color(label: str, label_to_key: dict[str, str]) -> str:
    """Look up the brand color for a caller. LLM cells use LLM_PALETTE
    (keyed by vote_key); DBs use DB_PALETTE (keyed by display label)."""
    key = label_to_key.get(label, label)
    if key in LLM_PALETTE:
        return LLM_PALETTE[key]
    return DB_PALETTE.get(label, COLORS["neutral"])


def compute_correctness() -> tuple[
    dict[str, dict[str, float]],
    dict[str, int],
    dict[str, dict[str, int]],
    dict[str, object],
]:
    """Per-(verdict, caller-label) correctness fraction, per-verdict n,
    per-(verdict, caller-label) correct counts, and meta (escalation count)."""
    bench, meta = load_benchmark_with_votes()
    by_verdict: dict[str, list[dict[str, object]]] = defaultdict(list)
    for entry in bench:
        by_verdict[entry["verdict"]].append(entry)

    fractions: dict[str, dict[str, float]] = {}
    counts_correct: dict[str, dict[str, int]] = {}
    counts_total: dict[str, int] = {}
    callers = _all_callers()
    for verdict in VERDICT_ORDER:
        proteins = by_verdict.get(verdict, [])
        counts_total[verdict] = len(proteins)
        fractions[verdict] = {}
        counts_correct[verdict] = {}
        for vote_key, label in callers:
            if not proteins:
                fractions[verdict][label] = 0.0
                counts_correct[verdict][label] = 0
                continue
            n_correct = 0
            for p in proteins:
                vote = p["votes"][vote_key]
                is_correct = vote if verdict in ("yes", "contextual") else (not vote)
                if is_correct:
                    n_correct += 1
            fractions[verdict][label] = n_correct / len(proteins)
            counts_correct[verdict][label] = n_correct
    return fractions, counts_total, counts_correct, meta


def overall_accuracy() -> dict[str, float]:
    """Pooled fraction correct per caller across every benchmark protein."""
    bench, _ = load_benchmark_with_votes()
    by_caller_correct: dict[str, int] = defaultdict(int)
    callers = _all_callers()
    for p in bench:
        for vote_key, label in callers:
            vote = p["votes"][vote_key]
            if p["verdict"] in ("yes", "contextual"):
                if vote:
                    by_caller_correct[label] += 1
            else:
                if not vote:
                    by_caller_correct[label] += 1
    n = len(bench)
    return {label: by_caller_correct[label] / n for _, label in callers}


def _long_dataframe() -> tuple[pd.DataFrame, dict[str, object]]:
    fractions, totals, correct_counts, meta = compute_correctness()
    rows = []
    for verdict in VERDICT_ORDER:
        for _, caller_label in _all_callers():
            rows.append({
                "verdict": verdict,
                "verdict_label": VERDICT_LABEL[verdict],
                "caller": caller_label,
                "fraction": fractions[verdict][caller_label],
                "n_correct": correct_counts[verdict][caller_label],
                "n_total": totals[verdict],
            })
    return pd.DataFrame(rows), meta


def _annotate_bars(ax, df: pd.DataFrame, caller_order: list[str]) -> None:
    """Walk bar patches in seaborn's (hue-major, x-major) order and
    label each with n_correct/n_total."""
    n_v = len(VERDICT_ORDER)
    for i, caller_label in enumerate(caller_order):
        for j, verdict in enumerate(VERDICT_ORDER):
            bar = ax.patches[i * n_v + j]
            row = df[(df.caller == caller_label) & (df.verdict == verdict)].iloc[0]
            ax.text(
                bar.get_x() + bar.get_width() / 2,
                bar.get_height() + 0.02,
                f"{row.n_correct}/{row.n_total}",
                ha="center", va="bottom",
                fontsize=7.5, color=COLORS["dark"],
            )


def _draw_group_separators(
    ax,
    caller_order: list[str],
    bar_width: float,
    gap: float,
    n_callers_left: int,
) -> None:
    """Draw a faint vertical separator between the LLM and DB clusters
    for each verdict group. Patch layout is hue-major then x-major."""
    n_v = len(VERDICT_ORDER)
    for verdict_idx in range(n_v):
        # Right edge of last LLM bar in this verdict group:
        last_llm_patch = ax.patches[(n_callers_left - 1) * n_v + verdict_idx]
        sep_x = last_llm_patch.get_x() + bar_width + (gap / 2)
        ax.axvline(
            sep_x,
            ymin=0.02, ymax=0.92,
            color=COLORS["neutral"],
            linestyle=":", linewidth=0.8, alpha=0.5,
        )


def make_by_class_plot(out_dir: Path) -> None:
    setup_plotting_style(style="whitegrid", context="notebook", font_scale=1.0)
    overall = overall_accuracy()
    df, meta = _long_dataframe()

    callers = _display_order(overall)
    caller_order = [label for _, label in callers]
    n_callers_left = len(LLM_CELLS)  # raw LLM cells only; routed Combined hidden
    label_to_key = {label: key for key, label in _all_callers()}
    palette = [_caller_color(label, label_to_key) for label in caller_order]

    fig, ax = plt.subplots(figsize=(14, 5.5))
    sns.barplot(
        data=df,
        x="verdict_label", y="fraction",
        hue="caller",
        order=[VERDICT_LABEL[v] for v in VERDICT_ORDER],
        hue_order=caller_order,
        palette=palette,
        edgecolor="none", saturation=1.0,
        ax=ax,
    )

    # Insert a visible gap between the LLM cluster (left) and the DB
    # cluster (right). Seaborn lays patches hue-major then x-major:
    # patches [0..n_v-1] = first caller across the 3 verdicts, etc.
    n_v = len(VERDICT_ORDER)
    n_callers = len(caller_order)
    bar_width = ax.patches[0].get_width()
    gap = bar_width * 0.8
    for caller_idx in range(n_callers_left, n_callers):
        for j in range(n_v):
            patch = ax.patches[caller_idx * n_v + j]
            patch.set_x(patch.get_x() + gap)

    _draw_group_separators(ax, caller_order, bar_width, gap, n_callers_left)
    _annotate_bars(ax, df, caller_order)

    ax.set_xlabel("")
    ax.set_ylabel("Fraction of class correctly classified")
    ax.set_title("Surface-caller correctness per ground-truth class — 5 M1 DBs vs LLM cells")
    ax.set_ylim(0, 1.14)
    ax.yaxis.set_major_locator(plt.MaxNLocator(6))

    handles, _ = ax.get_legend_handles_labels()
    legend_labels = [f"{lbl} ({overall[lbl]:.0%})" for lbl in caller_order]
    ax.legend(
        handles, legend_labels,
        title="Caller (overall acc.)",
        loc="upper left", bbox_to_anchor=(1.02, 1.0),
        frameon=False, borderaxespad=0.0,
    )

    totals_by_v = {v: df[df.verdict == v].iloc[0].n_total for v in VERDICT_ORDER}
    subtitle_parts = [f"n({v}) = {totals_by_v[v]}" for v in VERDICT_ORDER]
    n_esc = meta.get("n_escalated", 0)
    n_tot = meta.get("n_total", 0) or 1
    subtitle_parts.append(f"Combined escalates {n_esc}/{n_tot} ({n_esc/n_tot:.0%})")
    ax.text(
        0.5, -0.16, "  ·  ".join(subtitle_parts),
        transform=ax.transAxes, ha="center", va="top",
        fontsize=10, color=COLORS["neutral"],
    )
    sns.despine(ax=ax, top=True, right=True)

    out_dir.mkdir(parents=True, exist_ok=True)
    save_figure(
        fig, filename="db_correctness_by_class",
        output_dir=str(out_dir), formats=["pdf", "png"],
    )
    plt.close(fig)


def make_overall_plot(out_dir: Path) -> None:
    setup_plotting_style(style="whitegrid", context="notebook", font_scale=1.0)
    overall = overall_accuracy()
    callers = _display_order(overall)
    caller_order = [label for _, label in callers]
    label_to_key = {label: key for key, label in _all_callers()}
    colors = [_caller_color(label, label_to_key) for label in caller_order]

    df = pd.DataFrame({
        "caller": caller_order,
        "accuracy": [overall[lbl] for lbl in caller_order],
    })

    fig, ax = plt.subplots(figsize=(13, 4.8))
    sns.barplot(
        data=df, x="caller", y="accuracy",
        hue="caller", order=caller_order, hue_order=caller_order,
        palette=colors, legend=False,
        edgecolor="none", saturation=1.0, ax=ax,
    )

    # Insert a visual gap between LLM cluster (left) and DB cluster (right).
    n_callers_left = len(LLM_CELLS)
    bar_width = ax.patches[0].get_width()
    gap = bar_width * 0.5
    for caller_idx in range(n_callers_left, len(caller_order)):
        ax.patches[caller_idx].set_x(ax.patches[caller_idx].get_x() + gap)

    # Annotate AFTER the shift so the labels sit on the new bar centers.
    for bar, lbl in zip(ax.patches, caller_order):
        ax.text(
            bar.get_x() + bar.get_width() / 2,
            bar.get_height() + 0.012,
            f"{overall[lbl]:.1%}",
            ha="center", va="bottom",
            fontsize=9, color=COLORS["dark"],
        )

    # Realign x-ticks to the post-shift bar centers — otherwise labels
    # drift left of their bars in the DB cluster.
    tick_positions = [p.get_x() + p.get_width() / 2 for p in ax.patches]
    ax.set_xticks(tick_positions)
    ax.set_xticklabels(caller_order, rotation=30, ha="right", rotation_mode="anchor")

    ax.set_xlabel("")
    ax.set_ylabel("Overall accuracy")
    ax.set_title("Overall caller accuracy on 147-gene triage benchmark")
    ax.set_ylim(0, 1.05)
    ax.yaxis.set_major_locator(plt.MaxNLocator(6))
    sns.despine(ax=ax, top=True, right=True)

    save_figure(
        fig, filename="db_correctness_overall",
        output_dir=str(out_dir), formats=["pdf", "png"],
    )
    plt.close(fig)


WHOLE_GENOME_N = 19_464  # NCBI protein-coding ∩ has HGNC xref


# Anthropic per-1M-token pricing. cache_write = 1.25× input (5-min TTL),
# cache_read = 0.10× input. https://docs.anthropic.com/.../prompt-caching
_PRICE: dict[str, dict[str, float]] = {
    "claude-haiku-4-5":  {"in":  1.0, "cw":  1.25, "cr": 0.10, "out":  5.0},
    "claude-sonnet-4-6": {"in":  3.0, "cw":  3.75, "cr": 0.30, "out": 15.0},
    "claude-opus-4-7":   {"in": 15.0, "cw": 18.75, "cr": 1.50, "out": 75.0},
}
_WEB_SEARCH_USD_PER_QUERY = 0.01

# Empirical system-prompt size (cached tokens observed when caching
# was actually engaged in a sister run). Used as the inferred
# split-point for legacy records that lack cache_read/cache_creation
# fields. Sonnet's system.md cached at ≈5670 tokens.
_INFERRED_SYS_PROMPT_DEFAULT = 5700


def _llm_cost_per_call() -> dict[str, float]:
    """Cache-normalized mean cost per gene for each LLM cell.

    The goal is a fair production-grade $/call comparison even though
    historic runs in the repo were captured under different caching
    states. The rule:

    * If the per-call record carries non-zero ``cache_read_tokens``
      or ``cache_creation_tokens``, trust them: the run had real
      caching, so we compute cost = sys-amortized + uncached + output.
    * Otherwise the record is legacy/uncached. We infer the system
      prompt size from a sister variant that did cache (or fall back
      to a small constant), then split ``prompt_tokens`` into
      sys_prompt + user_message and amortize the sys portion as if
      caching had been active across the session.

    This makes "Sonnet (+ NCBI)" comparable to "Sonnet (+ NCBI + PubMed)"
    on the same x-axis without one being unfairly boosted because its
    capture happened to disable caching.
    """
    out: dict[str, float] = {}
    for vote_key, model, variant in LLM_CELLS:
        out[vote_key] = _cell_cost_per_call(model, variant)
    return out


def _cell_cost_per_call(model: str, variant: str) -> float:
    files = sorted((LLM_RUNS_DIR / model / variant).glob("*_run1.json"))
    if not files:
        return 0.0
    pt_total = cr_total = cw_total = ot_total = ws_total = 0
    for f in files:
        try:
            d = json.loads(f.read_text())
        except json.JSONDecodeError:
            continue
        pt_total += int(d.get("prompt_tokens") or 0)
        cr_total += int(d.get("cache_read_tokens") or 0)
        cw_total += int(d.get("cache_creation_tokens") or 0)
        ot_total += int(d.get("completion_tokens") or 0)
        ws_total += int(d.get("n_web_searches") or 0)
    n = len(files)
    pt = pt_total / n
    cr = cr_total / n
    cw = cw_total / n
    ot = ot_total / n
    ws = ws_total / n

    pricing = _PRICE.get(f"claude-{model}")
    if pricing is None:
        return 0.0

    if cr > 0 or cw > 0:
        # Caching observed — pt is the uncached portion (user message),
        # cr/cw is the cached system prompt. Honor what the runner saw.
        sys_size = max(cr, cw)
        user_size = pt
    else:
        # Legacy uncached. Split pt into sys-prompt + user_message
        # using the inferred system-prompt size.
        sys_size = min(_INFERRED_SYS_PROMPT_DEFAULT, pt)
        user_size = max(0.0, pt - sys_size)

    sys_amortized_per_cell = (
        sys_size * pricing["cw"] + (n - 1) * sys_size * pricing["cr"]
    ) / (n * 1_000_000)
    user_per_cell = user_size * pricing["in"] / 1_000_000
    out_per_cell = ot * pricing["out"] / 1_000_000
    web_per_cell = ws * _WEB_SEARCH_USD_PER_QUERY
    return sys_amortized_per_cell + user_per_cell + out_per_cell + web_per_cell


def make_cost_vs_accuracy_plot(out_dir: Path) -> None:
    """Scatter LLM cells in ($/whole-genome, accuracy) space. M1 DB
    accuracies are shown as horizontal reference lines since they have
    no per-call cost (one-time download)."""
    setup_plotting_style(style="whitegrid", context="notebook", font_scale=1.0)

    overall = overall_accuracy()
    cost_per_call = _llm_cost_per_call()

    fig, ax = plt.subplots(figsize=(10.5, 5.5))

    # LLM cells as scatter — x is $/whole-genome at 1 rep, y is overall accuracy.
    for vote_key, _, _ in LLM_CELLS:
        label = LLM_LABEL[vote_key]
        x = cost_per_call[vote_key] * WHOLE_GENOME_N
        y = overall[label] * 100
        color = LLM_PALETTE[vote_key]
        ax.scatter(x, y, s=180, c=color, edgecolor=COLORS["dark"],
                   linewidth=0.8, zorder=5)
        # Offset annotation slightly so points and labels don't overlap.
        ax.annotate(label, (x, y), xytext=(7, 6), textcoords="offset points",
                    fontsize=10, color=COLORS["dark"])

    # M1 DBs as horizontal reference lines (cost = $0; not on a $-axis log
    # scale, so depict them as accuracy thresholds the LLMs must beat).
    db_overall_sorted = sorted(
        ((label, overall[label]) for _, label in DB_FLAGS_5),
        key=lambda kv: -kv[1],
    )
    for label, acc in db_overall_sorted:
        color = DB_PALETTE[label]
        ax.axhline(acc * 100, linestyle="--", linewidth=1.2,
                   color=color, alpha=0.75, zorder=2)
        # Label at the right edge of the plot.
        ax.text(0.985, acc * 100, f"{label} {acc:.0%}",
                transform=ax.get_yaxis_transform(),
                ha="right", va="center", fontsize=8.5,
                color=color, zorder=3,
                bbox=dict(boxstyle="round,pad=0.18", fc="white",
                          ec="none", alpha=0.85))

    ax.set_xscale("log")
    ax.set_xlabel(f"Cost per whole-genome pass at 1 rep  ($, log scale; ×{WHOLE_GENOME_N:,} genes)")
    ax.set_ylabel("Overall accuracy on 147-gene benchmark (%)")
    ax.set_title("Cost vs accuracy — Claude cells vs M1 surface-database baselines")
    # Headroom on the y axis so labels don't clip.
    ymin = min(overall[lbl] for _, lbl in _all_callers()) * 100
    ax.set_ylim(max(35, ymin - 6), 100)

    sns.despine(ax=ax, top=True, right=True)
    save_figure(
        fig, filename="benchmark_cost_vs_accuracy",
        output_dir=str(out_dir), formats=["pdf", "png"],
    )
    plt.close(fig)


CAND_TSV_PATH = ROOT / "data/processed/candidate_universe/candidate_universe.tsv"


def _b(r: dict, k: str) -> bool:
    return r.get(k, "0") == "1"


def _f(r: dict, k: str) -> float | None:
    v = r.get(k, "")
    try:
        return float(v) if v else None
    except ValueError:
        return None


# Filter variants to plot. The 5 baselines anchor each group; only
# meaningful additional variants are included — i.e. ones that actually
# differ from baseline on the 147-gene benchmark. Drop-low-conf /
# drop-electronic-only / drop-unspecific / drop-mixed-conflict
# "stricter" variants are no-ops on this gene set (the benchmark
# proteins either pass the baseline filter already, or aren't in the
# candidate universe at all) so they don't appear here. Similarly,
# more-permissive UniProt and HPA variants would require reprocessing
# upstream raw data (the universe TSV pre-filters those at load time),
# so those aren't reachable from the current data either.
DB_VARIANTS: list[tuple[str, "callable", str]] = [
    ("UniProt baseline",       lambda r: _b(r, "uniprot_surface_flag"), "UniProt"),
    ("GO baseline",            lambda r: _b(r, "go_surface_flag"),      "GO"),
    ("HPA baseline",           lambda r: _b(r, "hpa_surface_flag"),     "HPA"),
    ("SURFY baseline",         lambda r: _b(r, "surfy_surface_flag"),   "SURFY"),
    # SURFY ML-score tiers — distinct strictness levels from the baseline binary flag.
    ("SURFY score>0.5",        lambda r: _b(r, "surfy_surface_flag") and (_f(r, "surfy_ml_score") or 0) > 0.5, "SURFY"),
    ("SURFY score>0.7",        lambda r: _b(r, "surfy_surface_flag") and (_f(r, "surfy_ml_score") or 0) > 0.7, "SURFY"),
    ("CSPA baseline",          lambda r: _b(r, "cspa_surface_flag"),    "CSPA"),
    # Consensus filters — the only filter that beats every single-DB baseline
    # is `n_sources_surface ≥ 2`. Stricter consensus levels become
    # precision-only filters (very high neg accuracy, low pos recall).
    ("Consensus ≥2 sources",   lambda r: int(r.get("n_sources_surface", "0") or 0) >= 2, "consensus"),
    ("Consensus ≥3 sources",   lambda r: int(r.get("n_sources_surface", "0") or 0) >= 3, "consensus"),
]

# Colors per group — brand palette for the 5 baselines; consensus gets
# the success-green family.
_VARIANT_GROUP_PALETTE: dict[str, list[str]] = {
    "UniProt":   [CATEGORICAL_PALETTE[0]],
    "GO":        [CATEGORICAL_PALETTE[1]],
    "HPA":       [CATEGORICAL_PALETTE[2]],
    "SURFY":     [CATEGORICAL_PALETTE[3], "#a895d6", "#d4b9e5"],
    "CSPA":      [CATEGORICAL_PALETTE[4]],
    "consensus": ["#2E7A55", "#5cae84"],
}


def _benchmark_with_universe_join() -> list[dict]:
    """Load benchmark rows joined to candidate_universe by UniProt
    accession. Returns one dict per benchmark protein found in
    candidate_universe, each with all DB-flag columns plus
    ``ground_truth_verdict``. Proteins missing from the universe are
    dropped — the universe is the input to the DB filters, so if a
    protein isn't there, no filter can evaluate it."""
    truth_by_acc: dict[str, str] = {}
    with BENCH_TSV.open() as fh:
        for r in csv.DictReader(fh, delimiter="\t"):
            truth_by_acc[r["uniprot_acc"]] = r["ground_truth_verdict"]
    out: list[dict] = []
    with CAND_TSV_PATH.open() as fh:
        for r in csv.DictReader(fh, delimiter="\t"):
            acc = r["uniprot_accession"]
            if acc in truth_by_acc:
                r["ground_truth_verdict"] = truth_by_acc[acc]
                out.append(r)
    return out


def make_db_variants_plot(out_dir: Path) -> None:
    """Supplemental figure: per-DB filter variants vs benchmark truth.

    Each bar is one filter variant's overall accuracy on the 147-gene
    benchmark, color-coded by DB-family group. Bars within a group are
    ordered by the variant's strictness (baseline → strict). DeepTMHMM
    and Compartments — surface flags not in the headline 5-DB plot —
    are shown in a separate "extra" group, and the consensus filters
    (`n_sources_surface ≥ N`) get their own group on the right.

    The base 5-DB result and the consensus filter are the two pieces
    worth quoting in any subsequent narrative: baselines are already
    well-calibrated (strict variants either don't move the needle or
    overshoot to 0% positive recall), and the only filter that beats
    every single-DB baseline is `n_sources_surface ≥ 2`.
    """
    setup_plotting_style(style="whitegrid", context="notebook", font_scale=1.0)
    rows = _benchmark_with_universe_join()
    n_total = len(rows)

    bars: list[dict] = []
    for name, fn, group in DB_VARIANTS:
        n_correct = 0
        n_pos_correct = n_pos_total = 0
        n_neg_correct = n_neg_total = 0
        for r in rows:
            truth = r["ground_truth_verdict"]
            vote = bool(fn(r))
            is_pos = truth in {"yes", "contextual"}
            if is_pos:
                n_pos_total += 1
                if vote:
                    n_pos_correct += 1
                    n_correct += 1
            else:
                n_neg_total += 1
                if not vote:
                    n_neg_correct += 1
                    n_correct += 1
        bars.append({
            "label": name,
            "group": group,
            "acc": n_correct / max(n_total, 1),
            "pos": n_pos_correct / max(n_pos_total, 1),
            "neg": n_neg_correct / max(n_neg_total, 1),
        })

    # Color per bar — index within its group.
    group_counters: dict[str, int] = {}
    colors: list[str] = []
    for b in bars:
        idx = group_counters.get(b["group"], 0)
        palette = _VARIANT_GROUP_PALETTE.get(b["group"], ["#666666"])
        colors.append(palette[min(idx, len(palette) - 1)])
        group_counters[b["group"]] = idx + 1

    fig, ax = plt.subplots(figsize=(15, 6))
    xs = list(range(len(bars)))
    accs = [b["acc"] * 100 for b in bars]
    ax.bar(xs, accs, color=colors, edgecolor="none")

    # Two-line bar annotations: overall %, then pos / neg %.
    for x, b in zip(xs, bars):
        ax.text(x, b["acc"] * 100 + 0.6, f"{b['acc']*100:.0f}",
                ha="center", va="bottom", fontsize=8.5,
                color=COLORS["dark"])
        ax.text(x, max(b["acc"] * 100 - 6, 4),
                f"+{b['pos']*100:.0f}/-{b['neg']*100:.0f}",
                ha="center", va="bottom", fontsize=7,
                color="white", fontweight="bold")

    # Group separators — light vertical lines between groups.
    last_group = bars[0]["group"]
    for i, b in enumerate(bars[1:], start=1):
        if b["group"] != last_group:
            ax.axvline(i - 0.5, color=COLORS["neutral"], linestyle=":", linewidth=0.8, alpha=0.5)
            last_group = b["group"]

    ax.set_xticks(xs)
    ax.set_xticklabels([b["label"] for b in bars], rotation=35, ha="right",
                       rotation_mode="anchor", fontsize=9)
    ax.set_ylabel("Overall accuracy on 147-gene benchmark (%)")
    ax.set_ylim(0, 105)
    ax.set_title(
        "Supplemental: filter-variant accuracy per surface-source database\n"
        f"(soft-credit scoring; n={n_total} benchmark proteins in candidate_universe)"
    )
    ax.text(
        0.5, -0.35,
        "In-bar text: +pos% / -neg% — fraction of yes/contextual-truth and "
        "no-truth proteins each variant correctly classifies",
        transform=ax.transAxes, ha="center", va="top", fontsize=9.5,
        color=COLORS["neutral"],
    )
    sns.despine(ax=ax, top=True, right=True)
    save_figure(
        fig, filename="db_variants_supplemental",
        output_dir=str(out_dir), formats=["pdf", "png"],
    )
    plt.close(fig)


def main() -> None:
    out_dir = ROOT / "data/analysis/triage_bench"
    make_by_class_plot(out_dir)
    make_overall_plot(out_dir)
    make_cost_vs_accuracy_plot(out_dir)
    make_db_variants_plot(out_dir)


if __name__ == "__main__":
    main()
