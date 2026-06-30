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
    # Sonnet 5 added 2026-06-30 — ncbi only (head-to-head model compare
    # with Sonnet 4.6's canonical ncbi cell). No naive/pubmed/web variants
    # sampled yet.
    ("_llm_sonnet5_ncbi",       "sonnet-5",   "ncbi"),
    ("_llm_opus_naive",         "opus-4-8",   "naive"),
    ("_llm_opus_ncbi",          "opus-4-8",   "ncbi"),
]
LLM_LABEL = {
    "_llm_haiku_naive":        "Haiku (naive)",
    "_llm_haiku_ncbi":         "Haiku (+ IDs)",
    "_llm_haiku_pubmed_ncbi":  "Haiku (+ IDs + PubMed)",
    "_llm_haiku_web_ncbi":     "Haiku (+ IDs + web)",
    "_llm_sonnet_naive":       "Sonnet 4.6 (naive)",
    "_llm_sonnet_ncbi":        "Sonnet 4.6 (+ IDs)",
    "_llm_sonnet_pubmed_ncbi": "Sonnet 4.6 (+ IDs + PubMed)",
    "_llm_sonnet_web_ncbi":    "Sonnet 4.6 (+ IDs + web)",
    "_llm_sonnet5_ncbi":       "Sonnet 5 (+ IDs)",
    "_llm_opus_naive":         "Opus (naive)",
    "_llm_opus_ncbi":          "Opus (+ IDs)",
    "_llm_combined":           "Combined (Haiku→Sonnet)",
}

# Combined cell: confidence-routed Haiku+NCBI → Sonnet+NCBI. Accept
# Haiku when it emits `confidence == "high"`, otherwise escalate to
# Sonnet. Mirrors the triage bench by-variant Combined group.
COMBINED_KEY = "_llm_combined"
COMBINED_PRIMARY = ("_llm_haiku_ncbi", "_llm_sonnet_ncbi")  # (cheap, escalation)

LLM_KEYS = [k for k, _, _ in LLM_CELLS] + [COMBINED_KEY]

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
    "_llm_sonnet5_ncbi":       "#b35238",   # Sonnet 5 — between sonnet_web_ncbi and opus_naive
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


def _dump_db_optimized_cutoffs() -> None:
    """Dump the optimized-cutoff accession sets to a small TSV.

    Lets the figures-folder gist ``make_db_correctness_by_class.py``
    reproduce the optimized-cutoff version of the by-class plot
    without re-loading the raw UniProt + CSPA dumps. Same pattern as
    ``_dump_db_cutoff_tradeoff_points``.

    Output: ``data/processed/triage_bench/db_optimized_cutoffs.tsv``
    (LFS-exempted in .gitattributes). Columns:
      accession, uniprot_optimized, cspa_optimized
    where the flag is 1 if the accession is admitted by the optimized
    rule for that source (TM+signal for UniProt, HC-only for CSPA),
    else 0. Rows include the union of both optimized sets so the gist
    can rebuild both flag columns from one file.
    """
    up = _optimized_uniprot_accs()
    cspa = _optimized_cspa_accs()
    out = ROOT / "data/processed/triage_bench/db_optimized_cutoffs.tsv"
    out.parent.mkdir(parents=True, exist_ok=True)
    with out.open("w", newline="") as fh:
        w = csv.DictWriter(
            fh, fieldnames=["accession", "uniprot_optimized", "cspa_optimized"],
            delimiter="\t",
        )
        w.writeheader()
        for acc in sorted(up | cspa):
            w.writerow({
                "accession": acc,
                "uniprot_optimized": int(acc in up),
                "cspa_optimized":    int(acc in cspa),
            })


