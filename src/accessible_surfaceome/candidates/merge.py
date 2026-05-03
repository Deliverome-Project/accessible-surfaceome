"""Merge the seven M1 sources into one candidate-universe table.

Sources (each loaded by its own ``_load_*`` function below):

1. **UniProt** — pre-filtered surface-candidate query
2. **GO** — annotations under the surface GO roots
3. **SURFY** — Bausch-Fluck 2018 SurfaceomeMasterTable
4. **CSPA** — Cell Surface Protein Atlas (Bausch-Fluck 2015)
5. **DeepTMHMM** — predicted membrane topology
6. **HPA** — Human Protein Atlas subcellular_location IF
7. **JensenLab COMPARTMENTS** — text-mining + experiments stars

The join key is the base ``uniprot_accession``. Before joining, each
source's accessions are reconciled against the current UniProt accession
history (``sec_ac.txt`` + ``delac_sp.txt``) so that, e.g., per-allele HLA
accessions that UniProt has since merged collapse onto the right
canonical primary.

Each source produces a boolean ``<source>_surface_flag`` derived from
its own evidence rule. The exact predicates are documented once in the
manifest's ``flag_rules`` block (assembled in ``main`` below) and in
``docs/reports/2026-04-17-m1-candidate-universe-onepager.md``.

Outputs (all under ``data/processed/candidate_universe/``):

- ``candidate_universe.tsv``               — rows with ``n_sources_surface >= 1``
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
from typing import TypedDict

import mygene
import pandas as pd

from accessible_surfaceome.candidates.traceability import (
    sha256_file,
    utc_now_iso,
)
from accessible_surfaceome.candidates.uniprot_accession_history import (
    load_accession_history,
)
from accessible_surfaceome.paths import (
    DATA_EXTERNAL_DIR,
    DATA_PROCESSED_DIR,
    REPO_ROOT,
)


class NormalizeStats(TypedDict):
    source: str
    input_rows: int
    deleted_rows_dropped: int
    secondary_rows_rewritten: int
    split_duplications: int
    output_rows: int

DATASET = "candidate_universe"
DEFAULT_OUTPUT_DIR = DATA_PROCESSED_DIR / "candidate_universe"
OUTPUT_TSV = "candidate_universe.tsv"
ZERO_SUPPORT_TSV = "candidate_universe_zero_support.tsv"
SUMMARY_JSON = "candidate_universe_summary.json"
MANIFEST_JSON = "candidate_universe_traceability.json"

UNIPROT_TSV = (
    DATA_EXTERNAL_DIR / "uniprot_human_surface_candidates"
    / "uniprot_human_surface_candidates.tsv"
)
GO_TSV = (
    DATA_EXTERNAL_DIR / "go_human_surface_annotations"
    / "go_human_surface_annotations_by_gene_product.tsv"
)
SURFY_TSV = DATA_PROCESSED_DIR / "surfy" / "surfy_human_snapshot.tsv"
CSPA_TSV = DATA_PROCESSED_DIR / "cspa" / "cspa_human_snapshot.tsv"
DEEPTMHMM_CAN_TSV = DATA_PROCESSED_DIR / "deeptmhmm" / "deeptmhmm_human_canonical.tsv"
DEEPTMHMM_ISO_TSV = DATA_PROCESSED_DIR / "deeptmhmm" / "deeptmhmm_human_isoforms.tsv"
HPA_TSV = DATA_PROCESSED_DIR / "hpa" / "hpa_human_snapshot.tsv"
COMPARTMENTS_TSV = (
    DATA_PROCESSED_DIR / "jensenlab_compartments"
    / "jensenlab_compartments_human_snapshot.tsv"
)
ACCESSION_HISTORY_DIR = DATA_EXTERNAL_DIR / "uniprot_accession_history"
SEC_AC_TXT = ACCESSION_HISTORY_DIR / "sec_ac.txt"
DELAC_SP_TXT = ACCESSION_HISTORY_DIR / "delac_sp.txt"

FLAG_COLUMNS = [
    "uniprot_surface_flag",
    "go_surface_flag",
    "surfy_surface_flag",
    "cspa_surface_flag",
    "deeptmhmm_surface_flag",
    "hpa_surface_flag",
    "compartments_surface_flag",
]
DB_FLAG_COLUMNS = [
    "uniprot_surface_flag",
    "go_surface_flag",
    "surfy_surface_flag",
    "cspa_surface_flag",
    "hpa_surface_flag",
    "compartments_surface_flag",
]


# CSPA Table_B category labels, in descending confidence order.
# The strings are repeated by design — they're the literal values UniProt
# parsed from the CSPA spreadsheet, and live here so a typo becomes a
# NameError at the call site rather than a silent miss.
CSPA_HIGH_CONFIDENCE = "1 - high confidence"
CSPA_PUTATIVE = "2 - putative"
CSPA_UNSPECIFIC = "3 - unspecific"
CSPA_KNOWN_CATEGORIES = (CSPA_HIGH_CONFIDENCE, CSPA_PUTATIVE, CSPA_UNSPECIFIC)
CSPA_CATEGORY_PRIORITY = {label: rank for rank, label in enumerate(reversed(CSPA_KNOWN_CATEGORIES), start=1)}


def _best_cspa_category(values: pd.Series) -> str:
    """Pick the highest-priority CSPA category across pre-collapse rows.

    Priority: high confidence > putative > unspecific > blank. This makes
    the collapsed ``cspa_category`` string consistent with the boolean
    flags (``cspa_is_high_confidence`` max and ``cspa_is_unspecific``
    min), avoiding the case where an allele's "high confidence" boolean
    wins while the category string is left as "2 - putative".
    """
    scored = [
        (CSPA_CATEGORY_PRIORITY.get(str(v), 0), str(v))
        for v in values
        if isinstance(v, str) and v.strip()
    ]
    if not scored:
        return ""
    scored.sort(key=lambda t: t[0], reverse=True)
    return scored[0][1]


def _first_nonempty_symbol(values: pd.Series) -> str:
    """Pick the first non-empty, non-``"0"`` string — protects gene-symbol
    collapses from CSPA's occasional ``"0"`` placeholder overriding a real
    symbol when ``first`` happens to hit the placeholder row.
    """
    for v in values:
        if isinstance(v, str):
            s = v.strip()
            if s and s != "0":
                return s
    return ""


def _normalize_accessions(
    df: pd.DataFrame,
    *,
    sec_ac: dict[str, list[str]],
    delac_sp: set[str],
    source_name: str,
    agg_override: dict[str, object] | None = None,
) -> tuple[pd.DataFrame, NormalizeStats]:
    """Rewrite secondary UniProt accessions to their current primaries.

    - Deleted Swiss-Prot accessions are dropped.
    - Secondary accessions are replaced by the current primary. If UniProt
      has split an old entry into multiple primaries, the row is duplicated
      once per primary and each derived row carries
      ``split_mapping_ambiguous = 1`` so downstream can distinguish
      "confident remap" from "one-of-N possible descendants" (the old
      annotation applies to at most one of the derived entries, not all).
    - Rows that collapse onto the same primary are aggregated. Default
      reducers are ``max`` for numeric columns and ``first`` for strings;
      pass ``agg_override`` to replace the reducer for specific columns
      (used for CSPA to preserve categorical semantics).
    - ``split_mapping_ambiguous`` uses ``min`` so a primary gains the
      ambiguous flag only if *every* pre-collapse row reaching it came
      from a split remap (any confident pre-collapse row clears the
      flag).

    Returns the normalized DataFrame plus a stats dict for traceability.
    """
    key = "uniprot_accession"
    df = df.copy()
    df[key] = df[key].astype(str).str.strip()

    n_in = len(df)
    n_deleted = int(df[key].isin(delac_sp).sum())
    df = df[~df[key].isin(delac_sp)].copy()

    is_secondary = df[key].isin(sec_ac)
    n_secondary_rows = int(is_secondary.sum())

    df["_primaries"] = df[key].map(lambda a: sec_ac.get(a, [a]))
    df["_primary_count"] = df["_primaries"].map(len)
    n_split_rewrites = int(
        df.loc[is_secondary, "_primaries"].map(len).sum() - n_secondary_rows
    )
    # Mark every explosion of a split accession (one secondary → 2+ primaries)
    # as ambiguous BEFORE the explode + groupby collapse.
    df["split_mapping_ambiguous"] = (df["_primary_count"] >= 2).astype(int)
    df = df.explode("_primaries").reset_index(drop=True)
    df[key] = df["_primaries"].astype(str)
    df = df.drop(columns=["_primaries", "_primary_count"])

    agg: dict[str, object] = {}
    for col in df.columns:
        if col == key:
            continue
        if pd.api.types.is_numeric_dtype(df[col]):
            agg[col] = "max"
        else:
            agg[col] = "first"
    # ``min`` so only primaries whose every contributing row was itself
    # ambiguous keep the flag; a confident (non-split) remap clears it.
    agg["split_mapping_ambiguous"] = "min"
    if agg_override:
        agg.update(agg_override)
    collapsed = df.groupby(key, as_index=False).agg(agg)

    stats: NormalizeStats = {
        "source": source_name,
        "input_rows": int(n_in),
        "deleted_rows_dropped": int(n_deleted),
        "secondary_rows_rewritten": int(n_secondary_rows),
        "split_duplications": int(n_split_rewrites),
        "output_rows": int(len(collapsed)),
    }
    return collapsed, stats


def _load_uniprot() -> pd.DataFrame:
    df = pd.read_csv(UNIPROT_TSV, sep="\t", dtype=str)
    df = df.rename(columns={"accession": "uniprot_accession", "entry_name": "uniprot_entry_name"})
    df = df[["uniprot_accession", "uniprot_entry_name", "gene_primary"]].copy()
    df["uniprot_surface_flag"] = 1
    return df


def _load_go() -> pd.DataFrame:
    """Load GO per-gene-product annotations and derive evidence-tier flags.

    Per plan step 4, experimental/curated/sequence-based annotations are
    treated as surface-positive; pure-electronic (IEA-only) rows are kept
    for transparency but do not set ``go_surface_flag`` (they count toward
    ``go_low_confidence_only`` instead). Downstream agreement counts
    therefore exclude electronic-only support.
    """
    df = pd.read_csv(GO_TSV, sep="\t", dtype=str)
    df = df.rename(
        columns={
            "DB_Object_ID": "uniprot_accession",
            "DB_Object_Symbol": "go_gene_symbol",
            "n_go_ids": "go_n_go_ids",
            "has_experimental": "go_has_experimental",
            "has_curated": "go_has_curated",
            "has_sequence": "go_has_sequence",
            "has_electronic": "go_has_electronic",
        }
    )
    keep = [
        "uniprot_accession",
        "go_gene_symbol",
        "go_n_go_ids",
        "go_has_experimental",
        "go_has_curated",
        "go_has_sequence",
        "go_has_electronic",
    ]
    df = df[keep].copy()
    df["go_n_go_ids"] = pd.to_numeric(df["go_n_go_ids"], errors="coerce").astype("Int64")
    for tier_col in ("go_has_experimental", "go_has_curated",
                      "go_has_sequence", "go_has_electronic"):
        df[tier_col] = pd.to_numeric(df[tier_col], errors="coerce").fillna(0).astype(int)
    df["go_low_confidence_only"] = (
        (df["go_has_electronic"] >= 1)
        & (df["go_has_experimental"] == 0)
        & (df["go_has_curated"] == 0)
        & (df["go_has_sequence"] == 0)
    ).astype(int)
    df["go_surface_flag"] = (df["go_low_confidence_only"] == 0).astype(int)
    return df


def _load_surfy() -> pd.DataFrame:
    """Load SURFY restricted to entries labeled as surface.

    The SURFY snapshot includes 20,193 rows covering SURFY ``surface``,
    ``nonsurface``, and unclassified proteins. For the M1 candidate-universe
    merge we only want the surface-positive subset (``surfy_is_surface == 1``);
    otherwise 17k explicit non-surface SURFY rows outer-merge in and inflate
    the ``n_sources_surface = 0`` bucket with non-candidates.
    """
    df = pd.read_csv(
        SURFY_TSV,
        sep="\t",
        dtype={"uniprot_accession": str, "gene_symbol": str, "surfy_label": str},
    )
    df = df.rename(columns={"gene_symbol": "surfy_gene_symbol"})
    df["surfy_is_surface"] = df["surfy_is_surface"].fillna(0).astype(int)
    df = df[df["surfy_is_surface"] == 1].copy()
    df["surfy_surface_flag"] = 1
    keep = ["uniprot_accession", "surfy_gene_symbol", "surfy_label",
            "surfy_ml_score", "surfy_surface_flag"]
    return df[keep]


def _load_cspa() -> pd.DataFrame:
    """Load CSPA detections with a provenance-preserving surface flag.

    CSPA Table_B labels each protein as ``high confidence`` / ``putative``
    / ``unspecific``, with a small residue (8 rows in the 2015 snapshot)
    detected via Table_A but never classified in Table_B (blank category).
    Only the explicitly positive categories count as surface support:

        cspa_surface_flag = cspa_is_high_confidence OR cspa_is_putative

    ``unspecific`` rows (non-specific detections / contaminants) and
    blank-category rows stay in the merge with ``cspa_surface_flag = 0``
    and their provenance columns set, so downstream can distinguish
    "absent from CSPA" from "seen only as unspecific" from "detected but
    not classified". ``cspa_category_missing`` is derived here rather
    than upstream so the merge-input semantics are self-contained.
    """
    df = pd.read_csv(
        CSPA_TSV,
        sep="\t",
        dtype={"uniprot_accession": str, "gene_symbol": str, "cspa_category": str},
    )
    df = df.rename(columns={"gene_symbol": "cspa_gene_symbol"})
    for col in ("cspa_is_high_confidence", "cspa_is_putative", "cspa_is_unspecific"):
        df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0).astype(int)
    df["cspa_category_missing"] = (
        (df["cspa_is_high_confidence"] == 0)
        & (df["cspa_is_putative"] == 0)
        & (df["cspa_is_unspecific"] == 0)
    ).astype(int)
    df["cspa_surface_flag"] = (
        (df["cspa_is_high_confidence"] == 1) | (df["cspa_is_putative"] == 1)
    ).astype(int)
    keep = [
        "uniprot_accession",
        "cspa_gene_symbol",
        "cspa_category",
        "cspa_is_high_confidence",
        "cspa_is_putative",
        "cspa_is_unspecific",
        "cspa_category_missing",
        "cspa_surface_flag",
    ]
    return df[keep].copy()


def _load_deeptmhmm() -> pd.DataFrame:
    can = pd.read_csv(DEEPTMHMM_CAN_TSV, sep="\t", dtype=str)
    iso = pd.read_csv(DEEPTMHMM_ISO_TSV, sep="\t", dtype=str)
    can["_source_cohort"] = "human_canonical"
    iso["_source_cohort"] = "human_isoforms"
    df = pd.concat([can, iso], ignore_index=True)
    df["predicted_surface_membrane"] = pd.to_numeric(
        df["predicted_surface_membrane"], errors="coerce"
    ).fillna(0).astype(int)

    # Collapse to base accession: surface_flag = any isoform is surface-membrane.
    # When picking a representative label, prefer rows whose label is consistent
    # with the surface flag (is_surface=1), then prefer the canonical cohort as
    # tiebreaker. This avoids the pathological case where the surface flag is
    # driven by an isoform but the canonical row (labeled SP or GLOB) wins the
    # representative-row selection and produces a label inconsistent with the
    # flag (observed for Q11206, Q8IYS5, Q9BT76 under the previous ordering).
    df["_is_surface"] = df["predicted_surface_membrane"]
    df["_rank"] = (
        df["_is_surface"] * 2
        + (df["_source_cohort"] == "human_canonical").astype(int)
    )
    df = df.sort_values(["uniprot_accession", "_rank"], ascending=[True, False])

    surface_flag = (
        df.groupby("uniprot_accession")["predicted_surface_membrane"].max().rename(
            "deeptmhmm_surface_flag"
        )
    )
    rep = df.drop_duplicates(subset=["uniprot_accession"], keep="first")[
        ["uniprot_accession", "deeptmhmm_label", "_source_cohort"]
    ].rename(columns={"_source_cohort": "deeptmhmm_label_source"})
    out = rep.merge(surface_flag, on="uniprot_accession", how="left")
    return out


def _load_hpa() -> pd.DataFrame:
    """Load HPA subcellular_location snapshot keyed on UniProt primary.

    The build_hpa.py output is already mapped ENSG → UniProt primary,
    with per-ENSG evidence duplicated onto each primary and
    ``hpa_split_mapping_ambiguous`` set for split cases. Here we
    collapse any remaining per-primary duplicates (one primary hit by
    multiple ENSGs) with boolean-OR semantics on the evidence flags.

    Columns carried through with domain-specific reducers:

    - per-tier PM / junction booleans: max (boolean OR across ENSGs)
    - state columns (pm_accessible, junctional, trafficking, secreted_only,
      surface_flag): max; except secreted_only uses min because it's a
      "this is ALL we have" label — any non-secreted evidence on a
      co-mapping ENSG clears it
    - reliability enums (pm_reliability / junction_reliability): recomputed
      post-groupby from the collapsed per-tier booleans so they stay
      consistent with those columns
    - low_confidence_only: recomputed post-groupby from the collapsed
      surface_flag
    """
    df = pd.read_csv(
        HPA_TSV,
        sep="\t",
        dtype={"uniprot_accession": str, "hpa_gene_symbol": str,
               "hpa_reliability": str, "hpa_pm_reliability": str,
               "hpa_junction_reliability": str,
               "hpa_locations": str, "hpa_go_ids": str,
               "ensembl_gene_id": str},
    ).fillna("")

    bool_cols = [
        "hpa_surface_flag",
        "hpa_low_confidence_only",
        "hpa_pm_accessible",
        "hpa_junctional",
        "hpa_secreted_only",
        "hpa_trafficking_associated",
        "hpa_pm_in_enhanced", "hpa_pm_in_supported",
        "hpa_pm_in_approved", "hpa_pm_in_uncertain",
        "hpa_cj_in_enhanced", "hpa_cj_in_supported",
        "hpa_cj_in_approved", "hpa_cj_in_uncertain",
        "hpa_has_extracellular",
        "hpa_split_mapping_ambiguous",
    ]
    for col in bool_cols:
        df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0).astype(int)

    def _join_nonempty(values: pd.Series) -> str:
        seen: set[str] = set()
        parts: list[str] = []
        for v in values:
            if not isinstance(v, str) or not v:
                continue
            for p in v.split(";" if ";" in v else "|"):
                p = p.strip()
                if p and p not in seen:
                    seen.add(p)
                    parts.append(p)
        return ";".join(parts)

    grouped = df.groupby("uniprot_accession", as_index=False).agg(
        hpa_gene_symbol=("hpa_gene_symbol", "first"),
        hpa_ensembl_gene_id=("ensembl_gene_id", lambda s: "|".join(sorted(set(
            str(v) for v in s if isinstance(v, str) and v
        )))),
        hpa_reliability=("hpa_reliability", "first"),
        hpa_locations=("hpa_locations", _join_nonempty),
        hpa_go_ids=("hpa_go_ids", _join_nonempty),
        hpa_surface_flag=("hpa_surface_flag", "max"),
        hpa_pm_accessible=("hpa_pm_accessible", "max"),
        hpa_junctional=("hpa_junctional", "max"),
        # secreted_only uses min: a primary retains the "secreted only"
        # label only if EVERY contributing ENSG was secreted-only. Any
        # ENSG with PM or junction evidence clears it.
        hpa_secreted_only=("hpa_secreted_only", "min"),
        hpa_trafficking_associated=("hpa_trafficking_associated", "max"),
        hpa_has_extracellular=("hpa_has_extracellular", "max"),
        hpa_pm_in_enhanced=("hpa_pm_in_enhanced", "max"),
        hpa_pm_in_supported=("hpa_pm_in_supported", "max"),
        hpa_pm_in_approved=("hpa_pm_in_approved", "max"),
        hpa_pm_in_uncertain=("hpa_pm_in_uncertain", "max"),
        hpa_cj_in_enhanced=("hpa_cj_in_enhanced", "max"),
        hpa_cj_in_supported=("hpa_cj_in_supported", "max"),
        hpa_cj_in_approved=("hpa_cj_in_approved", "max"),
        hpa_cj_in_uncertain=("hpa_cj_in_uncertain", "max"),
        # Pass the upstream ENSG-level split-ambiguity flag into
        # _normalize_accessions' ``split_mapping_ambiguous`` column so
        # the default ``min`` reducer combines it with any accession-
        # history-level ambiguity (HPA's UP primaries are already
        # current, so this always arrives as 0 from the history side,
        # but the upstream ENSG-level flag is preserved).
        split_mapping_ambiguous=("hpa_split_mapping_ambiguous", "min"),
    )

    # Re-derive per-collapse-level tier enums from the post-groupby
    # booleans so they stay consistent with those columns.
    def _best_tier_row(row: pd.Series, prefix: str) -> str:
        for tier in ("enhanced", "supported", "approved", "uncertain"):
            if row[f"hpa_{prefix}_in_{tier}"] == 1:
                return tier
        return ""

    grouped["hpa_pm_reliability"] = grouped.apply(
        lambda r: _best_tier_row(r, "pm"), axis=1
    )
    grouped["hpa_junction_reliability"] = grouped.apply(
        lambda r: _best_tier_row(r, "cj"), axis=1
    )
    grouped["hpa_low_confidence_only"] = (grouped["hpa_surface_flag"] == 0).astype(int)

    return grouped


def _load_compartments() -> pd.DataFrame:
    """Load JensenLab COMPARTMENTS snapshot keyed on UniProt primary.

    Same collapse semantics as HPA: one row per UniProt primary, max on
    per-channel stars and on the surface flag, min on the split-
    ambiguity flag.
    """
    df = pd.read_csv(
        COMPARTMENTS_TSV,
        sep="\t",
        dtype={"uniprot_accession": str, "ensembl_protein_id": str,
               "compartments_gene_symbol": str, "compartments_surface_terms": str},
    ).fillna("")
    for col in (
        "compartments_integrated_stars_max",
        "compartments_knowledge_stars_max",
        "compartments_experiments_stars_max",
        "compartments_textmining_stars_max",
        "compartments_predictions_stars_max",
    ):
        df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0.0).astype(float)
    for col in (
        "compartments_low_confidence_only",
        "compartments_surface_flag",
        "compartments_split_mapping_ambiguous",
    ):
        df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0).astype(int)

    def _join_terms(values: pd.Series) -> str:
        seen: set[str] = set()
        parts: list[str] = []
        for v in values:
            if not isinstance(v, str) or not v:
                continue
            for p in v.split(","):
                p = p.strip()
                if p and p not in seen:
                    seen.add(p)
                    parts.append(p)
        return ",".join(parts)

    grouped = df.groupby("uniprot_accession", as_index=False).agg(
        compartments_gene_symbol=("compartments_gene_symbol", "first"),
        compartments_ensembl_protein_id=("ensembl_protein_id", lambda s: "|".join(sorted(set(
            str(v) for v in s if isinstance(v, str) and v
        )))),
        compartments_integrated_stars_max=("compartments_integrated_stars_max", "max"),
        compartments_knowledge_stars_max=("compartments_knowledge_stars_max", "max"),
        compartments_experiments_stars_max=("compartments_experiments_stars_max", "max"),
        compartments_textmining_stars_max=("compartments_textmining_stars_max", "max"),
        compartments_predictions_stars_max=("compartments_predictions_stars_max", "max"),
        compartments_surface_terms=("compartments_surface_terms", _join_terms),
        compartments_low_confidence_only=("compartments_low_confidence_only", "min"),
        compartments_surface_flag=("compartments_surface_flag", "max"),
        # Upstream ENSP-level split-ambiguity flag carried through the
        # normalizer's generic ``split_mapping_ambiguous`` column; see
        # comment in _load_hpa.
        split_mapping_ambiguous=("compartments_split_mapping_ambiguous", "min"),
    )
    return grouped


def _consolidate_gene_symbol(row: pd.Series) -> str:
    for col in (
        "gene_primary",
        "surfy_gene_symbol",
        "cspa_gene_symbol",
        "go_gene_symbol",
        "hpa_gene_symbol",
        "compartments_gene_symbol",
    ):
        val = row.get(col)
        if isinstance(val, str) and val.strip():
            return val.strip()
    return ""


def _as_upper_list(value: object) -> list[str]:
    """Normalize a scalar/list value into uppercase string tokens."""
    if value is None:
        return []
    if isinstance(value, list):
        raw_values = value
    else:
        raw_values = [value]
    return [
        str(item).strip().upper()
        for item in raw_values
        if str(item).strip()
    ]


def _resolve_gene_symbols_with_mygene(
    symbols: list[str],
) -> tuple[pd.DataFrame, dict[str, int]]:
    """Resolve gene symbols with a single MyGene batch query (no fallback).

    Resolver statuses intentionally mirror the nomenclature statuses used in
    the tess/coral resolver stack:
    - ``exact``
    - ``normalized_alias``
    - ``normalized_previous``
    - ``ambiguous``
    - ``not_found``
    """
    if not symbols:
        empty = pd.DataFrame(
            columns=[
                "gene_symbol_query",
                "gene_symbol_resolved",
                "gene_symbol_mapping_status",
                "gene_symbol_mygene_score",
            ]
        )
        return empty, {
            "n_query_symbols": 0,
            "n_exact": 0,
            "n_normalized_alias": 0,
            "n_normalized_previous": 0,
            "n_ambiguous": 0,
            "n_not_found": 0,
        }

    mg = mygene.MyGeneInfo()
    try:
        raw_hits = mg.querymany(
            symbols,
            scopes="symbol,alias,prev_symbol",
            fields="symbol,alias,prev_symbol",
            species="human",
            as_dataframe=False,
            returnall=False,
            verbose=False,
        )
    except Exception as exc:  # pragma: no cover - network/runtime dependent
        raise RuntimeError(
            "MyGene symbol resolution failed for candidate-universe merge "
            "(no fallback configured)."
        ) from exc

    hits_by_query: dict[str, list[dict[str, object]]] = {}
    for raw in raw_hits:
        if not isinstance(raw, dict):
            continue
        query = str(raw.get("query", "")).strip().upper()
        if not query:
            continue
        hits_by_query.setdefault(query, []).append(raw)

    def _candidate(hit: dict[str, object], query: str) -> tuple[int, float, str, str] | None:
        symbol = str(hit.get("symbol", "")).strip().upper()
        if not symbol:
            return None
        score_value = hit.get("_score", 0.0)
        score = float(score_value) if isinstance(score_value, str | int | float) else 0.0
        aliases = set(_as_upper_list(hit.get("alias")))
        prev_symbols = set(_as_upper_list(hit.get("prev_symbol")))
        if symbol == query:
            return (0, score, symbol, "exact")
        if query in prev_symbols:
            return (1, score, symbol, "normalized_previous")
        if query in aliases:
            return (2, score, symbol, "normalized_alias")
        return None

    records: list[dict[str, object]] = []
    for query in symbols:
        candidates: list[tuple[int, float, str, str]] = []
        for hit in hits_by_query.get(query, []):
            if hit.get("notfound"):
                continue
            parsed = _candidate(hit, query)
            if parsed is not None:
                candidates.append(parsed)

        if not candidates:
            records.append(
                {
                    "gene_symbol_query": query,
                    "gene_symbol_resolved": "",
                    "gene_symbol_mapping_status": "not_found",
                    "gene_symbol_mygene_score": 0.0,
                }
            )
            continue

        best_rank = min(rank for rank, _score, _symbol, _status in candidates)
        best_rank_rows = [row for row in candidates if row[0] == best_rank]
        best_score = max(score for _rank, score, _symbol, _status in best_rank_rows)
        best_rows = [
            row for row in best_rank_rows if abs(row[1] - best_score) < 1e-12
        ]
        best_symbols = sorted({symbol for _rank, _score, symbol, _status in best_rows})

        if len(best_symbols) > 1:
            records.append(
                {
                    "gene_symbol_query": query,
                    "gene_symbol_resolved": "",
                    "gene_symbol_mapping_status": "ambiguous",
                    "gene_symbol_mygene_score": float(best_score),
                }
            )
            continue

        chosen = sorted(
            best_rows,
            key=lambda row: (row[0], -row[1], row[2]),
        )[0]
        _rank, score, symbol, status = chosen
        records.append(
            {
                "gene_symbol_query": query,
                "gene_symbol_resolved": symbol,
                "gene_symbol_mapping_status": status,
                "gene_symbol_mygene_score": float(score),
            }
        )

    result = pd.DataFrame.from_records(records).sort_values("gene_symbol_query")
    mapping_counts = (
        result["gene_symbol_mapping_status"].value_counts(dropna=False).to_dict()
    )
    stats = {
        "n_query_symbols": len(symbols),
        "n_exact": int(mapping_counts.get("exact", 0)),
        "n_normalized_alias": int(mapping_counts.get("normalized_alias", 0)),
        "n_normalized_previous": int(mapping_counts.get("normalized_previous", 0)),
        "n_ambiguous": int(mapping_counts.get("ambiguous", 0)),
        "n_not_found": int(mapping_counts.get("not_found", 0)),
    }
    return result, stats


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
        "uniprot": _load_uniprot(),
        "go": _load_go(),
        "surfy": _load_surfy(),
        "cspa": _load_cspa(),
        "deeptmhmm": _load_deeptmhmm(),
        "hpa": _load_hpa(),
        "compartments": _load_compartments(),
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
            "cspa_category": _best_cspa_category,
            "cspa_gene_symbol": _first_nonempty_symbol,
            # Default max reducer captures boolean-OR pre-collapse evidence
            # for the *_precollapse provenance columns added below.
        },
        "surfy": {
            "surfy_gene_symbol": _first_nonempty_symbol,
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
        norm_df, stats = _normalize_accessions(
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

    for col in FLAG_COLUMNS:
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
    # when another source has independently flagged the protein as
    # surface. Without this gate, dictionary-based NER over Medline
    # picks up contextual literature co-mentions for non-surface
    # proteins (TP53, MYC, ALB, IL1B, ...) and admits them. See
    # ``docs/reports/2026-04-17-jensenlab-compartments-integration.md``
    # for the rationale and rejected looser predicates.
    def _num(col: str) -> pd.Series:
        if col not in merged.columns:
            return pd.Series(0, index=merged.index)
        return pd.to_numeric(merged[col], errors="coerce").fillna(0)

    other_source_flagged = (
        (_num("uniprot_surface_flag") == 1)
        | (_num("go_surface_flag") == 1)
        | (_num("surfy_surface_flag") == 1)
        | (_num("cspa_surface_flag") == 1)
        | (_num("deeptmhmm_surface_flag") == 1)
        | (_num("hpa_surface_flag") == 1)
    )
    merged["compartments_corroborated"] = other_source_flagged.astype(int)
    merged.loc[~other_source_flagged, "compartments_surface_flag"] = 0

    merged["gene_symbol_input"] = merged.apply(_consolidate_gene_symbol, axis=1)
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
    gene_resolution, gene_resolution_stats = _resolve_gene_symbols_with_mygene(
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

    merged["n_sources_surface"] = merged[FLAG_COLUMNS].sum(axis=1).astype(int)
    merged["in_db_union"] = (merged[DB_FLAG_COLUMNS].sum(axis=1) > 0).astype(int)
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
        return ",".join(name_map[c] for c in FLAG_COLUMNS if row[c] == 1)

    merged["sources_present"] = merged.apply(_sources_present, axis=1)

    out_cols = [
        "uniprot_accession",
        "gene_symbol_input",
        "gene_symbol",
        "gene_symbol_mapping_status",
        "gene_symbol_resolved",
        "gene_symbol_mygene_score",
        "uniprot_entry_name",
        *FLAG_COLUMNS,
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
    #   - the candidate universe (n_sources_surface >= 1): at least one
    #     source has set its own surface flag under its own rule. These
    #     are the rows the downstream per-gene LLM reconciliation runs on.
    #   - the zero-support pool (n_sources_surface == 0): present in some
    #     raw source but filtered out of every positive-flag rule (GO-IEA-
    #     only, CSPA unspecific / blank, HPA secreted-only, accession-history-
    #     split-ambiguous, COMPARTMENTS below corroboration). Retained as a
    #     separate file for traceability; they carry no positive evidence so
    #     have nothing for the LLM to reconcile.
    merged_all = merged
    merged = merged_all[merged_all["n_sources_surface"] >= 1].copy().reset_index(drop=True)
    zero_support = merged_all[merged_all["n_sources_surface"] == 0].copy().reset_index(drop=True)

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
    # build_jensenlab_compartments.py. Any change here must also update
    # the loader, the ``flag_rules`` block, and the threshold referenced
    # in src/accessible_surfaceome/candidates/download_jensenlab_compartments.py
    # SURFACE_TERMS (GO set) / anywhere else it surfaces.
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
    per_source_counts = {name_map[c]: int(merged[c].sum()) for c in FLAG_COLUMNS}

    n_sources_total = len(FLAG_COLUMNS)
    n_db_sources_total = len(DB_FLAG_COLUMNS)
    agreement_counts = {
        f"{k}_of_{n_sources_total}": int((merged["n_sources_surface"] == k).sum())
        for k in range(0, n_sources_total + 1)
    }

    # Pairwise overlap (Jaccard) across every flag pair
    pairwise = {}
    for i, a in enumerate(FLAG_COLUMNS):
        for b in FLAG_COLUMNS[i + 1 :]:
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

    # All-sources intersection and all-DB agreement
    all_sources = int((merged["n_sources_surface"] == n_sources_total).sum())
    all_db = int(((merged[DB_FLAG_COLUMNS].sum(axis=1) == n_db_sources_total)).sum())

    summary = {
        "generated_at_utc": utc_now_iso(),
        "n_rows_total": int(len(merged)),
        "n_zero_support_rows_excluded": int(len(zero_support)),
        "n_in_db_union": int(merged["in_db_union"].sum()),
        "n_ml_only_edge_cases": int(merged["ml_only_edge_case"].sum()),
        "gene_symbol_resolution": gene_resolution_stats,
        "n_sources": n_sources_total,
        "n_db_sources": n_db_sources_total,
        "per_source_counts": per_source_counts,
        "agreement_counts": agreement_counts,
        f"n_with_all_{n_sources_total}_sources": all_sources,
        f"n_with_all_{n_db_sources_total}_db_sources": all_db,
        "pairwise_overlap": pairwise,
        "accession_normalization": norm_stats,
    }
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
                "filter": "n_sources_surface >= 1",
            },
            ZERO_SUPPORT_TSV: {
                "local_path": str(out_zero_tsv.relative_to(REPO_ROOT)),
                "sha256": sha256_file(tmp_zero_tsv),
                "size_bytes": tmp_zero_tsv.stat().st_size,
                "n_rows": int(len(zero_support)),
                "primary_key": "uniprot_accession",
                "filter": "n_sources_surface == 0 (accession present in a raw source but filtered out of every positive-flag rule — retained for traceability only)",
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
            "compartments_surface_flag": "1 iff max(compartments_experiments_stars_max, compartments_textmining_stars_max) >= 3 over the surface GO terms {GO:0005886, GO:0009986, GO:0031225, GO:0005887} AND compartments_split_mapping_ambiguous == 0 AND compartments_corroborated == 1. Corroboration requires at least one other source (uniprot, go, surfy, cspa, deeptmhmm, hpa) to have independently set its OWN surface_flag == 1 — see the compartments_corroborated entry for details. Rationale: the JensenLab tagger's dictionary-based NER over Medline picks up literature co-occurrences with 'plasma membrane' for many contextually-mentioned non-surface proteins (TP53, MYC, ALB, INS, IFNG, IL1B, IL13, IL17A, NGF, FGF4, FGF8, BCL2, NFE2L2 etc.) that are not therapeutic-delivery targets. Requiring another source to have passed its own surface-flag bar is the tightest available corroboration and prevents these lone-textmining calls from entering the universe; looser predicates (raw pool membership, GO-IEA-only, HPA-Uncertain-tier) were tried and leaked false positives. Three of the four COMPARTMENTS channels are carried as provenance only: (a) knowledge re-ingests GO + UniProt-SubCell (would triple-count existing first-class GO evidence); (b) predictions wraps WoLF PSORT + YLoc, sequence-based predictors in the same family as SURFY + DeepTMHMM (would triple-count ML-predictor evidence; empirically drives ~73%% of pre-filter hits); (c) experiments rows with source == 'HPA' are dropped upstream to avoid double-counting first-class HPA IF evidence. See docs/reports/2026-04-17-jensenlab-compartments-integration.md.",
            "compartments_corroborated": "1 iff at least one of the six other sources has independently flagged the protein as surface — i.e. uniprot_surface_flag OR go_surface_flag OR surfy_surface_flag OR cspa_surface_flag OR deeptmhmm_surface_flag OR hpa_surface_flag equals 1. Each source's own surface-flag rule encodes its 'this protein is membrane-accessible' predicate (go_surface_flag excludes pure-IEA, hpa_surface_flag requires PM/junctional at Enhanced/Supported/Approved tier, cspa_surface_flag requires high-confidence/putative, etc.), so requiring another source to have passed its own surface-flag bar is the correct corroboration threshold for therapeutic-delivery purposes. Looser predicates (raw pool membership, GO-IEA-only, HPA-Uncertain-tier) were tried and leaked false positives on cytokines / transcription factors / secreted proteins. Gates compartments_surface_flag.",
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
    print(f"  agreement (k/{n_sources_total} sources): {agreement_counts}")
    print(f"  all {n_sources_total} sources agree:       {all_sources:,}")
    print(f"  all {n_db_sources_total} DB sources agree:    {all_db:,}")


if __name__ == "__main__":
    main()
