"""Export deep-dive record facets from public D1 ``surface_annotation`` to a
committed figure-source TSV.

One row per published gene carrying the ``filters`` facets + a few top-level
fields the deep-dive figures derive from (final-categories buckets, record
richness, triage-vs-deep-dive, the S13 deterministic-features tiers). The
deep-dive figure builders in ``build_figure_tsvs.py`` read THIS TSV, so they
stay offline-reproducible (per tests/test_figure_tsv_reproducible_from_builder).

Re-run after each sweep batch — the figures re-render off the fresh export.
Uses ``json_extract`` in SQL so each row ships ~a few hundred bytes, NOT the
~120 KB annotation_json (pulling the full blob for the whole cohort is the
~145 MB that crashed the D1 isolate memory cap — see PR #104).

Also writes a companion ``triage_verdicts.tsv`` — one row per gene from the
genome-wide Sonnet triage run (``genome_full_sonnet_ncbi_v2``) carrying the
triage-stage verdict + reason. The S12 figure joins this against the deep-dive
export to compare the two stages' calls; keeping it a separate committed TSV
lets the S12 builder in ``build_figure_tsvs.py`` stay offline-reproducible.

Run:
    uv run python scripts/export_deep_dive_figure_source.py
"""
from __future__ import annotations

from pathlib import Path

import pandas as pd

from accessible_surfaceome.cloud.d1_client import D1Client, D1Config
from accessible_surfaceome.env import load_env

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "data/processed/deep_dive/deep_dive_records.tsv"
# Companion triage-verdict source: one row per gene carrying the TRIAGE-stage
# call (verdict + reason) from the genome-wide Sonnet triage run. This is the
# `triage_run` side the S12 figure joins against — the deep-dive export above
# only carries the deep-dive-side reason. Kept as a separate small TSV so the
# S12 builder in build_figure_tsvs.py stays offline-reproducible (it can't
# reach D1 during the reproducibility test).
TRIAGE_OUT = ROOT / "data/processed/deep_dive/triage_verdicts.tsv"
# Canonical genome-wide Sonnet triage run in public D1 (one row per gene,
# single model × variant × replicate). Its `predicted_reason` is drawn from
# the same closed `TriageReason` enum the deep-dive re-derives, so the two
# reasons are directly comparable in the S12 confusion matrix.
_TRIAGE_RUN_ID = "genome_full_sonnet_ncbi_v2"

# Per-replicate benchmark Sonnet+NCBI triage (the mainbench run, 3 replicates
# per gene) for the deep_dive_vs_sonnet_benchmark figure — its Sonnet accuracy
# bar shows one dot per replicate + SEM across them, matching the other accuracy
# figures. One row per (bench gene x replicate).
BENCH_SONNET_OUT = ROOT / "data/processed/deep_dive/benchmark_sonnet_replicates.tsv"
_MAINBENCH_RUN = "mainbench_canonical_v2"
_MAINBENCH_MODEL = "claude-sonnet-4-6"
_MAINBENCH_VARIANT = "ncbi"

# (output column, JSON path in annotation_json). Kept small + explicit so the
# query ships only what the figures need.
_FIELDS: list[tuple[str, str]] = [
    ("surface_accessibility", "$.filters.surface_accessibility"),
    ("confidence", "$.filters.confidence"),
    ("subcategory", "$.filters.subcategory"),
    ("state_dependence", "$.filters.state_dependence"),
    ("surface_call_reason", "$.filters.surface_call_reason"),
    ("surface_specificity", "$.filters.surface_specificity"),
    ("induction_trigger", "$.filters.induction_trigger"),
    ("tumor_associated", "$.filters.tumor_associated"),
    ("llm_family", "$.filters.llm_family"),
    ("evidence_grade", "$.filters.evidence_grade"),
    ("evidence_density", "$.filters.evidence_density"),
    ("n_papers_selected", "$.filters.n_papers_selected"),
    ("n_papers_found", "$.filters.n_papers_found"),
    ("expression_breadth", "$.filters.expression_breadth"),
    ("has_shed_form", "$.filters.has_shed_form"),
    ("has_secreted_form", "$.filters.has_secreted_form"),
    ("has_live_cell_surface_evidence", "$.filters.has_live_cell_surface_evidence"),
    ("triage_signal", "$.triage_signal"),
    ("record_confidence", "$.confidence"),
    ("evidence_count", "$.evidence_count"),
    ("primary_evidence_count", "$.primary_evidence_count"),
    ("model_path", "$.model_path"),
]