def _load_all_mainbench_records() -> list[dict]:
    """Pull every per-cell main-bench record from D1 in a single round-trip.

    Returns ALL replicates (3 per cell). Callers that want a single-rep
    view filter on ``replicate`` themselves (e.g. ``_load_llm_predictions``
    keeps rep=1 for the legacy point-estimate accuracy path).
    ``_per_rep_accuracy_by_cell`` sees the full set so the bar plot can
    render mean ± SEM with all 3 dots.

    Lazy-cached via ``_MAINBENCH_CACHE`` so repeated calls within one
    script run share one D1 query.
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
            "FROM triage_run WHERE run_id = ?;",
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
        if r["model"] == model_full
        and r["prompt_variant"] == variant
        and r["replicate"] == 1
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


def _per_rep_accuracy_by_cell() -> dict[tuple[str, str], list[float]]:
    """Soft-credit accuracy per replicate for every D1 (model_full, variant) cell.

    Returns ``{(claude-<model>, variant): [acc_rep1, acc_rep2, ...]}``. Used by
    ``make_overall_plot`` so each bar's height is the mean-across-reps with
    a SEM error bar and individual rep dots — the canonical generator's
    previous pooled ``overall_accuracy()`` collapsed this information.

    Soft-credit rule (matches ``_is_soft_match`` in
    ``scripts/augment_figure_tsvs_with_stable_ids.py``): predicted yes ↔
    contextual interchangeable; everything else exact-match.
    """
    bench, _ = load_benchmark_with_votes()
    # load_benchmark_with_votes yields records keyed on "gene" (the bench
    # TSV's column name) — not "gene_symbol". Track that down here so the
    # join below actually finds a truth label for every cell.
    truth_by_gene = {p["gene"]: p["verdict"] for p in bench}

    correct_total: dict[tuple[str, str, int], list[int]] = defaultdict(lambda: [0, 0])
    for r in _mainbench_records():
        truth = truth_by_gene.get(r["gene_symbol"])
        if truth is None:
            continue
        pv = (r.get("predicted_verdict") or "").strip()
        is_match = 0
        if pv and truth:
            if pv == truth or (pv in ("yes", "contextual") and truth in ("yes", "contextual")):
                is_match = 1
        key = (r["model"], r["prompt_variant"], r["replicate"])
        correct_total[key][0] += is_match
        correct_total[key][1] += 1

    out: dict[tuple[str, str], list[float]] = defaultdict(list)
    for (model_full, variant, _rep), (n_correct, n_total) in sorted(correct_total.items()):
        if n_total > 0:
            out[(model_full, variant)].append(n_correct / n_total)
    return dict(out)


def make_overall_plot(out_dir: Path, *, filename: str = "db_correctness_overall") -> None:
    """LLM-only overall accuracy on the 147-gene bench.

    Bar height = mean of per-replicate soft-credit accuracies. SEM error
    bars + individual per-rep scatter points overlaid so the run-to-run
    variability is visible (3 reps per cell). Color encodes the model;
    hatch pattern encodes the prompt variant.
    """

    setup_plotting_style(style="whitegrid", context="notebook", font_scale=1.0)
    rep_acc = _per_rep_accuracy_by_cell()

    # Group LLM cells by model. Variant order = light-to-dark context
    # walk so the hatch pattern reads as "amount of resolver / web /
    # literature scaffolding".
    VARIANT_ORDER = ["naive", "ncbi", "web_ncbi", "pubmed_ncbi"]
    VARIANT_LABEL = {
        "naive":        "naive",
        "ncbi":         "+ IDs",
        "web_ncbi":     "+ IDs + web",
        "pubmed_ncbi":  "+ IDs + PubMed",
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
    MODEL_ORDER = ["haiku-4-5", "sonnet-4-6", "sonnet-5", "opus-4-8"]
    MODEL_LABEL = {
        "haiku-4-5":  "Haiku 4.5",
        "sonnet-4-6": "Sonnet 4.6",
        "sonnet-5":   "Sonnet 5",
        "opus-4-8":   "Opus 4.8",
    }
    MODEL_COLOR = {
        "haiku-4-5":  "#f1c4ab",
        "sonnet-4-6": "#d87851",
        "sonnet-5":   "#b35238",
        "opus-4-8":   "#a85b3f",
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
        model_full = f"claude-{model_slug}"
        n_drawn = 0
        for variant, vote_key in cells_sorted:
            reps = rep_acc.get((model_full, variant), [])
            if not reps:
                # No D1 rows for this cell — skip rather than draw an
                # empty / 0-height bar. Was the failure mode that drew
                # phantom 33.3% bars for `opus-4-7` when D1 only had
                # `claude-opus-4-8`.
                continue
            mean_acc = sum(reps) / len(reps)
            color = MODEL_COLOR[model_slug]
            hatch = VARIANT_HATCH.get(variant, "")
            ax.bar(
                x, mean_acc, width=bar_width,
                color=color,
                edgecolor=COLORS["dark"],
                linewidth=0.6,
                hatch=hatch,
                zorder=3,
            )
            # SEM error bar — needs ≥ 2 reps.
            if len(reps) >= 2:
                sd = (sum((v - mean_acc) ** 2 for v in reps) / (len(reps) - 1)) ** 0.5
                sem = sd / (len(reps) ** 0.5)
                ax.errorbar(
                    x, mean_acc, yerr=sem, fmt="none",
                    ecolor=COLORS["dark"], elinewidth=1.0, capsize=3, capthick=1.0,
                    zorder=4,
                )
            # Individual per-rep dots, jittered within the bar so coincident
            # values don't fully overlap.
            for j, rv in enumerate(reps):
                jitter = (j - (len(reps) - 1) / 2) * (bar_width * 0.18)
                ax.scatter(
                    x + jitter, rv, s=18, color=COLORS["dark"],
                    edgecolor="white", linewidth=0.5, zorder=5, alpha=0.85,
                )
            ax.text(
                x, mean_acc + 0.018,
                f"{mean_acc:.1%}",
                ha="center", va="bottom",
                fontsize=10, color=COLORS["dark"],
            )
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
            n_drawn += 1
        # Center the model label under the block of variant bars that
        # we actually drew — using cells_sorted's count would mis-center
        # when a cell is skipped for missing data.
        if n_drawn > 0:
            block_end = x - inter_variant_gap - bar_width
            block_center = (model_block_start + block_end) / 2 + bar_width / 2
            tick_positions.append(block_center)
            tick_labels.append(MODEL_LABEL[model_slug])
        x += inter_model_gap

    ax.set_xticks(tick_positions)
    ax.set_xticklabels(tick_labels)
    ax.set_xlabel("")
    # Two-line ylabel so the bbox_inches="tight" save leaves enough margin
    # for it; the single-line "Overall accuracy on 147-gene benchmark" was
    # being clipped on the left edge.
    ax.set_ylabel("Overall accuracy on\n147-gene benchmark")
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
        fig, filename=filename,
        output_dir=str(out_dir), formats=["pdf", "png"],
    )
    plt.close(fig)


WHOLE_GENOME_N = 19_464  # NCBI protein-coding ∩ has HGNC xref


# Anthropic per-1M-token pricing. cache_write = 1.25× input (5-min TTL),
# cache_read = 0.10× input. https://docs.anthropic.com/.../prompt-caching
_PRICE: dict[str, dict[str, float]] = {
    "claude-haiku-4-5":  {"in":  1.0, "cw":  1.25, "cr": 0.10, "out":  5.0},
    "claude-sonnet-4-6": {"in":  3.0, "cw":  3.75, "cr": 0.30, "out": 15.0},
    "claude-sonnet-5":   {"in":  3.0, "cw":  3.75, "cr": 0.30, "out": 15.0},   # placeholder — confirm Anthropic list price
    "claude-opus-4-7":   {"in": 15.0, "cw": 18.75, "cr": 1.50, "out": 75.0},
    "claude-opus-4-8":   {"in": 15.0, "cw": 18.75, "cr": 1.50, "out": 75.0},
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

    This makes "Sonnet (+ IDs)" comparable to "Sonnet (+ IDs + PubMed)"
    on the same x-axis without one being unfairly boosted because its
    capture happened to disable caching.
    """
    out: dict[str, float] = {}
    for vote_key, model, variant in LLM_CELLS:
        out[vote_key] = _cell_cost_per_call(model, variant)
    return out


