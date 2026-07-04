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

# ADCdb antigen list — checked-in TSV scraped from the IDRBlab ADCdb search
# pages. 333 unique antigens; ~302 carry an inline HGNC symbol (the
# parenthesized last token of the "Antigen Name" string). The remaining ~31
# are descriptive glycans / variants / undisclosed antigens that we treat as
# unresolved.
ADCDB_TSV = REPO_ROOT / "data/external/adcdb/adcdb_antigens.tsv"

# Per-antigen curator-written Function descriptions scraped from ADCdb's
# antigen detail pages. ADCdb-internal text — read by the Function-text noise
# filter below.
ADCDB_FUNCTIONS_TSV = REPO_ROOT / "data/external/adcdb/adcdb_antigen_functions.tsv"

# Function-text patterns that match curator-written descriptions of canonical
# secreted / nuclear / intracellular protein families. Catches 12 of 15
# known-noise misses (the other 3 lack function text in ADCdb) and zero
# rescues. All patterns are biological function keywords, not subcellular
# location labels — so the filter is independent of UniProt's subcellular
# annotation.
_FN_NOISE_PATTERNS = "|".join([
    # Each pattern is a biological-function phrase from ADCdb's curator-written
    # text that distinguishes secreted / intracellular proteins. The bare
    # word "cytokine" was tested but is too ambiguous — it appears in many
    # surface-protein descriptions (TGFBR1, CD70, AXL, MERTK, FLT3, KIT,
    # CD47, CD74, TNFSF10…) where "receptor for" / "ligand for" is mentioned.
    # The patterns below match only when the protein itself is functioning
    # as a secreted / intracellular factor.
    # Cytokine pattern restricted to those described as "plays/stimulates roles
    # in..." (true secreted cytokines like IL13). Excludes "Cytokine which is
    # the ligand for" (CD70 — membrane-bound) and "Cytokine that binds to"
    # (TNF, TNFSF10 — also membrane-bound family).
    r"^\s*Cytokine\s+that\s+(?:plays|stimulates|induces)",
    r"growth\s+factor\s+active",                  # VEGFA: "Growth factor active in angiogenesis"
    r"transcription(?:al)?\s+(?:factor|elongation)",
    r"RNA\s+polymerase",                          # AFF4
    r"elongation\s+complex",                      # AFF4 (super elongation)
    r"histone\s+acetyltransferase",               # MSL1
    r"\bSNARE\b",                                 # BET1, VAMP8 — Golgi/endosomal SNAREs
    r"colloidal\s+osmotic",                       # ALB osmotic regulator
    r"chemotactic\s+for",                         # CCL1 — secreted chemokine
    r"in\s+saliva",                               # CA6 — secreted salivary protein
    r"carbonic\s+anhydrase\b",
    r"factor\s+\w+\s+cleaves",                    # CFD: "Factor D cleaves factor B"
    r"C3\s+convertase",                           # CFD complement convertase
    r"negative\s+regulator\s+of\s+skeletal",      # MSTN myostatin
    r"calcium-signaling.*kinase",                 # DCLK1
    r"kinase.*calcium-signaling",
    r"phosphate\s+cotransporter",                 # SLC34A2-class transporter
    r"\bplasma\s+protein\b",                      # ALB — NOT "plasma membrane"!
    r"most\s+abundant\s+protein\s+in\s+(?:blood|serum)",  # ALB
])
ADCDB_FN_NOISE = re.compile(rf"\b({_FN_NOISE_PATTERNS})\b", re.IGNORECASE)

