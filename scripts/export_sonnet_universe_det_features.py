"""Export deterministic features for the Sonnet dual-triage surface universe.

The S14 figure (``surfaceome_deterministic_features_placeholder``) compares the
structural / deterministic features of the deep-dive tiers (sourced from the
deep-dive RECORDS) against the FULL Sonnet dual-triage surface pool — every gene
the genome-wide Sonnet triage (``genome_full_sonnet_ncbi_v2``) called ``yes`` or
``contextual`` (~4,249 genes). Those genes are mostly NOT deep-dived, so their
det features come from the genome-wide D1 tables (``topology_public``,
``compara_ortholog``, ``compara_paralog``, ``schweke_homomer_public``,
``surface_bind_site``) instead — the SAME DeepTMHMM / Compara / Schweke
computation the records carry, just at genome-wide coverage. Topology coverage
for the Sonnet pool is ~100%, so the three continuous axes (TM count, protein
length, ECD length) are unbiased; the boolean features treat table-absence as a
real negative (no 1:1 ortholog / not a homomer / no concerning paralog / no
extracellular surface-bind site), matching how the records encode them.

One row per Sonnet-flagged gene with the same twelve feature columns the
deep-dive export derives, plus ``group='sonnet_dual_triage'``, so
``build_figure_tsvs.py`` can union it in as a fifth S14 facet.

Uses only scalar columns + one bounded ``per_residue_topology`` pull (for the
surface-bind anchors), so no full-blob / large-column fetch that would risk the
D1 isolate memory cap.

Run:
    uv run python scripts/export_sonnet_universe_det_features.py
"""
from __future__ import annotations

from pathlib import Path

import pandas as pd

from accessible_surfaceome.cloud.d1_client import D1Client, D1Config
from accessible_surfaceome.env import load_env

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "data/processed/deep_dive/sonnet_universe_det_features.tsv"
_TRIAGE_RUN_ID = "genome_full_sonnet_ncbi_v2"

# The exact twelve feature columns the deep-dive export derives (same names, so
# build_figure_tsvs can union the Sonnet rows straight into the S14 frame).
_FEATURE_COLS = [
    "tm_helix_count", "protein_length", "ecd_length_residues",
    "has_signal_peptide", "n_term_extracellular", "c_term_extracellular",
    "mouse_has_one2one", "cyno_has_one2one", "schweke_homomer",
    "alt_iso_diff_topo", "has_concerning_paralog", "has_ec_surface_bind_site",
]


def _to_int(series: pd.Series) -> pd.Series:
    return pd.to_numeric(series, errors="coerce")