def _cell_cost_per_call(model: str, variant: str) -> float:
    # Read the cell's per-record telemetry from D1 (uploaded under
    # MAINBENCH_D1_RUN_ID) — same fields the legacy JSON tree carried.
    cell_records = _load_llm_predictions(model, variant)
    records = list(cell_records.values())
    if not records:
        return 0.0
    pt_total = cr_total = cw_total = ot_total = ws_total = 0
    for d in records:
        pt_total += int(d.get("prompt_tokens") or 0)
        cr_total += int(d.get("cache_read_tokens") or 0)
        cw_total += int(d.get("cache_creation_tokens") or 0)
        ot_total += int(d.get("completion_tokens") or 0)
        ws_total += int(d.get("n_web_searches") or 0)
    n = len(records)
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

    # Mean-of-replicates accuracy (matches the bar heights in
    # db_correctness_overall — single-rep was the old shape and made
    # the y-axis inconsistent between the two supp figs).
    rep_acc = _per_rep_accuracy_by_cell()
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
        # Sonnet 5 (+ IDs) sits ~2pp below Sonnet 4.6 (+ IDs + PubMed)
        # at a very similar cost. Default (7, 10) would stack them; push
        # Sonnet 5 well below its point with a leader so the labels
        # don't overlap.
        "_llm_sonnet5_ncbi":       (  7, -36),
        "_llm_opus_naive":         (  7, -18),
        "_llm_opus_ncbi":          (  7,  10),
    }

    # LLM cells as scatter — x is $/whole-genome at 1 rep, y is mean-of-rep accuracy.
    for vote_key, model_slug, variant in LLM_CELLS:
        label = LLM_LABEL[vote_key]
        reps = rep_acc.get((f"claude-{model_slug}", variant), [])
        if not reps:
            continue
        x = cost_per_call[vote_key] * WHOLE_GENOME_N
        y = (sum(reps) / len(reps)) * 100
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

    # NOTE: M1 DB baselines used to be drawn here as horizontal reference
    # lines. Dropped 2026-05-12 — they compress the LLM-cell range against
    # the bottom 40-50% of the chart, making cost/accuracy differences
    # between Claude variants hard to read. The DB→LLM comparison lives
    # in db_correctness_overall and db_correctness_by_class instead.

    ax.set_xscale("log")
    ax.set_xlabel(f"Cost per whole-genome pass at 1 rep  ($, log scale; ×{WHOLE_GENOME_N:,} genes)")
    ax.set_ylabel("Overall accuracy on 147-gene benchmark (%)")
    # Zoom in on the LLM range — DB baselines (40-82%) are gone so we
    # no longer need to keep them in frame. Floor at min(LLM) - 2 to
    # leave a little headroom under the lowest cell.
    # Floor at min(LLM mean-of-rep accuracy) - 2pp.
    llm_means = [
        sum(reps) / len(reps) * 100
        for (_, _), reps in rep_acc.items() if reps
    ]
    ymin = min(llm_means) if llm_means else 80.0
    ax.set_ylim(max(78, ymin - 2), 100)

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