# ADCdb antigen-name regex filter. Drops entries whose `antigen_name` field
# matches a payload-mechanism keyword or an explicit intracellular/nuclear
# protein-name pattern. These are catalog noise — ADCdb attributing the
# cytotoxic payload's mechanism target as the antibody's binding target
# (TUBA1B for vedotin-class ADCs, PARP1 for olaparib payloads, etc.) — and
# they aren't surface antigens that an antibody actually engages.
#
# Uses ADCdb's own text only — no external annotation DBs. The Sonnet
# rescues (STEAP1, STEAP2, KLK3, GSDME, HSPA1A, MMP9, LRG1) and all
# clinical ADC targets (ALK, BSG, CA9, ASGR1, etc.) survive this filter
# because their antigen names don't match these patterns.
_ADCDB_NOISE_PATTERNS = "|".join([
    # Payload-mechanism (the cytotoxic drug's target, not the antibody's)
    r"tubulin", r"topoisomerase", r"ribosom", r"RNA\s+polymerase",
    r"DNA\s+polymerase", r"elongation\s+factor", r"kinesin",
    r"microtubule", r"spliceosome", r"histone",
    r"poly\s*\[ADP-ribose\]\s*polymerase",   # PARP1
    r"glutathione\s+peroxidase",             # GPX4
    # Specific intracellular / nuclear antigen names ADCdb attributes
    r"cellular\s+tumor\s+antigen\s+p53",     # TP53
    r"sequestosome",                          # SQSTM1
    r"3-oxoacyl", r"formylglycine", r"myotubularin",   # OXSM, SUMF1, MTM1
    r"metaxin",                               # MTX1, MTX2
    r"translocator\s+protein",                # TSPO
    r"Ras-related\s+protein",                 # RRAS
    r"phosphatidylserine\s+synthase",         # PTDSS1
    r"Tax1-binding",                          # TAX1BP3
    r"melanoma-associated\s+antigen",         # MAGEA1
    r"ribonuclease",                          # RPP25 / Lupus La
    r"galactosyltransferase",                 # A4GALT
    r"double\s+homeobox",                     # DUX4
    r"sjogren", r"lupus\s+la",                # SSB
    r"interferon-stimulated",                 # ISG20
    # Compartment / location keywords in the antigen NAME itself
    r"cytoplasm", r"cytosolic", r"nuclear\s+protein", r"mitochondrial\s+protein",
    # Apolipoprotein family — all secreted by definition (APOD's "surface"
    # signal comes from HDL-particle binding, not a dedicated surface anchor)
    r"apolipoprotein",
    # Pregnancy-specific glycoproteins — all secreted into maternal serum
    r"pregnancy-specific",
])
ADCDB_NAME_NOISE = re.compile(rf"\b({_ADCDB_NOISE_PATTERNS})\b", re.IGNORECASE)

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
    """TCE = bispecific (or higher) AND CD3E in the target field.

    TheraSAbDab has no TCE label — derived from Format + Target. We require
    CD3E in the target to avoid false positives: the BiTE/DART platform
    regex used previously caught Faricimab (VEGFA × ANGPT2, eye disease,
    not a TCE) and Lorigerlimab (PD-1 × CTLA-4, checkpoint bispecific,
    not a TCE) because both use a "Dual-Affinity Re-Targeting" platform
    despite not being T-cell engagers.
    """
    is_bispec = df["Format"].fillna("").str.contains(
        "Bispecific|Trispecific|Tetraspecific", case=False, regex=True
    )
    binds_cd3 = df["Target"].fillna("").str.contains("CD3E", case=False, regex=False)
    return is_bispec & binds_cd3


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


# Half-life-extension binding partners that appear in bispecific Target lists
# but aren't therapeutic targets (the antibody arm binds them to extend serum
# half-life; the actual therapeutic target is the other arm). Drop wherever
# seen in cluster extraction.
HALF_LIFE_BINDERS = {"ALB"}


def _cluster_to_hgnc(cluster: str, sym_to_hgnc: dict) -> str | None:
    for tok in cluster.split("/"):
        h = _resolve_symbol(tok.strip(), sym_to_hgnc)
        if h:
            return h
    return None


