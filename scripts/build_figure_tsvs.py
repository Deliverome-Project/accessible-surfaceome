"""Build per-figure consolidated TSVs from canonical sources.

Each published gist (``data/analysis/figures/gist_map.json``) gets
ONE bundled TSV that carries everything its mirror script needs.
This is the invariant the gist single-TSV pattern enforces — see
``tests/test_gist_single_tsv.py``.

Sources read (idempotent, no LLM, no D1):
  • ``data/eval/triage_benchmark_v1.tsv`` — 147-gene SurfaceBench
  • ``data/processed/triage_bench/mainbench_canonical_v2.tsv`` — per-cell preds + truth + 5 per-DB flags
  • ``data/processed/triage_bench/mainbench_replicates_v2.tsv`` — per-rep is_match + truth
  • ``data/processed/triage_bench/db_optimized_cutoffs.tsv`` — uniprot_optimized / cspa_optimized per UniProt
  • ``data/processed/catalog/whole_proteome_catalog.tsv`` — genome-wide DB-vote table

Outputs (one per non-compliant figure today, written to
``data/processed/figures/<slug>.tsv``):
  • ``benchmark_cost_vs_accuracy.tsv``
  • ``db_correctness_by_class.tsv``
  • ``db_correctness_overall.tsv``
  • ``db_vs_sonnet_whole_proteome.tsv``
  • ``ensemble_vs_best_db_vs_sonnet.tsv``
  • ``deep_dive_final_categories.tsv`` — MOCK placeholder

The remaining 4 gists already use a single canonical TSV as-is
(``db_cutoff_tradeoff``, ``db_overlap_venn``, ``paywall_bot_block_compare``,
``topology_coverage_by_source``, ``zero_db_rescues_by_triage``) — those
keep their existing TSV; no per-figure copy is written for them.

Run::

    uv run python scripts/build_figure_tsvs.py [--out data/processed/figures]
"""
from __future__ import annotations

import argparse
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUT = ROOT / "data/processed/figures"

BENCH_TSV       = ROOT / "data/eval/triage_benchmark_v1.tsv"
PREDS_TSV       = ROOT / "data/processed/triage_bench/mainbench_canonical_v2.tsv"
REPS_TSV        = ROOT / "data/processed/triage_bench/mainbench_replicates_v2.tsv"
OPT_CUTOFFS_TSV = ROOT / "data/processed/triage_bench/db_optimized_cutoffs.tsv"
CATALOG_TSV     = ROOT / "data/processed/catalog/whole_proteome_catalog.tsv"
FEATURES_TSV    = ROOT / "data/analysis/db_vs_sonnet_inclusion/per_protein_features.tsv"
POS_LONG_TSV    = ROOT / "data/processed/positive_controls/positive_control_long.tsv"
# Per-gene deep-dive record facets, exported from public D1 by
# scripts/export_deep_dive_figure_source.py. Re-run that after a sweep batch to
# refresh the deep-dive figures. Present only once the sweep has published rows;
# the deep-dive builders below no-op gracefully if it's absent (partial checkout).
DEEP_DIVE_TSV   = ROOT / "data/processed/deep_dive/deep_dive_records.tsv"
# Companion triage-verdict source (one row per gene: triage_verdict +
# triage_reason from the genome-wide Sonnet triage run), also exported by
# scripts/export_deep_dive_figure_source.py. The S12 figure joins it against
# the deep-dive export; kept separate so the deep-dive export stays purely
# deep-dive-side.
TRIAGE_VERDICTS_TSV = ROOT / "data/processed/deep_dive/triage_verdicts.tsv"


def _load_sources() -> dict[str, pd.DataFrame]:
    src = {
        "bench":    pd.read_csv(BENCH_TSV, sep="\t"),
        "preds":    pd.read_csv(PREDS_TSV, sep="\t"),
        "reps":     pd.read_csv(REPS_TSV, sep="\t"),
        "opt":      pd.read_csv(OPT_CUTOFFS_TSV, sep="\t"),
        "catalog":  pd.read_csv(CATALOG_TSV, sep="\t"),
        "features": pd.read_csv(FEATURES_TSV, sep="\t"),
    }
    if DEEP_DIVE_TSV.is_file():
        src["deep_dive"] = pd.read_csv(DEEP_DIVE_TSV, sep="\t")
    if TRIAGE_VERDICTS_TSV.is_file():
        src["triage_verdicts"] = pd.read_csv(TRIAGE_VERDICTS_TSV, sep="\t")
    return src


def _optimized_membership(df: pd.DataFrame, opt: pd.DataFrame, acc_col: str) -> pd.DataFrame:
    """Return a copy of ``df`` with optimized-cutoff DB membership +
    ``n_sources_optimized`` (the 5-DB vote under the SurfaceBench-tuned
    cutoffs: UniProt and CSPA use their recalibrated rule; GO CC, HPA,
    and SURFY use their unchanged ``*_surface_flag``). This is the
    downstream-canonical DB membership the accuracy figures already use;
    F3 (zero-DB rescues) and S9 (per-source coverage) join it so they
    stop using the pre-recalibration initial flags."""
    out = df.copy()
    uniprot_opt = set(opt.loc[opt["uniprot_optimized"] == 1, "accession"].astype(str))
    cspa_opt    = set(opt.loc[opt["cspa_optimized"]    == 1, "accession"].astype(str))
    acc = out[acc_col].astype(str)
    out["uniprot_optimized"] = acc.isin(uniprot_opt).astype(int)
    out["cspa_optimized"]    = acc.isin(cspa_opt).astype(int)
    return out


def _join_truth_into_preds(preds: pd.DataFrame, bench: pd.DataFrame) -> pd.DataFrame:
    """Denormalize ground_truth_verdict onto preds. The canonical
    mainbench_canonical_v2 already has this per CLAUDE.md — we
    no-op when the column is already there."""
    out = preds.copy()
    if "ground_truth_verdict" not in out.columns:
        truth = bench.set_index("gene_symbol")["ground_truth_verdict"]
        out["ground_truth_verdict"] = out["gene_symbol"].map(truth)
    return out