SURFY_TSV = ROOT / "data/processed/surfy/surfy_human_snapshot.tsv"
CSPA_TSV = ROOT / "data/processed/cspa/cspa_human_snapshot.tsv"


def _universe_size_per_variant() -> dict[str, int]:
    """For each DB_VARIANTS entry, compute how many human proteins
    the filter would admit if used as a universe gate. The size is the
    decision cost — more proteins admitted = more downstream agent
    triage work and more potential false positives in the universe.
    """
    sizes: dict[str, int] = {}

    # UniProt — strict / canonical / TM+signal / permissive ladder.
    n_strict_only = n_canonical = n_perm = n_tm = 0
    with UNIPROT_RAW_TSV.open() as fh:
        for r in csv.DictReader(fh, delimiter="\t"):
            locs = r.get("subcellular_locations") or ""
            parts = set(locs.split("|")) if locs else set()
            strict = _uniprot_has_strict_term(locs)
            topo = _uniprot_feat_int(r, "feature_topo_extracellular_count") > 0
            canonical = strict or topo
            perm = canonical or "Cell membrane" in parts
            tm = (_uniprot_feat_int(r, "feature_transmembrane_count") > 0
                  or _uniprot_feat_int(r, "feature_signal_count") > 0
                  or strict)
            if strict:
                n_strict_only += 1
            if canonical:
                n_canonical += 1
            if perm:
                n_perm += 1
            if tm:
                n_tm += 1
    sizes["UniProt strict-only\n(4 subcell terms)"] = n_strict_only
    sizes["UniProt baseline"] = n_canonical
    sizes["UniProt TM-or-signal-or-surface\n(topology proxy)"] = n_tm
    sizes["UniProt permissive\n(incl. plain Cell membrane)"] = n_perm

    # GO — exp+curated / canonical (+sequence) / permissive (+IEA).
    n_go_strict = n_go_base = n_go_perm = 0
    with GO_RAW_TSV.open() as fh:
        for r in csv.DictReader(fh, delimiter="\t"):
            exp_only = int(r.get("has_experimental") or 0) + int(r.get("has_curated") or 0)
            seq = int(r.get("has_sequence") or 0)
            ele = int(r.get("has_electronic") or 0)
            if exp_only > 0:
                n_go_strict += 1
            if exp_only + seq > 0:
                n_go_base += 1
            if exp_only + seq + ele > 0:
                n_go_perm += 1
    sizes["GO experimental+curated"] = n_go_strict
    sizes["GO baseline"] = n_go_base
    sizes["GO permissive\n(incl. IEA-only)"] = n_go_perm

    # HPA — Enhanced / canonical (E+S+A) / + Uncertain.
    n_hpa_enh = n_hpa = n_hpa_unc = 0
    with HPA_RAW_TSV.open() as fh:
        for r in csv.DictReader(fh, delimiter="\t"):
            in_enh = _hpa_pm_in_tier(r, "Enhanced")
            in_canon = _hpa_pm_flag(r)
            in_unc = in_canon or _hpa_pm_in_tier(r, "Uncertain")
            if in_enh:
                n_hpa_enh += 1
            if in_canon:
                n_hpa += 1
            if in_unc:
                n_hpa_unc += 1
    sizes["HPA Enhanced-only\n(strictest tier)"] = n_hpa_enh
    sizes["HPA baseline"] = n_hpa
    sizes["HPA + Uncertain tier"] = n_hpa_unc

    # SURFY — score>0.9 / >0.7 / >0.5 / canonical.
    n_s = n_s05 = n_s07 = n_s09 = 0
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
                if score > 0.9:
                    n_s09 += 1
    sizes["SURFY score>0.9"] = n_s09
    sizes["SURFY score>0.7"] = n_s07
    sizes["SURFY score>0.5"] = n_s05
    sizes["SURFY baseline"] = n_s

    # CSPA — HC-only / canonical / + unspecific.
    n_c_hc = n_c = n_c_uns = 0
    with CSPA_TSV.open() as fh:
        for r in csv.DictReader(fh, delimiter="\t"):
            hc = (r.get("cspa_is_high_confidence") or "").strip() == "1"
            pu = (r.get("cspa_is_putative") or "").strip() == "1"
            un = (r.get("cspa_is_unspecific") or "").strip() == "1"
            if hc:
                n_c_hc += 1
            if hc or pu:
                n_c += 1
            if hc or pu or un:
                n_c_uns += 1
    sizes["CSPA high-conf only"] = n_c_hc
    sizes["CSPA baseline"] = n_c
    sizes["CSPA + unspecific"] = n_c_uns

    # Consensus — ≥1 / ≥2 / ≥3 over candidate_universe.
    n_c1 = n_c2 = n_c3 = 0
    with CAND_TSV_PATH.open() as fh:
        for r in csv.DictReader(fh, delimiter="\t"):
            try:
                n = int(r.get("n_sources_surface") or 0)
            except (TypeError, ValueError):
                continue
            if n >= 1:
                n_c1 += 1
            if n >= 2:
                n_c2 += 1
            if n >= 3:
                n_c3 += 1
    sizes["Consensus\n≥1 source (= universe)"] = n_c1
    sizes["Consensus\n≥2 sources"] = n_c2
    sizes["Consensus\n≥3 sources"] = n_c3

    return sizes


