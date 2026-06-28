"""Build the three positive-control target lists for the surfaceome paper.

Sources:
  1. ADC = TheraSAbDab antibody-drug conjugates ∪ Open Targets MoA (all phases,
     antibody-binding rows; non-cytotoxic conjugates and family-expansion
     attributions filtered out).
  2. TCE = TheraSAbDab CD3-bispecifics + BiTE/DART platforms (derived; the
     resource has no TCE label of its own).
  3. ViralZone = human viral entry receptors (UniProt-anchored), pulled from
     the deliverome-internal repo's scrape.

For each list every target is resolved to a stable HGNC ID and joined against
candidate_universe_v3 to recover the per-DB surface flags + Sonnet verdicts.
Output: three augmented TSVs at ``data/processed/positive_controls/``, each
keyed on hgnc_id with hgnc_symbol/uniprot_acc/ensembl_gene/ncbi_gene_id +
5-DB flags + Sonnet (NCBI dual-pass) flag.

Run:

    uv run python scripts/build_positive_control_lists.py
"""

from __future__ import annotations

import io
import re
import sys
from pathlib import Path

import pandas as pd
import requests

from accessible_surfaceome.cloud.d1_client import D1Client
from accessible_surfaceome.env import load_env


REPO_ROOT = Path(__file__).resolve().parents[1]
CU_PATH = REPO_ROOT / "data/processed/candidate_universe/candidate_universe_v3.tsv"
COHORT_PATH = REPO_ROOT / "data/external/ncbi_gene_info/Homo_sapiens.protein_coding.with_hgnc.tsv"
OUT_DIR = REPO_ROOT / "data/processed/positive_controls"
OUT_DIR.mkdir(parents=True, exist_ok=True)

THERA_URL = (
    "https://opig.stats.ox.ac.uk/webapps/sabdab-sabpred/static/downloads/"
    "TheraSAbDab_SeqStruc_OnlineDownload.csv"
)
OT_RELEASE = "26.06"
OT_BASE = f"https://ftp.ebi.ac.uk/pub/databases/opentargets/platform/{OT_RELEASE}/output"
VZ_CSV = REPO_ROOT / "data/external/viralzone/viralzone_human_entry_receptors.csv"
VZ_SOURCE_NOTE = (
    "Mirrored from Deliverome-Project/deliverome-internal:data/raw/"
    "viralzone_human_entry_receptors.csv "
    "(Expasy ViralZone scrape; CC BY 4.0 attribution to ViralZone)."
)

# Non-cytotoxic conjugates that TheraSAbDab tags "ADC" but aren't classic
# cytotoxic ADCs (hydrogel half-life extension, IL-2 cytokine fusions,
# peptide hormone conjugates). Filtered out of the ADC positive-control list.
NON_CYTOTOXIC_PAYLOADS = re.compile(r"\b(tedromer|celmoleukin|cafraglutide)\b", re.IGNORECASE)

# Cytotoxic-payload protein names that Open Targets MoA lists as the "target"
# of certain ADC entries. These are payload-mechanism rows, not antibody-
# binding rows — drop them so the universe stays surface-only.
OT_PAYLOAD_NAMES = {
    "80S Ribosome", "Tubulin", "DNA topoisomerase 1", "Elongation factor 2",
    "Microtubule", "DNA topoisomerase 2", "DNA topoisomerase II", "60S Ribosome",
    "40S Ribosome", "Spliceosome", "RNA polymerase II", "DNA polymerase",
}

# HGNC previous-symbol fixes for the small set of named ADC/TCE targets that
# upstream catalogs still cite under retired symbols. Each entry is keyed on
# the legacy symbol (UPPER); value is the canonical HGNC-current symbol.
PREV_SYMBOL = {
    "PVRL4": "NECTIN4", "PVRL1": "NECTIN1", "PVRL2": "NECTIN2",
    "EGFRVIII": "EGFR", "HER1": "EGFR", "HER2": "ERBB2",
    "HER3": "ERBB3", "HER4": "ERBB4", "PSMA": "FOLH1",
}

# ----------------------------------------------------------------------
# Helpers
# ----------------------------------------------------------------------


def _http_get(url: str, *, expect_bytes: bool = False) -> bytes | str:
    """Polite GET with an identifying User-Agent."""
    headers = {"User-Agent": "accessible-surfaceome positive-control builder (becca@deliverome.org)"}
    r = requests.get(url, headers=headers, timeout=120)
    r.raise_for_status()
    return r.content if expect_bytes else r.text