# Deterministic-feature columns derived server-side from each record's
# `deterministic_features` block. Sourced from the RECORD — NOT the standalone
# `deeptmhmm_human_canonical.tsv`, which only covers the M1 candidate universe
# (2,359 surface candidates) and so left the low/uncertain/no tiers of Supp
# Fig 13 with tier-correlated missing topology (canonical 83% covered → 'no'
# 6%). Every deep-dived gene carries its own DeepTMHMM run in the record, so
# reading from here gives full coverage. json_extract for scalars; json_each
# for the ortholog / isoform lists (D1 ships the SQLite JSON1 ext). Only
# scalars cross the wire — no full-blob pull, so no isolate memory-cap risk
# (the 145 MB crash of PR #104 was from returning full annotation_json).
_DF = "$.deterministic_features"
_CT = f"{_DF}.canonical_topology"

# The viewer's 24 provenance:"llm" filter facets (deep-dive-fields.ts).
# `n_llm_evidence` counts, per gene, how many carry a POSITIVE / substantive
# finding — the agent affirmatively determined something. Definitive negatives
# and non-determinations do NOT count (null / "unknown" / "none" / "no" /
# "false" / "not_determined"): a confident "no shed form" is a valid call but
# not record *richness*, and counting it would flatten the metric to ~24 for
# every gene (the agent almost always makes SOME call — e.g. overexpression
# reads "not observed" for most genes). This positive-finding count is the
# LLM-side analogue of n_det_features and is what Fig 6 panel d plots as
# "LLM filters with a positive finding"; the fixed 24 is the manuscript's count
# of filter TYPES (the denominator). 21 facets live under $.filters; three read
# from their canonical nested homes — primary_compartment under
# biological_context, and the conditional restricted_subdomain.domain /
# secreted_form.source sub-fields of the accessibility-risk blocks (which fire
# only for genes that actually carry that risk — itself a richness signal).
_LLM_FACETS: list[tuple[str, str]] = [
    ("surface_accessibility", "$.filters.surface_accessibility"),
    ("confidence", "$.filters.confidence"),
    ("state_dependence", "$.filters.state_dependence"),
    ("subcategory", "$.filters.subcategory"),
    ("surface_call_reason", "$.filters.surface_call_reason"),
    ("llm_family", "$.filters.llm_family"),
    ("evidence_grade", "$.filters.evidence_grade"),
    ("expression_level", "$.filters.expression_level"),
    ("expression_breadth", "$.filters.expression_breadth"),
    ("surface_specificity", "$.filters.surface_specificity"),
    ("co_receptor_dependency", "$.filters.co_receptor_dependency"),
    ("induction_trigger", "$.filters.induction_trigger"),
    ("has_known_ligand", "$.filters.has_known_ligand"),
    ("low_endogenous_expression", "$.filters.low_endogenous_expression"),
    ("overexpression_surface_localization_observed",
     "$.filters.overexpression_surface_localization_observed"),
    ("has_shed_form", "$.filters.has_shed_form"),
    ("has_secreted_form", "$.filters.has_secreted_form"),
    ("has_epitope_masking", "$.filters.has_epitope_masking"),
    ("has_restricted_subdomain", "$.filters.has_restricted_subdomain"),
    ("tumor_associated", "$.filters.tumor_associated"),
    ("has_live_cell_surface_evidence", "$.filters.has_live_cell_surface_evidence"),
    ("primary_compartment",
     "$.biological_context.subcellular_localization.primary_compartment"),
    ("restricted_subdomain_kind", "$.accessibility_risks.restricted_subdomain.domain"),
    ("secreted_form_source", "$.accessibility_risks.secreted_form.source"),
]
_LLM_NULLISH = ("('unknown','none','unclear','not_applicable',"
                "'not_determined','no','false','0','')")
_N_LLM_EVIDENCE_SQL = "(" + " + ".join(
    f"(CASE WHEN json_extract(annotation_json,'{path}') IS NOT NULL AND "
    f"CAST(json_extract(annotation_json,'{path}') AS TEXT) NOT IN {_LLM_NULLISH} "
    "THEN 1 ELSE 0 END)" for _name, path in _LLM_FACETS
) + ")"