# Canonical baselines should reproduce candidate_universe.tsv flag counts
# within a small tolerance. The merge step drops some raw-source positives
# (split-mapping ambiguous, unmappable to UniProt anchor) so a perfect
# match isn't expected — but a >15% drift means the recomputed rule has
# diverged from the loader (the UniProt 415-vs-3175 bug class).
_CANONICAL_FLAG_COL = {
    "UniProt baseline": "uniprot_surface_flag",
    "GO baseline":      "go_surface_flag",
    "HPA baseline":     "hpa_surface_flag",
    "SURFY baseline":   "surfy_surface_flag",
    "CSPA baseline":    "cspa_surface_flag",
}


def _assert_canonical_sizes_match_universe(sizes: dict[str, int],
                                            tol: float = 0.15) -> None:
    """Fail loud if a canonical recompute drifts from the universe flag
    count by more than ``tol`` (default 15%). Catches the class of bug
    where the analysis re-implements a loader rule incorrectly."""
    univ_counts: dict[str, int] = dict.fromkeys(_CANONICAL_FLAG_COL.values(), 0)
    with CAND_TSV_PATH.open() as fh:
        for r in csv.DictReader(fh, delimiter="\t"):
            for col in univ_counts:
                if r.get(col) == "1":
                    univ_counts[col] += 1

    drifts: list[str] = []
    for variant_name, flag_col in _CANONICAL_FLAG_COL.items():
        recomputed = sizes.get(variant_name, 0)
        universe = univ_counts[flag_col]
        if universe == 0:
            continue
        drift = abs(recomputed - universe) / universe
        marker = "OK" if drift <= tol else "DRIFT"
        print(f"  [{marker}] {variant_name:<18s}  recompute={recomputed:5d}  "
              f"universe={universe:5d}  drift={drift*100:.1f}%")
        if drift > tol:
            drifts.append(
                f"{variant_name}: recompute={recomputed}, universe={universe} "
                f"(drift={drift*100:.1f}% > tol={tol*100:.0f}%)"
            )
    if drifts:
        raise AssertionError(
            "Canonical filter sizes diverge from candidate_universe.tsv — "
            "the analysis rule has drifted from the loader. Fix:\n  - "
            + "\n  - ".join(drifts)
        )