def _join_truth_into_reps(reps: pd.DataFrame, bench: pd.DataFrame) -> pd.DataFrame:
    out = reps.copy()
    if "ground_truth_verdict" not in out.columns:
        truth = bench.set_index("gene_symbol")["ground_truth_verdict"]
        out["ground_truth_verdict"] = out["gene_symbol"].map(truth)
    # has_deep_dive rides in from mainbench_replicates_v2 but is not a
    # reanalysis dimension for any benchmark accuracy/cost figure (those are
    # about triage calls, not deep-dive coverage), and no figure script reads
    # it — drop it so the four bench figure TSVs stay lean.
    out = out.drop(columns=["has_deep_dive"], errors="ignore")
    return out


def _join_optimized_cutoffs(catalog: pd.DataFrame, opt: pd.DataFrame) -> pd.DataFrame:
    """Denormalize the two ``*_optimized`` flags from db_optimized_cutoffs
    onto each candidate row, keyed on uniprot_acc/accession. Genes
    outside the optimized-cutoff set get 0 for both flags."""
    out = catalog.copy()
    uniprot_opt = set(opt.loc[opt["uniprot_optimized"] == 1, "accession"].astype(str))
    cspa_opt    = set(opt.loc[opt["cspa_optimized"]    == 1, "accession"].astype(str))
    out["uniprot_optimized"] = out["uniprot_acc"].astype(str).isin(uniprot_opt).astype(int)
    out["cspa_optimized"]    = out["uniprot_acc"].astype(str).isin(cspa_opt).astype(int)
    # Drop internal-only columns that leaked through from the catalog —
    # `universe_version` is provenance bookkeeping, not figure-input data.
    out = out.drop(columns=["universe_version"], errors="ignore")
    return out


# ─────────────────────────── per-figure builders ──────────────────────


def build_cost_vs_accuracy(src: dict[str, pd.DataFrame]) -> pd.DataFrame:
    """One row per (gene, model, prompt_variant, replicate). Carries
    tokens (per-rep, may be aggregated across reps depending on upstream)
    + ground_truth_verdict + is_match. The figure plots cost vs accuracy
    per (model, variant) cell — accuracy = mean(is_match), cost =
    aggregate(tokens). All columns it needs live on mainbench_replicates_v2
    once truth is denormalized in."""
    return _join_truth_into_reps(src["reps"], src["bench"])


def build_db_correctness_by_class(src: dict[str, pd.DataFrame]) -> pd.DataFrame:
    """One row per (gene, model, prompt_variant, replicate) on the bench.
    Carries truth + 5 per-DB flags + uniprot/cspa optimized-cutoff flags +
    is_match. The figure: per-bucket accuracy of Sonnet/ncbi vs the 5 DBs.

    We start from mainbench_replicates_v2 (per-rep), join in optimized
    cutoffs by uniprot_acc."""
    df = _join_truth_into_reps(src["reps"], src["bench"])
    uniprot_opt = set(src["opt"].loc[src["opt"]["uniprot_optimized"] == 1, "accession"].astype(str))
    cspa_opt    = set(src["opt"].loc[src["opt"]["cspa_optimized"]    == 1, "accession"].astype(str))
    df["uniprot_optimized"] = df["uniprot_acc"].astype(str).isin(uniprot_opt).astype(int)
    df["cspa_optimized"]    = df["uniprot_acc"].astype(str).isin(cspa_opt).astype(int)
    return df


def build_db_correctness_overall(src: dict[str, pd.DataFrame]) -> pd.DataFrame:
    """Same shape as by_class but the figure only needs the overall
    accuracy, no per-bucket breakdown. Same TSV works."""
    return _join_truth_into_reps(src["reps"], src["bench"])


def build_db_vs_sonnet_whole_proteome(src: dict[str, pd.DataFrame]) -> pd.DataFrame:
    """Genome-wide DB-vote + Sonnet-vote table. The catalog already has
    the per-DB flags + sonnet_verdict denormalized; we just join in the
    two optimized-cutoff columns."""
    return _join_optimized_cutoffs(src["catalog"], src["opt"])


def build_zero_db_rescues(src: dict[str, pd.DataFrame]) -> pd.DataFrame:
    """Figure 3 — zero-DB rescues, defined under the OPTIMIZED cutoffs
    (consistent with the accuracy figures). Per genome-wide gene: the
    Sonnet verdict + reason, the 5 per-DB flags with UniProt/CSPA on
    their recalibrated rule, and ``n_sources_optimized`` so the figure
    selects the zero-DB slice as ``n_sources_optimized == 0`` rather
    than the pre-recalibration ``n_sources_surface == 0``."""
    df = _optimized_membership(src["catalog"], src["opt"], "uniprot_acc")
    # n_sources_optimized = the 5-DB vote under optimized cutoffs:
    # UniProt + CSPA recalibrated, GO/HPA/SURFY unchanged surface_flag.
    df["n_sources_optimized"] = (
        df["uniprot_optimized"].fillna(0).astype(int)
        + df["cspa_optimized"].fillna(0).astype(int)
        + df["go_surface_flag"].fillna(0).astype(int)
        + df["hpa_surface_flag"].fillna(0).astype(int)
        + df["surfy_surface_flag"].fillna(0).astype(int)
    )
    return df.drop(columns=["universe_version"], errors="ignore")