_DET_EXPRS: list[tuple[str, str]] = [
    ("tm_helix_count",
     f"CAST(json_extract(annotation_json,'{_CT}.tm_helix_count') AS INT)"),
    ("protein_length",
     f"length(json_extract(annotation_json,'{_CT}.sequence'))"),
    ("ecd_length_residues",
     f"CAST(json_extract(annotation_json,'{_CT}.ecd_length_residues') AS INT)"),
    ("has_signal_peptide",
     f"CASE WHEN CAST(json_extract(annotation_json,'{_CT}.signal_peptide_length') "
     "AS INT) > 0 THEN 1 ELSE 0 END"),
    ("n_term_extracellular",
     f"CASE WHEN json_extract(annotation_json,'{_CT}.n_terminal_orientation')"
     "='extracellular' THEN 1 ELSE 0 END"),
    ("c_term_extracellular",
     f"CASE WHEN json_extract(annotation_json,'{_CT}.c_terminal_orientation')"
     "='extracellular' THEN 1 ELSE 0 END"),
    # "has a one-to-one ortholog" — the record stores Ensembl-Compara orthology
    # `type` but not Compara's separate high-confidence flag, so this is the
    # one2one-type test (looser than the old *_high_confidence column; renamed
    # to match the actual semantics).
    ("mouse_has_one2one",
     f"CASE WHEN EXISTS(SELECT 1 FROM json_each(annotation_json,'{_DF}.orthologs.mouse') "
     "WHERE json_extract(value,'$.type')='one2one') THEN 1 ELSE 0 END"),
    ("cyno_has_one2one",
     f"CASE WHEN EXISTS(SELECT 1 FROM json_each(annotation_json,'{_DF}.orthologs.cynomolgus') "
     "WHERE json_extract(value,'$.type')='one2one') THEN 1 ELSE 0 END"),
    ("schweke_homomer",
     f"CASE WHEN json_extract(annotation_json,'{_DF}.homo_oligomerization.is_homo_oligomer') "
     "IN (1,'true') THEN 1 ELSE 0 END"),
    ("alt_iso_diff_topo",
     f"CASE WHEN EXISTS(SELECT 1 FROM json_each(annotation_json,'{_DF}.isoform_topologies') "
     f"WHERE CAST(json_extract(value,'$.tm_helix_count') AS INT) != "
     f"CAST(json_extract(annotation_json,'{_CT}.tm_helix_count') AS INT)) THEN 1 ELSE 0 END"),
    # >=1 EXTRACELLULAR surface-binding site: a predicted surface_bind site whose
    # anchor residue sits in an 'O' (outside/extracellular) region of the
    # DeepTMHMM per-residue topology — excludes the intracellular / membrane
    # sites that a bare surface_bind.n_sites >= 1 would also count.
    ("has_ec_surface_bind_site",
     "CASE WHEN EXISTS(SELECT 1 FROM json_each(annotation_json,"
     f"'{_DF}.surface_bind.sites') WHERE substr(json_extract(annotation_json,"
     f"'{_CT}.per_residue_topology'), CAST(json_extract(value,'$.anchor_residue') "
     "AS INT), 1) = 'O') THEN 1 ELSE 0 END"),
    # Concerning paralog (binder-specificity risk): a paralog whose extracellular
    # domain is >=40% identical to this gene's (the viewer's mid band on
    # max_paralog_ecd_pct_identity) -> potential antibody cross-reactivity.
    ("has_concerning_paralog",
     "CASE WHEN CAST(json_extract(annotation_json,'$.filters.max_paralog_ecd_pct_identity') "
     "AS REAL) >= 40 THEN 1 ELSE 0 END"),
    # Unique papers with EXTRACELLULAR/primary evidence: distinct source papers
    # among the primary-tier (surface-method-tagged) evidence records — a PAPER
    # count (<= n_papers_selected), NOT the primary_evidence_count RECORD count
    # that previously mislabelled Fig 6 panel c "papers with EC". Powers panel c.
    ("n_papers_with_ec",
     "(SELECT COUNT(DISTINCT json_extract(sp.value,'$.source.source_id')) "
     "FROM json_each(annotation_json,'$.evidence') AS ev, "
     "json_each(ev.value,'$.spans') AS sp "
     "WHERE json_extract(ev.value,'$.evidence_tier')='primary')"),
    # Deterministic-annotation depth: how many of the 7 det-feature categories
    # carry data for this gene (topology / AF structure / surface-binding /
    # homo-oligomer / orthologs / paralogs / alt-isoforms). Powers Fig 6 panel e.
    ("n_det_features",
     "("
     f"(CASE WHEN json_extract(annotation_json,'{_CT}.tm_helix_count') IS NOT NULL THEN 1 ELSE 0 END)"
     f" + (CASE WHEN json_extract(annotation_json,'{_DF}.structure.afdb_id') IS NOT NULL THEN 1 ELSE 0 END)"
     f" + (CASE WHEN json_extract(annotation_json,'{_DF}.surface_bind.has_data') IN (1,'true') THEN 1 ELSE 0 END)"
     f" + (CASE WHEN json_extract(annotation_json,'{_DF}.homo_oligomerization.is_homo_oligomer') IN (1,'true') THEN 1 ELSE 0 END)"
     f" + (CASE WHEN EXISTS(SELECT 1 FROM json_each(annotation_json,'{_DF}.orthologs.mouse')) THEN 1 ELSE 0 END)"
     f" + (CASE WHEN EXISTS(SELECT 1 FROM json_each(annotation_json,'{_DF}.paralogs')) THEN 1 ELSE 0 END)"
     f" + (CASE WHEN EXISTS(SELECT 1 FROM json_each(annotation_json,'{_DF}.isoform_topologies')) THEN 1 ELSE 0 END)"
     ")"),
    # LLM filters with a positive/non-default (evidence-backed) determination —
    # the LLM-side analogue of n_det_features. Powers Fig 6 panel d.
    ("n_llm_evidence", _N_LLM_EVIDENCE_SQL),
]


