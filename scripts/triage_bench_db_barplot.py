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
  triage bench by-variant plot.

Correctness convention (binary: surface vs not-surface):

* truth = `yes`        → caller correct iff vote = True
* truth = `contextual` → caller correct iff vote = True
* truth = `no`         → caller correct iff vote = False

LLM vote = True iff the emitted verdict is ``yes`` or ``contextual``
(yes/contextual interchangeable for surface accessibility).

Outputs (PDF + PNG via the brand plotting config):

* ``data/analysis/triage_bench/db_correctness_by_class.{pdf,png}``
* ``data/analysis/triage_bench/db_correctness_overall.{pdf,png}``

# Reproduction: per-figure standalone gists (secret; minimal PyPA
# inline-script-metadata scripts fetching canonical TSVs via
# raw.githubusercontent.com).
# Mirrors live in data/analysis/figures/make_*.py (canonical
# source-of-truth; the gists are the readers' minimal-dep mirror).
#
#   db_correctness_by_class:
#     https://gist.github.com/beccajcarlson/2bb4f7aac629535982c142bc2032e04d
#   db_cutoff_tradeoff:
#     https://gist.github.com/beccajcarlson/f9319af882e372194bd30640c0cbf2ed
#   db_correctness_overall:
#     https://gist.github.com/beccajcarlson/9c765ed9673d7bd845c3ac091ad2204d
#   benchmark_cost_vs_accuracy:
#     https://gist.github.com/beccajcarlson/d7f764d2de288ae31cf44173bc396d41
#
# See Final-Figure Gist Convention in CLAUDE.md / AGENTS.md.
"""

from __future__ import annotations

import csv
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
    # Opus cells retired (2026-06-30): the published figures this module used to
    # render (db_correctness_by_class, db_correctness_overall,
    # benchmark_cost_vs_accuracy) are now standalone canonicals that read the
    # figure TSV, so their model list comes from the DATA — including Opus 4.8.
    # The hardcoded opus-4-7 rows here shipped EMPTY bars once predictions moved
    # to opus-4-8; the only artifacts still rendered from this module are the
    # non-published native-cutoff / db-variant comparisons, which don't need Opus.
]
LLM_LABEL = {
    "_llm_haiku_naive":        "Haiku (naive)",
    "_llm_haiku_ncbi":         "Haiku (+ IDs)",
    "_llm_haiku_pubmed_ncbi":  "Haiku (+ IDs + PubMed)",
    "_llm_haiku_web_ncbi":     "Haiku (+ IDs + web)",
    "_llm_sonnet_naive":       "Sonnet (naive)",
    "_llm_sonnet_ncbi":        "Sonnet (+ IDs)",
    "_llm_sonnet_pubmed_ncbi": "Sonnet (+ IDs + PubMed)",
    "_llm_sonnet_web_ncbi":    "Sonnet (+ IDs + web)",
    "_llm_combined":           "Combined (Haiku→Sonnet)",
}

# Combined cell: confidence-routed Haiku+NCBI → Sonnet+NCBI. Accept
# Haiku when it emits `confidence == "high"`, otherwise escalate to
# Sonnet. Mirrors the triage bench by-variant Combined group.
COMBINED_KEY = "_llm_combined"
COMBINED_PRIMARY = ("_llm_haiku_ncbi", "_llm_sonnet_ncbi")  # (cheap, escalation)


# Palette — DBs use the brand categorical palette (5 distinct colors).
# LLM cells get a sequential Claude-orange walk: lighter = less context /
# smaller model, darker = more context / larger model. Same family as the
# triage bench by-variant plot. Base Claude orange is #d87851.
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
# Per-cell LLM predictions used to come from the JSON tree at
# data/eval/triage_bench_v1/<model>/<variant>/<gene>_run1.json. Those
# files are now sourced from D1 — populated by running the triage
# runner with `--d1 --run-id mainbench_canonical_v2`. Update this
# constant if the bench is re-run under a different run_id.
MAINBENCH_D1_RUN_ID = "mainbench_canonical_v2"

# When True, ``load_benchmark_with_votes`` rewrites the per-benchmark
# UniProt and CSPA flags using the optimized cutoffs surfaced by the
# trade-off audit (UniProt → TM+signal, CSPA → HC-only). All other
# sources use their canonical rule. Toggled by main() so by-class and
# overall plots can be re-rendered under both rule sets.
_USE_OPTIMIZED_CUTOFFS = False


def _optimized_uniprot_accs() -> set[str]:
    """Set of UniProt accessions admitted by the TM+signal cutoff
    (TM > 0 OR signal_peptide > 0 OR strict subcellular term)."""
    accs: set[str] = set()
    with UNIPROT_RAW_TSV.open() as fh:
        for r in csv.DictReader(fh, delimiter="\t"):
            locs = r.get("subcellular_locations") or ""
            strict = _uniprot_has_strict_term(locs)
            tm = _uniprot_feat_int(r, "feature_transmembrane_count") > 0
            sig = _uniprot_feat_int(r, "feature_signal_count") > 0
            if strict or tm or sig:
                accs.add(r["accession"])
    return accs


def _optimized_cspa_accs() -> set[str]:
    """Set of UniProt accessions admitted by the CSPA HC-only cutoff
    (drops `putative` and `unspecific` categories)."""
    accs: set[str] = set()
    cspa_path = ROOT / "data/processed/cspa/cspa_human_snapshot.tsv"
    with cspa_path.open() as fh:
        for r in csv.DictReader(fh, delimiter="\t"):
            if (r.get("cspa_is_high_confidence") or "").strip() == "1":
                accs.add(r["uniprot_accession"])
    return accs


def _load_all_mainbench_records() -> list[dict]:
    """Pull every per-cell main-bench record from D1 in a single round-trip.

    Lazy-cached via ``functools.cache`` so repeated calls within one
    script run share one D1 query (we hit it from ``_load_llm_predictions``
    once per LLM cell + ``_cell_cost_per_call`` once per cell, ~21 calls
    total without the cache).
    """
    from accessible_surfaceome.cloud.d1_client import D1Client
    from accessible_surfaceome.env import load_env
    load_env()
    with D1Client() as d1:
        return d1.query(
            "SELECT gene_symbol, model, prompt_variant, replicate, "
            "       predicted_verdict, predicted_reason, "
            "       predicted_confidence, predicted_key_uncertainty, "
            "       verdict_reasoning, "
            "       prompt_tokens, completion_tokens, "
            "       cache_creation_tokens, cache_read_tokens, "
            "       n_web_searches, cost_usd, latency_s "
            "FROM triage_run WHERE run_id = ? AND replicate = 1;",
            [MAINBENCH_D1_RUN_ID],
        )


_MAINBENCH_CACHE: list[dict] | None = None


def _mainbench_records() -> list[dict]:
    """Memoised wrapper around ``_load_all_mainbench_records``."""
    global _MAINBENCH_CACHE
    if _MAINBENCH_CACHE is None:
        _MAINBENCH_CACHE = _load_all_mainbench_records()
    return _MAINBENCH_CACHE


def _load_llm_predictions(model: str, variant: str) -> dict[str, dict]:
    """Return ``{gene_symbol: run_record_dict}`` for one (model, variant) cell.

    Reads from D1 (run_id=mainbench_canonical_v1) rather than the legacy
    ``data/eval/triage_bench_v1/<model>/<variant>/<gene>_run1.json`` tree.
    Records carry the same shape as the legacy JSONs for the fields the
    plot script consumes (``predicted_verdict``, ``predicted_confidence``,
    token counts, costs).
    """
    model_full = f"claude-{model}"
    return {
        r["gene_symbol"]: r
        for r in _mainbench_records()
        if r["model"] == model_full and r["prompt_variant"] == variant
    }


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

    # Optionally override UniProt + CSPA flags with the audit's
    # optimized cutoffs (TM+signal and HC-only respectively). The
    # optimized UniProt rule (TM+signal) is LOOSER than canonical, so
    # it admits proteins that aren't currently in candidate_universe —
    # we synthesize a vote-row for them so the by-class plot reflects
    # the hypothetical optimized universe, not the canonical one
    # constrained to existing universe rows. CSPA HC-only is stricter,
    # so no new rows need to be added on its behalf.
    if _USE_OPTIMIZED_CUTOFFS:
        opt_up = _optimized_uniprot_accs()
        opt_cspa = _optimized_cspa_accs()
        for acc, votes in votes_by_acc.items():
            votes["uniprot_surface_flag"] = acc in opt_up
            votes["cspa_surface_flag"] = acc in opt_cspa
        # Add stub rows for benchmark accessions that AREN'T in the
        # canonical universe but ARE admitted by optimized UniProt.
        # Without this the by-class plot under-counts UniProt by 1
        # for each TM+signal-rescued benchmark positive (STEAP1, STEAP2).
        bench_accs = {r["uniprot_acc"] for r in bench}
        for acc in (bench_accs & opt_up) - set(votes_by_acc):
            votes_by_acc[acc] = {flag: False for flag, _ in DB_FLAGS_5}
            votes_by_acc[acc]["uniprot_surface_flag"] = True

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


def make_by_class_plot(out_dir: Path, *, filename: str = "db_correctness_by_class") -> None:
    """Per-class accuracy of Sonnet + IDs vs the 5 M1 surface DBs.

    Compares one canonical LLM cell against the five classical
    surface-flag sources across four columns:
      - overall  : pooled accuracy across all 147 proteins
      - yes      : accuracy on ground_truth=yes proteins
      - contextual : accuracy on ground_truth=contextual
      - no       : accuracy on ground_truth=no
    """

    # NOTE: db_optimized_cutoffs.tsv is a COMMITTED canonical artifact — the
    # 15-column augmented form (accession sets + stable IDs added by
    # augment_figure_tsvs_with_stable_ids.py). Rendering must NOT rewrite it:
    # _dump_db_optimized_cutoffs() emits only the raw 3-column form, which would
    # silently regress the augmented committed file (an observed trap). The
    # optimized accession sets used below come from _optimized_*_accs() in
    # memory; the figures/ gist reads the committed TSV. Regenerate that file
    # deliberately (dump + augment), never as a render side effect.

    setup_plotting_style(style="whitegrid", context="notebook", font_scale=1.0)
    overall = overall_accuracy()
    fractions, totals, _, _ = compute_correctness()

    # Restricted caller set: just the one canonical LLM + the 5 DBs.
    # DBs are sorted descending by overall accuracy on this benchmark
    # so the strongest source sits next to the LLM bar — same convention
    # as the cost-vs-accuracy plot. With optimized cutoffs applied (when
    # _USE_OPTIMIZED_CUTOFFS=True), the sort reflects the optimized
    # accuracies, which can rearrange the bar order vs canonical.
    SONNET_NCBI_KEY = "_llm_sonnet_ncbi"
    sonnet_label = LLM_LABEL[SONNET_NCBI_KEY]
    db_labels_sorted = sorted(
        (label for _, label in DB_FLAGS_5),
        key=lambda lbl: -overall[lbl],
    )
    callers_in_plot = [sonnet_label, *db_labels_sorted]

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
        fig, filename=filename,
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
    """Truthiness of a flag column. Accepts integer-formatted ('1') AND
    float-formatted ('1.0') — pandas float coercion serializes some
    candidate_universe boolean columns as '1.0' (e.g. go_has_*)."""
    v = r.get(k)
    if not v:
        return False
    try:
        return float(v) >= 1.0
    except (TypeError, ValueError):
        return False


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
    """Canonical HPA surface flag — mirrors the loader at
    ``src/accessible_surfaceome/sources/hpa.py:276-278``:

        hpa_surface_flag = (hpa_pm_accessible == 1) | (hpa_junctional == 1)

    where ``hpa_pm_accessible`` = Plasma membrane appears in Enhanced /
    Supported / Approved tier (NOT Uncertain), and ``hpa_junctional``
    = Cell Junctions in those same tiers.

    Earlier versions of this helper used "Plasma membrane in Main or
    Additional location", which is BOTH looser (includes Uncertain-tier
    PM rows the loader drops, +329 proteins) AND tighter (misses 173
    Cell-Junctions rows the loader counts as surface). Stay aligned to
    the loader rule — when in doubt cross-check via
    ``_assert_canonical_sizes_match_universe`` below.
    """
    for tier_col in ("Enhanced", "Supported", "Approved"):
        v = (r.get(tier_col) or "").lower()
        if "plasma membrane" in v or "cell junctions" in v:
            return True
    return False


# UniProt's `subcellular_locations` field is pipe-delimited. Cell-membrane
# terms eligible for the permissive variant — broader than the strict
# set used by the existing baseline loader.
_UNIPROT_PERMISSIVE_TERMS = (
    "Cell surface", "Apical cell membrane", "Basolateral cell membrane",
    "GPI-anchor", "Cell membrane",
)


def _hpa_pm_in_tier(r: dict, tier: str) -> bool:
    v = (r.get(tier) or "").lower()
    return "plasma membrane" in v or "cell junctions" in v


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
        r["_uniprot_strict_only"] = _uniprot_has_strict_term(locs)
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
        # call when present (canonical = high tier PM/CJ).
        sym = (bench_symbols.get(acc) or "").upper()
        hpa_rec = raw_hpa.get(sym) if sym else None
        r["_hpa_in_raw"] = hpa_rec is not None
        r["_hpa_pm_raw"] = bool(hpa_rec and _hpa_pm_flag(hpa_rec))
        r["_hpa_enhanced_only"] = bool(
            hpa_rec and _hpa_pm_in_tier(hpa_rec, "Enhanced")
        )
        r["_hpa_with_uncertain"] = bool(hpa_rec and (
            _hpa_pm_flag(hpa_rec)
            or _hpa_pm_in_tier(hpa_rec, "Uncertain")
        ))


DB_VARIANTS: list[tuple[str, "callable", str]] = [
    # UniProt — strict → canonical → TM+signal → permissive ladder.
    ("UniProt strict-only\n(4 subcell terms)",
        lambda r: bool(r.get("_uniprot_strict_only")),
        "UniProt"),
    ("UniProt baseline",
        lambda r: _b(r, "uniprot_surface_flag"),
        "UniProt"),
    ("UniProt TM-or-signal-or-surface\n(topology proxy)",
        lambda r: bool(r.get("_uniprot_tm_or_signal_or_surface")),
        "UniProt"),
    ("UniProt permissive\n(incl. plain Cell membrane)",
        lambda r: bool(r.get("_uniprot_permissive")),
        "UniProt"),
    # GO — experimental+curated → canonical (+sequence) → permissive (+IEA).
    ("GO experimental+curated",
        lambda r: _b(r, "go_has_experimental") or _b(r, "go_has_curated"),
        "GO"),
    ("GO baseline",
        lambda r: _b(r, "go_surface_flag"),
        "GO"),
    ("GO permissive\n(incl. IEA-only)",
        lambda r: bool(r.get("_go_permissive")),
        "GO"),
    # HPA — Enhanced-only → canonical → canonical+Uncertain.
    # HPA reads from the raw subcellular_location TSV (bypassing the
    # surface-pool filter at source-build time) so it can vote
    # "not surface" on proteins it imaged but didn't see at PM
    # (KRAS, ABCB9, vesicle-resident, etc.).
    ("HPA Enhanced-only\n(strictest tier)",
        lambda r: bool(r.get("_hpa_enhanced_only")),
        "HPA"),
    ("HPA baseline",
        lambda r: bool(r.get("_hpa_pm_raw")),
        "HPA"),
    ("HPA + Uncertain tier",
        lambda r: bool(r.get("_hpa_with_uncertain")),
        "HPA"),
    # SURFY — score>0.9 → score>0.7 → score>0.5 → canonical (any surface label).
    ("SURFY score>0.9",
        lambda r: _b(r, "surfy_surface_flag") and (_f(r, "surfy_ml_score") or 0) > 0.9,
        "SURFY"),
    ("SURFY score>0.7",
        lambda r: _b(r, "surfy_surface_flag") and (_f(r, "surfy_ml_score") or 0) > 0.7,
        "SURFY"),
    ("SURFY score>0.5",
        lambda r: _b(r, "surfy_surface_flag") and (_f(r, "surfy_ml_score") or 0) > 0.5,
        "SURFY"),
    ("SURFY baseline",
        lambda r: _b(r, "surfy_surface_flag"),
        "SURFY"),
    # CSPA — high-conf only → canonical (HC+putative) → + unspecific.
    ("CSPA high-conf only",
        lambda r: _b(r, "cspa_is_high_confidence"),
        "CSPA"),
    ("CSPA baseline",
        lambda r: _b(r, "cspa_surface_flag"),
        "CSPA"),
    ("CSPA + unspecific",
        lambda r: _b(r, "cspa_surface_flag") or _b(r, "cspa_is_unspecific"),
        "CSPA"),
    # Consensus — ≥1 (= the universe itself) → ≥2 → ≥3.
    ("Consensus\n≥1 source (= universe)",
        lambda r: int(r.get("n_sources_surface", "0") or 0) >= 1,
        "consensus"),
    ("Consensus\n≥2 sources",
        lambda r: int(r.get("n_sources_surface", "0") or 0) >= 2,
        "consensus"),
    ("Consensus\n≥3 sources",
        lambda r: int(r.get("n_sources_surface", "0") or 0) >= 3,
        "consensus"),
]

# Colors per group — brand palette for the 5 baselines; consensus gets
# the success-green family. Within each group the palette is sequenced
# strict→loose (strict = darkest). Index in palette = within-group
# strictness rank (0 = strictest).
_VARIANT_GROUP_PALETTE: dict[str, list[str]] = {
    # strict → canonical → TM+signal → permissive
    "UniProt":   ["#7a1f2a", "#a82e3d", CATEGORICAL_PALETTE[0], "#e08896"],
    # exp+curated → canonical → permissive
    "GO":        ["#1e3a32", "#2c5048", CATEGORICAL_PALETTE[1]],
    # Enhanced → canonical → +Uncertain
    "HPA":       ["#9a6803", CATEGORICAL_PALETTE[2], "#f1c168"],
    # score>0.9 → >0.7 → >0.5 → canonical
    "SURFY":     ["#5c4585", "#7a5da8", CATEGORICAL_PALETTE[3], "#c5a8e0"],
    # HC-only → canonical → +unspecific
    "CSPA":      ["#5a1a25", CATEGORICAL_PALETTE[4], "#c97a8a"],
    # ≥1 → ≥2 → ≥3 (loose to strict; reverse the visual)
    "consensus": ["#a8d4bd", "#5cae84", "#2E7A55"],
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


def _benchmark_with_universe_join(
    *, include_outside_universe: bool = False,
) -> tuple[list[dict], dict[str, str]]:
    """Load benchmark rows joined to candidate_universe by UniProt
    accession. Returns ``(rows, symbols)`` — one dict per benchmark
    protein found in candidate_universe, plus a mapping
    ``uniprot_accession → gene_symbol`` for all 147 benchmark rows
    (including those dropped from the universe join).

    When ``include_outside_universe=True`` (used by the cutoff trade-off
    plot to make its denominator match the by-class plot), additional
    stub rows are emitted for benchmark proteins NOT in
    candidate_universe — all `*_surface_flag` columns default to "0",
    so canonical lambdas vote False, but the raw-source injection step
    can still set `_uniprot_tm_or_signal_or_surface`, `_hpa_pm_raw`,
    etc. by pulling from upstream TSVs.
    """
    truth_by_acc: dict[str, str] = {}
    symbols: dict[str, str] = {}
    with BENCH_TSV.open() as fh:
        for r in csv.DictReader(fh, delimiter="\t"):
            truth_by_acc[r["uniprot_acc"]] = r["ground_truth_verdict"]
            symbols[r["uniprot_acc"]] = r["gene_symbol"]
    out: list[dict] = []
    seen: set[str] = set()
    with CAND_TSV_PATH.open() as fh:
        for r in csv.DictReader(fh, delimiter="\t"):
            acc = r["uniprot_accession"]
            if acc in truth_by_acc:
                r["ground_truth_verdict"] = truth_by_acc[acc]
                out.append(r)
                seen.add(acc)
    if include_outside_universe:
        # Stub-row template — every column referenced by a variant
        # lambda defaults to a falsy string. The raw-source injection
        # step still runs and can flip these via injected `_*` keys.
        for acc, truth in truth_by_acc.items():
            if acc in seen:
                continue
            out.append({
                "uniprot_accession": acc,
                "ground_truth_verdict": truth,
                "uniprot_surface_flag": "0",
                "go_surface_flag": "0",
                "hpa_surface_flag": "0",
                "surfy_surface_flag": "0",
                "cspa_surface_flag": "0",
                "go_has_experimental": "0",
                "go_has_curated": "0",
                "go_has_sequence": "0",
                "go_has_electronic": "0",
                "cspa_is_high_confidence": "0",
                "cspa_is_putative": "0",
                "cspa_is_unspecific": "0",
                "n_sources_surface": "0",
                "surfy_ml_score": "",
            })
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


def _dump_optimized_db_accs() -> None:
    """Dump the optimized-cutoff accession sets to two small TSVs so the
    figures-folder gist for db_correctness_by_class can apply the same
    cutoffs without re-loading the raw UniProt + CSPA dumps.

    Paths:
      data/processed/triage_bench/uniprot_tm_signal_accs.tsv
      data/processed/triage_bench/cspa_hc_only_accs.tsv

    Each file is a single-column TSV (header ``uniprot_acc``).
    """
    out_dir = ROOT / "data/processed/triage_bench"
    out_dir.mkdir(parents=True, exist_ok=True)
    up_accs = sorted(_optimized_uniprot_accs())
    cspa_accs = sorted(_optimized_cspa_accs())
    (out_dir / "uniprot_tm_signal_accs.tsv").write_text(
        "uniprot_acc\n" + "\n".join(up_accs) + "\n"
    )
    (out_dir / "cspa_hc_only_accs.tsv").write_text(
        "uniprot_acc\n" + "\n".join(cspa_accs) + "\n"
    )


def main() -> None:
    # Output dir overridable via DB_BARPLOT_OUT_DIR env var so the same
    # script can render into staging vs the "final" rendering folder
    # (data/analysis/triage_bench_final/) without code edits.
    out_dir = Path(os.environ.get(
        "DB_BARPLOT_OUT_DIR",
        str(ROOT / "data/analysis/triage_bench"),
    ))
    # db_correctness_by_class is Figure 2 and must ship on the benchmark-
    # OPTIMIZED cutoffs (UniProt TM+signal, CSPA HC-only) — the same membership
    # the figures/ gist and the accuracy claims use. Render that as the PRIMARY
    # (unsuffixed) output; keep the native pre-recalibration variant alongside
    # under a `_native_cutoffs` suffix for comparison. (Previously the primary
    # was the native cutoff and optimized was the suffixed variant, so a naive
    # re-render of db_correctness_by_class silently used the wrong cutoff.)
    global _USE_OPTIMIZED_CUTOFFS
    _USE_OPTIMIZED_CUTOFFS = True
    try:
        # Side-effect: dump the optimized accession sets so the figure-TSV
        # builders (scripts/build_figure_tsvs.py) can apply the same cutoffs
        # without re-loading the raw UniProt + CSPA dumps.
        _dump_optimized_db_accs()
    finally:
        _USE_OPTIMIZED_CUTOFFS = False

    # The published figures this module used to render are each now their own
    # canonical generator that reads the committed figure TSV — so the model
    # list comes from the DATA, not the opus-4-7 hardcode that shipped empty
    # bars once predictions moved to opus-4-8:
    #   db_correctness_by_class     -> scripts/db_correctness_by_class.py
    #   db_correctness_overall      -> scripts/db_correctness_overall.py
    #   benchmark_cost_vs_accuracy  -> scripts/benchmark_cost_vs_accuracy.py
    #   db_cutoff_tradeoff          -> scripts/db_cutoff_tradeoff.py
    # Rendering them here too would let a monolith re-run overwrite the
    # TSV-faithful figure with a recomputed one, so those calls are gone. This
    # module now only dumps the optimized-cutoff accession sets (above) and
    # renders the non-published internal comparison artifacts below (native
    # pre-recalibration by-class + the per-DB cutoff-variant panel). NOTE:
    # make_overall_plot / make_cost_vs_accuracy_plot / make_db_tradeoff_plot are
    # now unreferenced and slated for deletion in a dedicated monolith-teardown.
    make_by_class_plot(out_dir, filename="db_correctness_by_class_native_cutoffs")
    make_db_variants_plot(out_dir)


if __name__ == "__main__":
    main()