def build_topology_coverage_by_source(src: dict[str, pd.DataFrame]) -> pd.DataFrame:
    """Supp S9 — per-source topology coverage under the OPTIMIZED cutoffs.
    Starts from the per-protein-features table (topology classes + the
    initial ``src_*`` source flags) and joins UniProt/CSPA optimized
    membership so the figure renders UniProt and CSPA at their
    recalibrated cutoffs (GO/HPA/SURFY/Sonnet unchanged). Also carries
    ``n_sources_optimized`` so the Sonnet-only (zero-DB) subset is
    defined against the optimized DB vote, matching Figure 3."""
    feat = _optimized_membership(src["features"], src["opt"], "uniprot_accession")
    # GO/HPA/SURFY keep their initial src flags (not recalibrated).
    feat["n_sources_optimized"] = (
        feat["uniprot_optimized"].fillna(0).astype(int)
        + feat["cspa_optimized"].fillna(0).astype(int)
        + feat["src_go"].fillna(0).astype(int)
        + feat["src_hpa"].fillna(0).astype(int)
        + feat["src_surfy"].fillna(0).astype(int)
    )
    return feat


def build_bench_topology_vs_universe(src: dict[str, pd.DataFrame]) -> pd.DataFrame:
    """bench_topology_vs_universe — topology composition of the SurfaceBench
    benchmark vs the Sonnet 2-tier yes/contextual universe. The TSV is the UNION
    of the two cohorts with ``in_universe`` + ``is_bench`` flags so the figure
    plots each cohort's per-class topology:
      • universe (in_universe=True) — sonnet/pubmed yes/contextual (~4,426).
      • bench    (is_bench=True)    — the benchmark's GROUND-TRUTH yes/contextual
        genes (99), keyed by ``ground_truth_verdict`` — NOT conditioned on
        Sonnet's call. The 3 ground-truth-yc genes Sonnet miscalled (C3, SRC,
        TGOLN2) sit outside the universe but stay in the bench cohort, so they
        ride the union. (The old "bench acc in universe" tag both dropped these
        3 and let Sonnet false-positives on ground-truth-no genes leak in.)
    NOT cutoff-dependent — scores no DB membership."""
    yc = {"yes", "contextual"}
    feat = src["features"]
    in_universe = feat["sonnet_verdict"].isin(yc) | feat["pubmed_verdict"].isin(yc)
    bench = src["bench"]
    gt_col = "ground_truth_verdict" if "ground_truth_verdict" in bench.columns else "verdict"
    bench_yc = set(
        bench.loc[
            bench[gt_col].astype(str).str.strip().str.lower().isin(yc), "uniprot_acc"
        ].dropna().astype(str)
    )
    is_bench = feat["uniprot_accession"].astype(str).isin(bench_yc)
    mask = in_universe | is_bench
    keep = feat[mask]
    feature_cols = [
        "topo_gpi_anchored", "topo_gpcr_7tm", "topo_multi_pass_tm",
        "topo_single_pass_tm", "topo_signal_only_secreted",
        "topo_inner_leaflet_lipidated", "topo_no_tm_no_signal",
        "up_has_glyc", "deeptm_TM_NO_SP",
    ]

    def _int01(col: pd.Series) -> pd.Series:
        return col.map(lambda v: 1 if str(v).strip() in ("1", "1.0") else 0)

    out = pd.DataFrame({
        "gene_symbol": keep["gene_symbol"].to_numpy(),
        "uniprot_acc": keep["uniprot_accession"].to_numpy(),
        "in_universe": in_universe[mask].to_numpy(),
        "is_bench": is_bench[mask].to_numpy(),
    })
    for col in feature_cols:
        out[col] = _int01(keep[col]).to_numpy()
    return out.sort_values("gene_symbol", kind="stable", ignore_index=True)


def build_ensemble(src: dict[str, pd.DataFrame]) -> pd.DataFrame:
    """Bench + 5-DB flags + Sonnet ncbi vote + per-rep is_match. Same
    shape as db_correctness_by_class — one consolidated TSV serves both
    figures conceptually but each gist gets its own copy for the
    single-TSV-per-gist invariant."""
    return build_db_correctness_by_class(src)


# Deep-dive surface-call bucket predicates — PORTED VERBATIM from
# viewer/lib/catalog-presets.ts (passesCanonical / passesLikely / passesInduced /
# passesCellTypeRestricted) so the figure's buckets ARE the catalog presets.
# The buckets NEST: `likely` (passesLikely) is the umbrella; `canonical`,
# `cell_state` (induced, by trigger), `cell_type_restricted`, and the
# `likely_other` residual EXCLUSIVELY partition it; `no` = !passesLikely.
# KEEP IN SYNC with the .ts — guarded by tests/test_deep_dive_buckets_match_frontend.py.
_DD_INDUCTION_NON_NONE = {"oncogenic", "immune", "stress_hypoxia", "cell_death", "infection"}


def _dd_v(r: "pd.Series", k: str):
    x = r.get(k)
    return None if pd.isna(x) else x


def _dd_passes_canonical(r: "pd.Series") -> bool:
    return (
        _dd_v(r, "evidence_grade") in ("direct_multi_method", "direct_single_method")
        and _dd_v(r, "confidence") in ("high", "moderate")
        and _dd_v(r, "surface_specificity") in ("surface_dominant", "mixed")
        and _dd_v(r, "state_dependence") in ("low", "moderate", "unclear")
        and _dd_v(r, "surface_accessibility") in ("high", "moderate")
        and _dd_v(r, "evidence_density") in ("high", "moderate")
    )


def _dd_passes_likely(r: "pd.Series") -> bool:
    return (
        _dd_v(r, "evidence_grade")
        in ("direct_multi_method", "direct_single_method", "supportive_but_indirect")
        and _dd_v(r, "surface_specificity")
        in ("surface_dominant", "mixed", "mostly_intracellular")
        and _dd_v(r, "surface_accessibility") in ("high", "moderate", "low")
    )


def _dd_passes_induced(r: "pd.Series") -> bool:
    if not _dd_passes_likely(r):
        return False
    if _dd_v(r, "state_dependence") not in (None, "moderate", "high", "unclear"):
        return False
    if _dd_v(r, "surface_call_reason") in ("cell_state_induced", "lysosomal_exocytosis"):
        return True
    return _dd_v(r, "induction_trigger") in _DD_INDUCTION_NON_NONE


