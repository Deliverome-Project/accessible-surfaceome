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
import os
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
    # (vote_key, model_slug, variant). Order = canonical display order
    # for the LLM-block of the bar charts: per-model light-to-dark
    # context augmentation walk.
    ("_llm_haiku_naive",        "haiku-4-5",  "naive"),
    ("_llm_haiku_ncbi",         "haiku-4-5",  "ncbi"),
    ("_llm_haiku_pubmed_ncbi",  "haiku-4-5",  "pubmed_ncbi"),
    ("_llm_haiku_web_ncbi",     "haiku-4-5",  "web_ncbi"),
    ("_llm_sonnet_naive",       "sonnet-4-6", "naive"),
    ("_llm_sonnet_ncbi",        "sonnet-4-6", "ncbi"),
    ("_llm_sonnet_pubmed_ncbi", "sonnet-4-6", "pubmed_ncbi"),
    ("_llm_sonnet_web_ncbi",    "sonnet-4-6", "web_ncbi"),
    ("_llm_opus_naive",         "opus-4-7",   "naive"),
    ("_llm_opus_ncbi",          "opus-4-7",   "ncbi"),
]
LLM_LABEL = {
    "_llm_haiku_naive":        "Haiku (naive)",
    "_llm_haiku_ncbi":         "Haiku (+ NCBI)",
    "_llm_haiku_pubmed_ncbi":  "Haiku (+ NCBI + PubMed)",
    "_llm_haiku_web_ncbi":     "Haiku (+ NCBI + web)",
    "_llm_sonnet_naive":       "Sonnet (naive)",
    "_llm_sonnet_ncbi":        "Sonnet (+ NCBI)",
    "_llm_sonnet_pubmed_ncbi": "Sonnet (+ NCBI + PubMed)",
    "_llm_sonnet_web_ncbi":    "Sonnet (+ NCBI + web)",
    "_llm_opus_naive":         "Opus (naive)",
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
    "_llm_haiku_pubmed_ncbi":  "#eab695",   # tint 42% — fits between ncbi and web
    "_llm_haiku_web_ncbi":     "#ec9e7d",   # tint 38%
    "_llm_sonnet_naive":       "#e3a07d",   # tint 25%
    "_llm_sonnet_ncbi":        "#d87851",   # base Claude
    "_llm_sonnet_pubmed_ncbi": "#cb6f4a",   # base+, sits between ncbi and web
    "_llm_sonnet_web_ncbi":    "#c46139",   # shade 12%
    "_llm_opus_naive":         "#b66547",   # shade 18% — sits before opus_ncbi
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
    """Per-class accuracy of Sonnet + NCBI vs the 5 M1 surface DBs.

    Compares one canonical LLM cell against the five classical
    surface-flag sources across four columns:
      - overall  : pooled accuracy across all 147 proteins
      - yes      : accuracy on ground_truth=yes proteins
      - contextual : accuracy on ground_truth=contextual
      - no       : accuracy on ground_truth=no
    """

    setup_plotting_style(style="whitegrid", context="notebook", font_scale=1.0)
    overall = overall_accuracy()
    fractions, totals, _, _ = compute_correctness()

    # Restricted caller set: just the one canonical LLM + the 5 DBs.
    SONNET_NCBI_KEY = "_llm_sonnet_ncbi"
    sonnet_label = LLM_LABEL[SONNET_NCBI_KEY]
    db_labels = [label for _, label in DB_FLAGS_5]
    callers_in_plot = [sonnet_label, *db_labels]

    # Build a long DataFrame with 4 columns × n_callers rows.
    column_order = ["overall", "yes", "contextual", "no"]
    column_label = {
        "overall":    "overall\n(all 147 proteins)",
        "yes":        VERDICT_LABEL["yes"],
        "contextual": VERDICT_LABEL["contextual"],
        "no":         VERDICT_LABEL["no"],
    }
    rows = []
    for caller in callers_in_plot:
        for col in column_order:
            frac = overall[caller] if col == "overall" else fractions[col][caller]
            rows.append({
                "caller": caller,
                "column": col,
                "column_label": column_label[col],
                "fraction": frac,
            })
    df = pd.DataFrame(rows)

    label_to_key = {label: key for key, label in _all_callers()}
    palette = [_caller_color(label, label_to_key) for label in callers_in_plot]

    fig, ax = plt.subplots(figsize=(11, 5.5))
    sns.barplot(
        data=df,
        x="column_label", y="fraction",
        hue="caller",
        order=[column_label[c] for c in column_order],
        hue_order=callers_in_plot,
        palette=palette,
        edgecolor="none", saturation=1.0,
        ax=ax,
    )

    # Insert a visible gap between the single LLM bar and the 5-DB
    # cluster within each column group. Seaborn lays patches hue-major
    # then x-major: each caller has len(column_order) patches in a row.
    n_col = len(column_order)
    n_callers = len(callers_in_plot)
    bar_width = ax.patches[0].get_width()
    gap = bar_width * 0.6
    # First caller (Sonnet/ncbi) stays where it is. Shift every other
    # caller to the right by `gap`.
    for caller_idx in range(1, n_callers):
        for j in range(n_col):
            patch = ax.patches[caller_idx * n_col + j]
            patch.set_x(patch.get_x() + gap)

    # Per-bar percentage annotations.
    for i, caller in enumerate(callers_in_plot):
        for j, col in enumerate(column_order):
            patch = ax.patches[i * n_col + j]
            frac = df[(df.caller == caller) & (df.column == col)].iloc[0].fraction
            ax.text(
                patch.get_x() + patch.get_width() / 2,
                patch.get_height() + 0.01,
                f"{frac:.0%}",
                ha="center", va="bottom",
                fontsize=9, color=COLORS["dark"],
            )

    ax.set_xlabel("")
    ax.set_ylabel("Fraction correctly classified")
    ax.set_ylim(0, 1.14)
    ax.yaxis.set_major_locator(plt.MaxNLocator(6))

    handles, _ = ax.get_legend_handles_labels()
    legend_labels = [f"{lbl}  ({overall[lbl]:.0%})" for lbl in callers_in_plot]
    ax.legend(
        handles, legend_labels,
        title="Caller (overall acc.)",
        loc="upper left", bbox_to_anchor=(1.02, 1.0),
        frameon=False, borderaxespad=0.0,
    )

    # n-per-class subtitle.
    subtitle_parts = [f"n({v}) = {totals[v]}" for v in VERDICT_ORDER]
    n_all = sum(totals.values())
    subtitle_parts.insert(0, f"n(overall) = {n_all}")
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
    """LLM-only overall accuracy, grouped by model with hatched variants.

    Drops the M1 DB rows (they're in the by-class plot for direct LLM
    vs DB comparison). Within each model group (Haiku / Sonnet / Opus),
    one bar per variant — color encodes the model, hatch pattern
    encodes the variant.
    """

    setup_plotting_style(style="whitegrid", context="notebook", font_scale=1.0)
    overall = overall_accuracy()

    # Group LLM cells by model. Variant order = light-to-dark context
    # walk so the hatch pattern reads as "amount of resolver / web /
    # literature scaffolding".
    VARIANT_ORDER = ["naive", "ncbi", "web_ncbi", "pubmed_ncbi"]
    VARIANT_LABEL = {
        "naive":        "naive",
        "ncbi":         "+ NCBI",
        "web_ncbi":     "+ NCBI + web",
        "pubmed_ncbi":  "+ NCBI + PubMed",
    }
    # Hatch by variant — solid for naive, denser diagonal / cross /
    # dots as more context is layered on.
    VARIANT_HATCH = {
        "naive":        "",
        "ncbi":         "///",
        "web_ncbi":     "xxx",
        "pubmed_ncbi":  "...",
    }
    # One base color per model, sequential Claude orange light → dark.
    MODEL_ORDER = ["haiku-4-5", "sonnet-4-6", "opus-4-7"]
    MODEL_LABEL = {
        "haiku-4-5":  "Haiku 4.5",
        "sonnet-4-6": "Sonnet 4.6",
        "opus-4-7":   "Opus 4.7",
    }
    MODEL_COLOR = {
        "haiku-4-5":  "#f1c4ab",
        "sonnet-4-6": "#d87851",
        "opus-4-7":   "#a85b3f",
    }
    # Bucket: model → list of (variant, vote_key) actually run for that
    # model in this benchmark.
    cells_by_model: dict[str, list[tuple[str, str]]] = {m: [] for m in MODEL_ORDER}
    for vote_key, model_slug, variant in LLM_CELLS:
        if model_slug in cells_by_model:
            cells_by_model[model_slug].append((variant, vote_key))

    fig, ax = plt.subplots(figsize=(11, 5.2))

    # Manual bar placement so we can hatch + color each cell precisely.
    bar_width = 0.6
    inter_variant_gap = 0.05      # within-model spacing
    inter_model_gap = 0.9         # between-model spacing
    tick_positions: list[float] = []
    tick_labels: list[str] = []
    x = 0.0
    legend_seen_variants: set[str] = set()
    legend_handles: list = []
    legend_labels: list[str] = []

    for model_slug in MODEL_ORDER:
        cells = cells_by_model.get(model_slug, [])
        if not cells:
            continue
        # Order cells by VARIANT_ORDER so hatches read consistently.
        cells_sorted = sorted(
            cells,
            key=lambda vk: VARIANT_ORDER.index(vk[0]) if vk[0] in VARIANT_ORDER else 99,
        )
        model_block_start = x
        for variant, vote_key in cells_sorted:
            label = LLM_LABEL[vote_key]
            acc = overall[label]
            color = MODEL_COLOR[model_slug]
            hatch = VARIANT_HATCH.get(variant, "")
            ax.bar(
                x, acc, width=bar_width,
                color=color,
                edgecolor=COLORS["dark"],
                linewidth=0.6,
                hatch=hatch,
            )
            ax.text(
                x, acc + 0.012,
                f"{acc:.1%}",
                ha="center", va="bottom",
                fontsize=10, color=COLORS["dark"],
            )
            # Collect legend entries once per variant (color-agnostic
            # since hatch defines the variant; use neutral grey for
            # the legend swatch).
            if variant not in legend_seen_variants:
                legend_seen_variants.add(variant)
                legend_handles.append(
                    plt.Rectangle(
                        (0, 0), 1, 1,
                        facecolor="white",
                        edgecolor=COLORS["dark"],
                        hatch=hatch,
                        linewidth=0.6,
                    )
                )
                legend_labels.append(VARIANT_LABEL[variant])
            x += bar_width + inter_variant_gap
        # Center the model label under the block of variant bars.
        block_center = (model_block_start + (x - inter_variant_gap - bar_width)) / 2 + bar_width / 2
        tick_positions.append(block_center)
        tick_labels.append(MODEL_LABEL[model_slug])
        x += inter_model_gap

    ax.set_xticks(tick_positions)
    ax.set_xticklabels(tick_labels)
    ax.set_xlabel("")
    ax.set_ylabel("Overall accuracy on 147-gene benchmark")
    ax.set_ylim(0, 1.05)
    ax.yaxis.set_major_locator(plt.MaxNLocator(6))

    # Variant legend (hatch-only) to the right of the plot.
    ax.legend(
        legend_handles, legend_labels,
        title="Variant (hatch)",
        loc="upper left",
        bbox_to_anchor=(1.02, 1.0),
        frameon=False,
        borderaxespad=0.0,
    )

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

    # Per-cell label offsets (pixels) to deconflict dense clusters
    # (Sonnet naive/ncbi/PubMed all sit around 92-95% / $200-265 and
    # would stack with a single fixed offset). Calibrated to the
    # post-2026-05 final-canonical layout — re-tune if cells move.
    # When abs(dy) >= 16 we draw a short leader line so the
    # label → point mapping stays unambiguous.
    label_offsets: dict[str, tuple[int, int]] = {
        "_llm_haiku_naive":        (  7,   6),
        "_llm_haiku_ncbi":         (  7,  10),
        "_llm_haiku_pubmed_ncbi":  (  7, -18),
        "_llm_haiku_web_ncbi":     (  7,   6),
        "_llm_sonnet_naive":       (  7, -18),
        "_llm_sonnet_ncbi":        (  7,  10),
        "_llm_sonnet_pubmed_ncbi": (  7, -20),
        "_llm_sonnet_web_ncbi":    (  7,   6),
        "_llm_opus_naive":         (  7, -18),
        "_llm_opus_ncbi":          (  7,  10),
    }

    # LLM cells as scatter — x is $/whole-genome at 1 rep, y is overall accuracy.
    for vote_key, _, _ in LLM_CELLS:
        label = LLM_LABEL[vote_key]
        x = cost_per_call[vote_key] * WHOLE_GENOME_N
        y = overall[label] * 100
        color = LLM_PALETTE[vote_key]
        ax.scatter(x, y, s=180, c=color, edgecolor=COLORS["dark"],
                   linewidth=0.8, zorder=5)
        dx, dy = label_offsets.get(vote_key, (7, 6))
        arrowprops = (
            dict(arrowstyle="-", color=COLORS["neutral"],
                 linewidth=0.6, alpha=0.7, shrinkA=0, shrinkB=4)
            if abs(dy) >= 16 else None
        )
        ax.annotate(
            label, (x, y),
            xytext=(dx, dy), textcoords="offset points",
            fontsize=10, color=COLORS["dark"],
            arrowprops=arrowprops,
        )

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
# Raw upstream snapshots — used for source-level filter-variants that
# can't be reconstructed from the post-filter candidate_universe TSV.
UNIPROT_RAW_TSV = ROOT / "data/external/uniprot_human_surface_candidates/uniprot_human_surface_candidates.tsv"
GO_RAW_TSV = ROOT / "data/external/go_human_surface_annotations/go_human_surface_annotations_by_gene_product.tsv"
HPA_RAW_TSV = ROOT / "data/external/hpa_subcellular_location/subcellular_location.tsv"


def _b(r: dict, k: str) -> bool:
    return r.get(k, "0") == "1"


def _f(r: dict, k: str) -> float | None:
    v = r.get(k, "")
    try:
        return float(v) if v else None
    except ValueError:
        return None


# Filter variants to plot. Baselines for the 5 DBs anchor each group;
# additional variants surface raw-source filtering options that aren't
# reachable from candidate_universe (since each loader pre-filters).
#
# Variants included:
#   * UniProt permissive (incl. plain "Cell membrane") — broader
#     location-term set than the strict baseline.
#   * UniProt TM-or-signal-or-surface — topology proxy from raw
#     TM-domain and signal-peptide feature counts.
#   * GO permissive (incl. IEA-only annotations) — adds the
#     electronic-evidence tier from raw GO TSV.
#   * SURFY score>0.5 / >0.7 — ML-score strictness tiers.
#   * Consensus n_sources ≥ 2 / ≥ 3 — cross-source agreement.
#
# Under coverage-aware scoring (the current scheme; proteins missing
# from a source aren't counted against it), the UniProt variants tie
# the baseline — they only matter as coverage extenders, not as
# accuracy improvements. The GO permissive variant remains a real
# accuracy gain (+9pp) on top of much wider coverage (n=125 vs 89).
#
# What was tested and excluded (no-ops on this benchmark):
#   * Drop-electronic-only / drop-low-conf / drop-unspecific etc:
#     identical to baseline.
#   * HPA reliability tiers, Main-vs-Additional location splits,
#     extracellular-location field: 60-64% under coverage-aware
#     scoring regardless — HPA's microscopy signal doesn't
#     discriminate surface accessibility well.
#   * SURFY tm/signal columns: snapshot has them all zero.
#   * CSPA experiment-count / probability thresholds: 65-70% range,
#     no traction.

# Functions used by the plot below — extra raw lookups for UniProt
# and GO. Defined inside _build_db_variants so the raw TSVs only load
# when this supplemental figure is rendered.
def _load_raw_uniprot() -> dict[str, dict]:
    if not UNIPROT_RAW_TSV.exists():
        return {}
    out: dict[str, dict] = {}
    with UNIPROT_RAW_TSV.open() as fh:
        for r in csv.DictReader(fh, delimiter="\t"):
            out[r["accession"]] = r
    return out


def _load_raw_go() -> dict[str, dict]:
    if not GO_RAW_TSV.exists():
        return {}
    out: dict[str, dict] = {}
    with GO_RAW_TSV.open() as fh:
        for r in csv.DictReader(fh, delimiter="\t"):
            out[r["DB_Object_ID"]] = r
    return out


def _uniprot_has_strict_term(s: str | None) -> bool:
    if not s:
        return False
    parts = s.split("|")
    return any(t in parts for t in ("Cell surface", "Apical cell membrane",
                                     "Basolateral cell membrane", "GPI-anchor"))


def _uniprot_feat_int(r: dict, key: str) -> int:
    try:
        return int(r.get(key) or 0)
    except (TypeError, ValueError):
        return 0


def _go_evidence_count(r: dict) -> int:
    """Count any-evidence tiers (including IEA)."""
    return sum(int(r.get(k) or 0) for k in
               ("has_experimental", "has_curated", "has_sequence", "has_electronic"))


def _load_raw_hpa() -> dict[str, dict]:
    """Load raw HPA subcellular_location.tsv keyed by Gene name (upper).

    Bypasses the surface-candidate pool filter applied at
    ``src/accessible_surfaceome/sources/hpa.py`` build time so that HPA
    can still be scored on proteins it imaged but didn't see at PM
    (KRAS, ABCB9, ATG9A, etc.). The pool filter is correct for
    universe-feeding but artificially shrinks HPA's negative-call
    surface in benchmark scoring.
    """
    if not HPA_RAW_TSV.exists():
        return {}
    out: dict[str, dict] = {}
    with HPA_RAW_TSV.open() as fh:
        for r in csv.DictReader(fh, delimiter="\t"):
            sym = (r.get("Gene name") or "").strip().upper()
            if sym:
                out[sym] = r
    return out


def _hpa_pm_flag(r: dict) -> bool:
    """Raw HPA PM call — Plasma membrane in Main or Additional location."""
    main = (r.get("Main location") or "").lower()
    addl = (r.get("Additional location") or "").lower()
    return "plasma membrane" in main or "plasma membrane" in addl


# UniProt's `subcellular_locations` field is pipe-delimited. Cell-membrane
# terms eligible for the permissive variant — broader than the strict
# set used by the existing baseline loader.
_UNIPROT_PERMISSIVE_TERMS = (
    "Cell surface", "Apical cell membrane", "Basolateral cell membrane",
    "GPI-anchor", "Cell membrane",
)


def _inject_raw_source_flags(rows: list[dict], bench_symbols: dict[str, str]) -> None:
    """Look up each benchmark row's UniProt accession in the raw
    upstream UniProt, GO, and HPA TSVs and inject extra boolean fields
    that the DB_VARIANTS lambdas consume.

    For HPA in particular this bypasses the surface-candidate pool
    filter so HPA can score on proteins it imaged but didn't see at
    PM. ``bench_symbols`` maps uniprot_accession → gene_symbol so the
    HPA gene-symbol lookup works for rows where candidate_universe
    didn't carry the symbol through.
    """
    raw_uniprot = _load_raw_uniprot()
    raw_go = _load_raw_go()
    raw_hpa = _load_raw_hpa()
    for r in rows:
        acc = r.get("uniprot_accession") or ""
        u = raw_uniprot.get(acc, {})
        locs = u.get("subcellular_locations") or ""
        loc_parts = set(locs.split("|")) if locs else set()
        r["_uniprot_permissive"] = (
            any(t in loc_parts for t in _UNIPROT_PERMISSIVE_TERMS)
            or _uniprot_feat_int(u, "feature_topo_extracellular_count") > 0
        )
        r["_uniprot_tm_or_signal_or_surface"] = (
            _uniprot_feat_int(u, "feature_transmembrane_count") > 0
            or _uniprot_feat_int(u, "feature_signal_count") > 0
            or _uniprot_has_strict_term(locs)
        )
        g = raw_go.get(acc, {})
        r["_go_permissive"] = _go_evidence_count(g) > 0
        # Raw HPA — by symbol. _hpa_in_raw distinguishes "HPA imaged
        # this protein" from "no antibody". _hpa_pm_raw is HPA's PM
        # call when present.
        sym = (bench_symbols.get(acc) or "").upper()
        hpa_rec = raw_hpa.get(sym) if sym else None
        r["_hpa_in_raw"] = hpa_rec is not None
        r["_hpa_pm_raw"] = bool(hpa_rec and _hpa_pm_flag(hpa_rec))


DB_VARIANTS: list[tuple[str, "callable", str]] = [
    # UniProt baselines + raw-source variants. Lambdas take a dict
    # with `_raw_uniprot`/`_raw_go` injected by _build_db_variants.
    ("UniProt baseline",
        lambda r: _b(r, "uniprot_surface_flag"),
        "UniProt"),
    ("UniProt permissive\n(incl. plain Cell membrane)",
        lambda r: bool(r.get("_uniprot_permissive")),
        "UniProt"),
    ("UniProt TM-or-signal-or-surface\n(topology proxy)",
        lambda r: bool(r.get("_uniprot_tm_or_signal_or_surface")),
        "UniProt"),
    # GO baseline + permissive (incl. IEA)
    ("GO baseline",
        lambda r: _b(r, "go_surface_flag"),
        "GO"),
    ("GO permissive\n(incl. IEA-only)",
        lambda r: bool(r.get("_go_permissive")),
        "GO"),
    # HPA, SURFY, CSPA — baseline only (no meaningful variants found).
    # HPA reads from the raw subcellular_location TSV (bypassing the
    # surface-pool filter at source-build time) so it can vote
    # "not surface" on proteins it imaged but didn't see at PM
    # (KRAS, ABCB9, vesicle-resident, etc.).
    ("HPA baseline",
        lambda r: bool(r.get("_hpa_pm_raw")),
        "HPA"),
    ("SURFY baseline",
        lambda r: _b(r, "surfy_surface_flag"),
        "SURFY"),
    ("SURFY score>0.5",
        lambda r: _b(r, "surfy_surface_flag") and (_f(r, "surfy_ml_score") or 0) > 0.5,
        "SURFY"),
    ("SURFY score>0.7",
        lambda r: _b(r, "surfy_surface_flag") and (_f(r, "surfy_ml_score") or 0) > 0.7,
        "SURFY"),
    ("CSPA baseline",
        lambda r: _b(r, "cspa_surface_flag"),
        "CSPA"),
    # Consensus filters (cross-source agreement)
    ("Consensus\n≥2 sources",
        lambda r: int(r.get("n_sources_surface", "0") or 0) >= 2,
        "consensus"),
    ("Consensus\n≥3 sources",
        lambda r: int(r.get("n_sources_surface", "0") or 0) >= 3,
        "consensus"),
]

# Colors per group — brand palette for the 5 baselines; consensus gets
# the success-green family. Within UniProt and GO the baseline anchors
# the brand color and variants step toward darker shades.
_VARIANT_GROUP_PALETTE: dict[str, list[str]] = {
    "UniProt":   [CATEGORICAL_PALETTE[0], "#a82e3d", "#7a1f2a"],
    "GO":        [CATEGORICAL_PALETTE[1], "#2c5048"],
    "HPA":       [CATEGORICAL_PALETTE[2]],
    "SURFY":     [CATEGORICAL_PALETTE[3], "#a895d6", "#d4b9e5"],
    "CSPA":      [CATEGORICAL_PALETTE[4]],
    "consensus": ["#2E7A55", "#5cae84"],
}


# Per-source missing-handling rule for benchmark scoring. Different
# sources have different relationships between "absence" and "negative
# signal" (empirically validated; see README of this plot):
#
#   * UniProt, GO CC, SURFY, CSPA — missing-from-source = predict "no".
#     For UniProt and SURFY this is empirically informative (negatives
#     are 89-96% missing from the surface-extract; absence is curated /
#     ML-design intent). For GO and CSPA, catalog absence isn't strong
#     negative signal, but treating it as a predict-no vote matches the
#     decision-use case of "if I used this filter as the gate, what
#     would the universe look like".
#   * HPA — missing = abstain. HPA's coverage gap is antibody-driven,
#     and missing-rates are flat or yes-enriched across truth labels
#     (no antibody → no information). HPA still gets scored on the
#     ~98/147 proteins it actually imaged.
#
# A "covered" predicate returns True iff the source's data is loaded
# for the row. Only HPA filters rows by this predicate; all other
# sources include all rows and treat missing data as a predict-no.
def _has_hpa_raw(r: dict) -> bool:
    """HPA covered if the raw subcellular TSV has any record for the
    benchmark protein's gene symbol — independent of whether HPA's
    pool filter would have admitted it."""
    return bool(r.get("_hpa_in_raw"))


GROUP_COVERAGE_FN: dict[str, "callable"] = {
    "UniProt":   lambda r: True,   # missing → predict no
    "GO":        lambda r: True,   # missing → predict no
    "HPA":       _has_hpa_raw,      # missing → abstain
    "SURFY":     lambda r: True,   # missing → predict no
    "CSPA":      lambda r: True,   # missing → predict no
    "consensus": lambda r: True,
}


def _benchmark_with_universe_join() -> tuple[list[dict], dict[str, str]]:
    """Load benchmark rows joined to candidate_universe by UniProt
    accession. Returns ``(rows, symbols)`` — one dict per benchmark
    protein found in candidate_universe, plus a mapping
    ``uniprot_accession → gene_symbol`` for all benchmark rows
    (including those dropped from the universe join). Proteins missing
    from the universe are dropped from ``rows`` but kept in
    ``symbols`` so HPA's raw-by-symbol lookup can still recover them.
    """
    truth_by_acc: dict[str, str] = {}
    symbols: dict[str, str] = {}
    with BENCH_TSV.open() as fh:
        for r in csv.DictReader(fh, delimiter="\t"):
            truth_by_acc[r["uniprot_acc"]] = r["ground_truth_verdict"]
            symbols[r["uniprot_acc"]] = r["gene_symbol"]
    out: list[dict] = []
    with CAND_TSV_PATH.open() as fh:
        for r in csv.DictReader(fh, delimiter="\t"):
            acc = r["uniprot_accession"]
            if acc in truth_by_acc:
                r["ground_truth_verdict"] = truth_by_acc[acc]
                out.append(r)
    return out, symbols


def make_db_variants_plot(out_dir: Path) -> None:
    """Supplemental figure: per-DB filter variants vs benchmark truth.

    Per-source missing-handling: UniProt / GO / SURFY / CSPA score
    missing-from-source as predict-no (since for UniProt and SURFY
    that absence is curated negative evidence, and for GO / CSPA
    treating it as predict-no matches the universe-gating use case).
    HPA scores missing-from-source as abstain (antibody coverage gap;
    miss-rate empirically flat across truth labels). HPA also reads
    the raw subcellular_location TSV so it can vote on proteins
    imaged-but-not-PM that the source builder's surface pool drops.
    """
    setup_plotting_style(style="whitegrid", context="notebook", font_scale=1.0)
    rows, bench_symbols = _benchmark_with_universe_join()
    _inject_raw_source_flags(rows, bench_symbols)
    n_total = len(rows)

    bars: list[dict] = []
    for name, fn, group in DB_VARIANTS:
        cov = GROUP_COVERAGE_FN.get(group, lambda r: True)
        n_scored = 0
        n_correct = 0
        n_pos_correct = n_pos_total = 0
        n_neg_correct = n_neg_total = 0
        for r in rows:
            if not cov(r):
                continue
            n_scored += 1
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
            "n_scored": n_scored,
            "acc": n_correct / max(n_scored, 1),
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
    ax.set_xticklabels(
        [f"{b['label']}\n(n={b['n_scored']})" for b in bars],
        rotation=35, ha="right", rotation_mode="anchor", fontsize=9,
    )
    ax.set_ylabel("Accuracy on covered benchmark proteins (%)")
    ax.set_ylim(0, 105)
    ax.set_title(
        "Supplemental: filter-variant accuracy per surface-source database\n"
        f"(soft-credit scoring; benchmark n={n_total} ∩ candidate_universe; "
        "each DB scored only on proteins it covers)"
    )
    ax.text(
        0.5, -0.38,
        "In-bar text: +pos% / -neg% — fraction of yes/contextual-truth and "
        "no-truth covered proteins each variant correctly classifies. "
        "Per-bar (n=) is the size of that source's coverage of the benchmark.",
        transform=ax.transAxes, ha="center", va="top", fontsize=9.5,
        color=COLORS["neutral"],
    )
    sns.despine(ax=ax, top=True, right=True)
    save_figure(
        fig, filename="db_variants_supplemental",
        output_dir=str(out_dir), formats=["pdf", "png"],
    )
    plt.close(fig)


SURFY_TSV = ROOT / "data/processed/surfy/surfy_human_snapshot.tsv"
CSPA_TSV = ROOT / "data/processed/cspa/cspa_human_snapshot.tsv"


def _universe_size_per_variant() -> dict[str, int]:
    """For each DB_VARIANTS entry, compute how many human proteins
    the filter would admit if used as a universe gate. The size is the
    decision cost — more proteins admitted = more downstream agent
    triage work and more potential false positives in the universe.
    """
    sizes: dict[str, int] = {}

    # UniProt — count rows in raw UniProt TSV matching each criterion.
    n_strict = n_perm = n_tm = 0
    with UNIPROT_RAW_TSV.open() as fh:
        for r in csv.DictReader(fh, delimiter="\t"):
            locs = r.get("subcellular_locations") or ""
            parts = set(locs.split("|")) if locs else set()
            strict = _uniprot_has_strict_term(locs)
            perm = strict or "Cell membrane" in parts \
                or _uniprot_feat_int(r, "feature_topo_extracellular_count") > 0
            tm = (_uniprot_feat_int(r, "feature_transmembrane_count") > 0
                  or _uniprot_feat_int(r, "feature_signal_count") > 0
                  or strict)
            if strict:
                n_strict += 1
            if perm:
                n_perm += 1
            if tm:
                n_tm += 1
    sizes["UniProt baseline"] = n_strict
    sizes["UniProt permissive\n(incl. plain Cell membrane)"] = n_perm
    sizes["UniProt TM-or-signal-or-surface\n(topology proxy)"] = n_tm

    # GO — count raw GO rows by evidence tier.
    n_go_base = n_go_perm = 0
    with GO_RAW_TSV.open() as fh:
        for r in csv.DictReader(fh, delimiter="\t"):
            exp = (int(r.get("has_experimental") or 0)
                   + int(r.get("has_curated") or 0)
                   + int(r.get("has_sequence") or 0))
            ele = int(r.get("has_electronic") or 0)
            if exp > 0:
                n_go_base += 1
            if exp + ele > 0:
                n_go_perm += 1
    sizes["GO baseline"] = n_go_base
    sizes["GO permissive\n(incl. IEA-only)"] = n_go_perm

    # HPA — raw PM-annotated count.
    n_hpa = 0
    with HPA_RAW_TSV.open() as fh:
        for r in csv.DictReader(fh, delimiter="\t"):
            if _hpa_pm_flag(r):
                n_hpa += 1
    sizes["HPA baseline"] = n_hpa

    # SURFY — surface-labeled, optionally score-thresholded.
    n_s = n_s05 = n_s07 = 0
    with SURFY_TSV.open() as fh:
        for r in csv.DictReader(fh, delimiter="\t"):
            if (r.get("surfy_label") or "").strip() == "surface":
                n_s += 1
                try:
                    score = float(r.get("surfy_ml_score") or 0)
                except ValueError:
                    score = 0.0
                if score > 0.5:
                    n_s05 += 1
                if score > 0.7:
                    n_s07 += 1
    sizes["SURFY baseline"] = n_s
    sizes["SURFY score>0.5"] = n_s05
    sizes["SURFY score>0.7"] = n_s07

    # CSPA — high-conf OR putative.
    n_c = 0
    with CSPA_TSV.open() as fh:
        for r in csv.DictReader(fh, delimiter="\t"):
            hc = (r.get("cspa_is_high_confidence") or "").strip() == "1"
            pu = (r.get("cspa_is_putative") or "").strip() == "1"
            if hc or pu:
                n_c += 1
    sizes["CSPA baseline"] = n_c

    # Consensus — count proteins in candidate_universe meeting threshold.
    n_c2 = n_c3 = 0
    with CAND_TSV_PATH.open() as fh:
        for r in csv.DictReader(fh, delimiter="\t"):
            try:
                n = int(r.get("n_sources_surface") or 0)
            except (TypeError, ValueError):
                continue
            if n >= 2:
                n_c2 += 1
            if n >= 3:
                n_c3 += 1
    sizes["Consensus\n≥2 sources"] = n_c2
    sizes["Consensus\n≥3 sources"] = n_c3

    return sizes


def make_db_tradeoff_plot(out_dir: Path) -> None:
    """Cutoff-strictness trade-off: universe size vs benchmark accuracy.

    X-axis = N human proteins the filter would admit if used as the
    universe gate (the cost of looser cutoffs — more candidates to
    triage downstream, more false-positives to filter).
    Y-axis = filter accuracy on the 147-gene benchmark under the
    per-source scoring rule (see ``make_db_variants_plot`` docstring).

    Within each DB group, variants are connected by a line ordered
    from strict-and-small to loose-and-large so the trade-off curve
    is visually obvious. The annotation on each marker lists the
    pos%/neg% recall split, which is what changes most as you loosen
    a filter (loose → recall pos at the cost of admitting more no's).
    """
    setup_plotting_style(style="whitegrid", context="notebook", font_scale=1.0)
    rows, bench_symbols = _benchmark_with_universe_join()
    _inject_raw_source_flags(rows, bench_symbols)

    sizes = _universe_size_per_variant()

    # Compute accuracy per variant under the same per-source rules as
    # the bar plot.
    points: list[dict] = []
    for name, fn, group in DB_VARIANTS:
        cov = GROUP_COVERAGE_FN.get(group, lambda r: True)
        n_correct = n_pos_correct = n_pos_total = n_neg_correct = n_neg_total = 0
        n_scored = 0
        for r in rows:
            if not cov(r):
                continue
            n_scored += 1
            vote = bool(fn(r))
            is_pos = r["ground_truth_verdict"] in {"yes", "contextual"}
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
        points.append({
            "label": name,
            "group": group,
            "size": sizes.get(name, 0),
            "acc": n_correct / max(n_scored, 1),
            "pos": n_pos_correct / max(n_pos_total, 1),
            "neg": n_neg_correct / max(n_neg_total, 1),
        })

    # Shorter labels for legibility in the scatter.
    short_label = {
        "UniProt baseline": "UniProt strict",
        "UniProt permissive\n(incl. plain Cell membrane)": "UniProt permissive",
        "UniProt TM-or-signal-or-surface\n(topology proxy)": "UniProt TM+signal",
        "GO baseline": "GO strict",
        "GO permissive\n(incl. IEA-only)": "GO permissive (+IEA)",
        "HPA baseline": "HPA",
        "SURFY baseline": "SURFY base",
        "SURFY score>0.5": "SURFY >0.5",
        "SURFY score>0.7": "SURFY >0.7",
        "CSPA baseline": "CSPA",
        "Consensus\n≥2 sources": "Consensus ≥2",
        "Consensus\n≥3 sources": "Consensus ≥3",
    }
    # Manual (dx, dy) offsets in display-points to keep labels from
    # overlapping in the dense upper-right cluster.
    offsets = {
        "UniProt strict":         (10, 4),
        "UniProt permissive":     (10, -22),
        "UniProt TM+signal":      (-20, 12),
        "GO strict":              (10, -16),
        "GO permissive (+IEA)":   (10, 8),
        "HPA":                    (-50, -16),
        "SURFY base":             (-110, 8),
        "SURFY >0.5":             (8, -4),
        "SURFY >0.7":             (-90, -8),
        "CSPA":                   (-50, -16),
        "Consensus ≥2":           (10, 6),
        "Consensus ≥3":           (10, 4),
    }

    fig, ax = plt.subplots(figsize=(13.5, 7.5))

    # Draw per-group connecting lines (sorted by size).
    group_to_pts: dict[str, list[dict]] = defaultdict(list)
    for p in points:
        group_to_pts[p["group"]].append(p)

    for g, pts in group_to_pts.items():
        if len(pts) < 2:
            continue
        s = sorted(pts, key=lambda p: p["size"])
        palette = _VARIANT_GROUP_PALETTE.get(g, ["#666666"])
        line_color = palette[0]
        ax.plot([p["size"] for p in s], [p["acc"] * 100 for p in s],
                color=line_color, linewidth=1.4, alpha=0.55, zorder=2)

    # Draw all points + labels.
    for p in points:
        palette = _VARIANT_GROUP_PALETTE.get(p["group"], ["#666666"])
        idx = sorted(group_to_pts[p["group"]], key=lambda q: q["size"]).index(p)
        color = palette[min(idx, len(palette) - 1)]
        ax.scatter(p["size"], p["acc"] * 100,
                   s=140, color=color, edgecolor="white",
                   linewidth=1.6, zorder=3)
        short = short_label.get(p["label"], p["label"])
        dx, dy = offsets.get(short, (10, 6))
        ax.annotate(
            f"{short}\n+{p['pos']*100:.0f}/-{p['neg']*100:.0f}",
            xy=(p["size"], p["acc"] * 100),
            xytext=(dx, dy), textcoords="offset points",
            fontsize=8, color=COLORS["dark"],
            bbox={"boxstyle": "round,pad=0.3", "fc": "white",
                  "ec": color, "lw": 0.7, "alpha": 0.92},
        )

    # Legend — one entry per group.
    seen = set()
    handles = []
    for p in points:
        if p["group"] in seen:
            continue
        seen.add(p["group"])
        palette = _VARIANT_GROUP_PALETTE.get(p["group"], ["#666666"])
        handles.append(plt.Line2D([], [], marker="o", linestyle="-",
                                   color=palette[0], markersize=9,
                                   label=p["group"]))
    ax.legend(handles=handles, loc="lower right", fontsize=9,
              frameon=True, framealpha=0.9, title="DB family")

    ax.set_xscale("log")
    ax.set_xlabel("Universe size — proteins this filter would admit "
                  "(log scale; lower = stricter / fewer downstream candidates)")
    ax.set_ylabel("Accuracy on 147-gene benchmark (%)")
    ax.set_ylim(35, 100)
    ax.set_xlim(200, 6000)
    ax.set_title(
        "Filter cutoff trade-off — strictness vs accuracy\n"
        "Annotation: variant • +pos/-neg recall (per-source missing rule: "
        "UniProt/GO/SURFY/CSPA absence→no-vote; HPA absence→abstain)"
    )
    sns.despine(ax=ax, top=True, right=True)
    save_figure(
        fig, filename="db_cutoff_tradeoff",
        output_dir=str(out_dir), formats=["pdf", "png"],
    )
    plt.close(fig)


def main() -> None:
    # Output dir overridable via DB_BARPLOT_OUT_DIR env var so the same
    # script can render into staging vs the "final" rendering folder
    # (data/analysis/triage_bench_final/) without code edits.
    out_dir = Path(os.environ.get(
        "DB_BARPLOT_OUT_DIR",
        str(ROOT / "data/analysis/triage_bench"),
    ))
    make_by_class_plot(out_dir)
    make_overall_plot(out_dir)
    make_cost_vs_accuracy_plot(out_dir)
    make_db_variants_plot(out_dir)
    make_db_tradeoff_plot(out_dir)


if __name__ == "__main__":
    main()
