"""Per-source inclusion-bias audit for the v2 candidate universe.

Answers: for the 6,521 proteins in candidate_universe_v2, what features
distinguish inclusion in each of the 5 M1 source DBs (UniProt, GO, HPA,
SURFY, CSPA) vs. inclusion via Sonnet (the LLM triage layer)?

Only **non-self-referential biological features** are scored — UniProt
topology (TM count / signal / glyc / lipidation), DeepTMHMM, topology
class (GPI vs single-pass-TM vs multi-pass-TM vs signal-only-secreted
vs no-TM-no-signal vs lipid-anchor-only), Schweke homomer flag, and
macro-collapsed HGNC gene-group families (GPCR, SLC, CD molecule,
Ig-domain, RTK, Tetraspanin, Cadherin, Integrin, ABC transporter,
Voltage/Ligand-gated channel, Connexin, Claudin, MHC/HLA, TNF-receptor,
Chemokine ligand, Olfactory receptor). DB-specific evidence flags
(HPA reliability, CSPA category, SURFY ML score, COMPARTMENTS stars,
GO evidence) are intentionally excluded so each source's enrichment
reflects biology, not self-membership.

For each inclusion source, computes the enrichment of every feature in
"included rows" vs. "excluded rows of the v2 universe":
  - Continuous features: Mann-Whitney U + Cliff's delta + medians.
  - Binary features: Fisher's exact + log OR (Haldane corrected) +
    Cliff's-delta equivalent (p_in - p_out).

Outputs to data/analysis/db_vs_sonnet_inclusion/:
  - per_protein_features.tsv  -- the joined feature table (6,521 rows)
  - inclusion_enrichment.tsv  -- one row per (source, feature)
  - inclusion_heatmap.{pdf,png}  -- signed effect heatmap
  - inclusion_summary.json    -- universe sizes + per-source inclusion counts

Run from the repo root::

    uv run python scripts/audit_db_vs_sonnet_inclusion.py
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns
from scipy.stats import fisher_exact, mannwhitneyu

from accessible_surfaceome.audit._plotting_config import (
    DIVERGING_PALETTE,
    save_figure,
    setup_plotting_style,
)

REPO = Path(__file__).resolve().parents[1]
V2 = REPO / "data/processed/candidate_universe/candidate_universe_v2.tsv"
V1 = REPO / "data/processed/candidate_universe/candidate_universe.tsv"
UNIPROT = REPO / "data/external/uniprot_human_surface_candidates/uniprot_human_surface_candidates.tsv"
SCHWEKE = REPO / "data/external/schweke_homomer_atlas/surfaceome_x_schweke_homomers_full.tsv"
HGNC = REPO / "data/external/hgnc/hgnc_complete_set.tsv"
OUT_DIR = REPO / "data/analysis/db_vs_sonnet_inclusion"


# HGNC gene-group → macro-family. Order = display order in the heatmap.
# Patterns are case-insensitive substrings matched against the
# pipe-delimited ``gene_group`` cell. A gene can match multiple
# macros (it has multiple groups), and that's fine: each macro is an
# independent binary feature.
HGNC_FAMILY_PATTERNS: list[tuple[str, list[str]]] = [
    ("fam_gpcr", ["G protein-coupled receptors", "Frizzled class receptors"]),
    ("fam_olfactory_receptor", ["Olfactory receptors"]),
    ("fam_slc_transporter", ["Solute carrier"]),
    ("fam_abc_transporter", ["ATP binding cassette"]),
    ("fam_cd_molecule", ["CD molecules"]),
    ("fam_ig_domain", [
        "Immunoglobulin like domain",
        "Ig-like cell adhesion molecule",
    ]),
    ("fam_rtk", ["Receptor tyrosine kinases", "Eph receptors"]),
    ("fam_tetraspanin", ["Tetraspanins"]),
    ("fam_cadherin", ["Cadherins", "Protocadherins"]),
    ("fam_integrin", ["Integrins"]),
    ("fam_voltage_gated_channel", ["voltage-gated", "Voltage-gated"]),
    ("fam_ligand_gated_channel", ["Ligand-gated"]),
    ("fam_connexin", ["Connexins", "Gap junction"]),
    ("fam_claudin", ["Claudins"]),
    ("fam_mhc_hla", ["histocompatibility", "MHC class"]),
    ("fam_tnfrsf", ["Tumor necrosis factor receptor"]),
    ("fam_chemokine_ligand", ["Chemokine ligands"]),
    ("fam_chemokine_receptor", ["Chemokine receptors"]),
    # Inner-leaflet membrane-associated families. These are the
    # canonical "GO calls them surface, but they're cytoplasmic-face"
    # proteins (KRAS, SRC, RhoA, Gαi, etc). Expected pattern: strongly
    # positive in GO inclusion (GO's "plasma membrane" GO term doesn't
    # distinguish leaflet), negative in HPA / CSPA / SURFY and ideally
    # Sonnet.
    ("fam_ras_gtpase", ["RAS type GTPase family", "RAB, member RAS oncogene"]),
    ("fam_rho_gtpase", ["Rho family GTPases"]),
    ("fam_arf_gtpase", ["ARF GTPase family"]),
    ("fam_src_kinase", ["Src family tyrosine kinases"]),
    ("fam_g_protein_subunit", ["G protein subunits"]),
]

# Topology class — mutually exclusive bucket assigned per protein,
# then one-hot-encoded for the enrichment scoring. Priority order
# (first match wins) reflects what dominates surface presentation:
# GPI overrides "multi-pass TM" because a GPI-anchored protein with
# a stray TM-helix annotation is still GPI-anchored at the cell surface.
TOPOLOGY_CLASS_ORDER: list[str] = [
    "topo_gpi_anchored",  # outer leaflet, accessible
    "topo_intramembrane",
    "topo_gpcr_7tm",
    "topo_multi_pass_tm",
    "topo_single_pass_tm",
    "topo_signal_only_secreted",
    # Inner-leaflet lipid anchor: prenylated (KRAS, RhoA) or
    # myristoylated (SRC, LCK), no TM, no signal peptide. NOT cell
    # surface; broken out so we can see which DBs over-call it.
    "topo_inner_leaflet_lipidated",
    # Palmitoylation alone is leaflet-ambiguous; kept as its own
    # bucket so it doesn't contaminate either anchor class.
    "topo_palmitoylated_only",
    "topo_no_tm_no_signal",
]

# Feature catalog. Order is the row order in the heatmap (grouped by
# theme: topology numeric → topology class → HGNC family → orthogonal).
BINARY_FEATURES: list[str] = [
    "up_has_signal",
    "up_has_tm",
    "up_multi_pass",
    "up_has_extracellular_topo",
    "up_has_glyc",
    "up_has_lipidation",
    "deeptm_TM",
    "deeptm_SP_plus_TM",
    "deeptm_SP_only",
    "deeptm_BETA",
    "deeptm_GLOB",
    *TOPOLOGY_CLASS_ORDER,
    *(name for name, _ in HGNC_FAMILY_PATTERNS),
    "schweke_homomer",
]

CONTINUOUS_FEATURES: list[str] = [
    "up_length",
    "up_tm_count",
    "up_glyc_count",
    "up_lipidation_count",
    "up_topo_extracellular_count",
    "m1_n_db_votes",
]

INCLUSION_SOURCES: list[tuple[str, str]] = [
    ("uniprot", "src_uniprot"),
    ("go", "src_go"),
    ("hpa", "src_hpa"),
    ("surfy", "src_surfy"),
    ("cspa", "src_cspa"),
    # Single Sonnet column = sonnet_verdict in {"yes", "contextual"}.
    # The previous "sonnet_yes" strict variant correlated heavily with
    # m1_n_db_votes (sonnet only commits to strict-yes when DBs corroborate),
    # which is uninformative for biology — dropped.
    ("sonnet", "src_sonnet"),
]

# Feature provenance. Tied to row labels in the heatmap so a reader
# can see at a glance whether a row came from a sequence-level call
# (UniProt features), a predicted topology (DeepTMHMM), a curated
# gene group (HGNC), an experimental complex (Schweke), or the cohort
# meta itself. All five sources are deterministic — none are LLM-
# derived.
PROVENANCE_COLORS: dict[str, str] = {
    "UniProt (annotation count)": "#3D6B60",     # teal-mid
    "UniProt (keyword-derived)": "#7AAB9F",      # teal-light
    "DeepTMHMM (predicted topology)": "#F4AA28",  # amber-bright
    "HGNC (curated gene group)": "#8878C8",      # lavender-bright
    "Schweke 2024 (homomer atlas)": "#BC3C4C",   # maroon-light
    "Cohort meta": "#6E1428",                    # maroon-dark
}
FEATURE_PROVENANCE: dict[str, str] = {
    # UniProt feature-count columns from
    # data/external/uniprot_human_surface_candidates/uniprot_human_surface_candidates.tsv
    # (curated counts from the UniProt REST API features endpoint).
    "up_has_signal": "UniProt (annotation count)",
    "up_has_tm": "UniProt (annotation count)",
    "up_multi_pass": "UniProt (annotation count)",
    "up_has_extracellular_topo": "UniProt (annotation count)",
    "up_has_glyc": "UniProt (annotation count)",
    "up_has_lipidation": "UniProt (annotation count)",
    "up_length": "UniProt (annotation count)",
    "up_tm_count": "UniProt (annotation count)",
    "up_glyc_count": "UniProt (annotation count)",
    "up_lipidation_count": "UniProt (annotation count)",
    "up_topo_extracellular_count": "UniProt (annotation count)",
    # DeepTMHMM predicted-topology one-hots (canonical isoform, from
    # data/external/deeptmhmm_surfaceome_predictions/human_canonical_non_hla/
    # via the v1 candidate-universe TSV).
    "deeptm_TM": "DeepTMHMM (predicted topology)",
    "deeptm_SP_plus_TM": "DeepTMHMM (predicted topology)",
    "deeptm_SP_only": "DeepTMHMM (predicted topology)",
    "deeptm_BETA": "DeepTMHMM (predicted topology)",
    "deeptm_GLOB": "DeepTMHMM (predicted topology)",
    # Topology classes are derived from UniProt's `keywords` column —
    # see _derive_topology_class() for the exact rules. Specifically:
    #   topo_gpi_anchored     <- "GPI-anchor" keyword
    #   topo_intramembrane    <- "Intramembrane" keyword + 0 TM
    #   topo_gpcr_7tm         <- "G-protein coupled receptor" + tm>=5
    #   topo_multi_pass_tm    <- tm>=2 (after above buckets claim)
    #   topo_single_pass_tm   <- tm==1 (after above)
    #   topo_signal_only_*    <- sig>=1, tm==0
    #   topo_inner_leaflet_* <- "Prenylation" OR "Myristate", tm==0, sig==0
    #   topo_palmitoylated_* <- "Palmitate" (no prenyl/myr), tm==0, sig==0
    #   topo_no_tm_no_signal <- everything else with tm==0, sig==0
    "topo_gpi_anchored": "UniProt (keyword-derived)",
    "topo_intramembrane": "UniProt (keyword-derived)",
    "topo_gpcr_7tm": "UniProt (keyword-derived)",
    "topo_multi_pass_tm": "UniProt (keyword-derived)",
    "topo_single_pass_tm": "UniProt (keyword-derived)",
    "topo_signal_only_secreted": "UniProt (keyword-derived)",
    "topo_inner_leaflet_lipidated": "UniProt (keyword-derived)",
    "topo_palmitoylated_only": "UniProt (keyword-derived)",
    "topo_no_tm_no_signal": "UniProt (keyword-derived)",
    # HGNC curated `gene_group` (from data/external/hgnc/hgnc_complete_set.tsv).
    # See HGNC_FAMILY_PATTERNS for the macro -> substring-pattern map.
    **{name: "HGNC (curated gene group)" for name, _ in HGNC_FAMILY_PATTERNS},
    # Schweke 2024 homomer-prediction atlas.
    "schweke_homomer": "Schweke 2024 (homomer atlas)",
    # Cohort meta — number of M1 DBs that voted "surface" for this gene.
    "m1_n_db_votes": "Cohort meta",
}


def _load_v2() -> pd.DataFrame:
    df = pd.read_csv(V2, sep="\t", dtype=str).fillna("")
    for c in [
        "m1_uniprot_flag",
        "m1_go_flag",
        "m1_hpa_flag",
        "m1_surfy_flag",
        "m1_cspa_flag",
        "m1_n_db_votes",
    ]:
        df[c] = pd.to_numeric(df[c], errors="coerce").fillna(0).astype(int)
    df["src_uniprot"] = (df["m1_uniprot_flag"] == 1).astype(int)
    df["src_go"] = (df["m1_go_flag"] == 1).astype(int)
    df["src_hpa"] = (df["m1_hpa_flag"] == 1).astype(int)
    df["src_surfy"] = (df["m1_surfy_flag"] == 1).astype(int)
    df["src_cspa"] = (df["m1_cspa_flag"] == 1).astype(int)
    # One Sonnet column: verdict in {"yes", "contextual"} (4,233 rows).
    # The strict "yes"-only variant correlated heavily with M1 consensus
    # (Cliff's δ vs m1_n_db_votes ≈ +0.70) — dropped because that's a
    # corroboration signal, not a biology signal.
    df["src_sonnet"] = df["sonnet_verdict"].isin(["yes", "contextual"]).astype(int)
    return df


def _join_uniprot_features(df: pd.DataFrame) -> pd.DataFrame:
    up = pd.read_csv(UNIPROT, sep="\t", dtype=str).fillna("")
    keep = {
        "accession": "uniprot_accession",
        "length": "up_length",
        "feature_transmembrane_count": "up_tm_count",
        "feature_signal_count": "up_signal_count",
        "feature_topo_extracellular_count": "up_topo_extracellular_count",
        "feature_lipidation_count": "up_lipidation_count",
        "feature_glycosylation_count": "up_glyc_count",
        "keywords": "up_keywords",
    }
    up = up[list(keep)].rename(columns=keep)
    for c in [
        "up_length",
        "up_tm_count",
        "up_signal_count",
        "up_topo_extracellular_count",
        "up_lipidation_count",
        "up_glyc_count",
    ]:
        up[c] = pd.to_numeric(up[c], errors="coerce")
    up = up.drop_duplicates(subset="uniprot_accession", keep="first")
    df = df.merge(up, on="uniprot_accession", how="left")

    # Derived binary topology features. NaN -> NaN (proteins not in the
    # UniProt surface-candidate file are treated as missing rather than
    # negative; the enrichment computation drops them).
    for col, src in [
        ("up_has_signal", "up_signal_count"),
        ("up_has_tm", "up_tm_count"),
        ("up_has_glyc", "up_glyc_count"),
        ("up_has_lipidation", "up_lipidation_count"),
        ("up_has_extracellular_topo", "up_topo_extracellular_count"),
    ]:
        df[col] = (df[src] > 0).astype("float")
        df.loc[df[src].isna(), col] = np.nan
    df["up_multi_pass"] = (df["up_tm_count"] > 1).astype("float")
    df.loc[df["up_tm_count"].isna(), "up_multi_pass"] = np.nan
    return df


def _derive_topology_class(df: pd.DataFrame) -> pd.DataFrame:
    """One-hot the mutually-exclusive topology buckets in TOPOLOGY_CLASS_ORDER.

    Priority order (first match wins): a GPI-anchored protein with a
    stray annotated TM still presents as GPI at the surface; a 7TM
    GPCR is grouped under the GPCR bucket rather than generic
    multi-pass-TM. Proteins outside the UniProt surface-candidate set
    (no keyword cell) get NaN across all topology classes — they fall
    into "missing" rather than being silently called negative.
    """
    kw = df["up_keywords"].fillna("")
    has_kw = kw.str.len() > 0
    kw_lower = kw.str.lower()

    is_gpi = kw_lower.str.contains("gpi-anchor", regex=False)
    is_gpcr_keyword = kw_lower.str.contains("g-protein coupled receptor", regex=False)
    is_intramembrane = kw_lower.str.contains("intramembrane", regex=False)
    is_secreted_kw = kw_lower.str.contains("secreted", regex=False)
    # Inner-leaflet lipid markers. Prenylation (farnesyl / geranylgeranyl,
    # C-terminal CAAX, e.g. KRAS, RhoA) and myristoylation (N-terminal
    # glycine, e.g. SRC, LCK) both anchor the protein to the cytoplasmic
    # leaflet of the plasma membrane — they are NOT surface-accessible.
    is_prenyl = kw_lower.str.contains("prenylation", regex=False)
    is_myristoyl = kw_lower.str.contains("myristate", regex=False)
    is_palmitoyl = kw_lower.str.contains("palmitate", regex=False)
    is_inner_leaflet_lipid = is_prenyl | is_myristoyl

    tm = df["up_tm_count"].fillna(0)
    sig = df["up_signal_count"].fillna(0)
    lip = df["up_lipidation_count"].fillna(0)

    klass = pd.Series([""] * len(df), index=df.index)
    # 1. GPI wins outright.
    klass = klass.mask((klass == "") & is_gpi, "topo_gpi_anchored")
    # 2. Intramembrane proteins (embedded but not crossing the bilayer).
    klass = klass.mask((klass == "") & is_intramembrane & (tm == 0), "topo_intramembrane")
    # 3. 7TM GPCR — multi-pass with the dedicated UniProt keyword.
    klass = klass.mask((klass == "") & is_gpcr_keyword & (tm >= 5), "topo_gpcr_7tm")
    # 4. Generic multi-pass TM.
    klass = klass.mask((klass == "") & (tm >= 2), "topo_multi_pass_tm")
    # 5. Single-pass TM (Type I/II/III).
    klass = klass.mask((klass == "") & (tm == 1), "topo_single_pass_tm")
    # 6. Signal peptide only — likely secreted.
    klass = klass.mask(
        (klass == "") & (sig >= 1) & (tm == 0) & (is_secreted_kw | (lip == 0)),
        "topo_signal_only_secreted",
    )
    # 7. Inner-leaflet lipid-anchored (prenyl / myristoyl, no TM, no signal).
    #    Captures the KRAS / SRC / RhoA / LCK class that GO over-calls
    #    as "surface" via the leaflet-agnostic "plasma membrane" GO term.
    klass = klass.mask(
        (klass == "") & is_inner_leaflet_lipid & (tm == 0) & (sig == 0),
        "topo_inner_leaflet_lipidated",
    )
    # 8. Palmitoylated-only (no prenyl / no myristoyl, no TM, no signal).
    #    Leaflet-ambiguous; kept as a separate bucket so it doesn't
    #    contaminate either anchor class.
    klass = klass.mask(
        (klass == "") & is_palmitoyl & (tm == 0) & (sig == 0),
        "topo_palmitoylated_only",
    )
    # 9. No TM, no signal, no lipid anchor → peripheral / intracellular.
    klass = klass.mask((klass == "") & has_kw & (tm == 0) & (sig == 0), "topo_no_tm_no_signal")

    # One-hot. Proteins without UniProt keyword data (~2,400 of v2)
    # get NaN across every topo_* column rather than zero.
    for name in TOPOLOGY_CLASS_ORDER:
        df[name] = (klass == name).astype("float")
        df.loc[~has_kw, name] = np.nan
    return df


def _join_deeptmhmm(df: pd.DataFrame) -> pd.DataFrame:
    """DeepTMHMM topology one-hot from the v1 candidate-universe TSV.

    v1 is the only source that already aligns DeepTMHMM predictions to
    uniprot_accession; pulling them here keeps the script self-contained
    instead of re-parsing the raw .3line file.
    """
    v1 = pd.read_csv(V1, sep="\t", dtype=str).fillna("")
    v1_subset = (
        v1[["uniprot_accession", "deeptmhmm_label"]]
        .drop_duplicates(subset="uniprot_accession", keep="first")
    )
    df = df.merge(v1_subset, on="uniprot_accession", how="left")
    for label, slug in [
        ("TM", "deeptm_TM"),
        ("SP+TM", "deeptm_SP_plus_TM"),
        ("SP", "deeptm_SP_only"),
        ("BETA", "deeptm_BETA"),
        ("GLOB", "deeptm_GLOB"),
    ]:
        df[slug] = (df["deeptmhmm_label"] == label).astype("float")
        df.loc[df["deeptmhmm_label"].isna() | (df["deeptmhmm_label"] == ""), slug] = np.nan
    return df


def _join_hgnc_families(df: pd.DataFrame) -> pd.DataFrame:
    """Macro-family one-hots from HGNC ``gene_group``.

    HGNC ships ~700 fine-grained gene groups (e.g. "Olfactory receptors,
    family 4"). We collapse them into a handful of surface-relevant
    macros via case-insensitive substring patterns. A gene with multiple
    groups can be positive in multiple macros — each macro is its own
    independent binary feature.
    """
    hgnc = pd.read_csv(HGNC, sep="\t", dtype=str).fillna("")
    hgnc = hgnc[["hgnc_id", "gene_group"]].drop_duplicates(subset="hgnc_id", keep="first")
    df = df.merge(hgnc, on="hgnc_id", how="left")
    gg = df["gene_group"].fillna("")
    gg_lower = gg.str.lower()
    has_hgnc = gg.str.len() > 0
    for name, patterns in HGNC_FAMILY_PATTERNS:
        hit = pd.Series(False, index=df.index)
        for pat in patterns:
            hit = hit | gg_lower.str.contains(pat.lower(), regex=False)
        df[name] = hit.astype("float")
        df.loc[~has_hgnc, name] = np.nan
    return df


def _join_schweke(df: pd.DataFrame) -> pd.DataFrame:
    sk = pd.read_csv(SCHWEKE, sep="\t", dtype=str).fillna("")
    sk = sk[["uniprot_accession", "schweke_homomer"]].copy()
    sk["schweke_homomer"] = (sk["schweke_homomer"] == "yes").astype(int)
    sk = sk.drop_duplicates(subset="uniprot_accession", keep="first")
    return df.merge(sk, on="uniprot_accession", how="left")


def build_features() -> pd.DataFrame:
    df = _load_v2()
    df = _join_uniprot_features(df)
    df = _derive_topology_class(df)
    df = _join_deeptmhmm(df)
    df = _join_hgnc_families(df)
    df = _join_schweke(df)
    return df


# ----------------------------------------------------------------------
# Per-source enrichment
# ----------------------------------------------------------------------


def _cliffs_delta_continuous(in_vals: np.ndarray, out_vals: np.ndarray) -> float:
    """Cliff's delta from a Mann-Whitney U on the larger group.

    Range [-1, 1]. Positive = included > excluded; negative = included < excluded.
    Returns NaN if either group has fewer than 2 finite values.
    """
    if in_vals.size < 2 or out_vals.size < 2:
        return float("nan")
    u_stat, _ = mannwhitneyu(in_vals, out_vals, alternative="two-sided")
    return 2.0 * (u_stat / (in_vals.size * out_vals.size)) - 1.0


def _log_or_haldane(a: int, b: int, c: int, d: int) -> tuple[float, float, float]:
    """Haldane-Anscombe corrected log OR with 95% CI.

    a = in & feature_positive, b = in & feature_negative,
    c = out & feature_positive, d = out & feature_negative.
    """
    aa, bb, cc, dd = a + 0.5, b + 0.5, c + 0.5, d + 0.5
    log_or = float(np.log((aa * dd) / (bb * cc)))
    se = float(np.sqrt(1 / aa + 1 / bb + 1 / cc + 1 / dd))
    return log_or, log_or - 1.96 * se, log_or + 1.96 * se


def _binary_enrichment(
    feature: str, in_vals: pd.Series, out_vals: pd.Series
) -> dict[str, float | str]:
    in_vals = in_vals.dropna().astype(int)
    out_vals = out_vals.dropna().astype(int)
    a = int(in_vals.sum())
    b = int(in_vals.size - a)
    c = int(out_vals.sum())
    d = int(out_vals.size - c)
    if (a + b) == 0 or (c + d) == 0:
        return {
            "in_n": int(a + b),
            "out_n": int(c + d),
            "in_summary": float("nan"),
            "out_summary": float("nan"),
            "effect": float("nan"),
            "effect_kind": "prop_diff",
            "effect_ci_lo": float("nan"),
            "effect_ci_hi": float("nan"),
            "aux_effect": float("nan"),
            "aux_effect_kind": "log_or",
            "p_value": float("nan"),
        }
    p_in = a / (a + b)
    p_out = c / (c + d)
    prop_diff = p_in - p_out  # Cliff's-delta equivalent for binary; range [-1, 1].
    log_or, lo, hi = _log_or_haldane(a, b, c, d)
    _, pval = fisher_exact([[a, b], [c, d]])
    return {
        "in_n": int(a + b),
        "out_n": int(c + d),
        "in_summary": float(p_in),
        "out_summary": float(p_out),
        "effect": float(prop_diff),
        "effect_kind": "prop_diff",
        "effect_ci_lo": float("nan"),
        "effect_ci_hi": float("nan"),
        "aux_effect": float(log_or),
        "aux_effect_kind": "log_or",
        "aux_effect_ci_lo": float(lo),
        "aux_effect_ci_hi": float(hi),
        "p_value": float(pval),
    }


def _continuous_enrichment(
    feature: str, in_vals: pd.Series, out_vals: pd.Series
) -> dict[str, float | str]:
    in_arr = pd.to_numeric(in_vals, errors="coerce").dropna().to_numpy()
    out_arr = pd.to_numeric(out_vals, errors="coerce").dropna().to_numpy()
    if in_arr.size < 2 or out_arr.size < 2:
        return {
            "in_n": int(in_arr.size),
            "out_n": int(out_arr.size),
            "in_summary": float("nan"),
            "out_summary": float("nan"),
            "effect": float("nan"),
            "effect_kind": "cliffs_delta",
            "effect_ci_lo": float("nan"),
            "effect_ci_hi": float("nan"),
            "aux_effect": float("nan"),
            "aux_effect_kind": "mean_diff",
            "p_value": float("nan"),
        }
    _, pval = mannwhitneyu(in_arr, out_arr, alternative="two-sided")
    delta = _cliffs_delta_continuous(in_arr, out_arr)
    return {
        "in_n": int(in_arr.size),
        "out_n": int(out_arr.size),
        "in_summary": float(np.median(in_arr)),
        "out_summary": float(np.median(out_arr)),
        "effect": float(delta),
        "effect_kind": "cliffs_delta",
        "effect_ci_lo": float("nan"),
        "effect_ci_hi": float("nan"),
        "aux_effect": float(np.mean(in_arr) - np.mean(out_arr)),
        "aux_effect_kind": "mean_diff",
        "p_value": float(pval),
    }


def _bh_qvalue(pvals: pd.Series) -> pd.Series:
    """Benjamini-Hochberg q-values. NaN p-values stay NaN."""
    p = pvals.to_numpy(dtype=float)
    n = np.isfinite(p).sum()
    order = np.argsort(np.where(np.isfinite(p), p, np.inf))
    ranked = np.arange(1, p.size + 1)
    q = np.full_like(p, np.nan)
    if n == 0:
        return pd.Series(q, index=pvals.index)
    q_ordered = p[order] * n / ranked
    # Step-down: cumulative min from the end.
    q_ordered = np.minimum.accumulate(q_ordered[::-1])[::-1]
    q_ordered = np.minimum(q_ordered, 1.0)
    q[order] = q_ordered
    # Mask out positions where the original p was NaN.
    q = np.where(np.isfinite(p), q, np.nan)
    return pd.Series(q, index=pvals.index)


def compute_enrichment(df: pd.DataFrame) -> pd.DataFrame:
    rows: list[dict] = []
    for source_name, source_col in INCLUSION_SOURCES:
        in_mask = df[source_col] == 1
        out_mask = ~in_mask  # complement = "rest of the v2 universe"
        for feat in BINARY_FEATURES:
            stats = _binary_enrichment(feat, df.loc[in_mask, feat], df.loc[out_mask, feat])
            rows.append({"source": source_name, "feature": feat, "feature_type": "binary", **stats})
        for feat in CONTINUOUS_FEATURES:
            stats = _continuous_enrichment(feat, df.loc[in_mask, feat], df.loc[out_mask, feat])
            rows.append(
                {"source": source_name, "feature": feat, "feature_type": "continuous", **stats}
            )
    out = pd.DataFrame(rows)
    out["q_value"] = _bh_qvalue(out["p_value"])
    return out


# ----------------------------------------------------------------------
# Figure
# ----------------------------------------------------------------------


def _star(qval: float) -> str:
    if not np.isfinite(qval):
        return ""
    if qval < 0.001:
        return "***"
    if qval < 0.01:
        return "**"
    if qval < 0.05:
        return "*"
    return ""


def make_heatmap(enrichment: pd.DataFrame, out_dir: Path) -> None:
    """Signed-effect heatmap: rows=features, cols=sources, cell=effect."""
    setup_plotting_style(font_scale=1.0)
    feature_order = BINARY_FEATURES + CONTINUOUS_FEATURES
    source_order = [name for name, _ in INCLUSION_SOURCES]

    effect = (
        enrichment.pivot(index="feature", columns="source", values="effect")
        .reindex(index=feature_order, columns=source_order)
    )
    qvals = (
        enrichment.pivot(index="feature", columns="source", values="q_value")
        .reindex(index=feature_order, columns=source_order)
    )
    annot = qvals.map(_star)

    # Two-panel layout: a thin left strip colored by feature provenance
    # (UniProt / DeepTMHMM / HGNC / Schweke / cohort meta) + the main
    # enrichment heatmap. The strip is the answer to "where does each
    # row come from?" at a glance.
    fig = plt.figure(figsize=(11.5, 17))
    gs = fig.add_gridspec(
        1,
        2,
        width_ratios=[0.55, 12],
        wspace=0.05,
        left=0.18,
        right=0.92,
        top=0.96,
        bottom=0.08,
    )
    prov_ax = fig.add_subplot(gs[0, 0])
    ax = fig.add_subplot(gs[0, 1], sharey=prov_ax)

    # Provenance strip: one colored cell per row in feature_order.
    prov_index = list(range(len(feature_order)))
    prov_colors = [
        PROVENANCE_COLORS[FEATURE_PROVENANCE[f]] for f in feature_order
    ]
    for i, c in enumerate(prov_colors):
        prov_ax.add_patch(
            plt.Rectangle((0, i), 1, 1, facecolor=c, edgecolor="white", linewidth=0.5)
        )
    prov_ax.set_xlim(0, 1)
    prov_ax.set_ylim(len(feature_order), 0)
    prov_ax.set_xticks([])
    prov_ax.set_yticks([])
    prov_ax.set_xlabel("Source", labelpad=8, fontsize=10)
    for spine in prov_ax.spines.values():
        spine.set_visible(False)

    sns.heatmap(
        effect,
        cmap=DIVERGING_PALETTE,
        center=0.0,
        vmin=-0.6,
        vmax=0.6,
        annot=annot,
        fmt="",
        annot_kws={"size": 11, "weight": "bold"},
        cbar_kws={
            "label": (
                "Signed effect, range [−1, +1]\n"
                "(binary: p_in − p_out;\n"
                " continuous: Cliff's δ)\n"
                "stars: BH q-value tiers"
            ),
            "shrink": 0.55,
            "pad": 0.02,
        },
        linewidths=0.5,
        linecolor="white",
        ax=ax,
    )
    ax.set_xlabel("Inclusion source")
    ax.set_ylabel("")
    ax.tick_params(axis="x", rotation=35)
    for tick in ax.get_xticklabels():
        tick.set_horizontalalignment("right")
    # Mirror y-axis tick labels to the left panel so they sit next to
    # the provenance strip.
    ax.tick_params(axis="y", labelleft=False, labelright=False)
    prov_ax.set_yticks([i + 0.5 for i in prov_index])
    prov_ax.set_yticklabels(feature_order, fontsize=9)
    prov_ax.tick_params(axis="y", left=False, pad=2)

    # Section dividers. Binary topology / inner-leaflet / family /
    # orthogonal / continuous — visible reading aid for what the
    # heatmap shows top-to-bottom.
    def _idx(feat: str) -> int:
        return feature_order.index(feat)

    dividers = [
        ("TM topology", 0, _idx("topo_gpi_anchored") - 0.5),
        ("Cell-surface topology classes", _idx("topo_gpi_anchored") - 0.5,
         _idx("topo_inner_leaflet_lipidated") - 0.5),
        ("INNER-LEAFLET (not cell-surface)",
         _idx("topo_inner_leaflet_lipidated") - 0.5,
         _idx("topo_no_tm_no_signal") - 0.5),
        ("Other peripheral", _idx("topo_no_tm_no_signal") - 0.5,
         _idx("fam_gpcr") - 0.5),
        ("HGNC families (surface)", _idx("fam_gpcr") - 0.5,
         _idx("fam_ras_gtpase") - 0.5),
        ("HGNC families (INNER-LEAFLET)", _idx("fam_ras_gtpase") - 0.5,
         _idx("schweke_homomer") - 0.5),
        ("Orthogonal / cohort", _idx("schweke_homomer") - 0.5,
         len(feature_order)),
    ]
    for _, _, y in dividers[1:]:
        ax.axhline(y, color="black", linewidth=0.8)
    ax.axhline(len(BINARY_FEATURES), color="black", linewidth=1.5)

    # Build a provenance legend below the figure.
    from matplotlib.patches import Patch

    legend_handles = [
        Patch(facecolor=color, label=name)
        for name, color in PROVENANCE_COLORS.items()
    ]
    ax.legend(
        handles=legend_handles,
        loc="upper center",
        bbox_to_anchor=(0.5, -0.07),
        ncol=3,
        fontsize=9,
        frameon=False,
        title="Feature provenance (all deterministic)",
        title_fontsize=10,
    )

    save_figure(fig, "inclusion_heatmap", output_dir=out_dir, formats=("pdf", "png"))
    plt.close(fig)


def make_per_source_bars(enrichment: pd.DataFrame, out_dir: Path) -> None:
    """Per-source top-feature bar plot (signed effect, sorted by |effect|).

    One small-multiples panel per inclusion source; the top 12 features
    by |effect| within each source are shown, colored by sign.
    """
    setup_plotting_style(font_scale=0.9)
    source_order = [name for name, _ in INCLUSION_SOURCES]
    n_src = len(source_order)
    ncols = 2
    nrows = (n_src + ncols - 1) // ncols
    fig, axes = plt.subplots(nrows, ncols, figsize=(13, 4 * nrows))
    axes = np.array(axes).reshape(-1)
    for ax, source in zip(axes, source_order):
        sub = (
            enrichment[(enrichment["source"] == source) & enrichment["effect"].notna()]
            .assign(abs_effect=lambda d: d["effect"].abs())
            .sort_values("abs_effect", ascending=False)
            .head(12)
            .sort_values("effect")
            .reset_index(drop=True)
        )
        features = sub["feature"].tolist()
        effects = sub["effect"].astype(float).tolist()
        qvals = sub["q_value"].astype(float).tolist()
        y_pos = list(range(len(features)))
        colors = ["#BC3C4C" if v > 0 else "#3D6B60" for v in effects]
        ax.barh(y_pos, effects, color=colors, edgecolor="white")
        ax.set_yticks(y_pos)
        ax.set_yticklabels(features)
        ax.axvline(0, color="black", linewidth=0.8)
        ax.set_xlim(-0.7, 0.7)
        ax.set_xlabel(f"{source}: effect (in − out)")
        sns.despine(ax=ax, top=True, right=True)
        for i, (effect, qval) in enumerate(zip(effects, qvals)):
            star = _star(qval)
            if star:
                xpos = effect + (0.02 if effect > 0 else -0.02)
                ax.text(
                    xpos,
                    i,
                    star,
                    va="center",
                    ha="left" if effect > 0 else "right",
                    fontsize=10,
                    weight="bold",
                )
    for ax in axes[n_src:]:
        ax.axis("off")
    fig.tight_layout()
    save_figure(fig, "inclusion_per_source_bars", output_dir=out_dir, formats=("pdf", "png"))
    plt.close(fig)


SURFY_FOCUS_FEATURES: list[tuple[str, str]] = [
    ("topo_gpcr_7tm", "7TM GPCR"),
    ("topo_multi_pass_tm", "Multi-pass TM\n(non-GPCR)"),
    ("topo_single_pass_tm", "Single-pass TM\n(Type I/II/III)"),
    ("topo_gpi_anchored", "GPI-anchored\n(outer leaflet)"),
    ("topo_signal_only_secreted", "Signal-peptide only\n(secreted-likely)"),
    ("topo_inner_leaflet_lipidated", "Inner-leaflet lipidated\n(KRAS, SRC, RhoA — NOT surface)"),
    ("topo_no_tm_no_signal", "No TM, no signal\n(peripheral / cytosolic)"),
    ("schweke_homomer", "Schweke-predicted homomer"),
]


def make_surfy_topology_coverage(df: pd.DataFrame, out_dir: Path) -> None:
    """For each topology class, the inclusion rate of every source.

    Answers: "is SURFY mostly catching TM proteins?" Yes — SURFY's
    bars are tall for 7TM-GPCR, multi-pass TM, and single-pass TM,
    short for GPI / signal-only / peripheral. By plotting all sources
    side-by-side the reader can also see which sources over-call
    inner-leaflet proteins (GO + HPA), correctly under-call them
    (UniProt / SURFY / CSPA / Sonnet), and where the surface-DB
    coverage gaps are (e.g. CSPA's GPCR blind spot).
    """
    setup_plotting_style(font_scale=0.9)
    source_order = [name for name, _ in INCLUSION_SOURCES]
    source_colors = {
        "uniprot": "#3D6B60",
        "go": "#BC3C4C",
        "hpa": "#F4AA28",
        "surfy": "#8878C8",
        "cspa": "#6E1428",
        "sonnet": "#244840",
    }

    n_feat = len(SURFY_FOCUS_FEATURES)
    ncols = 2
    nrows = (n_feat + ncols - 1) // ncols
    fig, axes = plt.subplots(nrows, ncols, figsize=(14, 3.0 * nrows))
    axes = np.array(axes).reshape(-1)

    for ax, (feat_col, pretty) in zip(axes, SURFY_FOCUS_FEATURES):
        # Universe rate = fraction of v2 (with feature data) that carries
        # this feature.
        universe_rate = float(df[feat_col].dropna().mean())
        rates_pct = []
        for src_name, src_col in INCLUSION_SOURCES:
            mask = df[src_col] == 1
            vals = df.loc[mask, feat_col].dropna()
            rate = float(vals.mean()) if vals.size else float("nan")
            rates_pct.append(rate * 100)
        colors = [source_colors[s] for s in source_order]
        ax.bar(range(len(source_order)), rates_pct, color=colors, edgecolor="white")
        ax.axhline(
            universe_rate * 100,
            color="black",
            linestyle="--",
            linewidth=1.0,
            label=f"v2 universe ({universe_rate * 100:.1f}%)",
        )
        ax.set_xticks(range(len(source_order)))
        ax.set_xticklabels(source_order, rotation=35, ha="right")
        ax.set_ylabel("% of source's included set")
        ax.set_xlabel("")
        ax.text(
            0.0,
            1.04,
            pretty,
            transform=ax.transAxes,
            ha="left",
            va="bottom",
            fontsize=11,
            weight="bold",
        )
        plt.setp(ax.get_yticklabels(), fontsize=9)
        ax.legend(fontsize=8, loc="upper right", frameon=False)
        sns.despine(ax=ax, top=True, right=True)
    for ax in axes[n_feat:]:
        ax.axis("off")
    fig.text(
        0.5,
        1.005,
        "What each source includes, by topology class",
        ha="center",
        va="bottom",
        fontsize=14,
        weight="bold",
    )
    fig.tight_layout(rect=(0, 0, 1, 0.99))
    save_figure(fig, "topology_coverage_by_source", output_dir=out_dir, formats=("pdf", "png"))
    plt.close(fig)


# ----------------------------------------------------------------------
# Main
# ----------------------------------------------------------------------


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--out-dir",
        type=Path,
        default=OUT_DIR,
        help="Output directory (default: data/analysis/db_vs_sonnet_inclusion).",
    )
    args = parser.parse_args()
    out_dir: Path = args.out_dir
    out_dir.mkdir(parents=True, exist_ok=True)

    print(f"[1/4] Building per-protein feature table from {V2.name}")
    df = build_features()
    feat_path = out_dir / "per_protein_features.tsv"
    df.to_csv(feat_path, sep="\t", index=False)
    print(f"      Wrote {len(df):,} rows × {df.shape[1]} cols -> {feat_path}")

    print("[2/4] Computing per-source inclusion enrichment")
    enrichment = compute_enrichment(df)
    enr_path = out_dir / "inclusion_enrichment.tsv"
    enrichment.to_csv(enr_path, sep="\t", index=False)
    print(f"      Wrote {len(enrichment):,} (source × feature) rows -> {enr_path}")

    print("[3/4] Writing summary JSON")
    summary = {
        "universe_size": int(len(df)),
        "inclusion_counts": {
            name: int(df[col].sum()) for name, col in INCLUSION_SOURCES
        },
        "feature_coverage": {
            feat: int(df[feat].notna().sum())
            for feat in BINARY_FEATURES + CONTINUOUS_FEATURES
        },
    }
    (out_dir / "inclusion_summary.json").write_text(json.dumps(summary, indent=2))
    print(f"      Wrote -> {out_dir / 'inclusion_summary.json'}")

    print("[4/4] Rendering figures")
    make_heatmap(enrichment, out_dir)
    make_per_source_bars(enrichment, out_dir)
    make_surfy_topology_coverage(df, out_dir)
    print("Done.")


if __name__ == "__main__":
    main()