def _dd_passes_cell_type_restricted(r: "pd.Series") -> bool:
    if not _dd_passes_likely(r):
        return False
    if _dd_v(r, "state_dependence") not in ("moderate", "high"):
        return False
    return _dd_v(r, "surface_call_reason") == "tissue_restricted_surface"


def _dd_assign_bucket(r: "pd.Series") -> tuple[str, str]:
    """(category, subcategory). FIVE top-level tiers, a confidence spectrum —
    `canonical` (strict) > `likely` > `low` > `uncertain` > `no`.

    `canonical`/`likely` are the frontend presets (canonical = passesCanonical;
    likely = passesLikely & !canonical, fanned out into cell_type_restricted +
    cell_state-by-trigger + the likely residual for Panel b). Everything that
    fails passesLikely is split by the deep-dive's tentative `surface_accessibility`
    call rather than lumped into one "no": `no` (accessibility=no, leaned
    negative), `uncertain` (accessibility=uncertain), and `low` (accessibility
    low or moderate but below the evidence bar — "maybe surface, weak evidence").
    NB nearly all below-likely genes carry weak/conflicting evidence — partly the
    pretrim-cap recall bug — so low/uncertain/no are tentative leans on thin
    literature, not settled calls."""
    if not _dd_passes_likely(r):
        acc = _dd_v(r, "surface_accessibility")
        if acc == "uncertain":
            return ("uncertain", "all")
        if acc in ("low", "moderate"):
            return ("low", "all")
        return ("no", "all")  # accessibility == 'no' (the leaned-negative calls)
    if _dd_passes_canonical(r):
        return ("canonical", "all")
    if _dd_passes_cell_type_restricted(r):
        return ("likely", "cell_type_restricted")
    if _dd_passes_induced(r):
        trig = _dd_v(r, "induction_trigger")
        return ("likely", f"cell_state_{trig if trig in _DD_INDUCTION_NON_NONE else 'other'}")
    return ("likely", "likely_other")


# Five top-level deep-dive tiers, best → worst, as the confidence spectrum
# `_dd_assign_bucket` returns for its `category`. Shared ordering so every
# deep-dive figure renders the tiers in the same left-to-right / top-to-bottom
# sequence.
DD_TIER_ORDER = ["canonical", "likely", "low", "uncertain", "no"]


def _dd_tier(r: "pd.Series") -> str:
    """Top-level 5-tier deep-dive verdict (``category`` from
    ``_dd_assign_bucket``) for a single record — the per-gene tier every
    deep-dive figure keys on."""
    return _dd_assign_bucket(r)[0]


def build_deep_dive_final_categories(src: dict[str, pd.DataFrame]) -> pd.DataFrame:
    """PER-GENE table behind the final-categories figure — one row per
    deep-dived gene with its tier (``category``) + sub-bucket (``subcategory``),
    so readers can look through WHICH gene lands where, not just the bar totals.
    The figure aggregates these rows into the per-(category, subcategory) counts
    it plots (Panel a = per-category totals, Panel b = the ``likely``
    sub-buckets).

    ``_dd_assign_bucket`` gives (category, subcategory): the five tiers
    (``canonical`` / ``likely`` / ``low`` / ``uncertain`` / ``no``) with
    ``likely`` fanned out into its ``cell_type_restricted`` /
    ``cell_state_<trigger>`` / ``likely_other`` sub-buckets. Carries stable IDs
    (hgnc_id / ensembl_gene / ncbi_gene_id from the catalog, uniprot_acc from the
    record) per the figure-input-TSV conventions, plus the
    ``surface_call_reason`` + ``induction_trigger`` context that drove the call.

    Columns: gene_symbol, hgnc_id, uniprot_acc, ensembl_gene, ncbi_gene_id,
    category, subcategory, surface_call_reason, induction_trigger.

    PRELIMINARY — only the genes swept so far (pre-QA-fix). The below-likely
    tiers are inflated by ``evidence_grade='weak'`` records, partly the
    pretrim-cap recall bug deleting foundational papers; re-run after the sweep
    + QA fixes for the final figure."""
    cols = ["gene_symbol", "hgnc_id", "uniprot_acc", "ensembl_gene",
            "ncbi_gene_id", "category", "subcategory", "surface_call_reason",
            "induction_trigger"]
    dd = src.get("deep_dive")
    if dd is None or dd.empty:
        return _empty_deep_dive_frame(cols)
    buckets = [_dd_assign_bucket(r) for _, r in dd.iterrows()]
    out = pd.DataFrame({
        "gene_symbol": dd["gene_symbol"].astype(str),
        "uniprot_acc": dd["uniprot_acc"].astype(str),
        "category": [b[0] for b in buckets],
        "subcategory": [b[1] for b in buckets],
        "surface_call_reason": dd["surface_call_reason"].astype(str),
        "induction_trigger": dd["induction_trigger"].astype(str),
    })
    # Stable IDs from the catalog (candidate_universe), keyed by symbol.
    cat = src.get("catalog")
    cat_by_gene = (
        cat.drop_duplicates("hgnc_symbol").set_index("hgnc_symbol")
        if cat is not None and "hgnc_symbol" in cat.columns else None
    )
    for idc in ["hgnc_id", "ensembl_gene", "ncbi_gene_id"]:
        out[idc] = (out["gene_symbol"].map(cat_by_gene[idc]).astype("string")
                    if cat_by_gene is not None and idc in cat_by_gene.columns
                    else pd.Series([pd.NA] * len(out), dtype="string"))
    return (
        out[cols]
        .sort_values(["category", "subcategory", "gene_symbol"], kind="stable")
        .reset_index(drop=True)
    )


def _empty_deep_dive_frame(columns: list[str]) -> pd.DataFrame:
    """Correctly-typed empty frame for the deep-dive figures when the export
    isn't in this checkout (partial hydration) — keeps the pipeline
    reproducible without inventing rows."""
    return pd.DataFrame(columns=columns)