# Variant labels (long → short) for the cutoff trade-off scatter.
_VARIANT_SHORT_LABEL = {
    "UniProt strict-only\n(4 subcell terms)":              "strict-4",
    "UniProt baseline":                                    "canonical",
    "UniProt TM-or-signal-or-surface\n(topology proxy)":   "TM+signal",
    "UniProt permissive\n(incl. plain Cell membrane)":     "permissive",
    "GO experimental+curated":                             "exp+curated",
    "GO baseline":                                         "canonical",
    "GO permissive\n(incl. IEA-only)":                     "+ IEA",
    "HPA Enhanced-only\n(strictest tier)":                 "Enhanced",
    "HPA baseline":                                        "canonical",
    "HPA + Uncertain tier":                                "+ Uncertain",
    "SURFY score>0.9":                                     ">0.9",
    "SURFY score>0.7":                                     ">0.7",
    "SURFY score>0.5":                                     ">0.5",
    "SURFY baseline":                                      "canonical",
    "CSPA high-conf only":                                 "HC-only",
    "CSPA baseline":                                       "canonical",
    "CSPA + unspecific":                                   "+ unspecific",
}

# Which variant in each group counts as "canonical" — gets the diamond
# marker. Mirrors the rules audited against candidate_universe.tsv.
_CANONICAL_VARIANT = {
    "UniProt": "UniProt baseline",
    "GO":      "GO baseline",
    "HPA":     "HPA baseline",
    "SURFY":   "SURFY baseline",
    "CSPA":    "CSPA baseline",
}

# Recommended-after-trade-off variant per source (star marker). Only
# set when the trade-off analysis prefers a non-canonical cutoff —
# leave None when canonical is the right call.
_RECOMMENDED_VARIANT = {
    "UniProt": "UniProt TM-or-signal-or-surface\n(topology proxy)",
    "GO":      None,
    "HPA":     None,
    "SURFY":   None,
    "CSPA":    "CSPA high-conf only",
}


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


def _dump_db_cutoff_tradeoff_points(
    points_by_group: dict[str, list[dict]],
) -> None:
    """Write the cutoff-trade-off precomputed points to a flat TSV.

    Path: ``data/processed/triage_bench/db_cutoff_tradeoff_points.tsv``.
    The figures-folder gist script reads this so a reader can
    reproduce the plot without re-loading the raw DB sources.
    """
    out_tsv = (
        ROOT / "data/processed/triage_bench/db_cutoff_tradeoff_points.tsv"
    )
    out_tsv.parent.mkdir(parents=True, exist_ok=True)
    rows: list[dict] = []
    for group, pts in points_by_group.items():
        for p in pts:
            rows.append({
                "group":     group,
                "label":     p["label"],
                "size":      p["size"],
                "acc":       p["acc"],
                "pos":       p["pos"],
                "neg":       p["neg"],
                "canonical": int(p["label"] == _CANONICAL_VARIANT.get(group)),
                "recommended": int(p["label"] == _RECOMMENDED_VARIANT.get(group)),
            })
    with out_tsv.open("w", newline="") as fh:
        w = csv.DictWriter(
            fh,
            fieldnames=["group", "label", "size", "acc", "pos", "neg",
                        "canonical", "recommended"],
            delimiter="\t",
        )
        w.writeheader()
        w.writerows(rows)