def _load_cohort() -> tuple[pd.DataFrame, dict, dict, dict]:
    cohort = pd.read_csv(COHORT_PATH, sep="\t")
    nn = cohort.dropna(subset=["ensembl_gene"])
    sym_to_hgnc = dict(zip(cohort["gene_symbol"], cohort["hgnc_id"]))
    ensg_to_hgnc = dict(zip(nn["ensembl_gene"], nn["hgnc_id"]))
    ensg_to_sym = dict(zip(nn["ensembl_gene"], nn["gene_symbol"]))
    return cohort, sym_to_hgnc, ensg_to_hgnc, ensg_to_sym


def _resolve_symbol(s: str, sym_to_hgnc: dict) -> str | None:
    if not s:
        return None
    s = s.strip()
    if s in sym_to_hgnc:
        return sym_to_hgnc[s]
    su = s.upper()
    if su in PREV_SYMBOL:
        return sym_to_hgnc.get(PREV_SYMBOL[su])
    if su in sym_to_hgnc:
        return sym_to_hgnc[su]
    return None


# ----------------------------------------------------------------------
# Source-specific pulls
# ----------------------------------------------------------------------


def pull_therasabdab() -> pd.DataFrame:
    """Fetch TheraSAbDab CSV and return as DataFrame."""
    print(f"[therasabdab] downloading {THERA_URL}")
    raw = _http_get(THERA_URL, expect_bytes=True)
    return pd.read_csv(io.BytesIO(raw))


def pull_open_targets() -> tuple[pd.DataFrame, pd.DataFrame]:
    """Pull drug_molecule + drug_mechanism_of_action parquet files."""
    print(f"[open_targets] release {OT_RELEASE}")
    mol_url = f"{OT_BASE}/drug_molecule/part-00000-5581d2c3-048b-4097-934f-51cec06d7ff0-c000.snappy.parquet"
    moa_urls = [
        f"{OT_BASE}/drug_mechanism_of_action/part-0000{i}-10b94b1b-f29a-440c-98e0-c91862b6d2a8-c000.snappy.parquet"
        for i in (0, 1)
    ]
    mol = pd.read_parquet(io.BytesIO(_http_get(mol_url, expect_bytes=True)))
    moa = pd.concat(
        [pd.read_parquet(io.BytesIO(_http_get(u, expect_bytes=True))) for u in moa_urls],
        ignore_index=True,
    )
    return mol, moa


def pull_viralzone() -> pd.DataFrame:
    """Load the ViralZone human-entry receptor CSV from the in-repo mirror.

    Source: ``data/external/viralzone/viralzone_human_entry_receptors.csv``,
    mirrored from deliverome-internal so the public reproduction does not
    depend on private-repo auth.
    """
    print(f"[viralzone] reading {VZ_CSV.relative_to(REPO_ROOT)}")
    return pd.read_csv(VZ_CSV)


# ----------------------------------------------------------------------
# Filters + target extraction
# ----------------------------------------------------------------------


def _therasabdab_adc_mask(df: pd.DataFrame) -> pd.Series:
    is_adc = (
        df["Format"].fillna("").str.contains("ADC", case=False, regex=False)
        | df["Notes"].fillna("").str.contains("ADC with", case=False, regex=False)
    )
    non_cytotoxic = df["Notes"].fillna("").apply(
        lambda s: bool(NON_CYTOTOXIC_PAYLOADS.search(str(s)))
    )
    n_dropped = (is_adc & non_cytotoxic).sum()
    print(f"[therasabdab/adc] dropped {n_dropped} non-cytotoxic conjugates (tedromer/celmoleukin/cafraglutide)")
    return is_adc & ~non_cytotoxic


def _therasabdab_tce_mask(df: pd.DataFrame) -> pd.Series:
    """TCE = bispecific+CD3E binding OR BiTE/DART platform.

    TheraSAbDab has no TCE label — derived from Format + Target + Development Tech.
    """
    is_bispec = df["Format"].fillna("").str.contains("Bispecific|Trispecific|Tetraspecific", case=False, regex=True)
    binds_cd3 = df["Target"].fillna("").str.contains("CD3E", case=False, regex=False)
    bite_tech = df["Development Tech"].fillna("").str.contains("BiTE|DART|Dual-Affinity", case=False, regex=True)
    return (is_bispec & binds_cd3) | bite_tech


def _target_clusters(targets_str) -> list[str]:
    """Split a TheraSAbDab Target cell into individual binding-partner clusters."""
    if pd.isna(targets_str):
        return []
    slots = []
    for raw in re.split(r";", str(targets_str)):
        raw = raw.strip()
        if not raw:
            continue
        for sub in re.split(r"\s+and\s+|&", raw):
            sub = sub.strip()
            if sub:
                slots.append(sub)
    return slots