def build_evidence_corpus_vs_selected(src: dict[str, pd.DataFrame]) -> pd.DataFrame:
    """Per-gene discovery→selection funnel: the size of the discovery corpus
    (``n_papers_found``) vs the papers the agent read full-text
    (``n_papers_selected``), tagged with the agent's ``evidence_grade`` and the
    deep-dive tier.

    One row per published deep-dive record with real gene symbols and real
    counts (was a MOCK lognormal draw before the sweep produced records).
    ``n_papers_found`` landed in schema 2.14.0 so a handful of legacy records
    carry a null there — those rows are dropped from the funnel (both axes must
    be present to plot a point). Columns:
    ``gene_symbol, uniprot_acc, papers_found, papers_selected, evidence_grade,
    tier``.

    PRELIMINARY — ~1,197 of ~5,128 swept, pre-QA-fix.
    """
    cols = ["gene_symbol", "uniprot_acc", "papers_found", "papers_selected",
            "evidence_grade", "tier"]
    dd = src.get("deep_dive")
    if dd is None or dd.empty:
        return _empty_deep_dive_frame(cols)
    out = pd.DataFrame({
        "gene_symbol": dd["gene_symbol"].astype(str),
        "uniprot_acc": dd["uniprot_acc"].astype(str),
        "papers_found": pd.to_numeric(dd["n_papers_found"], errors="coerce"),
        "papers_selected": pd.to_numeric(dd["n_papers_selected"], errors="coerce"),
        "evidence_grade": dd["evidence_grade"].astype(str),
        "tier": [_dd_tier(r) for _, r in dd.iterrows()],
    })
    # A point needs both axes; drop records missing either count (legacy
    # pre-2.14.0 records have no n_papers_found).
    out = out.dropna(subset=["papers_found", "papers_selected"])
    out["papers_found"] = out["papers_found"].astype(int)
    out["papers_selected"] = out["papers_selected"].astype(int)
    return out.sort_values("gene_symbol", kind="stable").reset_index(drop=True)


def build_deep_dive_record_richness(src: dict[str, pd.DataFrame]) -> pd.DataFrame:
    """Per-gene record richness across the five axes the figure draws, split by
    the deep-dive tier. One row per published deep-dive record with real values
    (was MOCK before the sweep). Columns:
    ``gene_symbol, tier, surface_verdict_bucket, papers_found, papers_selected,
    papers_with_ec, n_filters_evidence, n_det_features, evidence_grade``.

    Axes:
      • ``papers_found``       — discovery-corpus size (``n_papers_found``); now
        real (median ~240) — was fully synthesised while the field was unstored.
      • ``papers_selected``    — unique papers read full-text (``n_papers_selected``).
      • ``papers_with_ec``     — ``primary_evidence_count`` (the primary-tier,
        surface-method-tagged evidence — the "extracellular evidence" subset).
      • ``n_filters_evidence`` — ``evidence_count`` (populated evidence records).
      • ``n_det_features``     — how many of the 6 deterministic-feature
        categories carry data (topology / AF structure / surface-binding /
        homo-oligomer / orthologs / alt-isoforms), 0–6; real per-gene value
        derived in the export from each record's ``deterministic_features``.

    ``surface_verdict_bucket`` (``no`` vs ``surface_yes``) is kept for
    back-compat; ``tier`` (the finer 5-tier call) is what the figure now facets
    every panel by (a/b: canonical/likely/low/no; c/d/e: canonical/likely/low).

    PRELIMINARY — pre-QA-fix; counts grow as the sweep progresses.
    """
    cols = ["gene_symbol", "tier", "surface_verdict_bucket", "papers_found",
            "papers_selected", "papers_with_ec", "n_filters_evidence",
            "n_det_features", "evidence_grade"]
    dd = src.get("deep_dive")
    if dd is None or dd.empty:
        return _empty_deep_dive_frame(cols)
    tiers = [_dd_tier(r) for _, r in dd.iterrows()]
    acc = dd["surface_accessibility"].astype(str)
    # surface_yes-even-weak = any accessibility except 'no'.
    bucket = acc.map(lambda v: "no" if v == "no" else "surface_yes")
    out = pd.DataFrame({
        "gene_symbol": dd["gene_symbol"].astype(str),
        "tier": tiers,
        "surface_verdict_bucket": bucket,
        "papers_found": pd.to_numeric(dd["n_papers_found"], errors="coerce"),
        "papers_selected": pd.to_numeric(dd["n_papers_selected"], errors="coerce"),
        "papers_with_ec": pd.to_numeric(dd["n_papers_with_ec"], errors="coerce")
        if "n_papers_with_ec" in dd.columns
        else pd.to_numeric(dd["primary_evidence_count"], errors="coerce"),
        "n_filters_evidence": pd.to_numeric(dd["evidence_count"], errors="coerce"),
        "n_det_features": pd.to_numeric(
            dd.get("n_det_features"), errors="coerce").astype("Int64")
        if "n_det_features" in dd.columns
        else pd.Series([pd.NA] * len(dd), dtype="Int64"),
        "evidence_grade": dd["evidence_grade"].astype(str),
    })
    return out.sort_values(["surface_verdict_bucket", "gene_symbol"],
                           kind="stable").reset_index(drop=True)


