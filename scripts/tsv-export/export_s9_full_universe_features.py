"""Export the FULL any-yes-vote universe with genome-wide topology for Supp Fig 9.

S9 (``topology_coverage_by_source``) was built on the M1-limited
``per_protein_features.tsv``: only 794 zero-DB Sonnet rescues (vs the canonical
**960**) and topology scored for just the DB-flagged subset — so the zero-DB
Sonnet row read as misleadingly EMPTY (missing data, not depletion). This
rebuilds the source on the FULL any-yes-vote universe (Sonnet yes/contextual
incl. the PubMed rescue, OR any optimized-DB vote), with topology for every
gene:

  • universe + source flags   ← the Fig-3 table (``zero_db_rescues_by_triage.tsv``);
    ``src_sonnet`` = the canonical ``sonnet_verdict`` (incl. PubMed rescue), so
    ``sonnet_only`` (Sonnet-yc AND ``n_sources_optimized==0``) = 960.
  • 8 UniProt/keyword features ← the UniProt surface-candidates file + a fresh
    REST pull for the ~900 zero-DB accessions it doesn't cover. Feature counts +
    keyword-derived topology classes follow
    ``scripts/audit_db_vs_sonnet_inclusion.py`` exactly (same precedence).
  • ``deeptm_TM_NO_SP``        ← ``topology_public`` (D1), genome-wide DeepTMHMM.

Writes ``data/processed/db_vs_sonnet_inclusion/per_protein_features_topology_full.tsv``;
``build_topology_coverage_by_source`` reads it OFFLINE to produce the figure TSV
(so the figure stays reproducible-from-builder while this export carries the
UniProt/D1 pulls).

Run (needs UniProt network + D1):
    uv run python scripts/export_s9_full_universe_features.py
"""
from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

from accessible_surfaceome.cloud.d1_client import D1Client, D1Config
from accessible_surfaceome.env import load_env
from accessible_surfaceome.sources.uniprot import _feature_counts, iter_pages

ROOT = Path(__file__).resolve().parents[1]
ZERO_DB = ROOT / "data/processed/figures/zero_db_rescues_by_triage.tsv"
UNIPROT_CAND = ROOT / "data/external/uniprot_human_surface_candidates/uniprot_human_surface_candidates.tsv"
OUT = ROOT / "data/processed/db_vs_sonnet_inclusion/per_protein_features_topology_full.tsv"

_YC = ("yes", "contextual")
_TOPO_CLASSES = [
    "topo_gpi_anchored", "topo_gpcr_7tm", "topo_multi_pass_tm",
    "topo_single_pass_tm", "topo_signal_only_secreted",
    "topo_inner_leaflet_lipidated", "topo_no_tm_no_signal",
]


def _pull_uniprot(accs: list[str]) -> pd.DataFrame:
    """UniProt feature counts + keywords for ``accs`` (batched REST search)."""
    rows: list[dict] = []
    batch = 90
    for i in range(0, len(accs), batch):
        chunk = accs[i:i + batch]
        query = "(" + " OR ".join(f"accession:{a}" for a in chunk) + ")"
        entries, _ = iter_pages(query, page_size=200, timeout=90,
                                retry_max_attempts=4, min_request_interval_ms=300)
        for e in entries:
            fc = _feature_counts(e)
            kw = "|".join(k.get("name", "") for k in (e.get("keywords") or [])
                          if k.get("name"))
            rows.append({
                "uniprot_accession": e.get("primaryAccession", ""),
                "up_tm_count": fc["transmembrane"], "up_signal_count": fc["signal"],
                "up_lipidation_count": fc["lipid"], "up_glyc_count": fc["glycosylation"],
                "up_topo_extracellular_count": fc["topo_extracellular"],
                "up_keywords": kw,
            })
        print(f"  UniProt pull: {min(i + batch, len(accs))}/{len(accs)}", flush=True)
    return pd.DataFrame(rows)