def collect_therasabdab_hgncs(df: pd.DataFrame, mask: pd.Series, sym_to_hgnc: dict) -> set[str]:
    """Extract unique HGNC IDs from the rows passing mask, dropping
    half-life-extension binding partners (e.g. ALB)."""
    out: set[str] = set()
    for t in df.loc[mask, "Target"]:
        for cluster in _target_clusters(t):
            # Skip half-life arms entirely (ALB on Gocatamig, etc.)
            first_token = cluster.split("/")[0].strip().upper()
            if first_token in HALF_LIFE_BINDERS:
                continue
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


def collect_adcdb_hgncs(sym_to_hgnc: dict) -> set[str]:
    """Resolve ADCdb antigens to HGNC IDs via the inline gene symbol.

    The ``adcdb_antigens.tsv`` file is the parsed letter-page dump (Antigen ID
    + Antigen Name + inline gene symbol). 27 of 268 antigens are descriptive
    glycans / variants / undisclosed and lack an inline HGNC symbol; those
    are unresolved by design.
    """
    if not ADCDB_TSV.is_file():
        print(f"[adcdb] {ADCDB_TSV.relative_to(REPO_ROOT)} not present; skipping")
        return set()
    print(f"[adcdb] reading {ADCDB_TSV.relative_to(REPO_ROOT)}")
    df = pd.read_csv(ADCDB_TSV, sep="\t")
    # Re-parse multi-target antigen names ("A (GENE_A); B (GENE_B)") to take
    # the FIRST parenthesized symbol — the primary target. The scraped TSV's
    # `gene_symbol_inline` was set from the LAST parenthesized token, which
    # for dual-target ADCs like "PDGFRB; VEGFA" routes to the secondary
    # binding partner rather than the primary therapeutic target.
    #
    # Multi-target delimiter is `";\s"` (semicolon + whitespace) — a bare
    # `";"` test incorrectly catches HTML entities like `&#039;` (apostrophe)
    # which contain `;`, e.g. ADCdb's "5'-nucleotidase (NT5E)" came through
    # as "5&#039;-nucleotidase (NT5E)" and would have been mis-routed.
    multi_re = re.compile(r";\s")
    multi_mask = df["antigen_name"].fillna("").apply(lambda s: bool(multi_re.search(s)))
    first_sym_re = re.compile(r"\(([A-Z0-9][A-Z0-9-]{1,12})\)")
    def first_sym(s: str) -> str | None:
        if not isinstance(s, str) or not multi_re.search(s):
            return None
        head = multi_re.split(s, maxsplit=1)[0]
        m = first_sym_re.search(head)
        return m.group(1) if m else None
    df.loc[multi_mask, "gene_symbol_inline"] = (
        df.loc[multi_mask, "antigen_name"].apply(first_sym)
    )
    # Tier 1: antigen-name regex on the antigen NAME field (ADCdb-internal)
    name_mask = df["antigen_name"].fillna("").apply(
        lambda s: bool(ADCDB_NAME_NOISE.search(str(s)))
    )
    n_dropped_name = name_mask.sum()
    if n_dropped_name:
        print(
            f"[adcdb] name-regex noise filter: dropped {n_dropped_name} "
            f"entries (e.g. {', '.join(df.loc[name_mask, 'gene_symbol_inline'].dropna().head(5).tolist())})"
        )
    df = df[~name_mask]

    # Tier 2: function-text regex on the curator-written Function field
    # (ADCdb-internal, scraped from per-antigen detail pages).
    if ADCDB_FUNCTIONS_TSV.is_file():
        funcs = pd.read_csv(ADCDB_FUNCTIONS_TSV, sep="\t")
        df = df.merge(funcs, on="adcdb_tar_id", how="left")
        fn_mask = df["function_text"].fillna("").apply(
            lambda s: bool(ADCDB_FN_NOISE.search(str(s)))
        )
        n_dropped_fn = fn_mask.sum()
        if n_dropped_fn:
            print(
                f"[adcdb] function-regex noise filter: dropped {n_dropped_fn} "
                f"entries (e.g. {', '.join(df.loc[fn_mask, 'gene_symbol_inline'].dropna().head(5).tolist())})"
            )
        df = df[~fn_mask]
    else:
        print(f"[adcdb] function TSV not present at {ADCDB_FUNCTIONS_TSV} — skipping Tier 2 filter")
    out: set[str] = set()
    for sym in df["gene_symbol_inline"].dropna():
        h = _resolve_symbol(str(sym).strip(), sym_to_hgnc)
        if h:
            out.add(h)
    return out


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
    """Return the set of gene symbols positive in any of the three full-genome
    Sonnet runs: NCBI v1, NCBI v2, OR the PubMed-augmented rescue pass.

    Positive = predicted_verdict in {yes, contextual}. Matches the universe
    v3 build's Sonnet inclusion rule exactly (see
    ``scripts/build_candidate_universe_v3.py``): a gene appears in v3
    as ``source='sonnet_only'`` whenever any of these three passes caught
    it — so we count it as a Sonnet positive here too.

    Earlier versions excluded the PubMed pass; that under-counted rescues
    (e.g. KLK2, which only the PubMed pass caught, was systematically
    omitted from the rescue list while still appearing in v3).
    """
    load_env()
    with D1Client() as d1:
        rows = d1.query(
            """
            SELECT DISTINCT gene_symbol FROM triage_run
            WHERE run_id IN ('genome_full_sonnet_ncbi_v1',
                             'genome_full_sonnet_ncbi_v2',
                             'genome_full_sonnet_pubmed_ncbi_v1')
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
    """Build the augmented indicator TSV for one category.

    All five per-DB flags (UniProt / GO / HPA / SURFY / CSPA) and
    ``n_db_votes`` are read directly from ``candidate_universe_v3``, whose
    ``*_flag`` columns already carry the SurfaceBench-optimized cutoffs (the
    optimization is applied upstream in the v3 build).
    """
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
        rec["sonnet_full_flag"] = int(h in sonnet_pos_hgnc)
        rows.append(rec)
    return pd.DataFrame(rows)


def main() -> None:
    print("=== Loading cohort + candidate universe ===")
    cohort, sym_to_hgnc, ensg_to_hgnc, ensg_to_sym = _load_cohort()
    cohort_desc = dict(zip(cohort["ensembl_gene"].dropna(), cohort["description"]))
    cu = pd.read_csv(CU_PATH, sep="\t")
    sym_to_hgnc_cu = dict(zip(cu["gene_symbol"], cu["hgnc_id"]))

    print("=== Sonnet dual-pass positives from D1 ===")
    sonnet_pos = fetch_sonnet_dual_positive()
    sonnet_pos_hgnc = {sym_to_hgnc_cu[s] for s in sonnet_pos if s in sym_to_hgnc_cu}
    sonnet_pos_hgnc |= {sym_to_hgnc[s] for s in sonnet_pos if s in sym_to_hgnc and s not in sym_to_hgnc_cu}
    print(f"  Sonnet dual-pass positive HGNCs: {len(sonnet_pos_hgnc)}")

    print("=== ADC ===")
    df_t = pull_therasabdab()
    mol, moa = pull_open_targets()
    adc_mask = _therasabdab_adc_mask(df_t)
    tdab_adc = collect_therasabdab_hgncs(df_t, adc_mask, sym_to_hgnc)
    ot_adc = collect_open_targets_adc_hgncs(mol, moa, ensg_to_hgnc, ensg_to_sym, cohort_desc)
    adcdb_adc = collect_adcdb_hgncs(sym_to_hgnc)
    adc_union = tdab_adc | ot_adc | adcdb_adc
    print(
        f"  TheraSAbDab ADC HGNCs: {len(tdab_adc)}; "
        f"Open Targets ADC HGNCs: {len(ot_adc)}; "
        f"ADCdb HGNCs: {len(adcdb_adc)};  union: {len(adc_union)}"
    )
    # Per-HGNC ADC-source provenance, priority TheraSAbDab > Open Targets > ADCdb.
    # Used by the figure script to stack each ADC bar by source.
    adc_source = {}
    for h in adc_union:
        if h in tdab_adc:
            adc_source[h] = "TheraSAbDab"
        elif h in ot_adc:
            adc_source[h] = "Open Targets"
        else:
            adc_source[h] = "ADCdb"

    print("=== TCE ===")
    tce_mask = _therasabdab_tce_mask(df_t)
    tce = collect_therasabdab_hgncs(df_t, tce_mask, sym_to_hgnc)
    print(f"  TheraSAbDab TCE HGNCs: {len(tce)}")

    print("=== ViralZone ===")
    try:
        vz = pull_viralzone()
        vz_set = collect_viralzone_hgncs(vz, cu)
    except Exception as e:
        print(f"  WARN: ViralZone fetch failed ({e}); skipping. The published")
        print("        TSV must be checked in manually — read from")
        print("        deliverome-internal LFS.")
        vz_set = set()
    print(f"  ViralZone HGNCs: {len(vz_set)}")

    per_set = {}
    for label, hgnc_set in [("ADC", adc_union), ("TCE", tce), ("VZ", vz_set)]:
        out = OUT_DIR / f"positive_control_{label}.tsv"
        df_out = build_indicator_df(hgnc_set, cu, cohort, sonnet_pos_hgnc)
        if label == "ADC":
            df_out["adc_source"] = df_out["hgnc_id"].map(adc_source)
        df_out.to_csv(out, sep="\t", index=False)
        per_set[label] = df_out
        print(f"  Wrote {out} ({len(df_out)} rows)")

    # Long-form combined TSV — one row per (category × gene) so the user can
    # grep / filter / sort across all three positive-control sets without
    # joining three files. Also useful for the figure's tidy seaborn pipeline.
    combined = pd.concat(
        [df.assign(category=label) for label, df in per_set.items()],
        ignore_index=True,
    )
    col_order = (
        ["category", "hgnc_id", "hgnc_symbol", "uniprot_acc", "ensembl_gene", "ncbi_gene_id"]
        + ["uniprot_flag", "go_flag", "hpa_flag", "surfy_flag", "cspa_flag", "n_db_votes",
           "sonnet_full_flag", "adc_source"]
    )
    combined = combined[[c for c in col_order if c in combined.columns]]
    combined_path = OUT_DIR / "positive_control_long.tsv"
    combined.to_csv(combined_path, sep="\t", index=False)
    print(f"  Wrote {combined_path} ({len(combined)} rows across {combined['category'].nunique()} categories)")

    # Per-(category, source) coverage summary — exactly the table the figure
    # renders. Keeps the headline numbers checked-in alongside the per-gene
    # data so a reviewer can verify counts without re-running anything.
    sources = {
        "UniProt": "uniprot_flag", "GO": "go_flag", "HPA": "hpa_flag",
        "SURFY": "surfy_flag", "CSPA": "cspa_flag", "Sonnet": "sonnet_full_flag",
    }
    summary_rows = []
    for label, df in per_set.items():
        n_total = len(df)
        for src, col in sources.items():
            n = int(df[col].astype(int).sum())
            summary_rows.append({
                "category": label, "source": src,
                "n_in_source": n, "n_total": n_total,
                "pct_in_source": round(n / n_total * 100, 1) if n_total else 0.0,
            })
    summary_path = OUT_DIR / "positive_control_db_coverage_summary.tsv"
    pd.DataFrame(summary_rows).to_csv(summary_path, sep="\t", index=False)
    print(f"  Wrote {summary_path} ({len(summary_rows)} rows)")


if __name__ == "__main__":
    main()