def build_triage_vs_deep_dive_reason(src: dict[str, pd.DataFrame]) -> pd.DataFrame:
    """Per-gene comparison of the TRIAGE-stage call against the DEEP-DIVE call,
    for every gene with both. Two figure panels read this one TSV:

      • Panel a (verdict flow): ``triage_verdict`` (yes/contextual/no from the
        genome-wide Sonnet triage run) → ``deep_dive_tier`` (the 5-tier
        ``_dd_assign_bucket`` call).
      • Panel b (reason confusion): ``triage_reason`` × ``deep_dive_reason``
        (``surface_call_reason``), both drawn from the shared ``TriageReason``
        enum.
      • Panel c (DB concordance): per-DB surface membership (UniProt / GO /
        SURFY / CSPA / HPA), so the figure shows what fraction of
        deep-dive-surface genes each database — and the Sonnet triage stage —
        also calls surface. The two RECALIBRATED DBs (UniProt, CSPA) use their
        OPTIMIZED positive-list membership (``uniprot_optimized`` /
        ``cspa_optimized`` from ``db_optimized_cutoffs.tsv``), NOT the native
        ``*_surface_flag`` — figures outside Figure 1 must score the recalibrated
        DBs on the tuned cutoff (test_figures_use_optimized_cutoffs). GO / SURFY
        / HPA were never recalibrated, so their ``*_surface_flag`` is correct.

    The triage verdict/reason come from the committed ``triage_verdicts.tsv``
    companion (D1's ``genome_full_sonnet_ncbi_v2`` run), joined by gene_symbol;
    GO/SURFY/HPA flags from the catalog (candidate_universe), UniProt/CSPA
    optimized membership from ``opt``. Columns: ``gene_symbol, uniprot_acc,
    triage_verdict, triage_reason, deep_dive_reason, deep_dive_tier,
    go_surface_flag, surfy_surface_flag, hpa_surface_flag, uniprot_optimized,
    cspa_optimized``.

    Real data, small n as the sweep progresses; PRELIMINARY, pre-QA-fix.
    """
    cols = ["gene_symbol", "uniprot_acc", "triage_verdict", "triage_reason",
            "deep_dive_reason", "deep_dive_tier"]
    # Panel-c concordance columns. GO/SURFY/HPA were never recalibrated -> use
    # their native *_surface_flag. UniProt/CSPA ARE recalibrated -> use the
    # OPTIMIZED positive-list membership (uniprot_optimized / cspa_optimized);
    # test_figures_use_optimized_cutoffs forbids the native flags outside Fig 1.
    native_flags = ["go_surface_flag", "surfy_surface_flag", "hpa_surface_flag"]
    opt_flags = ["uniprot_optimized", "cspa_optimized"]
    db_flags = native_flags + opt_flags
    dd = src.get("deep_dive")
    tri = src.get("triage_verdicts")
    if dd is None or dd.empty or tri is None or tri.empty:
        return _empty_deep_dive_frame(cols + db_flags)
    tri_by_gene = tri.drop_duplicates("gene_symbol").set_index("gene_symbol")
    out = pd.DataFrame({
        "gene_symbol": dd["gene_symbol"].astype(str),
        "uniprot_acc": dd["uniprot_acc"].astype(str),
        "deep_dive_reason": dd["surface_call_reason"].astype(str),
        "deep_dive_tier": [_dd_tier(r) for _, r in dd.iterrows()],
    })
    out["triage_verdict"] = out["gene_symbol"].map(
        tri_by_gene["triage_verdict"]).astype("object")
    out["triage_reason"] = out["gene_symbol"].map(
        tri_by_gene["triage_reason"]).astype("object")
    # Panel c — per-DB surface concordance: what fraction of deep-dive-surface
    # genes each source also flags (the "agrees more with Sonnet triage or with
    # the databases?" comparison).
    cat = src.get("catalog")
    cat_by_gene = (
        cat.drop_duplicates("hgnc_symbol").set_index("hgnc_symbol")
        if cat is not None and "hgnc_symbol" in cat.columns else None
    )
    # GO/SURFY/HPA native surface flags, joined from the catalog by symbol.
    for c in native_flags:
        if cat_by_gene is not None and c in cat_by_gene.columns:
            out[c] = pd.to_numeric(
                out["gene_symbol"].map(cat_by_gene[c]), errors="coerce"
            ).astype("Int64")
        else:
            out[c] = pd.Series([pd.NA] * len(out), dtype="Int64")
    # UniProt/CSPA OPTIMIZED membership: canonical accession (catalog's
    # uniprot_acc, else the record's) in the `opt` positive list -> 1, else 0.
    opt = src.get("opt")
    acc = (out["gene_symbol"].map(cat_by_gene["uniprot_acc"])
           if cat_by_gene is not None and "uniprot_acc" in cat_by_gene.columns
           else out["uniprot_acc"]).astype(str)
    for col in opt_flags:
        accs = (set(opt.loc[opt[col] == 1, "accession"].astype(str))
                if opt is not None and col in opt.columns else set())
        out[col] = acc.isin(accs).astype("Int64")
    # Keep only genes we could match a triage call for.
    out = out.dropna(subset=["triage_verdict", "triage_reason"])
    out = out[cols + db_flags]
    return out.sort_values("gene_symbol", kind="stable").reset_index(drop=True)


