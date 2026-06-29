"""Per-source loaders for the candidate-universe merge.

One ``load_<source>`` function per data source, each returning a
DataFrame keyed on ``uniprot_accession`` with a ``<source>_surface_flag``
boolean derived from the source's evidence rule. The merge orchestrator
in ``__init__.py`` runs these, reconciles each result against the current
UniProt accession history, and outer-merges them on ``uniprot_accession``.

The six loaders are deliberately one-per-source (not abstracted via a
common interface): each source's evidence semantics is different enough
that a shared base would obscure the per-source rules rather than make
them clearer.
"""

from __future__ import annotations

import pandas as pd

from accessible_surfaceome.paths import (
    DATA_EXTERNAL_DIR,
    DATA_PROCESSED_DIR,
)

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


# CSPA Table_B category labels, in descending confidence order.
# The strings are repeated by design — they're the literal values UniProt
# parsed from the CSPA spreadsheet, and live here so a typo becomes a
# NameError at the call site rather than a silent miss.
CSPA_HIGH_CONFIDENCE = "1 - high confidence"
CSPA_PUTATIVE = "2 - putative"
CSPA_UNSPECIFIC = "3 - unspecific"
CSPA_KNOWN_CATEGORIES = (CSPA_HIGH_CONFIDENCE, CSPA_PUTATIVE, CSPA_UNSPECIFIC)
CSPA_CATEGORY_PRIORITY = {label: rank for rank, label in enumerate(reversed(CSPA_KNOWN_CATEGORIES), start=1)}


def best_cspa_category(values: pd.Series) -> str:
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


def first_nonempty_symbol(values: pd.Series) -> str:
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


UNIPROT_STRICT_SURFACE_TERMS = (
    "Cell surface",
    "Apical cell membrane",
    "Basolateral cell membrane",
    "GPI-anchor",
)


def load_uniprot() -> pd.DataFrame:
    """Load UniProt candidates and flag only strictly surface-localized rows.

    The upstream fetch query is broad (``Cell membrane`` plus the strict terms
    plus ``Extracellular`` topology) so the cached TSV serves both the M1
    candidate list and any future broader sweep. For M1 we tighten the
    surface flag to require either an explicit cell-surface / apical /
    basolateral / GPI subcellular location or at least one extracellular
    topology feature. Plain ``Cell membrane`` annotations are excluded — they
    include cytoplasmic-side and lateral-membrane proteins that aren't
    apples-to-apples with the other sources' surface labels.
    """
    df = pd.read_csv(UNIPROT_TSV, sep="\t", dtype=str)
    df = df.rename(columns={"accession": "uniprot_accession", "entry_name": "uniprot_entry_name"})

    locations = df["subcellular_locations"].fillna("")
    has_strict_term = locations.apply(
        lambda s: any(term in s.split("|") for term in UNIPROT_STRICT_SURFACE_TERMS)
    )
    extracellular = pd.to_numeric(
        df["feature_topo_extracellular_count"], errors="coerce"
    ).fillna(0).astype(int) > 0
    surface = (has_strict_term | extracellular).astype(int)

    df = df[["uniprot_accession", "uniprot_entry_name", "gene_primary"]].copy()
    df["uniprot_surface_flag"] = surface.values
    df = df[df["uniprot_surface_flag"] == 1].reset_index(drop=True)
    return df


def load_go() -> pd.DataFrame:
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


def load_surfy() -> pd.DataFrame:
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


def load_cspa() -> pd.DataFrame:
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


def load_deeptmhmm() -> pd.DataFrame:
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


def load_hpa() -> pd.DataFrame:
    """Load HPA subcellular_location snapshot keyed on UniProt primary.

    The HPA build output is already mapped ENSG → UniProt primary, with
    per-ENSG evidence duplicated onto each primary and
    ``hpa_split_mapping_ambiguous`` set for split cases. Here we collapse
    any remaining per-primary duplicates (one primary hit by multiple
    ENSGs) with boolean-OR semantics on the evidence flags.

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
        # normalize_accessions' ``split_mapping_ambiguous`` column so
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
