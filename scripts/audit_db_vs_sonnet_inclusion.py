"""Per-source inclusion-bias audit for the v2 candidate universe.

Answers: for the 6,588 proteins in the v3 cohort-cleaned candidate
universe (v3-kept + v3-dropped), what features
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
V3 = REPO / "data/processed/candidate_universe/candidate_universe_v3.tsv"
# Final-figure output dir — every promoted figure lands here so the
# Zenodo deposit, the published gists, and the readers' figure
# folder are all the same path.
FIGURES_DIR = REPO / "data/analysis/figures"
V3_DROPPED = REPO / "data/processed/candidate_universe/candidate_universe_v3_dropped.tsv"
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
    "deeptm_TM_NO_SP",
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
    # m1_n_db_votes (cohort meta — # of M1 DBs that voted "surface")
    # intentionally excluded: it's not biology, it's the cohort's own
    # consensus state. Including it would tautologically inflate each
    # source's effect because in-source membership ↔ vote ≥ 1.
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
    "deeptm_TM_NO_SP": "DeepTMHMM (predicted topology)",
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
}


def _load_v3() -> pd.DataFrame:
    """Load v3-kept (5,105) + v3-dropped (1,483) = 6,588-row cohort-
    cleaned candidate universe.

    Why 6,588 and not 5,105: the dropped rows are still legitimate
    candidate-universe members — they just didn't survive the
    Sonnet=no/high-conf/1-DB rule. For the source-inclusion analysis
    we WANT them in the universe so the per-DB inclusion sets reflect
    each DB's actual contribution. Sonnet's inclusion set excludes
    them by construction (their sonnet_verdict is 'no'), which is the
    correct semantic.

    v2 (6,711) → v3-input (6,588): v3 builder also tightens the
    cohort via gene_identifier_public, pruning 117-ish pseudogene /
    ERV / Ig-V-segment / isoform-collision rows that v2 had absorbed
    without intersecting the 19,464-row protein-coding cohort. The
    6,588 is exactly v2 ∩ Homo_sapiens.protein_coding.with_hgnc.

    v3 schema changes vs v2 the loader projects across:
      * `uniprot_acc`        <-  `uniprot_accession`
      * `<db>_flag`          <-  `m1_<db>_flag`
      * `n_db_votes`         <-  `m1_n_db_votes`
      * new cols: `ncbi_gene_id`, `deeptmhmm_flag`, `compartments_flag`,
                  `pubmed_verdict`, `pubmed_confidence`
    """
    df_kept = pd.read_csv(V3, sep="\t", dtype=str).fillna("")
    df_dropped = pd.read_csv(V3_DROPPED, sep="\t", dtype=str).fillna("")
    df = pd.concat([df_kept, df_dropped], ignore_index=True)
    # Normalize the column the rest of the script joins on.
    if "uniprot_acc" in df.columns and "uniprot_accession" not in df.columns:
        df = df.rename(columns={"uniprot_acc": "uniprot_accession"})
    for c in ["uniprot_flag", "go_flag", "hpa_flag", "surfy_flag", "cspa_flag",
              "n_db_votes"]:
        df[c] = pd.to_numeric(df[c], errors="coerce").fillna(0).astype(int)
    df["src_uniprot"] = (df["uniprot_flag"] == 1).astype(int)
    df["src_go"] = (df["go_flag"] == 1).astype(int)
    df["src_hpa"] = (df["hpa_flag"] == 1).astype(int)
    df["src_surfy"] = (df["surfy_flag"] == 1).astype(int)
    df["src_cspa"] = (df["cspa_flag"] == 1).astype(int)
    # Sonnet inclusion: verdict in {"yes", "contextual"}. v3 has already
    # trimmed Sonnet=no/high-conf rows that were in v2, so the "sonnet"
    # set is smaller here by construction.
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
        # DeepTMHMM "TM" class = TM without signal peptide. Renamed
        # to `deeptm_TM_NO_SP` so the feature label is unambiguous —
        # earlier `deeptm_TM` read as "any TM" which conflated with
        # `up_has_tm` (the broader UniProt-annotation flag that
        # covers BOTH TM-only and SP+TM proteins).
        ("TM", "deeptm_TM_NO_SP"),
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
    df = _load_v3()
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
    """Signed-effect heatmap: rows=features, cols=sources, cell=effect.

    Drops feature rows where max |effect| across sources < 0.20 — uninformative
    rows (every DB scores near zero) crowded the figure without contributing
    signal. The full 49-row matrix is still in the enrichment TSV; we trim
    only at the rendering step.
    """
    setup_plotting_style(font_scale=1.0)
    full_order = BINARY_FEATURES + CONTINUOUS_FEATURES
    source_order = [name for name, _ in INCLUSION_SOURCES]

    effect = (
        enrichment.pivot(index="feature", columns="source", values="effect")
        .reindex(index=full_order, columns=source_order)
    )
    qvals = (
        enrichment.pivot(index="feature", columns="source", values="q_value")
        .reindex(index=full_order, columns=source_order)
    )
    annot = qvals.map(_star)

    # Filter: keep only rows that move SOMEWHERE in the heatmap. A row
    # whose largest absolute effect across all 6 sources is below 0.20
    # is, by construction, a row of near-white cells — visually dead
    # space. We keep the BINARY vs CONTINUOUS split intact so the
    # post-filter dividers + provenance grouping still read correctly.
    max_abs = effect.abs().max(axis=1).fillna(0)
    keep = max_abs >= 0.20
    binary_kept = [f for f in BINARY_FEATURES if bool(keep.get(f, False))]
    continuous_kept = [f for f in CONTINUOUS_FEATURES if bool(keep.get(f, False))]
    feature_order = binary_kept + continuous_kept
    effect = effect.reindex(index=feature_order)
    qvals = qvals.reindex(index=feature_order)
    annot = annot.reindex(index=feature_order)
    n_dropped = len(full_order) - len(feature_order)
    print(
        f"      Heatmap: kept {len(feature_order)}/{len(full_order)} rows "
        f"(dropped {n_dropped} with max |effect| < 0.20)"
    )

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
    prov_ax.set_xlabel("Source", labelpad=8, fontsize=13)
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
        # Project min font size = 13 (matches xtick/ytick.labelsize
        # in _plotting_config). Star annotations were 11; bumped.
        annot_kws={"size": 13, "weight": "bold"},
        cbar_kws={
            "label": (
                "Signed effect, range [−1, +1]\n"
                "(binary: p_in − p_out;\n"
                " continuous: Cliff's δ)\n"
                "stars: BH q-value tiers"
            ),
            "shrink": 0.55,
            # Pad bumped 0.06 → 0.14 so the colorbar steps fully
            # outside the heatmap's right edge — including its
            # rightmost source column's x-tick text — instead of
            # crowding the sonnet column. Tradeoff: ~8% wider canvas
            # for the heatmap+cbar pair.
            "pad": 0.14,
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
    prov_ax.set_yticklabels(feature_order, fontsize=13)
    prov_ax.tick_params(axis="y", left=False, pad=2)

    # Section divider between binary and continuous blocks — the only
    # divider that survives once we filter rows to max |effect| ≥ 0.20
    # (the per-theme anchor features like `topo_gpi_anchored` get
    # dropped at the filter step, breaking the per-section dividers
    # that used them as anchors).
    ax.axhline(len(binary_kept), color="black", linewidth=1.5)

    # Build a provenance legend below the figure.
    from matplotlib.patches import Patch

    legend_handles = [
        Patch(facecolor=color, label=name)
        for name, color in PROVENANCE_COLORS.items()
    ]
    # Legend below the heatmap. -0.09 lands just below the rotated
    # x-tick labels without leaving a wasteful gap (earlier -0.12 was
    # visibly disconnected). subplots_adjust(bottom=0.10) reserves
    # exactly enough vertical space for the two-line legend block.
    ax.legend(
        handles=legend_handles,
        loc="upper center",
        bbox_to_anchor=(0.5, -0.09),
        ncol=3,
        fontsize=13,
        frameon=False,
        title="Feature provenance (all deterministic)",
        title_fontsize=14,
    )
    fig.subplots_adjust(bottom=0.10)

    save_figure(fig, "inclusion_heatmap", output_dir=out_dir, formats=("pdf", "png"))
    plt.close(fig)


def make_clustered_heatmap(enrichment: pd.DataFrame, out_dir: Path) -> None:
    """Hierarchically-clustered heatmap of the same signed effects.

    Both axes are clustered (average linkage on correlation distance);
    features and sources are reordered so blocks with similar inclusion
    patterns sit together. Loses the manually-curated section grouping
    that the un-clustered heatmap has, but surfaces patterns the manual
    order can't (e.g. "GO clusters with HPA's bias", "sonnet is closest
    to UniProt").
    """
    # font_scale=1.0 so per-element fontsizes are read literally from
    # the project min (13) — earlier 0.85 was shrinking everything
    # below the floor.
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

    # Same row filter as the unclustered main heatmap (now retired):
    # drop features whose max |effect| across all sources < 0.20.
    # Uninformative rows crowd the dendrogram + slow the linkage step
    # without contributing meaningful clusters.
    max_abs = effect.abs().max(axis=1).fillna(0)
    keep_threshold = max_abs >= 0.20
    n_below_threshold = int((~keep_threshold).sum())
    if n_below_threshold:
        print(
            f"      Clustermap: dropping {n_below_threshold} feature(s) "
            f"with max |effect| < 0.20"
        )

    # NaN handling: scipy's linkage refuses NaNs. Fill with 0 (no
    # effect) for the linkage step only; pass the original (with NaNs)
    # to the heatmap so empty cells stay visually missing.
    effect_for_link = effect.fillna(0.0)

    # Also drop zero-variance rows — features whose effect is ≈ 0
    # across every source. Their pairwise correlation distance is
    # undefined, which crashes scipy.linkage.
    keep_variance = effect_for_link.var(axis=1) > 1e-12

    keep_rows = keep_threshold & keep_variance
    effect_for_link = effect_for_link.loc[keep_rows]
    effect_for_plot = effect.loc[keep_rows]
    feature_order_kept = effect_for_link.index.tolist()

    # Provenance row colors (one cell per row, same palette as the
    # retired main heatmap's left strip). Strip name is "Provenance"
    # so it doesn't collide with the column strip below (both used
    # to be "Source", which was visually confusing).
    row_colors = pd.Series(
        {f: PROVENANCE_COLORS[FEATURE_PROVENANCE[f]] for f in feature_order_kept},
        name="Provenance",
    )
    # Column colors: one distinct color per source, matching the
    # palette used in `make_surfy_topology_coverage` (the per-DB
    # bar chart) so a reader scanning between the heatmap and the
    # bars gets the SAME color for the SAME source. Was: 2-tone
    # M1-DB-teal vs Sonnet-maroon, which obscured per-DB identity.
    col_color_map = {
        "sonnet":  "#d87851",   # Claude-orange (BRAND_CLAUDE_ORANGE)
        "uniprot": "#BC3C4C",   # maroon-light
        "go":      "#3D6B60",   # teal-mid
        "hpa":     "#F4AA28",   # amber-bright
        "surfy":   "#8878C8",   # lavender-bright
        "cspa":    "#6E1428",   # maroon-dark
    }
    col_colors = pd.Series(
        {name: col_color_map[name] for name, _ in INCLUSION_SOURCES},
        name="Source",
    )

    g = sns.clustermap(
        effect_for_link,
        cmap=DIVERGING_PALETTE,
        center=0.0,
        vmin=-0.6,
        vmax=0.6,
        method="average",
        metric="correlation",
        row_colors=row_colors,
        col_colors=col_colors,
        linewidths=0.4,
        linecolor="white",
        # Narrower canvas (was 14 × 8 → 9 × 8). With 6 columns the
        # 14"-wide heatmap was rendering each column ~2" wide;
        # squeezing to 9" gives ~1.2" per column — thinner data cells
        # AND room on the right for the colorbar without overlap.
        figsize=(9, 8),
        # Colorbar at x=0.93 — clear of the heatmap which now ends
        # around x=0.88 because the narrower canvas forces the
        # clustermap layout to leave the rightmost ~12% as margin.
        # Height 0.55, in the y-middle of the heatmap area.
        cbar_pos=(0.93, 0.18, 0.020, 0.55),
        cbar_kws={"label": "Signed effect [−1, +1]"},
        dendrogram_ratio=(0.10, 0.13),
        # Thicker color strips (was 0.018; now 0.035) so the per-row
        # provenance and per-column source-coloring bands actually
        # read at a glance instead of being hairline annotations.
        colors_ratio=0.035,
        xticklabels=True,
        yticklabels=True,
    )

    # Star annotation on the reordered grid (clustermap.ax_heatmap is
    # the actual data axes, with rows/cols permuted to dendrogram order).
    row_order = g.dendrogram_row.reordered_ind
    col_order = g.dendrogram_col.reordered_ind
    feat_reordered = [feature_order_kept[i] for i in row_order]
    src_reordered = [source_order[i] for i in col_order]
    for ri, feat in enumerate(feat_reordered):
        for ci, src in enumerate(src_reordered):
            star = _star(float(qvals.loc[feat, src]))
            if star and not np.isnan(effect_for_plot.loc[feat, src]):
                g.ax_heatmap.text(
                    ci + 0.5,
                    ri + 0.5,
                    star,
                    ha="center",
                    va="center",
                    fontsize=13,
                    weight="bold",
                    color="black",
                )

    g.ax_heatmap.set_xlabel("Inclusion source")
    g.ax_heatmap.set_ylabel("")
    g.ax_heatmap.tick_params(axis="x", rotation=35)
    for tick in g.ax_heatmap.get_xticklabels():
        tick.set_horizontalalignment("right")

    # Legends for the two color strips, placed below the figure.
    from matplotlib.patches import Patch

    prov_handles = [
        Patch(facecolor=color, label=name)
        for name, color in PROVENANCE_COLORS.items()
    ]
    # Per-source legend handles, in the same order the topology
    # coverage bars render (sonnet first as reference, then DBs).
    source_handles = [
        Patch(facecolor=col_color_map[k], label=k)
        for k in ("sonnet", "uniprot", "surfy", "cspa", "go", "hpa")
    ]
    # Both legends sit BELOW the x-tick labels (which include the
    # 35°-rotated source names). Earlier placement at y=-0.005 was
    # colliding with the tick text; -0.06 leaves room.
    # Legends right under the x-tick labels — pulled from y=−0.06 →
    # y=0.02 (closer to the heatmap, not orphaned below). With
    # subplots_adjust(bottom=0.13) reserving room AND figure-relative
    # coords on the legend, the labels sit ~half an inch from the
    # x-tick text rather than floating mid-page.
    # Legends pulled further down (y was 0.02; now −0.08) so they
    # sit well below the x-tick labels of the heatmap with breathing
    # room. subplots_adjust(bottom=0.20) reserves more vertical space
    # than the previous 0.13 to absorb the negative-y legend coords.
    prov_legend = g.fig.legend(
        handles=prov_handles,
        loc="lower left",
        bbox_to_anchor=(0.08, -0.08),
        ncol=2,
        fontsize=13,
        frameon=False,
        title="Row strip — feature provenance",
        title_fontsize=14,
    )
    src_legend = g.fig.legend(
        handles=source_handles,
        loc="lower right",
        bbox_to_anchor=(0.92, -0.08),
        ncol=2,
        fontsize=13,
        frameon=False,
        title="Col strip — inclusion source",
        title_fontsize=14,
    )
    g.fig.subplots_adjust(bottom=0.20)

    # Force matplotlib's tight-bbox calculation to INCLUDE the
    # figure-level legends. The default save_figure helper passes
    # bbox_inches='tight' but the auto-discovered extra-artists
    # list misses figure.legend() output because it isn't attached
    # to an axes — so the legends were getting CLIPPED below the
    # figure boundary on the saved PNG/PDF even though they
    # rendered correctly on screen. Passing them explicitly via
    # bbox_extra_artists is the matplotlib-blessed fix.
    for ext in ("pdf", "png"):
        path = out_dir / f"inclusion_heatmap_clustered.{ext}"
        g.fig.savefig(
            path,
            dpi=300,
            bbox_inches="tight",
            bbox_extra_artists=[prov_legend, src_legend],
        )
        print(f"  Saved: {path}")
    plt.close(g.fig)


def _db_vs_sonnet_enrichment(df: pd.DataFrame) -> pd.DataFrame:
    """For each (DB source, feature) pair, compute the signed effect with
    SONNET'S INCLUDED SET as the comparator instead of the universe
    complement.

      - in  group = rows where the DB source's flag is 1 (e.g. uniprot's
                    3,015)
      - out group = rows where src_sonnet == 1 (Sonnet's 4,249)

    The two groups overlap on genes both DB and Sonnet include — that's
    expected; what we're asking is "is feature X distributed differently
    across DB's call set than Sonnet's call set?", which is a valid
    two-sample test even with overlap (Fisher's exact on the 2×2 sample
    counts, Mann-Whitney U on the continuous values).

    Sonnet itself is excluded as an "in" source — comparing Sonnet to
    Sonnet would produce a row of zeros and clutter the figure.
    """
    out_rows: list[dict] = []
    sonnet_mask = df["src_sonnet"] == 1
    for source_name, source_col in INCLUSION_SOURCES:
        if source_name == "sonnet":
            continue
        in_mask = df[source_col] == 1
        for feat in BINARY_FEATURES:
            stats = _binary_enrichment(
                feat, df.loc[in_mask, feat], df.loc[sonnet_mask, feat]
            )
            out_rows.append(
                {"source": source_name, "feature": feat,
                 "feature_type": "binary", **stats}
            )
        for feat in CONTINUOUS_FEATURES:
            stats = _continuous_enrichment(
                feat, df.loc[in_mask, feat], df.loc[sonnet_mask, feat]
            )
            out_rows.append(
                {"source": source_name, "feature": feat,
                 "feature_type": "continuous", **stats}
            )
    out = pd.DataFrame(out_rows)
    out["q_value"] = _bh_qvalue(out["p_value"])
    return out


def make_per_source_bars(enrichment: pd.DataFrame, out_dir: Path) -> None:
    """Per-DB top-feature bar plot vs Sonnet.

    NOT the same enrichment as the heatmap. Each DB panel renders the
    top-12 features by |signed effect| where the effect is
    p(feature | DB-included) - p(feature | Sonnet-included)
    (continuous: Cliff's δ on DB's distribution vs Sonnet's). Sonnet
    itself isn't a panel — it IS the reference.

    Positive bar = feature is over-represented in the DB's call set
    relative to Sonnet's (e.g. CSPA's strong positive on `up_has_glyc`
    reflects CSPA's cell-surface-capture chemistry biasing toward
    glycoproteins more than Sonnet does). Negative bar = under-
    represented relative to Sonnet (e.g. CSPA's negative on `topo_
    gpcr_7tm` reflects the GPCR-glycosylation blind spot).

    Feature pool is the same as the heatmap (BINARY_FEATURES +
    CONTINUOUS_FEATURES). The selection rule within each panel is
    top-12 by |effect| with the q-value star surfaced on the bar tip,
    so a reader's eye lands on the LARGEST and CONFIDENT
    differentiators rather than the full ~50-feature row.
    """
    # font_scale=1.0 (was 0.9) so rcParams-derived tick labels meet
    # project floor 13pt.
    setup_plotting_style(font_scale=1.0)
    # `enrichment` here is the DB-vs-Sonnet table, which omits a
    # Sonnet-vs-Sonnet row by construction — derive the source order
    # from what's actually in the table so the layout stays in sync
    # if INCLUSION_SOURCES ever grows.
    source_order = list(dict.fromkeys(enrichment["source"].tolist()))

    # Pick a GLOBAL top-N feature set, ranked by the spread of effects
    # across DBs+Sonnet on the main (vs-universe) enrichment table —
    # i.e. the features that most strongly differentiate sources.
    # Using the same features in every panel means rows align across
    # panels and the reader can scan a feature horizontally to compare
    # DBs directly. Was: top-12 by |effect| WITHIN each panel — easier
    # for a per-DB story but impossible to compare across panels.
    universe_enrichment = pd.read_csv(
        OUT_DIR / "inclusion_enrichment.tsv", sep="\t"
    )
    piv = universe_enrichment.pivot(
        index="feature", columns="source", values="effect"
    )
    discriminator_rank = (
        piv.max(axis=1) - piv.min(axis=1)
    ).sort_values(ascending=False)
    # Global top-8 by range. The per-DB-top-2 gate is intentionally
    # gone — verified that today's top-8 already covers every DB's
    # top-2 except CSPA's secondary `up_has_signal`. Skipping the gate
    # keeps the panel symmetric (every DB renders the SAME 8 rows)
    # and lets the topology-coverage figure absorb CSPA's signal-
    # peptide signal via `up_has_signal` being part of its 12-row
    # binary set instead.
    feature_row_order = list(discriminator_rank.head(8).index)

    n_src = len(source_order)
    # 3-column layout so the 5 DBs land 3 + 2 across two rows. Was
    # 2 cols × 3 rows; the extra column ratio gives each panel a
    # squatter aspect that makes the 12-row bar chart less stretched.
    ncols = 3
    nrows = (n_src + ncols - 1) // ncols
    fig, axes = plt.subplots(nrows, ncols, figsize=(16, 4.2 * nrows))
    axes = np.array(axes).reshape(-1)
    for ax, source in zip(axes, source_order):
        sub = (
            enrichment[
                (enrichment["source"] == source)
                & enrichment["feature"].isin(feature_row_order)
                & enrichment["effect"].notna()
            ]
            .set_index("feature")
            .reindex(feature_row_order)
            .reset_index()
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
        ax.set_xlabel(f"{source}: effect ({source} − Sonnet)")
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
                    fontsize=13,
                    weight="bold",
                )
    for ax in axes[n_src:]:
        ax.axis("off")
    fig.tight_layout()
    save_figure(fig, "inclusion_per_source_bars", output_dir=out_dir, formats=("pdf", "png"))
    plt.close(fig)


SURFY_FOCUS_FEATURES: list[tuple[str, str]] = [
    # 12 binary features → 4 rows × 3 cols. Dropped from the previous
    # set:
    #   - `up_has_tm` — redundant with single-pass + multi-pass + 7TM
    #     panels (it's just their disjunction).
    #   - `up_multi_pass` — redundant with multi-pass-TM + 7TM (same).
    # Added in their place:
    #   - `up_has_signal` — any UniProt signal peptide annotation.
    #     Independent of TM presence, so distinct from
    #     topo_signal_only_secreted (which requires no TM).
    #   - `deeptm_SP_only` — DeepTMHMM secreted classification.
    #     Pairs visually with deeptm_TM_NO_SP so the reader sees
    #     parallel "no SP, TM only" vs "SP only, no TM" calls.
    # `up_has_extracellular_topo` survives despite being a subset of
    # `up_has_tm` because it requires curator-resolved orientation
    # (UniProt "Topological domain — Extracellular" annotation), which
    # the architecture-class panels don't directly assert.
    # Schweke-predicted homomer remains dropped (no DB filters on it,
    # panel was always flat). The flag still lives in the main heatmap.
    ("topo_gpi_anchored", "GPI-anchored\n(outer leaflet)"),
    ("topo_gpcr_7tm", "7TM GPCR"),
    ("topo_multi_pass_tm", "Multi-pass TM\n(non-GPCR)"),
    ("topo_single_pass_tm", "Single-pass TM\n(Type I/II/III)"),
    ("topo_signal_only_secreted",
     "Likely secreted\n(SP + no TM + no anchor)"),
    ("topo_inner_leaflet_lipidated", "Inner-leaflet lipidated\n(prenyl/myristoyl + no TM/SP)"),
    ("topo_no_tm_no_signal", "No TM, no signal\n(peripheral / cytosolic)"),
    # `up_has_extracellular_topo` removed — single-pass and multi-pass
    # TM proteins by definition have extracellular topology, so the
    # signal it carried was already in those architecture panels.
    # `up_has_signal` removed — its signal is split across
    # `topo_signal_only_secreted` (SP only, no TM) and
    # `topo_single_pass_tm` (most Type I receptors carry SP), and it
    # was the lowest-range discriminator of the surviving set.
    ("up_has_glyc", "Glycosylation site\n(UniProt feature)"),
    ("deeptm_TM_NO_SP", "TM without signal peptide\n(DeepTMHMM class)"),
    # `deeptm_SP_only` was here to balance `deeptm_TM_NO_SP` as
    # parallel DeepTMHMM classes — but in this surface-candidate
    # universe almost every DeepTMHMM "SP-only" call is actually a
    # GPI-anchored protein (ACHE, ALPL, BST1, CA4 — the C-terminal
    # GPI signal gets cleaved and replaced by the anchor, so
    # DeepTMHMM sees just the N-terminal SP and no TM). The panel
    # was therefore redundant with the GPI-anchored panel above.
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
    # font_scale=1.0 (was 0.9) so rcParams-derived tick labels stay
    # at the project floor of 13pt; 0.9 scaled them to 11.7pt below
    # the min. Per-element overrides further down already at 13/14.
    setup_plotting_style(font_scale=1.0)
    # Explicit source order for this panel — Sonnet first as the
    # implicit reference, then the 5 DBs in
    # uniprot / surfy / cspa / go / hpa order so the figure renders
    # the same source-axis as `data/analysis/figures/
    # make_db_correctness_by_class.py`. Colors come from the
    # BRAND_PALETTE used there so a reader scanning back and forth
    # between the two figures gets the SAME color for the SAME source.
    source_order = ["sonnet", "uniprot", "surfy", "cspa", "go", "hpa"]
    source_colors = {
        # Sonnet = Claude-orange (BRAND_CLAUDE_ORANGE = "#d87851") —
        # same color used for Sonnet in
        # data/analysis/figures/make_db_correctness_by_class.py so
        # a reader gets the SAME color for Sonnet across both
        # figures. Earlier teal-dark choice was wrong.
        "sonnet":  "#d87851",
        # 5 DB colors, indexed identically to BRAND_PALETTE[0..4] in
        # make_db_correctness_by_class.py (UniProt, GO CC, HPA,
        # SURFY, CSPA — by ORIGINAL palette assignment, not panel
        # order).
        "uniprot": "#BC3C4C",  # maroon-light
        "go":      "#3D6B60",  # teal-mid
        "hpa":     "#F4AA28",  # amber-bright
        "surfy":   "#8878C8",  # lavender-bright
        "cspa":    "#6E1428",  # maroon-dark
    }

    n_feat = len(SURFY_FOCUS_FEATURES)
    # 9 features → clean 3×3 grid. Was 4×3 with 12 features; the
    # redundant trim (drop has_signal, has_extracellular_topo,
    # deeptm_SP_only) takes us to 9 which fits a perfect square.
    ncols = 3
    nrows = (n_feat + ncols - 1) // ncols
    fig, axes = plt.subplots(nrows, ncols, figsize=(16, 3.6 * nrows))
    axes = np.array(axes).reshape(-1)

    for ax, (feat_col, pretty) in zip(axes, SURFY_FOCUS_FEATURES):
        # Denominator = the full v3-input universe (= ANY positive
        # vote across uniprot, go, hpa, surfy, cspa, OR sonnet).
        # The bar height for source S on feature F reads:
        #   (# proteins where S-included AND F-positive)
        #   / |universe|  (= 6,588)
        #
        # The v3 universe was BUILT from "any DB yes OR Sonnet
        # yes/contextual", so every member already has at least one
        # positive vote — "% of any yes vote across all sources" is
        # the same as "% of universe". Was: 5,546 = strict-DB union
        # only (the 5-DB-yes intersection of the universe).
        any_yes_size = int(len(df))
        # Walk source_order (the panel order) explicitly — the
        # iteration order has to match `source_order` so the bar
        # rate-list lines up with the color list and the x-tick
        # labels below. Previous version iterated INCLUSION_SOURCES
        # and silently mis-paired bars with colors when the two
        # orders diverged.
        src_col_by_name = dict(INCLUSION_SOURCES)
        rates_pct = []
        for src_name in source_order:
            src_col = src_col_by_name[src_name]
            mask = df[src_col] == 1
            feat = pd.to_numeric(df.loc[mask, feat_col], errors="coerce")
            n_pos = int((feat == 1).sum())
            rates_pct.append(100.0 * n_pos / any_yes_size)
        colors = [source_colors[s] for s in source_order]
        ax.bar(range(len(source_order)), rates_pct, color=colors, edgecolor="white")
        # Cohort-average reference line removed — the bars are
        # already comparable to each other within a panel, and the
        # dashed average line was crowding the top of the canvas on
        # high-prevalence features (e.g. up_has_tm where bars hit ~95%
        # and the line sat squashed against the panel ceiling).
        ax.set_xticks(range(len(source_order)))
        ax.set_xticklabels(source_order, rotation=35, ha="right")
        # Y-axis label = denominator. The full v3-input universe
        # (6,588 proteins) is the reference — every universe member
        # has ≥1 yes vote across the 6 sources by construction, so
        # "% of any yes vote" reads cleanly as "% of universe."
        ax.set_ylabel("% of any-yes-vote\nuniverse")
        ax.set_xlabel("")
        ax.text(
            0.0,
            1.04,
            pretty,
            transform=ax.transAxes,
            ha="left",
            va="bottom",
            fontsize=14,
            weight="bold",
        )
        plt.setp(ax.get_yticklabels(), fontsize=13)
        sns.despine(ax=ax, top=True, right=True)
    for ax in axes[n_feat:]:
        ax.axis("off")
    fig.tight_layout()
    # Embed the published reproduction-gist URL into the figure
    # metadata (PNG Source tEXt chunk, PDF Subject info field) so
    # the citation travels with the file across slide decks /
    # blog posts. Reader extracts with `exiftool figure.png | grep
    # Source` or PIL's Image.open(p).info["Source"].
    # Published figure → data/analysis/figures/ (not the audit's
    # OUT_DIR). Convention: only PROMOTED figures live in the
    # figures folder; audit intermediates stay in their analysis
    # subdir.
    save_figure(
        fig, "topology_coverage_by_source",
        output_dir=FIGURES_DIR,
        formats=("pdf", "png"),
        gist_url="https://gist.github.com/beccajcarlson/95b0f4cdcaf6a6b91f57539cd1515a25",
    )
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

    print(f"[1/4] Building per-protein feature table from {V3.name}")
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
    # Both heatmap variants (un-clustered and clustered) retired per
    # user — the per-source bars + topology coverage figures
    # carry the analytical story more directly. The function bodies
    # stay in source for reference but are no longer called.
    # Per-DB bars use a SEPARATE enrichment table where the comparator
    # is Sonnet's included set instead of the universe complement.
    # Saved alongside the canonical vs-universe table so a reanalyst
    # can pull either comparison.
    db_vs_sonnet = _db_vs_sonnet_enrichment(df)
    dbs_path = out_dir / "inclusion_per_db_vs_sonnet.tsv"
    db_vs_sonnet.to_csv(dbs_path, sep="\t", index=False)
    print(f"      Wrote {len(db_vs_sonnet):,} (DB × feature) vs-Sonnet rows -> {dbs_path}")
    make_per_source_bars(db_vs_sonnet, out_dir)
    make_surfy_topology_coverage(df, out_dir)
    print("Done.")


if __name__ == "__main__":
    main()