def build_deep_dive_vs_sonnet_benchmark(src: dict[str, pd.DataFrame]) -> pd.DataFrame:
    """New Supp figure — how the DEEP DIVE does on SurfaceBench, for the bench
    genes deep-dived so far (the intersection), vs the Sonnet+NCBI triage on the
    SAME genes. Per-gene SOFT-CREDIT correctness (a contextually-surface protein
    is correct when called surface) for both predictors against the curated
    ground truth. The figure aggregates: overall accuracy + accuracy per
    ground-truth bucket (yes / contextual / no).

    ``deep_dive_surface`` = tier in {canonical, likely, low}; ``sonnet_surface``
    / ``gt_surface`` = verdict in {yes, contextual}. Columns: gene_symbol +
    stable IDs, ground_truth_verdict, sonnet_verdict, deep_dive_tier, gt_surface,
    sonnet_surface, deep_dive_surface, sonnet_correct, deep_dive_correct.

    PRELIMINARY — only the bench genes deep-dived so far (27 of 147); the 'no'
    bucket is tiny. Widens as the sweep covers more bench genes.
    """
    cols = ["gene_symbol", "hgnc_id", "uniprot_acc", "ensembl_gene",
            "ncbi_gene_id", "ground_truth_verdict", "sonnet_verdict",
            "deep_dive_tier", "gt_surface", "sonnet_surface",
            "deep_dive_surface", "sonnet_correct", "deep_dive_correct",
            "sonnet_correct_r1", "sonnet_correct_r2", "sonnet_correct_r3"]
    bench = src.get("bench")
    dd = src.get("deep_dive")
    if bench is None or dd is None or dd.empty:
        return _empty_deep_dive_frame(cols)
    yc = {"yes", "contextual"}
    dd_u = dd.drop_duplicates("gene_symbol").copy()
    dd_u["gene_symbol"] = dd_u["gene_symbol"].astype(str)
    dd_by_gene = dd_u.set_index("gene_symbol")
    dd_genes = set(dd_by_gene.index)
    # Per-replicate Sonnet+NCBI predictions (mainbench, 3 reps/gene) so the
    # figure shows one accuracy dot per replicate + SEM across them, not a
    # meaningless 0/1 dot per gene.
    rep_by_gene: dict[str, dict[int, str]] = {}
    rep_path = ROOT / "data/processed/deep_dive/benchmark_sonnet_replicates.tsv"
    if rep_path.is_file():
        reps = pd.read_csv(rep_path, sep="\t")
        for _, rr in reps.iterrows():
            rep_by_gene.setdefault(str(rr["gene_symbol"]), {})[
                int(rr["replicate"])] = str(rr["predicted_verdict"])
    rows = []
    for _, br in bench.iterrows():
        g = str(br["gene_symbol"])
        if g not in dd_genes:
            continue
        tier = _dd_tier(dd_by_gene.loc[g])
        gt_s = str(br["ground_truth_verdict"]) in yc
        son_s = str(br["sonnet_verdict"]) in yc
        dd_s = tier in ("canonical", "likely", "low")
        reps_g = rep_by_gene.get(g, {})
        rep_correct = {r: (int((reps_g[r] in yc) == gt_s) if r in reps_g else "")
                       for r in (1, 2, 3)}
        rows.append({
            "gene_symbol": g,
            "hgnc_id": br.get("hgnc_id", ""),
            "uniprot_acc": br.get("uniprot_acc", ""),
            "ensembl_gene": br.get("ensembl_gene", ""),
            "ncbi_gene_id": br.get("ncbi_gene_id", ""),
            "ground_truth_verdict": str(br["ground_truth_verdict"]),
            "sonnet_verdict": str(br["sonnet_verdict"]),
            "deep_dive_tier": tier,
            "gt_surface": int(gt_s),
            "sonnet_surface": int(son_s),
            "deep_dive_surface": int(dd_s),
            "sonnet_correct": int(son_s == gt_s),
            "deep_dive_correct": int(dd_s == gt_s),
            "sonnet_correct_r1": rep_correct[1],
            "sonnet_correct_r2": rep_correct[2],
            "sonnet_correct_r3": rep_correct[3],
        })
    return pd.DataFrame(rows, columns=cols).sort_values(
        ["ground_truth_verdict", "gene_symbol"], kind="stable"
    ).reset_index(drop=True)


def build_curator_vs_agent_reason(src: dict[str, pd.DataFrame]) -> pd.DataFrame:
    """Per-gene curator-vs-agent reason comparison. The figure is a
    3-panel composite (panel a: bucket-strict accuracy across 10 model
    variants; panel b: per-reason accuracy across 4 frontier configs;
    panel c: Sonnet/ncbi confusion matrix). Needs all (model, variant)
    predictions, so we start from the per-rep TSV (10 model variants ×
    147 genes × 3 reps + per-cell preds collapsed across reps for
    panel c).

    Per-rep TSV already has ground_truth_reason + ground_truth_verdict
    denormalized; predicted_reason comes from the per-cell collapse
    when we keep one row per (gene, model, variant, replicate).
    Slim the columns we don't need (tokens, cost, latency) to keep
    the TSV under the 5 MB practical cap."""
    keep = [
        "gene_symbol", "uniprot_acc", "hgnc_id",
        "model", "prompt_variant", "replicate",
        "predicted_verdict", "predicted_reason", "is_match",
        "ground_truth_verdict", "ground_truth_reason",
    ]
    reps = src["reps"]
    # ground_truth_reason isn't on mainbench_replicates_v2 — join from bench
    if "ground_truth_reason" not in reps.columns:
        reason_lookup = src["bench"].set_index("gene_symbol")["ground_truth_reason"]
        reps = reps.assign(
            ground_truth_reason=reps["gene_symbol"].map(reason_lookup)
        )
    return reps[keep]


_DB_FLAG_COLS = [
    "uniprot_surface_flag", "go_surface_flag", "hpa_surface_flag",
    "surfy_surface_flag", "cspa_surface_flag",
]


def build_db_overlap_venn(src: dict[str, pd.DataFrame]) -> pd.DataFrame:
    """Figure 1 — the five databases' surface-membership overlap under
    each source's INITIAL (pre-recalibration) cutoff.

    This is a databases-overlap figure, NOT a whole-proteome view, so it
    gets its own minimal per-figure TSV rather than reusing the big
    whole_proteome_catalog.tsv. Columns: stable identifiers + the five
    initial ``*_surface_flag`` columns. Restricted to the union (rows
    where at least one source flags surface), since proteins no source
    calls aren't part of any Venn region. Deliberately DROPS:
      • ``universe_version`` — internal provenance, too technical for a
        figure-input TSV (per the figure-input-TSV conventions).
      • the optimized-cutoff columns + ``n_sources_surface`` — Figure 1
        is about the native/initial source definitions only.
      • ``sonnet_verdict`` / ``sonnet_reason`` / ``verdict_source`` —
        the triage agent isn't part of this DB-overlap figure.
    """
    cat = src["catalog"]
    keep_ids = ["hgnc_id", "hgnc_symbol", "uniprot_acc", "ensembl_gene", "ncbi_gene_id"]
    cols = [c for c in keep_ids if c in cat.columns] + _DB_FLAG_COLS
    out = cat[cols].copy()
    # Union members only: at least one source flags surface.
    flag_any = out[_DB_FLAG_COLS].apply(
        lambda s: s.astype(str).isin(["1", "1.0"]).astype(int)
    ).sum(axis=1)
    out = out[flag_any > 0].reset_index(drop=True)
    return out