def _cluster_to_hgnc(cluster: str, sym_to_hgnc: dict) -> str | None:
    for tok in cluster.split("/"):
        h = _resolve_symbol(tok.strip(), sym_to_hgnc)
        if h:
            return h
    return None


def collect_therasabdab_hgncs(df: pd.DataFrame, mask: pd.Series, sym_to_hgnc: dict) -> set[str]:
    """Extract unique HGNC IDs from the rows passing mask."""
    out: set[str] = set()
    for t in df.loc[mask, "Target"]:
        for cluster in _target_clusters(t):
            h = _cluster_to_hgnc(cluster, sym_to_hgnc)
            if h:
                out.add(h)
    return out


def _is_consistent_target(
    ensg: str, target_name: str, mechanism: str,
    ensg_to_sym: dict, cohort_desc: dict,
) -> bool:
    """Drop OT MoA family-expansion rows: keep an ENSG only if its symbol or
    canonical description appears in the row's targetName/mechanism text."""
    sym = ensg_to_sym.get(ensg)
    if not sym:
        return True
    blob = f"{target_name} {mechanism}".upper()
    if sym.upper() in blob:
        return True
    desc = (cohort_desc.get(ensg) or "").upper()
    if desc and any(tok for tok in desc.split() if len(tok) > 4 and tok in blob):
        return True
    return False


def collect_open_targets_adc_hgncs(
    mol: pd.DataFrame, moa: pd.DataFrame,
    ensg_to_hgnc: dict, ensg_to_sym: dict, cohort_desc: dict,
) -> set[str]:
    adcs = set(mol[mol["drugType"] == "Antibody drug conjugate"]["id"])
    moa_ab = moa[~moa["targetName"].isin(OT_PAYLOAD_NAMES)]
    kept_per_chembl: dict[str, set[str]] = {}
    dropped = 0
    for _, row in moa_ab.iterrows():
        cids = row["chemblIds"]
        if cids is None or len(cids) == 0:
            continue
        adc_cids = [c for c in cids if c in adcs]
        if not adc_cids:
            continue
        tgts = row["targets"] if row["targets"] is not None else []
        target_name = str(row.get("targetName", ""))
        mechanism = str(row.get("mechanismOfAction", ""))
        keep_ensgs: set[str] = set()
        for t in tgts:
            if not str(t).startswith("ENSG"):
                continue
            if _is_consistent_target(t, target_name, mechanism, ensg_to_sym, cohort_desc):
                keep_ensgs.add(t)
            else:
                dropped += 1
        for cid in adc_cids:
            kept_per_chembl.setdefault(cid, set()).update(keep_ensgs)
    print(f"[open_targets/adc] dropped {dropped} family-expansion ENSG attributions")
    hgncs = {ensg_to_hgnc[e] for s in kept_per_chembl.values() for e in s if e in ensg_to_hgnc}
    return hgncs


def collect_viralzone_hgncs(vz: pd.DataFrame, cu: pd.DataFrame) -> set[str]:
    """Parse the Receptor field's UniProt accessions and resolve via the universe."""
    uniprot_re = re.compile(r"([OPQ][0-9][A-Z0-9]{3}[0-9]|[A-NR-Z][0-9](?:[A-Z][A-Z0-9]{2}[0-9]){1,2})")
    accs: set[str] = set()
    for v in vz["Receptor"].dropna():
        accs.update(uniprot_re.findall(str(v)))
    uni_to_hgnc = dict(zip(cu["uniprot_acc"].dropna(), cu["hgnc_id"]))
    return {uni_to_hgnc[a] for a in accs if a in uni_to_hgnc}


# ----------------------------------------------------------------------
# Sonnet dual-pass via D1
# ----------------------------------------------------------------------


def fetch_sonnet_dual_positive() -> set[str]:
    """Return the set of gene symbols positive in either NCBI v1 or v2.

    Positive = predicted_verdict in {yes, contextual}. PubMed-augmented
    variant is excluded — it's a separate exploration, not part of the
    paper's dual triage strategy.
    """
    load_env()
    with D1Client() as d1:
        rows = d1.query(
            """
            SELECT DISTINCT gene_symbol FROM triage_run
            WHERE run_id IN ('genome_full_sonnet_ncbi_v1', 'genome_full_sonnet_ncbi_v2')
              AND predicted_verdict IN ('yes', 'contextual');
            """,
            [],
        )
    return {r["gene_symbol"] for r in rows}


# ----------------------------------------------------------------------
# Output build
# ----------------------------------------------------------------------


