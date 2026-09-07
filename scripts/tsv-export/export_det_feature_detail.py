"""Export quantitative deterministic-feature detail from D1 (per gene) for S14.

The S14 figure's boolean det-feature flags (`mouse_has_one2one`,
`cyno_has_one2one`, `schweke_homomer`, `has_concerning_paralog`,
`has_ec_surface_bind_site`) tell you IF a gene has the feature but not the
MAGNITUDE. A reader analysing the bundled TSV can't tell whether a "concerning
paralog" is 40% or 95% identical, which gene it is, or how many surface-bind
sites there are. This adds the magnitude behind each flag:

  mouse_ortholog_pct_id / cyno_ortholog_pct_id  ortholog % identity (1:1)
  homomer_stoichiometry                          Schweke stoichiometry (2/3/4…)
  top_paralog_symbol / top_paralog_ecd_pct       closest paralog + its ECD % id
  n_ec_surface_bind_sites                        # extracellular surface-bind sites

All from the genome-wide D1 tables (`compara_ortholog` / `schweke_homomer_public`
/ `compara_paralog` / `surface_bind_site` + `topology_public`), keyed on
`gene_symbol` so `build_figure_tsvs.py` can LEFT-JOIN it into BOTH S14 facets
(the deep-dive tiers AND the Sonnet pool) — the same computation for every gene,
so the magnitude columns are uniform regardless of facet. One row per gene that
carries any of the detail.

Run:
    uv run python scripts/export_det_feature_detail.py
"""
from __future__ import annotations

from collections import Counter
from pathlib import Path

import pandas as pd

from accessible_surfaceome.cloud.d1_client import D1Client, D1Config
from accessible_surfaceome.env import load_env

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "data/processed/deep_dive/det_feature_detail.tsv"

_DETAIL_COLS = [
    "mouse_ortholog_pct_id", "cyno_ortholog_pct_id", "homomer_stoichiometry",
    "top_paralog_symbol", "top_paralog_ecd_pct", "n_ec_surface_bind_sites",
]


def _to_num(s: pd.Series) -> pd.Series:
    return pd.to_numeric(s, errors="coerce")


def main() -> int:
    load_env()
    with D1Client(D1Config.from_env_public()) as d1:
        # Canonical-human topology anchors the gene set + gives per_residue for
        # the extracellular surface-bind test. Scalar cols + the per-residue
        # string only (bounded — canonical rows).
        topo = pd.DataFrame(d1.query(
            "SELECT gene_symbol, uniprot_acc, per_residue_topology FROM topology_public "
            "WHERE species='human' AND is_canonical IN ('1', 1) "
            "AND cohort='human_canonical'", []))
        # 1:1 ortholog % identity (best per species).
        orth = pd.DataFrame(d1.query(
            "SELECT human_gene_symbol AS gene_symbol, species, "
            "MAX(CAST(percent_identity AS REAL)) AS pct FROM compara_ortholog "
            "WHERE orthology_type='ortholog_one2one' "
            "AND species IN ('mouse','cynomolgus') "
            "GROUP BY human_gene_symbol, species", []))
        # Schweke homomer stoichiometry (largest model if several).
        hom = pd.DataFrame(d1.query(
            "SELECT gene_symbol, MAX(CAST(stoichiometry AS INT)) AS homomer_stoichiometry "
            "FROM schweke_homomer_public WHERE stoichiometry IS NOT NULL "
            "GROUP BY gene_symbol", []))
        # Closest paralog by ECD identity (rank 1 = highest ECD % id per gene).
        par = pd.DataFrame(d1.query(
            "SELECT human_gene_symbol AS gene_symbol, "
            "paralog_gene_symbol AS top_paralog_symbol, "
            "CAST(ecd_pct_identity AS REAL) AS top_paralog_ecd_pct "
            "FROM compara_paralog WHERE rank_by_ecd_identity=1", []))
        # Surface-bind sites (paired with per_residue below to keep only the
        # ones anchored in an extracellular 'O' region).
        sites = pd.DataFrame(d1.query(
            "SELECT uniprot_acc, anchor_residue FROM surface_bind_site", []))

    # --- extracellular surface-bind site count per gene ---
    per_res = topo.dropna(subset=["uniprot_acc"]).set_index(
        "uniprot_acc")["per_residue_topology"].to_dict()
    acc_to_gene = dict(zip(topo["uniprot_acc"], topo["gene_symbol"]))
    ec_counts: Counter = Counter()
    sites = sites[sites["uniprot_acc"].isin(per_res)]
    for acc, grp in sites.groupby("uniprot_acc"):
        prt = per_res.get(acc)
        gene = acc_to_gene.get(acc)
        if not isinstance(prt, str) or not prt or not gene:
            continue
        n = sum(1 for a in _to_num(grp["anchor_residue"]).dropna().astype(int)
                if 1 <= a <= len(prt) and prt[a - 1] == "O")
        if n:
            ec_counts[gene] = max(ec_counts[gene], n)
    ec = pd.DataFrame({"gene_symbol": list(ec_counts),
                       "n_ec_surface_bind_sites": list(ec_counts.values())})

    # --- assemble one row per gene ---
    orth["pct"] = _to_num(orth["pct"]).round(1)
    opiv = (orth.pivot_table(index="gene_symbol", columns="species",
                             values="pct", aggfunc="max")
            .rename(columns={"mouse": "mouse_ortholog_pct_id",
                             "cynomolgus": "cyno_ortholog_pct_id"})
            .reset_index())
    par["top_paralog_ecd_pct"] = _to_num(par["top_paralog_ecd_pct"]).round(1)

    out = topo[["gene_symbol"]].drop_duplicates()
    for frame in (opiv, hom, par.drop_duplicates("gene_symbol"), ec):
        out = out.merge(frame, on="gene_symbol", how="left")
    out = out[out[_DETAIL_COLS].notna().any(axis=1)].sort_values("gene_symbol")

    OUT.parent.mkdir(parents=True, exist_ok=True)
    out.to_csv(OUT, sep="\t", index=False)
    print(f"wrote {OUT.relative_to(ROOT)}: {len(out)} genes with det-feature detail")
    for c in _DETAIL_COLS:
        print(f"  {c}: {out[c].notna().sum()} populated")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