def _select_sql() -> str:
    cols = ",\n  ".join(
        f"json_extract(annotation_json, '{path}') AS {name}"
        for name, path in _FIELDS
    )
    det_cols = ",\n  ".join(f"{expr} AS {name}" for name, expr in _DET_EXPRS)
    return (
        "SELECT gene_symbol, uniprot_acc, schema_version,\n  "
        + cols
        + ",\n  "
        + det_cols
        + "\nFROM surface_annotation ORDER BY gene_symbol;"
    )


def _triage_sql() -> str:
    """One row per gene from the genome-wide Sonnet triage run: the triage
    verdict + reason the S12 figure joins against the deep-dive record."""
    return (
        "SELECT gene_symbol, uniprot_acc, "
        "predicted_verdict AS triage_verdict, "
        "predicted_reason AS triage_reason "
        "FROM triage_run_public WHERE run_id = ? ORDER BY gene_symbol;"
    )


def _bench_sonnet_sql() -> str:
    """One row per (bench gene x replicate) from the mainbench Sonnet+NCBI run —
    the per-replicate triage predictions the benchmark figure aggregates into an
    accuracy dot per replicate + SEM across replicates."""
    return (
        "SELECT gene_symbol, replicate, predicted_verdict "
        "FROM triage_run_public "
        "WHERE run_id = ? AND model = ? AND prompt_variant = ? "
        "ORDER BY gene_symbol, replicate;"
    )


def main() -> int:
    load_env()
    with D1Client(D1Config.from_env_public()) as d1:
        rows = d1.query(_select_sql(), [])
        triage_rows = d1.query(_triage_sql(), [_TRIAGE_RUN_ID])
        bench_sonnet_rows = d1.query(
            _bench_sonnet_sql(),
            [_MAINBENCH_RUN, _MAINBENCH_MODEL, _MAINBENCH_VARIANT],
        )
    df = pd.DataFrame(rows)
    OUT.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(OUT, sep="\t", index=False)
    print(f"wrote {OUT.relative_to(ROOT)}: {len(df)} deep-dive records")

    triage = pd.DataFrame(triage_rows)
    triage.to_csv(TRIAGE_OUT, sep="\t", index=False)
    print(f"wrote {TRIAGE_OUT.relative_to(ROOT)}: {len(triage)} triage verdicts "
          f"(run_id={_TRIAGE_RUN_ID})")

    bench_sonnet = pd.DataFrame(bench_sonnet_rows)
    bench_sonnet.to_csv(BENCH_SONNET_OUT, sep="\t", index=False)
    print(f"wrote {BENCH_SONNET_OUT.relative_to(ROOT)}: {len(bench_sonnet)} bench "
          f"Sonnet replicate cells ({_MAINBENCH_RUN}/{_MAINBENCH_MODEL}/{_MAINBENCH_VARIANT})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