def build_indicator_df(
    hgnc_set: set[str],
    cu: pd.DataFrame, cohort: pd.DataFrame,
    sonnet_pos_hgnc: set[str],
) -> pd.DataFrame:
    """Build the augmented indicator TSV for one category."""
    cu_by_hgnc = cu.set_index("hgnc_id")
    cohort_by_hgnc = cohort.set_index("hgnc_id")
    rows = []
    for h in sorted(hgnc_set):
        in_cu = h in cu_by_hgnc.index
        in_cohort = h in cohort_by_hgnc.index
        rec = {"hgnc_id": h}
        if in_cohort:
            cr = cohort_by_hgnc.loc[h]
            cr = cr.iloc[0] if isinstance(cr, pd.DataFrame) else cr
            rec["hgnc_symbol"] = cr.get("gene_symbol")
            rec["ensembl_gene"] = cr.get("ensembl_gene")
            rec["ncbi_gene_id"] = cr.get("ncbi_gene_id")
        if in_cu:
            cr = cu_by_hgnc.loc[h]
            cr = cr.iloc[0] if isinstance(cr, pd.DataFrame) else cr
            rec["uniprot_acc"] = cr.get("uniprot_acc")
            for db in ("uniprot", "go", "hpa", "surfy", "cspa"):
                rec[f"{db}_flag"] = int(cr.get(f"{db}_flag", 0))
            rec["n_db_votes"] = int(cr.get("n_db_votes", 0))
        else:
            rec.setdefault("uniprot_acc", None)
            for db in ("uniprot", "go", "hpa", "surfy", "cspa"):
                rec[f"{db}_flag"] = 0
            rec["n_db_votes"] = 0
        rec["sonnet_ncbi_dual_flag"] = int(h in sonnet_pos_hgnc)
        rows.append(rec)
    return pd.DataFrame(rows)


def main() -> None:
    print(f"=== Loading cohort + candidate universe ===")
    cohort, sym_to_hgnc, ensg_to_hgnc, ensg_to_sym = _load_cohort()
    cohort_desc = dict(zip(cohort["ensembl_gene"].dropna(), cohort["description"]))
    cu = pd.read_csv(CU_PATH, sep="\t")
    sym_to_hgnc_cu = dict(zip(cu["gene_symbol"], cu["hgnc_id"]))

    print(f"=== Sonnet dual-pass positives from D1 ===")
    sonnet_pos = fetch_sonnet_dual_positive()
    sonnet_pos_hgnc = {sym_to_hgnc_cu[s] for s in sonnet_pos if s in sym_to_hgnc_cu}
    sonnet_pos_hgnc |= {sym_to_hgnc[s] for s in sonnet_pos if s in sym_to_hgnc and s not in sym_to_hgnc_cu}
    print(f"  Sonnet dual-pass positive HGNCs: {len(sonnet_pos_hgnc)}")

    print(f"=== ADC ===")
    df_t = pull_therasabdab()
    mol, moa = pull_open_targets()
    adc_mask = _therasabdab_adc_mask(df_t)
    tdab_adc = collect_therasabdab_hgncs(df_t, adc_mask, sym_to_hgnc)
    ot_adc = collect_open_targets_adc_hgncs(mol, moa, ensg_to_hgnc, ensg_to_sym, cohort_desc)
    adc_union = tdab_adc | ot_adc
    print(f"  TheraSAbDab ADC HGNCs: {len(tdab_adc)};  Open Targets ADC HGNCs: {len(ot_adc)};  union: {len(adc_union)}")

    print(f"=== TCE ===")
    tce_mask = _therasabdab_tce_mask(df_t)
    tce = collect_therasabdab_hgncs(df_t, tce_mask, sym_to_hgnc)
    print(f"  TheraSAbDab TCE HGNCs: {len(tce)}")

    print(f"=== ViralZone ===")
    try:
        vz = pull_viralzone()
        vz_set = collect_viralzone_hgncs(vz, cu)
    except Exception as e:
        print(f"  WARN: ViralZone fetch failed ({e}); skipping. The published")
        print(f"        TSV must be checked in manually — read from")
        print(f"        deliverome-internal LFS.")
        vz_set = set()
    print(f"  ViralZone HGNCs: {len(vz_set)}")

    for label, hgnc_set in [("ADC", adc_union), ("TCE", tce), ("VZ", vz_set)]:
        out = OUT_DIR / f"positive_control_{label}.tsv"
        df_out = build_indicator_df(hgnc_set, cu, cohort, sonnet_pos_hgnc)
        df_out.to_csv(out, sep="\t", index=False)
        print(f"  Wrote {out} ({len(df_out)} rows)")


if __name__ == "__main__":
    main()