def build_positive_control_db_coverage_bars(src: dict[str, pd.DataFrame]) -> pd.DataFrame:
    """Long-form positive-control coverage. Pass-through copy of the
    canonical ``positive_control_long.tsv`` — one row per (category × gene)
    with the per-DB flags + sonnet_full_flag + adc_source already
    denormalized. The figure groups by (category, source) and sums the
    flags from this single TSV without any joins."""
    return pd.read_csv(POS_LONG_TSV, sep="\t")


def build_surfaceome_deterministic_features_placeholder(
    src: dict[str, pd.DataFrame],
) -> pd.DataFrame:
    """Per-gene deterministic features for Supp Fig 13, faceted by the REAL
    deep-dive tier — sourced from the deep-dive RECORDS so every deep-dived
    gene has full coverage.

    This used to join the standalone ``deeptmhmm_human_canonical.tsv``, which
    only covers the M1 candidate universe (~2,359 surface candidates). That left
    topology tier-correlated MISSING (canonical ~83% covered → 'no' ~6%),
    biasing every per-feature fraction on exactly the low/uncertain/no tiers we
    want to break out. Each deep-dived gene carries its OWN DeepTMHMM run in its
    record, so the export (``deep_dive_records.tsv``) now derives the
    deterministic-feature columns from ``deterministic_features`` — full
    coverage, no bias.

    ``group`` is the 5-tier ``_dd_tier`` call (canonical / likely / low /
    uncertain / no); the figure combines uncertain+no onto a single facet.
    ``pending`` (not-yet-deep-dived) genes are excluded by construction — the
    export holds only published records.

    Feature columns (all real per-gene, from the record): ``tm_helix_count``,
    ``protein_length``, ``has_signal_peptide``, ``n_term_extracellular``,
    ``c_term_extracellular``, ``mouse_has_one2one`` / ``cyno_has_one2one`` (has a
    one-to-one ortholog — the record stores Compara orthology ``type`` but not
    its separate high-confidence flag, so this is looser than the old
    ``*_high_confidence`` column and renamed to match), ``schweke_homomer``,
    ``alt_iso_diff_topo``.

    Mirrors ``scripts/surfaceome_deterministic_features_placeholder.py``
    ``load_data()`` — it reads this bundled single TSV.

    PRELIMINARY — pre-QA-fix; counts grow as the sweep progresses.
    """
    feature_cols = ["tm_helix_count", "protein_length", "ecd_length_residues",
                    "has_signal_peptide",
                    "n_term_extracellular", "c_term_extracellular",
                    "mouse_has_one2one", "cyno_has_one2one",
                    "schweke_homomer", "alt_iso_diff_topo",
                    "has_ec_surface_bind_site", "has_concerning_paralog"]
    cols = ["gene_symbol", "group", *feature_cols]
    dd = src.get("deep_dive")
    if dd is None or dd.empty:
        return _empty_deep_dive_frame(cols)
    out = pd.DataFrame({"gene_symbol": dd["gene_symbol"].astype(str)})
    out["group"] = [_dd_tier(r) for _, r in dd.iterrows()]
    for c in feature_cols:
        out[c] = pd.to_numeric(dd[c], errors="coerce") if c in dd.columns else pd.NA
    return out[cols].sort_values(
        ["group", "gene_symbol"], kind="stable").reset_index(drop=True)


BUILDERS: dict[str, callable] = {
    "db_overlap_venn":               build_db_overlap_venn,
    "benchmark_cost_vs_accuracy":    build_cost_vs_accuracy,
    "db_correctness_by_class":       build_db_correctness_by_class,
    "db_correctness_overall":        build_db_correctness_overall,
    "db_vs_sonnet_whole_proteome":   build_db_vs_sonnet_whole_proteome,
    "ensemble_vs_best_db_vs_sonnet": build_ensemble,
    "deep_dive_final_categories":    build_deep_dive_final_categories,
    "evidence_corpus_vs_selected":   build_evidence_corpus_vs_selected,
    "deep_dive_record_richness":     build_deep_dive_record_richness,
    "triage_vs_deep_dive_reason":    build_triage_vs_deep_dive_reason,
    "deep_dive_vs_sonnet_benchmark": build_deep_dive_vs_sonnet_benchmark,
    "curator_vs_agent_reason":       build_curator_vs_agent_reason,
    "zero_db_rescues_by_triage":     build_zero_db_rescues,
    "topology_coverage_by_source":   build_topology_coverage_by_source,
    "bench_topology_vs_universe":    build_bench_topology_vs_universe,
    "positive_control_db_coverage_bars":  build_positive_control_db_coverage_bars,
    "surfaceome_deterministic_features_placeholder":
        build_surfaceome_deterministic_features_placeholder,
}


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--out", type=Path, default=DEFAULT_OUT,
                    help=f"output dir (default: {DEFAULT_OUT.relative_to(ROOT)})")
    args = ap.parse_args()

    args.out.mkdir(parents=True, exist_ok=True)
    print("  loading canonical sources …")
    src = _load_sources()
    for slug, builder in BUILDERS.items():
        df = builder(src)
        out_path = args.out / f"{slug}.tsv"
        df.to_csv(out_path, sep="\t", index=False)
        size_kb = out_path.stat().st_size / 1024
        print(f"  wrote {out_path.relative_to(ROOT)}  ({len(df):>5} rows, {size_kb:>6.1f} KB)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