def _derive_topology(df: pd.DataFrame) -> pd.DataFrame:
    """Mutually-exclusive topo_* one-hot — replicates
    audit_db_vs_sonnet_inclusion._derive_topology_class exactly (same precedence).
    NaN keywords → NaN across all classes (missing, not negative)."""
    kw = df["up_keywords"].fillna("")
    has_kw = kw.str.len() > 0
    low = kw.str.lower()
    is_gpi = low.str.contains("gpi-anchor", regex=False)
    is_gpcr = low.str.contains("g-protein coupled receptor", regex=False)
    is_intramem = low.str.contains("intramembrane", regex=False)
    is_secreted = low.str.contains("secreted", regex=False)
    is_prenyl = low.str.contains("prenylation", regex=False)
    is_myr = low.str.contains("myristate", regex=False)
    is_inner_lipid = is_prenyl | is_myr
    tm = df["up_tm_count"].fillna(0)
    sig = df["up_signal_count"].fillna(0)
    lip = df["up_lipidation_count"].fillna(0)

    klass = pd.Series([""] * len(df), index=df.index)
    klass = klass.mask((klass == "") & is_gpi, "topo_gpi_anchored")
    klass = klass.mask((klass == "") & is_intramem & (tm == 0), "topo_intramembrane")
    klass = klass.mask((klass == "") & is_gpcr & (tm >= 5), "topo_gpcr_7tm")
    klass = klass.mask((klass == "") & (tm >= 2), "topo_multi_pass_tm")
    klass = klass.mask((klass == "") & (tm == 1), "topo_single_pass_tm")
    klass = klass.mask((klass == "") & (sig >= 1) & (tm == 0) & (is_secreted | (lip == 0)),
                       "topo_signal_only_secreted")
    klass = klass.mask((klass == "") & is_inner_lipid & (tm == 0) & (sig == 0),
                       "topo_inner_leaflet_lipidated")
    klass = klass.mask((klass == "") & has_kw & (tm == 0) & (sig == 0), "topo_no_tm_no_signal")

    for name in _TOPO_CLASSES:
        df[name] = (klass == name).astype("float")
        df.loc[~has_kw, name] = np.nan
    df["up_has_glyc"] = (df["up_glyc_count"] > 0).astype("float")
    df.loc[df["up_glyc_count"].isna(), "up_has_glyc"] = np.nan
    return df