def main() -> int:
    load_env()
    with D1Client(D1Config.from_env_public()) as d1:
        # 1. Sonnet-flagged surface pool (yes + contextual).
        son = pd.DataFrame(d1.query(
            "SELECT DISTINCT gene_symbol, uniprot_acc FROM triage_run_public "
            "WHERE run_id = ? AND predicted_verdict IN ('yes','contextual')",
            [_TRIAGE_RUN_ID],
        ))
        syms = set(son["gene_symbol"])
        print(f"Sonnet-flagged surface genes: {len(son)}")

        # 2. Canonical-human topology — the six topology features + per-residue
        #    string (bounded to canonical rows only). One row per gene.
        topo = pd.DataFrame(d1.query(
            "SELECT gene_symbol, uniprot_acc, tm_helix_count, protein_length, "
            "ecd_length_residues, signal_peptide_length, n_terminal_orientation, "
            "c_terminal_orientation, per_residue_topology FROM topology_public "
            "WHERE species = 'human' AND is_canonical IN ('1', 1) "
            "AND cohort = 'human_canonical'",
            [],
        ))
        topo = topo[topo["gene_symbol"].isin(syms)].drop_duplicates("gene_symbol")

        # 3. Alt-isoform topology change — any human isoform whose TM-helix count
        #    differs from the canonical. Scalar cols only.
        iso = pd.DataFrame(d1.query(
            "SELECT gene_symbol, is_canonical, tm_helix_count FROM topology_public "
            "WHERE species = 'human'",
            [],
        ))
        iso = iso[iso["gene_symbol"].isin(syms)].copy()
        iso["tm"] = _to_int(iso["tm_helix_count"])
        iso["canon"] = iso["is_canonical"].astype(str).isin(("1", "True"))
        canon_tm = iso[iso["canon"]].set_index("gene_symbol")["tm"].to_dict()
        alt_diff: set[str] = set()
        for gsym, grp in iso.groupby("gene_symbol"):
            ct = canon_tm.get(gsym)
            if ct is None:
                continue
            others = grp[~grp["canon"]]["tm"].dropna()
            if (others != ct).any():
                alt_diff.add(gsym)

        # 4. 1:1 orthologs (mouse / cynomolgus) — presence of a one2one row.
        orth = pd.DataFrame(d1.query(
            "SELECT DISTINCT human_gene_symbol, species FROM compara_ortholog "
            "WHERE orthology_type = 'ortholog_one2one'",
            [],
        ))
        mouse_o2o = set(orth[orth["species"] == "mouse"]["human_gene_symbol"])
        cyno_o2o = set(orth[orth["species"] == "cynomolgus"]["human_gene_symbol"])

        # 5. Homo-oligomer (Schweke) — presence in the atlas.
        homomer = {r["gene_symbol"] for r in d1.query(
            "SELECT DISTINCT gene_symbol FROM schweke_homomer_public", [])}

        # 6. Concerning paralog — a paralog with ECD %id >= 40 (viewer mid band).
        conc_par = {r["human_gene_symbol"] for r in d1.query(
            "SELECT DISTINCT human_gene_symbol FROM compara_paralog "
            "WHERE CAST(ecd_pct_identity AS REAL) >= 40", [])}

        # 7. >=1 EXTRACELLULAR surface-bind site — a predicted site whose anchor
        #    residue sits in an 'O' (outside/extracellular) region of the
        #    canonical per-residue topology.
        sites = pd.DataFrame(d1.query(
            "SELECT uniprot_acc, anchor_residue FROM surface_bind_site", []))
    # ---- compute per-gene features (pandas, outside the D1 context) ----
    per_res = topo.set_index("uniprot_acc")["per_residue_topology"].to_dict()
    ec_bind_accs: set[str] = set()
    sites = sites[sites["uniprot_acc"].isin(per_res)]
    for acc, grp in sites.groupby("uniprot_acc"):
        prt = per_res.get(acc)
        if not isinstance(prt, str) or not prt:
            continue
        for a in _to_int(grp["anchor_residue"]).dropna().astype(int):
            if 1 <= a <= len(prt) and prt[a - 1] == "O":
                ec_bind_accs.add(acc)
                break

    df = topo.copy()
    df["tm_helix_count"] = _to_int(df["tm_helix_count"])
    df["protein_length"] = _to_int(df["protein_length"])
    df["ecd_length_residues"] = _to_int(df["ecd_length_residues"])
    df["has_signal_peptide"] = (_to_int(df["signal_peptide_length"]) > 0).astype(int)
    df["n_term_extracellular"] = (df["n_terminal_orientation"] == "extracellular").astype(int)
    df["c_term_extracellular"] = (df["c_terminal_orientation"] == "extracellular").astype(int)
    df["mouse_has_one2one"] = df["gene_symbol"].isin(mouse_o2o).astype(int)
    df["cyno_has_one2one"] = df["gene_symbol"].isin(cyno_o2o).astype(int)
    df["schweke_homomer"] = df["gene_symbol"].isin(homomer).astype(int)
    df["alt_iso_diff_topo"] = df["gene_symbol"].isin(alt_diff).astype(int)
    df["has_concerning_paralog"] = df["gene_symbol"].isin(conc_par).astype(int)
    df["has_ec_surface_bind_site"] = df["uniprot_acc"].isin(ec_bind_accs).astype(int)
    df["group"] = "sonnet_dual_triage"

    out = df[["gene_symbol", "group", *_FEATURE_COLS]].sort_values("gene_symbol")
    OUT.parent.mkdir(parents=True, exist_ok=True)
    out.to_csv(OUT, sep="\t", index=False)
    print(f"wrote {OUT.relative_to(ROOT)}: {len(out)} Sonnet-universe det-feature rows")
    print("  coverage — topology (all rows carry it):", len(out))
    for c in ("mouse_has_one2one", "cyno_has_one2one", "schweke_homomer",
              "alt_iso_diff_topo", "has_concerning_paralog", "has_ec_surface_bind_site"):
        print(f"    {c}: {int(out[c].sum())} positive")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