def make_db_tradeoff_plot(out_dir: Path) -> None:
    """Cutoff-strictness trade-off as five per-source subplots.

    One subplot per surface DB (consensus skipped — it isn't a per-source
    cutoff knob). X-axis is the universe size that filter would admit
    (log scale, cost of looser cutoffs); Y-axis is benchmark accuracy.

    Markers encode the decision status:
      * Circle ('o') — alternative cutoff option, not currently used.
      * Diamond ('D') — the canonical baseline as currently configured
        in the merge loaders. Cross-checked against
        ``candidate_universe.tsv`` flag counts.
      * Star ('*') — recommended cutoff after the trade-off audit, IF
        different from canonical. Annotated on UniProt and CSPA only.
    """
    setup_plotting_style(style="whitegrid", context="notebook", font_scale=1.0)
    # Score on ALL 147 benchmark proteins (include the 6 that aren't
    # in candidate_universe) so the denominator matches the by-class
    # final plot. Stub rows default to flag="0"; raw-source injection
    # can still rescue them via _uniprot_tm_or_signal_or_surface,
    # _hpa_pm_raw, etc.
    rows, bench_symbols = _benchmark_with_universe_join(include_outside_universe=True)
    _inject_raw_source_flags(rows, bench_symbols)

    sizes = _universe_size_per_variant()
    print("Canonical baseline sanity check (raw recompute vs universe flags):")
    _assert_canonical_sizes_match_universe(sizes)

    # Compute accuracy per variant.
    points_by_group: dict[str, list[dict]] = defaultdict(list)
    for name, fn, group in DB_VARIANTS:
        if group == "consensus":
            continue   # consensus isn't a per-source cutoff knob
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
        points_by_group[group].append({
            "label": name,
            "size": sizes.get(name, 0),
            "acc": n_correct / max(n_scored, 1),
            "pos": n_pos_correct / max(n_pos_total, 1),
            "neg": n_neg_correct / max(n_neg_total, 1),
        })

    # NOTE: db_cutoff_tradeoff_points.tsv is a COMMITTED canonical artifact (the
    # gist + the published figure read it). Rendering must NOT rewrite it — the
    # in-render recompute can differ from the committed points and would silently
    # overwrite them (same trap class as db_optimized_cutoffs.tsv). The plot below
    # renders from points_by_group in memory; regenerate the committed TSV
    # deliberately via _dump_db_cutoff_tradeoff_points, never as a render side effect.

    group_order = ["UniProt", "GO", "HPA", "SURFY", "CSPA"]
    fig, axes = plt.subplots(2, 3, figsize=(14, 8.5), sharey=True)
    axes = axes.flatten()

    # Within-subplot label-side preferences: index in size-sorted order
    # → (ha, dx_pts, dy_pts). Tweaked per source so labels of nearby
    # points fan out instead of stacking.
    LABEL_LAYOUT = {
        "UniProt": [
            ("left",  10, 0),    # strict-4 (far left, label right)
            ("right", -10, -28), # canonical (cluster; label below-left)
            ("left",  12, 18),   # TM+signal (cluster; label above-right)
            ("left",  12, -22),  # permissive (cluster; label below-right)
        ],
        "GO": [
            ("right", -10, 18),  # exp+curated → label up-left
            ("center", 0, -28),  # canonical → label below-center
            ("left",  10, 18),   # + IEA → label up-right
        ],
        "HPA": [
            ("left",  10, 0),    # Enhanced (far left)
            ("right", -10, 18),  # canonical
            ("left",  10, -22),  # + Uncertain
        ],
        "SURFY": [
            ("left",  10, 0),    # >0.9 (far left)
            ("center", 0, -28),  # >0.7
            ("right", -10, 22),  # >0.5 (near canonical)
            ("left",  12, -22),  # canonical
        ],
        "CSPA": [
            ("center", 0, 22),   # HC-only
            ("center", 0, -28),  # canonical
            ("left",  12, 0),    # + unspecific
        ],
    }

    for gi, group in enumerate(group_order):
        ax = axes[gi]
        pts = sorted(points_by_group[group], key=lambda p: p["size"])
        palette = _VARIANT_GROUP_PALETTE.get(group, ["#666666"])

        # Strictness-ladder line.
        ax.plot([p["size"] for p in pts], [p["acc"] * 100 for p in pts],
                color=palette[0], linewidth=1.6, alpha=0.5, zorder=2)

        canonical_name = _CANONICAL_VARIANT.get(group)
        recommended_name = _RECOMMENDED_VARIANT.get(group)
        layout = LABEL_LAYOUT.get(group, [("center", 0, 18)] * len(pts))

        for idx, p in enumerate(pts):
            color = palette[min(idx, len(palette) - 1)]
            is_canonical = (p["label"] == canonical_name)
            is_recommended = (p["label"] == recommended_name)
            if is_recommended:
                marker, msize, edge = "*", 420, "#1c4d2e"
            elif is_canonical:
                marker, msize, edge = "D", 180, "#222222"
            else:
                marker, msize, edge = "o", 110, "white"
            ax.scatter(p["size"], p["acc"] * 100,
                       marker=marker, s=msize, color=color,
                       edgecolor=edge, linewidth=1.6, zorder=4)

            short = _VARIANT_SHORT_LABEL.get(p["label"], p["label"])
            ha, dx, dy = layout[min(idx, len(layout) - 1)]
            ax.annotate(
                f"{short}\nn={p['size']:,} • +{p['pos']*100:.0f}/-{p['neg']*100:.0f}",
                xy=(p["size"], p["acc"] * 100),
                xytext=(dx, dy), textcoords="offset points",
                ha=ha, va="center",
                fontsize=8, color=COLORS["dark"],
                bbox={"boxstyle": "round,pad=0.3", "fc": "white",
                      "ec": color, "lw": 0.7, "alpha": 0.94},
            )

        ax.set_xscale("log")
        # ax.set_title is suppressed by the project no-titles policy
        # (see audit/_plotting_config.setup_plotting_style); use an
        # in-axes text annotation instead.
        ax.text(
            0.02, 0.97, group,
            transform=ax.transAxes, ha="left", va="top",
            fontsize=14, fontweight="bold", color=palette[0],
        )
        ax.set_ylim(25, 102)
        # Per-source X span: extend slightly past data range so labels
        # don't fall off the panel edges.
        xs = [p["size"] for p in pts]
        x_lo = max(40, min(xs) / 1.8)
        x_hi = max(xs) * 1.8
        ax.set_xlim(x_lo, x_hi)
        ax.grid(True, which="major", alpha=0.25)
        sns.despine(ax=ax, top=True, right=True)

    # Shared axis labels via the sixth (empty) cell — also hosts a
    # marker-legend so the diamond/star meanings are obvious.
    legend_ax = axes[5]
    legend_ax.axis("off")
    legend_handles = [
        plt.Line2D([], [], marker="o", linestyle="", color="#8a8a8a",
                   markersize=10, markeredgecolor="white", markeredgewidth=1.4,
                   label="Alternative cutoff (not used)"),
        plt.Line2D([], [], marker="D", linestyle="", color="#8a8a8a",
                   markersize=11, markeredgecolor="#222222", markeredgewidth=1.4,
                   label="Canonical (current merge rule)"),
        plt.Line2D([], [], marker="*", linestyle="", color="#8a8a8a",
                   markersize=18, markeredgecolor="#1c4d2e", markeredgewidth=1.4,
                   label="Recommended after trade-off audit"),
    ]
    legend_ax.legend(handles=legend_handles, loc="center", fontsize=11,
                     frameon=True, framealpha=0.95, title="Marker shape",
                     title_fontsize=12)
    legend_ax.text(
        0.5, 0.05,
        "Annotation per point: variant • universe size • +pos%/-neg% recall.\n"
        "Per-source missing rule: UniProt/GO/SURFY/CSPA absence → predict 'no'; "
        "HPA absence → abstain.",
        transform=legend_ax.transAxes, ha="center", va="bottom",
        fontsize=9, color=COLORS["neutral"],
    )

    # Shared axis labels — use the figure-level supxlabel/supylabel.
    fig.supxlabel("Universe size — proteins this filter would admit "
                  "(log scale; lower = stricter)", fontsize=11, y=0.02)
    fig.supylabel("Accuracy on 147-gene benchmark (%)", fontsize=11, x=0.005)
    # No fig-level title (per project no-titles plotting policy).
    plt.tight_layout(rect=[0.015, 0.03, 1, 0.985])
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
        # Side-effect: dump the optimized accession sets so the figures/ gist
        # for db_correctness_by_class can apply the same cutoffs without
        # re-loading the raw UniProt + CSPA dumps.
        _dump_optimized_db_accs()
        make_by_class_plot(out_dir)  # db_correctness_by_class — OPTIMIZED (published)
    finally:
        _USE_OPTIMIZED_CUTOFFS = False
    make_by_class_plot(out_dir, filename="db_correctness_by_class_native_cutoffs")

    # db_correctness_overall (Supp Fig 1) is now its own canonical generator,
    # scripts/db_correctness_overall.py — it reads the figure TSV so its model
    # list comes from the DATA, not a hardcode. The old make_overall_plot path
    # here shipped empty bars when the data moved from opus-4-7 to opus-4-8;
    # that figure is no longer rendered from this monolith.
    make_cost_vs_accuracy_plot(out_dir)
    make_db_variants_plot(out_dir)
    make_db_tradeoff_plot(out_dir)


if __name__ == "__main__":
    main()