def main() -> int:
    load_env()
    # 1. Universe + canonical source flags from the Fig-3 table.
    z = pd.read_csv(ZERO_DB, sep="\t")
    sy = z["sonnet_verdict"].isin(_YC)
    uni = z[sy | (z["n_sources_optimized"] > 0)].copy()
    uni["src_sonnet"] = sy[uni.index].astype(int)
    uni["src_surfy"] = pd.to_numeric(uni["surfy_surface_flag"], errors="coerce").fillna(0).astype(int)
    uni["src_go"] = pd.to_numeric(uni["go_surface_flag"], errors="coerce").fillna(0).astype(int)
    uni["src_hpa"] = pd.to_numeric(uni["hpa_surface_flag"], errors="coerce").fillna(0).astype(int)
    uni = uni.rename(columns={"uniprot_acc": "uniprot_accession"})
    uni["gene_symbol"] = uni["hgnc_symbol"]
    keep = ["uniprot_accession", "hgnc_id", "hgnc_symbol", "gene_symbol",
            "ensembl_gene", "ncbi_gene_id", "src_sonnet", "src_surfy",
            "src_go", "src_hpa", "uniprot_optimized", "cspa_optimized", "n_sources_optimized"]
    # Key by GENE (hgnc_id) so the count matches the canonical per-gene universe
    # (sonnet_only = 960 genes; 6 accessions are shared by >1 gene, so a
    # per-accession dedup would undercount to 949). Topology still joins by the
    # gene's uniprot_accession.
    uni = uni[[c for c in keep if c in uni.columns]].drop_duplicates("hgnc_id")
    n_son_only = int(((uni["src_sonnet"] == 1) & (uni["n_sources_optimized"] == 0)).sum())
    print(f"any-yes universe: {len(uni)} | sonnet_only (target 960): {n_son_only}")

    # 2. UniProt features: existing candidates file + fresh pull for the gap.
    cand = pd.read_csv(UNIPROT_CAND, sep="\t", dtype=str).rename(columns={
        "accession": "uniprot_accession",
        "feature_transmembrane_count": "up_tm_count",
        "feature_signal_count": "up_signal_count",
        "feature_lipidation_count": "up_lipidation_count",
        "feature_glycosylation_count": "up_glyc_count",
        "feature_topo_extracellular_count": "up_topo_extracellular_count",
        "keywords": "up_keywords"})
    upcols = ["uniprot_accession", "up_tm_count", "up_signal_count", "up_lipidation_count",
              "up_glyc_count", "up_topo_extracellular_count", "up_keywords"]
    cand = cand[upcols].drop_duplicates("uniprot_accession")
    gap = sorted(set(uni["uniprot_accession"].dropna()) - set(cand["uniprot_accession"]))
    # Cache the gap pull (gitignored blob cache) so re-runs are instant.
    cache = ROOT / "data/external/blob_cache/_s9_uniprot_gap_cache.tsv"
    cache.parent.mkdir(parents=True, exist_ok=True)
    if cache.is_file():
        pulled = pd.read_csv(cache, sep="\t", dtype=str)
        missing = sorted(set(gap) - set(pulled["uniprot_accession"]))
        print(f"UniProt gap cache: {len(pulled)} cached, {len(missing)} to pull")
        if missing:
            pulled = pd.concat([pulled, _pull_uniprot(missing)], ignore_index=True)
            pulled.to_csv(cache, sep="\t", index=False)
    else:
        print(f"UniProt gap accessions to pull: {len(gap)}")
        pulled = _pull_uniprot(gap) if gap else pd.DataFrame(columns=pd.Index(upcols))
        pulled.to_csv(cache, sep="\t", index=False)
    up = pd.concat([cand, pulled], ignore_index=True).drop_duplicates("uniprot_accession", keep="last")
    for c in ["up_tm_count", "up_signal_count", "up_lipidation_count", "up_glyc_count",
              "up_topo_extracellular_count"]:
        up[c] = pd.to_numeric(up[c], errors="coerce")

    df = uni.merge(up, on="uniprot_accession", how="left")
    df = _derive_topology(df)

    # 3. DeepTMHMM TM-without-signal class, genome-wide from topology_public.
    with D1Client(D1Config.from_env_public()) as d1:
        topo = pd.DataFrame(d1.query(
            "SELECT uniprot_acc AS uniprot_accession, deeptmhmm_label FROM topology_public "
            "WHERE species='human' AND is_canonical IN ('1',1) AND cohort='human_canonical'", []))
    topo = topo.drop_duplicates("uniprot_accession")
    df = df.merge(topo, on="uniprot_accession", how="left")
    df["deeptm_TM_NO_SP"] = (df["deeptmhmm_label"] == "TM").astype("float")
    df.loc[df["deeptmhmm_label"].isna(), "deeptm_TM_NO_SP"] = np.nan

    # Trim to stable IDs + source flags + the 9 features (drop the intermediate
    # raw UniProt counts + keyword strings — the keyword column alone bloats the
    # TSV to ~1.8 MB; the figure + reanalysis need only the derived features).
    final_cols = (
        ["uniprot_accession", "hgnc_id", "hgnc_symbol", "gene_symbol",
         "ensembl_gene", "ncbi_gene_id", "src_sonnet", "src_surfy", "src_go",
         "src_hpa", "uniprot_optimized", "cspa_optimized", "n_sources_optimized"]
        + _TOPO_CLASSES + ["up_has_glyc", "deeptm_TM_NO_SP"]
    )
    df = df[[c for c in final_cols if c in df.columns]]
    OUT.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(OUT, sep="\t", index=False)
    print(f"\nwrote {OUT.relative_to(ROOT)}: {len(df)} rows")
    print(f"  sonnet_only = {n_son_only}")
    print("  topo coverage (non-null) — "
          + ", ".join(f"{c.replace('topo_','')}: {int(df[c].notna().sum())}"
                      for c in ("topo_gpi_anchored", "up_has_glyc", "deeptm_TM_NO_SP")))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
