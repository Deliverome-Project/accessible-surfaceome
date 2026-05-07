"""Merge the seven M1 sources into one candidate-universe table.

Sources (each loaded by a ``load_*`` function in ``loaders.py``):

Five **gating** sources — each independently admits proteins to the universe
under its own evidence rule:

1. **UniProt** — pre-filtered surface-candidate query
2. **GO** — annotations under the surface GO roots
3. **SURFY** — Bausch-Fluck 2018 SurfaceomeMasterTable
4. **CSPA** — Cell Surface Protein Atlas (Bausch-Fluck 2015)
5. **HPA** — Human Protein Atlas subcellular_location IF

Two **auxiliary** sources — emitted per row but do not contribute to
universe membership or to the k-of-5 agreement count:

6. **DeepTMHMM** — predicted membrane topology (run on a partial cohort)
7. **JensenLab COMPARTMENTS** — text-mining + experiments stars
   (corroboration-gated; contributes 0 unique members by construction)

The join key is the base ``uniprot_accession``. Before joining, each
source's accessions are reconciled against the current UniProt accession
history (``sec_ac.txt`` + ``delac_sp.txt``) so that, e.g., per-allele HLA
accessions that UniProt has since merged collapse onto the right
canonical primary. That step lives in ``normalize.py``.

Each source produces a boolean ``<source>_surface_flag`` derived from
its own evidence rule. The exact predicates are documented once in the
manifest's ``flag_rules`` block (assembled in ``main`` below) and in
``docs/reports/2026-04-17-m1-candidate-universe-onepager.md``.

Outputs (all under ``data/processed/candidate_universe/``):

- ``candidate_universe.tsv``               — rows with ``in_db_union == 1``
  (at least one of uniprot/go/surfy/cspa/hpa flags surface; DeepTMHMM and
  COMPARTMENTS do not contribute to universe membership but their columns
  are emitted as auxiliary evidence for downstream agent assessment)
- ``candidate_universe_zero_support.tsv``  — present in some source but
  filtered out of every positive-flag rule (kept for traceability)
- ``candidate_universe_summary.json``      — per-source counts, agreement
  histogram, pairwise Jaccard
- ``candidate_universe_traceability.json`` — input SHA256s + flag_rules prose
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import pandas as pd

from accessible_surfaceome.merge.gene_symbols import (
    consolidate_gene_symbol,
    resolve_gene_symbols_with_mygene,
)
from accessible_surfaceome.merge.loaders import (
    COMPARTMENTS_TSV,
    CSPA_HIGH_CONFIDENCE,
    CSPA_KNOWN_CATEGORIES,
    CSPA_PUTATIVE,
    CSPA_TSV,
    CSPA_UNSPECIFIC,
    DEEPTMHMM_CAN_TSV,
    DEEPTMHMM_ISO_TSV,
    GO_TSV,
    HPA_TSV,
    SURFY_TSV,
    UNIPROT_TSV,
    best_cspa_category,
    first_nonempty_symbol,
    load_compartments,
    load_cspa,
    load_deeptmhmm,
    load_go,
    load_hpa,
    load_surfy,
    load_uniprot,
)
from accessible_surfaceome.merge.normalize import (
    NormalizeStats,
    normalize_accessions,
)
from accessible_surfaceome.paths import (
    DATA_EXTERNAL_DIR,
    DATA_PROCESSED_DIR,
    REPO_ROOT,
)
from accessible_surfaceome.sources._support.accession_history import (
    load_accession_history,
)
from accessible_surfaceome.sources._support.traceability import (
    sha256_file,
    utc_now_iso,
)

DATASET = "candidate_universe"
DEFAULT_OUTPUT_DIR = DATA_PROCESSED_DIR / "candidate_universe"
OUTPUT_TSV = "candidate_universe.tsv"
ZERO_SUPPORT_TSV = "candidate_universe_zero_support.tsv"
SUMMARY_JSON = "candidate_universe_summary.json"
MANIFEST_JSON = "candidate_universe_traceability.json"

ACCESSION_HISTORY_DIR = DATA_EXTERNAL_DIR / "uniprot_accession_history"
SEC_AC_TXT = ACCESSION_HISTORY_DIR / "sec_ac.txt"
DELAC_SP_TXT = ACCESSION_HISTORY_DIR / "delac_sp.txt"

GATING_FLAG_COLUMNS = [
    "uniprot_surface_flag",
    "go_surface_flag",
    "surfy_surface_flag",
    "cspa_surface_flag",
    "hpa_surface_flag",
]
AUXILIARY_FLAG_COLUMNS = [
    "deeptmhmm_surface_flag",
    "compartments_surface_flag",
]
ALL_FLAG_COLUMNS = GATING_FLAG_COLUMNS + AUXILIARY_FLAG_COLUMNS


def build_arg_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    return p


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    return build_arg_parser().parse_args(argv)


def main(argv: list[str] | None = None) -> None:
    args = parse_args(argv)
    out_dir: Path = args.output_dir
    out_dir.mkdir(parents=True, exist_ok=True)

    print("loading UniProt accession-history reference ...")
    sec_ac, delac_sp = load_accession_history(ACCESSION_HISTORY_DIR)
    print(f"  sec_ac entries={len(sec_ac):,}  delac_sp entries={len(delac_sp):,}")

    print("loading sources ...")
    raw_sources = {
        "uniprot": load_uniprot(),
        "go": load_go(),
        "surfy": load_surfy(),
        "cspa": load_cspa(),
        "deeptmhmm": load_deeptmhmm(),
        "hpa": load_hpa(),
        "compartments": load_compartments(),
    }

    # Reconcile accessions against current UniProt (sec_ac -> primary,
    # drop delac_sp), then collapse duplicates that arise when multiple
    # secondaries reconcile onto the same primary (common for HLA
    # alleles). Per-source overrides preserve semantics where the
    # default max/first reducers would drop meaningful detail. CSPA
    # also carries ``cspa_any_*_precollapse`` columns (boolean-OR of
    # raw per-row evidence) so ``cspa_mixed_category_conflict`` can
    # flag primaries that inherited disagreeing categories from
    # multiple historical accessions.
    source_agg_overrides: dict[str, dict[str, object]] = {
        "cspa": {
            "cspa_category": best_cspa_category,
            "cspa_gene_symbol": first_nonempty_symbol,
            # Default max reducer captures boolean-OR pre-collapse evidence
            # for the *_precollapse provenance columns added below.
        },
        "surfy": {
            "surfy_gene_symbol": first_nonempty_symbol,
        },
    }
    # Clone CSPA's raw category booleans into *_precollapse columns before
    # normalization so the default max reducer aggregates them faithfully
    # (the primary flags are re-derived from the category below).
    raw_sources["cspa"] = raw_sources["cspa"].assign(
        cspa_any_high_confidence_precollapse=raw_sources["cspa"]["cspa_is_high_confidence"],
        cspa_any_putative_precollapse=raw_sources["cspa"]["cspa_is_putative"],
        cspa_any_unspecific_precollapse=raw_sources["cspa"]["cspa_is_unspecific"],
        cspa_any_missing_category_precollapse=raw_sources["cspa"]["cspa_category_missing"],
    )
    normalized: dict[str, pd.DataFrame] = {}
    norm_stats: list[NormalizeStats] = []
    for name, df in raw_sources.items():
        norm_df, stats = normalize_accessions(
            df, sec_ac=sec_ac, delac_sp=delac_sp, source_name=name,
            agg_override=source_agg_overrides.get(name),
        )
        # Rename the per-source ambiguity flag so each source tracks its
        # own split-mapping quarantine (pre-merge); the merge below uses
        # these to gate per-source surface flags.
        norm_df = norm_df.rename(
            columns={"split_mapping_ambiguous": f"{name}_split_mapping_ambiguous"}
        )
        if name == "cspa":
            cat = norm_df["cspa_category"].astype(str)
            norm_df["cspa_is_high_confidence"] = (cat == CSPA_HIGH_CONFIDENCE).astype(int)
            norm_df["cspa_is_putative"] = (cat == CSPA_PUTATIVE).astype(int)
            norm_df["cspa_is_unspecific"] = (cat == CSPA_UNSPECIFIC).astype(int)
            norm_df["cspa_category_missing"] = (~cat.isin(CSPA_KNOWN_CATEGORIES)).astype(int)
            # Flag cases where the headline category differs from the
            # union of pre-collapse evidence — i.e. at least two distinct
            # categories were observed before normalization. For unmerged
            # primaries this is always 0.
            for col in (
                "cspa_any_high_confidence_precollapse",
                "cspa_any_putative_precollapse",
                "cspa_any_unspecific_precollapse",
                "cspa_any_missing_category_precollapse",
            ):
                norm_df[col] = pd.to_numeric(norm_df[col], errors="coerce").fillna(0).astype(int)
            n_distinct_precollapse = (
                norm_df["cspa_any_high_confidence_precollapse"]
                + norm_df["cspa_any_putative_precollapse"]
                + norm_df["cspa_any_unspecific_precollapse"]
                + norm_df["cspa_any_missing_category_precollapse"]
            )
            norm_df["cspa_mixed_category_conflict"] = (n_distinct_precollapse >= 2).astype(int)
        normalized[name] = norm_df
        norm_stats.append(stats)
        print(
            f"  {name:<10s} {stats['input_rows']:>5d} -> {stats['output_rows']:>5d}  "
            f"(rewrote {stats['secondary_rows_rewritten']} secondary, "
            f"dropped {stats['deleted_rows_dropped']} deleted, "
            f"{stats['split_duplications']} split-duplications)"
        )

    merged = normalized["uniprot"]
    for other_name in ("go", "surfy", "cspa", "deeptmhmm", "hpa", "compartments"):
        merged = merged.merge(normalized[other_name], on="uniprot_accession", how="outer")

    for col in ALL_FLAG_COLUMNS:
        merged[col] = merged[col].fillna(0).astype(int)

    # Quarantine split-history remaps: if a per-source row arrived at a
    # primary only via a split secondary (one old accession -> multiple
    # current primaries), its ``<source>_split_mapping_ambiguous`` flag
    # is 1. The original annotation applies to AT MOST one derived
    # primary, not all. Zero out that source's surface flag for those
    # ambiguous rows so they don't contribute to ``n_sources_surface``
    # or pairwise overlap metrics. The evidence columns are retained and
    # the ambiguity flag is emitted in the output for manual resolution.
    split_ambig_cols: list[str] = []
    for name in ("uniprot", "go", "surfy", "cspa", "deeptmhmm",
                 "hpa", "compartments"):
        ambig_col = f"{name}_split_mapping_ambiguous"
        flag_col = f"{name}_surface_flag"
        if ambig_col in merged.columns:
            merged[ambig_col] = merged[ambig_col].fillna(0).astype(int)
            merged.loc[merged[ambig_col] == 1, flag_col] = 0
            split_ambig_cols.append(ambig_col)
    merged["split_mapping_ambiguous_any_source"] = (
        merged[split_ambig_cols].sum(axis=1) > 0
    ).astype(int) if split_ambig_cols else 0

    # COMPARTMENTS corroboration gate: only fire compartments_surface_flag
    # when another GATING source has independently flagged the protein
    # as surface. Without this gate, dictionary-based NER over Medline
    # picks up contextual literature co-mentions for non-surface
    # proteins (TP53, MYC, ALB, IL1B, ...) and admits them. The
    # corroborator list intentionally excludes DeepTMHMM, which is also
    # auxiliary in this milestone — an auxiliary source must not rescue
    # another auxiliary source. See
    # ``docs/reports/2026-04-17-jensenlab-compartments-integration.md``
    # for the rationale and rejected looser predicates.
    def _num(col: str) -> pd.Series:
        if col not in merged.columns:
            return pd.Series(0, index=merged.index)
        return pd.to_numeric(merged[col], errors="coerce").fillna(0)

    gating_corroborator = (
        (_num("uniprot_surface_flag") == 1)
        | (_num("go_surface_flag") == 1)
        | (_num("surfy_surface_flag") == 1)
        | (_num("cspa_surface_flag") == 1)
        | (_num("hpa_surface_flag") == 1)
    )
    merged["compartments_corroborated"] = gating_corroborator.astype(int)
    merged.loc[~gating_corroborator, "compartments_surface_flag"] = 0

    merged["gene_symbol_input"] = merged.apply(consolidate_gene_symbol, axis=1)
    merged["gene_symbol_query"] = (
        merged["gene_symbol_input"].astype(str).str.strip().str.upper()
    )
    gene_symbol_universe = sorted(
        {
            symbol
            for symbol in merged["gene_symbol_query"]
            if isinstance(symbol, str) and symbol
        }
    )
    gene_resolution, gene_resolution_stats = resolve_gene_symbols_with_mygene(
        gene_symbol_universe
    )
    merged = merged.merge(gene_resolution, on="gene_symbol_query", how="left")
    merged["gene_symbol_mapping_status"] = (
        merged["gene_symbol_mapping_status"].fillna("not_found").astype(str)
    )
    merged["gene_symbol_resolved"] = (
        merged["gene_symbol_resolved"].fillna("").astype(str).str.strip()
    )
    merged["gene_symbol"] = merged["gene_symbol_resolved"].where(
        merged["gene_symbol_resolved"] != "",
        merged["gene_symbol_input"].astype(str).str.strip(),
    )
    merged["gene_symbol_mygene_score"] = pd.to_numeric(
        merged["gene_symbol_mygene_score"], errors="coerce"
    ).fillna(0.0)
    merged = merged.drop(columns=["gene_symbol_query"])

    merged["n_sources_surface"] = merged[GATING_FLAG_COLUMNS].sum(axis=1).astype(int)
    merged["in_db_union"] = (merged[GATING_FLAG_COLUMNS].sum(axis=1) > 0).astype(int)
    # ml_only_edge_case rows have deeptmhmm topology support but no
    # gating-source surface annotation. They are excluded from the
    # candidate universe (DeepTMHMM is a membrane-topology predictor
    # that does not distinguish plasma membrane from intracellular
    # membranes, so it cannot stand alone as surface evidence). The
    # deeptmhmm_* columns remain on every universe row as auxiliary
    # evidence for the downstream agent assessment steps.
    merged["ml_only_edge_case"] = (
        (merged["deeptmhmm_surface_flag"] == 1) & (merged["in_db_union"] == 0)
    ).astype(int)

    name_map = {
        "uniprot_surface_flag": "uniprot",
        "go_surface_flag": "go",
        "surfy_surface_flag": "surfy",
        "cspa_surface_flag": "cspa",
        "deeptmhmm_surface_flag": "deeptmhmm",
        "hpa_surface_flag": "hpa",
        "compartments_surface_flag": "compartments",
    }

    def _sources_present(row: pd.Series) -> str:
        return ",".join(name_map[c] for c in ALL_FLAG_COLUMNS if row[c] == 1)

    merged["sources_present"] = merged.apply(_sources_present, axis=1)

    out_cols = [
        "uniprot_accession",
        "gene_symbol_input",
        "gene_symbol",
        "gene_symbol_mapping_status",
        "gene_symbol_resolved",
        "gene_symbol_mygene_score",
        "uniprot_entry_name",
        *ALL_FLAG_COLUMNS,
        "n_sources_surface",
        "in_db_union",
        "ml_only_edge_case",
        "sources_present",
        "go_n_go_ids",
        "go_has_experimental",
        "go_has_curated",
        "go_has_sequence",
        "go_has_electronic",
        "go_low_confidence_only",
        "surfy_label",
        "surfy_ml_score",
        "cspa_category",
        "cspa_is_high_confidence",
        "cspa_is_putative",
        "cspa_is_unspecific",
        "cspa_category_missing",
        "cspa_any_high_confidence_precollapse",
        "cspa_any_putative_precollapse",
        "cspa_any_unspecific_precollapse",
        "cspa_any_missing_category_precollapse",
        "cspa_mixed_category_conflict",
        "uniprot_split_mapping_ambiguous",
        "go_split_mapping_ambiguous",
        "surfy_split_mapping_ambiguous",
        "cspa_split_mapping_ambiguous",
        "deeptmhmm_split_mapping_ambiguous",
        "hpa_split_mapping_ambiguous",
        "compartments_split_mapping_ambiguous",
        "split_mapping_ambiguous_any_source",
        "deeptmhmm_label",
        "deeptmhmm_label_source",
        # HPA provenance — therapeutic-delivery-relevant state columns
        "hpa_reliability",
        "hpa_pm_accessible",
        "hpa_junctional",
        "hpa_secreted_only",
        "hpa_trafficking_associated",
        "hpa_pm_reliability",
        "hpa_junction_reliability",
        "hpa_pm_in_enhanced",
        "hpa_pm_in_supported",
        "hpa_pm_in_approved",
        "hpa_pm_in_uncertain",
        "hpa_cj_in_enhanced",
        "hpa_cj_in_supported",
        "hpa_cj_in_approved",
        "hpa_cj_in_uncertain",
        "hpa_has_extracellular",
        "hpa_locations",
        "hpa_go_ids",
        "hpa_low_confidence_only",
        "hpa_ensembl_gene_id",
        # COMPARTMENTS provenance
        "compartments_integrated_stars_max",
        "compartments_knowledge_stars_max",
        "compartments_experiments_stars_max",
        "compartments_textmining_stars_max",
        "compartments_predictions_stars_max",
        "compartments_surface_terms",
        "compartments_low_confidence_only",
        "compartments_corroborated",
        "compartments_ensembl_protein_id",
    ]
    for col in out_cols:
        if col not in merged.columns:
            merged[col] = ""
    merged = merged[out_cols].sort_values(
        ["n_sources_surface", "uniprot_accession"], ascending=[False, True]
    ).reset_index(drop=True)

    merged = merged[merged["uniprot_accession"].notna()].copy()
    merged["uniprot_accession"] = merged["uniprot_accession"].astype(str).str.strip()
    merged = merged[merged["uniprot_accession"] != ""].copy()

    # Split the merged frame into:
    #   - the candidate universe (in_db_union == 1): at least one of the
    #     five gating sources (uniprot/go/surfy/cspa/hpa) has set its
    #     own surface flag under its own rule. DeepTMHMM and COMPARTMENTS
    #     are auxiliary: their columns are still emitted on every
    #     universe row as evidence for the downstream agent assessment
    #     steps but they do not gate membership.
    #     - DeepTMHMM is held out because it is a membrane-topology
    #       predictor that does not distinguish plasma membrane from
    #       intracellular membranes, run on a partial cohort here.
    #     - COMPARTMENTS is held out because the corroboration gate
    #       above guarantees that every COMPARTMENTS-flagged protein is
    #       already gated in by ≥ 1 of the five gating sources, so
    #       COMPARTMENTS contributes 0 unique members.
    #   - the zero-support pool (in_db_union == 0): present in some
    #     raw source but filtered out of every gating positive-flag
    #     rule (GO-IEA-only, CSPA unspecific / blank, HPA secreted-only,
    #     accession-history-split-ambiguous, or ml_only_edge_case =
    #     DeepTMHMM-only / COMPARTMENTS-only-uncorroborated). Retained
    #     as a separate file for traceability; they carry no gating
    #     positive evidence so have nothing for the LLM to reconcile.
    merged_all = merged
    merged = merged_all[merged_all["in_db_union"] == 1].copy().reset_index(drop=True)
    zero_support = merged_all[merged_all["in_db_union"] == 0].copy().reset_index(drop=True)

    # --- pre-publication assertion: documented flag_rules reconcile with output ---
    # Re-derive each surface flag from the raw evidence columns in the merged
    # table and compare to the emitted ``*_surface_flag`` count. Any drift
    # here means ``flag_rules`` in the manifest is out of sync with the code
    # (a silent failure mode that would mislead downstream auditors). Runs
    # BEFORE writing the TSV so a failure cannot leave a stale/partial
    # artifact on disk; the previous ``candidate_universe.tsv`` stays intact
    # until the new one passes validation.
    def _int(col: str) -> pd.Series:
        return pd.to_numeric(merged[col], errors="coerce").fillna(0).astype(int)

    def _float(col: str) -> pd.Series:
        return pd.to_numeric(merged[col], errors="coerce").fillna(0.0).astype(float)

    # COMPARTMENTS stars threshold — mirror of the rule in
    # accessible_surfaceome.sources.compartments. Any change here must also
    # update the loader, the ``flag_rules`` block, and the threshold
    # referenced in the SURFACE_TERMS GO set anywhere else it surfaces.
    compartments_flag_threshold = 3.0

    expected = {
        "go_surface_flag": (
            (
                (_int("go_has_experimental") >= 1)
                | (_int("go_has_curated") >= 1)
                | (_int("go_has_sequence") >= 1)
            )
            & (_int("go_split_mapping_ambiguous") == 0)
        ).astype(int),
        "cspa_surface_flag": (
            (
                (_int("cspa_any_high_confidence_precollapse") == 1)
                | (_int("cspa_any_putative_precollapse") == 1)
            )
            & (_int("cspa_split_mapping_ambiguous") == 0)
        ).astype(int),
        "hpa_surface_flag": (
            (
                (_int("hpa_pm_accessible") == 1)
                | (_int("hpa_junctional") == 1)
            )
            & (_int("hpa_split_mapping_ambiguous") == 0)
        ).astype(int),
        "compartments_surface_flag": (
            (
                pd.concat(
                    [
                        _float("compartments_experiments_stars_max"),
                        _float("compartments_textmining_stars_max"),
                    ],
                    axis=1,
                ).max(axis=1)
                >= compartments_flag_threshold
            )
            & (_int("compartments_split_mapping_ambiguous") == 0)
            & (_int("compartments_corroborated") == 1)
        ).astype(int),
    }
    for flag_col, derived in expected.items():
        mismatch = int((_int(flag_col) != derived).sum())
        if mismatch:
            raise RuntimeError(
                f"flag_rules drift: {flag_col} disagrees with documented "
                f"predicate on {mismatch} rows. Update flag_rules in the "
                f"manifest or the loader logic so they match."
            )

    # Write each output to a sibling ``*.tmp`` file, then ``replace`` it
    # over the published name once everything (summary + manifest) is
    # assembled. Plain rename — no per-run staging directory needed for
    # a single-user research script.
    out_tsv = out_dir / OUTPUT_TSV
    tmp_tsv = out_tsv.with_suffix(out_tsv.suffix + ".tmp")
    merged.to_csv(tmp_tsv, sep="\t", index=False)
    out_zero_tsv = out_dir / ZERO_SUPPORT_TSV
    tmp_zero_tsv = out_zero_tsv.with_suffix(out_zero_tsv.suffix + ".tmp")
    zero_support.to_csv(tmp_zero_tsv, sep="\t", index=False)

    # --- summary ---
    per_source_counts = {
        name_map[c]: int(merged[c].sum()) for c in ALL_FLAG_COLUMNS
    }

    n_gating_sources = len(GATING_FLAG_COLUMNS)
    agreement_counts = {
        f"{k}_of_{n_gating_sources}": int((merged["n_sources_surface"] == k).sum())
        for k in range(0, n_gating_sources + 1)
    }

    # Pairwise overlap (Jaccard) across every flag pair (gating + auxiliary)
    pairwise = {}
    for i, a in enumerate(ALL_FLAG_COLUMNS):
        for b in ALL_FLAG_COLUMNS[i + 1 :]:
            set_a = set(merged.loc[merged[a] == 1, "uniprot_accession"])
            set_b = set(merged.loc[merged[b] == 1, "uniprot_accession"])
            union = set_a | set_b
            inter = set_a & set_b
            pairwise[f"{name_map[a]}__{name_map[b]}"] = {
                "n_a": len(set_a),
                "n_b": len(set_b),
                "n_intersect": len(inter),
                "n_union": len(union),
                "jaccard": (len(inter) / len(union)) if union else 0.0,
            }

    # All-gating-sources agreement
    all_gating = int(
        (merged[GATING_FLAG_COLUMNS].sum(axis=1) == n_gating_sources).sum()
    )

    # COMPARTMENTS auxiliary: by construction every flagged row must also
    # be flagged by ≥ 1 gating source. Compute and assert the unique
    # contribution is zero before publishing — see invariant below.
    n_compartments_supported = int(merged["compartments_surface_flag"].sum())
    n_compartments_unique = int(
        (
            (merged["compartments_surface_flag"] == 1)
            & (merged[GATING_FLAG_COLUMNS].sum(axis=1) == 0)
        ).sum()
    )

    summary = {
        "generated_at_utc": utc_now_iso(),
        "n_rows_total": int(len(merged)),
        "n_zero_support_rows_excluded": int(len(zero_support)),
        "n_in_db_union": int(merged["in_db_union"].sum()),
        "n_ml_only_edge_cases": int(merged["ml_only_edge_case"].sum()),
        "gene_symbol_resolution": gene_resolution_stats,
        "gating_sources": [name_map[c] for c in GATING_FLAG_COLUMNS],
        "auxiliary_sources": [name_map[c] for c in AUXILIARY_FLAG_COLUMNS],
        "n_gating_sources": n_gating_sources,
        "per_source_counts": per_source_counts,
        "agreement_counts": agreement_counts,
        f"n_with_all_{n_gating_sources}_gating_sources": all_gating,
        "n_compartments_supported": n_compartments_supported,
        "n_compartments_unique": n_compartments_unique,
        "pairwise_overlap": pairwise,
        "accession_normalization": norm_stats,
    }

    # COMPARTMENTS uniqueness invariant: the corroboration gate above
    # guarantees that every COMPARTMENTS-flagged row is also flagged by
    # at least one gating source. If a future refactor weakens the gate
    # — e.g. drops the corroboration term, broadens the stars threshold
    # without re-checking, or accidentally lets COMPARTMENTS into
    # GATING_FLAG_COLUMNS — this invariant catches it before publishing
    # and prevents COMPARTMENTS from silently expanding the universe.
    if n_compartments_unique:
        raise RuntimeError(
            f"COMPARTMENTS auxiliary invariant violated: "
            f"{n_compartments_unique} rows have compartments_surface_flag == 1 "
            f"but zero gating-source flags. The corroboration gate (or the "
            f"GATING_FLAG_COLUMNS list) has drifted. Refusing to publish."
        )
    summary_path = out_dir / SUMMARY_JSON
    tmp_summary = summary_path.with_suffix(summary_path.suffix + ".tmp")
    tmp_summary.write_text(
        json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )

    # --- traceability ---
    def _src_record(path: Path, label: str) -> dict:
        return {
            "label": label,
            "local_path": str(path.relative_to(REPO_ROOT)),
            "sha256": sha256_file(path),
            "size_bytes": path.stat().st_size,
        }

    manifest = {
        "dataset": DATASET,
        "generated_at_utc": utc_now_iso(),
        "script": Path(__file__).relative_to(REPO_ROOT).as_posix(),
        "sources": [
            _src_record(UNIPROT_TSV, "uniprot"),
            _src_record(GO_TSV, "go"),
            _src_record(SURFY_TSV, "surfy"),
            _src_record(CSPA_TSV, "cspa"),
            _src_record(DEEPTMHMM_CAN_TSV, "deeptmhmm_human_canonical"),
            _src_record(DEEPTMHMM_ISO_TSV, "deeptmhmm_human_isoforms"),
            _src_record(HPA_TSV, "hpa"),
            _src_record(COMPARTMENTS_TSV, "jensenlab_compartments"),
            _src_record(SEC_AC_TXT, "uniprot_sec_ac"),
            _src_record(DELAC_SP_TXT, "uniprot_delac_sp"),
        ],
        "outputs": {
            OUTPUT_TSV: {
                "local_path": str(out_tsv.relative_to(REPO_ROOT)),
                "sha256": sha256_file(tmp_tsv),
                "size_bytes": tmp_tsv.stat().st_size,
                "n_rows": int(len(merged)),
                "primary_key": "uniprot_accession",
                "filter": "in_db_union == 1 (at least one of uniprot/go/surfy/cspa/hpa flags surface; DeepTMHMM and COMPARTMENTS evidence is emitted on each row but does not contribute to universe membership)",
            },
            ZERO_SUPPORT_TSV: {
                "local_path": str(out_zero_tsv.relative_to(REPO_ROOT)),
                "sha256": sha256_file(tmp_zero_tsv),
                "size_bytes": tmp_zero_tsv.stat().st_size,
                "n_rows": int(len(zero_support)),
                "primary_key": "uniprot_accession",
                "filter": "in_db_union == 0 (accession present in a raw source but filtered out of every gating positive-flag rule, including ml_only_edge_case = DeepTMHMM-only rows and COMPARTMENTS-only-uncorroborated rows — retained for traceability only)",
            },
        },
        "gene_symbol_resolution": {
            "method": "MyGene querymany over merged-symbol universe",
            "scopes": "symbol,alias,prev_symbol",
            "fields": "symbol,alias,prev_symbol",
            "species": "human",
            "fallback": "none",
            "stats": gene_resolution_stats,
        },
        "flag_rules": {
            "uniprot_surface_flag": "1 iff accession present in UniProt surface-candidate snapshot AND uniprot_split_mapping_ambiguous == 0",
            "go_surface_flag": "1 iff NOT go_low_confidence_only (i.e., has_experimental OR has_curated OR has_sequence; pure-IEA rows kept for provenance but do not count) AND go_split_mapping_ambiguous == 0",
            "surfy_surface_flag": "1 iff surfy_is_surface == 1 (label == 'surface') AND surfy_split_mapping_ambiguous == 0",
            "cspa_surface_flag": "1 iff cspa_any_high_confidence_precollapse == 1 OR cspa_any_putative_precollapse == 1 (boolean-OR of pre-collapse evidence; unspecific and blank-category detections stay with flag=0 for provenance) AND cspa_split_mapping_ambiguous == 0",
            "cspa_mixed_category_conflict": "1 iff 2+ distinct CSPA categories were observed across pre-collapse rows that reconciled to the same current primary (headline cspa_category uses priority: high > putative > unspecific > blank; full pre-collapse evidence preserved in cspa_any_*_precollapse)",
            "deeptmhmm_surface_flag": "1 iff any DeepTMHMM cohort row has predicted_surface_membrane == 1 (label in {TM, SP+TM}; BETA excluded — human beta-barrels are mitochondrial outer membrane, not plasma-membrane) AND deeptmhmm_split_mapping_ambiguous == 0",
            "hpa_surface_flag": "1 iff (hpa_pm_accessible == 1 OR hpa_junctional == 1) AND hpa_split_mapping_ambiguous == 0. hpa_pm_accessible = 'Plasma membrane' appears in Enhanced / Supported / Approved tier (per-tier-specific reliability, NOT gene-wide Reliability — avoids overcalls where the gene's strong localization is nuclear/cytosolic while the PM call lands in Uncertain). hpa_junctional = 'Cell Junctions' appears in Enhanced / Supported / Approved tier (admits ADC-accessible epithelial junction proteins: cadherins, claudins, JAM, occludin, desmosomal cadherins). HPA's 'Extracellular location' column is populated entirely by 'Predicted to be secreted' (SignalP-based sequence prediction, not IF evidence) and does NOT contribute to the flag; secreted-only rows stay in the pool with hpa_secreted_only = 1 for provenance. Vesicles/Endosomes/Lysosomes are surfaced via hpa_trafficking_associated (provenance only; never a pool-admission signal on their own — that would reintroduce ABCB9-class false positives). See docs/reports/2026-04-17-hpa-therapeutic-delivery-refinement.md.",
            "compartments_surface_flag": "1 iff max(compartments_experiments_stars_max, compartments_textmining_stars_max) >= 3 over the surface GO terms {GO:0005886, GO:0009986, GO:0031225, GO:0005887} AND compartments_split_mapping_ambiguous == 0 AND compartments_corroborated == 1. Corroboration requires at least one of the five gating sources (uniprot, go, surfy, cspa, hpa) to have independently set its OWN surface_flag == 1 — see the compartments_corroborated entry for details. COMPARTMENTS is auxiliary in this milestone: its flag is emitted on every universe row but does not contribute to in_db_union, n_sources_surface, or the k-of-5 agreement count. Rationale: the JensenLab tagger's dictionary-based NER over Medline picks up literature co-occurrences with 'plasma membrane' for many contextually-mentioned non-surface proteins (TP53, MYC, ALB, INS, IFNG, IL1B, IL13, IL17A, NGF, FGF4, FGF8, BCL2, NFE2L2 etc.) that are not therapeutic-delivery targets. Requiring another gating source to have passed its own surface-flag bar is the tightest available corroboration and prevents these lone-textmining calls from entering the universe; looser predicates (raw pool membership, GO-IEA-only, HPA-Uncertain-tier) were tried and leaked false positives. Three of the four COMPARTMENTS channels are carried as provenance only: (a) knowledge re-ingests GO + UniProt-SubCell (would triple-count existing first-class GO evidence); (b) predictions wraps WoLF PSORT + YLoc, sequence-based predictors in the same family as SURFY + DeepTMHMM (would triple-count ML-predictor evidence; empirically drives ~73%% of pre-filter hits); (c) experiments rows with source == 'HPA' are dropped upstream to avoid double-counting first-class HPA IF evidence. See docs/reports/2026-04-17-jensenlab-compartments-integration.md.",
            "compartments_corroborated": "1 iff at least one of the five gating sources has independently flagged the protein as surface — i.e. uniprot_surface_flag OR go_surface_flag OR surfy_surface_flag OR cspa_surface_flag OR hpa_surface_flag equals 1. DeepTMHMM (also auxiliary in this milestone) is intentionally excluded from the corroborator set: an auxiliary source must not rescue another auxiliary source. Each gating source's own surface-flag rule encodes its 'this protein is membrane-accessible' predicate (go_surface_flag excludes pure-IEA, hpa_surface_flag requires PM/junctional at Enhanced/Supported/Approved tier, cspa_surface_flag requires high-confidence/putative, etc.), so requiring a gating source to have passed its own surface-flag bar is the correct corroboration threshold for therapeutic-delivery purposes. Looser predicates (raw pool membership, GO-IEA-only, HPA-Uncertain-tier) were tried and leaked false positives on cytokines / transcription factors / secreted proteins. Gates compartments_surface_flag.",
            "<source>_split_mapping_ambiguous": "1 iff the source's row for this primary arrived only via an accession-history split (one historical accession -> multiple current primaries) or, for HPA/compartments, via an ambiguous ENSG/ENSP -> UniProt mapping. Evidence may apply to at most one of the derived primaries; excluded from the per-source surface flag to avoid inflating agreement until manually resolved.",
            "split_mapping_ambiguous_any_source": "1 iff any of the per-source split_mapping_ambiguous flags is set for this primary.",
        },
    }
    manifest_path = out_dir / MANIFEST_JSON
    tmp_manifest = manifest_path.with_suffix(manifest_path.suffix + ".tmp")
    tmp_manifest.write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )

    # Publish: rename each ``*.tmp`` over its final name. ``Path.replace``
    # is atomic per file on POSIX; the four files don't update as a
    # bundle, but a partially-applied set is still self-describing
    # (the manifest records the exact SHA256 of every output it ships with).
    for src, dst in (
        (tmp_tsv, out_tsv),
        (tmp_zero_tsv, out_zero_tsv),
        (tmp_summary, summary_path),
        (tmp_manifest, manifest_path),
    ):
        src.replace(dst)

    print(f"wrote {out_tsv.relative_to(REPO_ROOT)}  n_rows={len(merged):,}")
    print(f"  per-source surface counts: {per_source_counts}")
    print(f"  agreement (k/{n_gating_sources} gating sources): {agreement_counts}")
    print(f"  all {n_gating_sources} gating sources agree: {all_gating:,}")
    print(
        f"  COMPARTMENTS (auxiliary): supported={n_compartments_supported:,} "
        f"unique={n_compartments_unique}"
    )


if __name__ == "__main__":
    main()
