"""
Build candidate_universe_v3.tsv = v2 universe minus Sonnet=no/high-conf rows
that are present in only 1 of the 5 gating DBs (UniProt/GO/SURFY/CSPA/HPA).

v3 = (Sonnet yes/contextual on canonical run UNION ≥1 of 5 gating DBs UNION
      Sonnet yes/contextual on pubmed_ncbi rescue run)
     MINUS (Sonnet=no high-conf AND only 1 of 5 gating DBs).

DB membership uses the **bench-optimized cutoffs** (the same thresholds the
DB-accuracy figures and the zero-DB-rescue figure use): UniProt is expanded
to admit transmembrane/signal-peptide proteins and CSPA is tightened to
high-confidence only, via ``data/processed/triage_bench/db_optimized_cutoffs.tsv``
joined on uniprot_acc; GO / HPA / SURFY are unchanged (no recalibration).
The optimized vote count ``n_db_votes`` replaces the former initial count, so
the universe gate (≥1 DB OR Sonnet-yc), the 1-of-5 trim, and the
``sonnet_only`` (zero-DB) source label are all on optimized membership.

Because candidate_universe_public carries only the INITIAL ``*_surface_flag``
columns, the optimized flags are joined in locally. The full table (all
~19,324 protein-coding genes, not just the initial union) is pulled so genes
that optimized-UniProt newly flags but Sonnet rejected are still admitted —
they would be invisible to a query filtered on the initial vote.

Bench check: re-confirmed 0 bench yes/contextual genes are removed.
"""
import csv
from collections import Counter
from pathlib import Path

from accessible_surfaceome.cloud.d1_client import D1Client, D1Config
from accessible_surfaceome.env import load_env

load_env()

RUN = "genome_full_sonnet_ncbi_v2"
RUN_PM = "genome_full_sonnet_pubmed_ncbi_v1"
OUT_DIR = Path("data/processed/candidate_universe")
OUT_KEEP = OUT_DIR / "candidate_universe_v3.tsv"
OUT_DROP = OUT_DIR / "candidate_universe_v3_dropped.tsv"
OPT_CUTOFFS = Path("data/processed/triage_bench/db_optimized_cutoffs.tsv")

# One row per gene: aggregate the 5 gating DB flags and Sonnet's canonical verdict.
# Stable IDs backfilled from gene_identifier_public per the figure-TSV convention.
SQL = """
WITH base AS (
  SELECT
    c.gene_symbol,
    MAX(c.uniprot_surface_flag) AS uniprot_flag,
    MAX(c.go_surface_flag)      AS go_flag,
    MAX(c.surfy_surface_flag)   AS surfy_flag,
    MAX(c.cspa_surface_flag)    AS cspa_flag,
    MAX(c.hpa_surface_flag)     AS hpa_flag,
    MAX(c.deeptmhmm_surface_flag)    AS deeptmhmm_flag,
    MAX(c.compartments_surface_flag) AS compartments_flag,
    MAX(c.uniprot_surface_flag + c.go_surface_flag + c.surfy_surface_flag
        + c.cspa_surface_flag + c.hpa_surface_flag) AS n_db_votes
  FROM candidate_universe_public c
  GROUP BY c.gene_symbol
),
sonnet AS (
  SELECT gene_symbol, predicted_verdict, predicted_confidence, predicted_reason
  FROM triage_run_public WHERE run_id = ?
),
pubmed AS (
  SELECT gene_symbol, predicted_verdict AS pm_verdict, predicted_confidence AS pm_conf
  FROM triage_run_public WHERE run_id = ?
),
ids AS (
  SELECT hgnc_symbol, hgnc_id, uniprot_acc, ensembl_gene, ncbi_gene_id
  FROM gene_identifier_public
)
SELECT
  b.gene_symbol,
  i.hgnc_id, i.uniprot_acc, i.ensembl_gene, i.ncbi_gene_id,
  b.uniprot_flag, b.go_flag, b.surfy_flag, b.cspa_flag, b.hpa_flag,
  b.deeptmhmm_flag, b.compartments_flag,
  s.predicted_verdict   AS sonnet_verdict,
  s.predicted_confidence AS sonnet_confidence,
  s.predicted_reason    AS sonnet_reason,
  p.pm_verdict          AS pubmed_verdict,
  p.pm_conf             AS pubmed_confidence
FROM base b
LEFT JOIN sonnet s ON s.gene_symbol = b.gene_symbol
LEFT JOIN pubmed p ON p.gene_symbol = b.gene_symbol
LEFT JOIN ids    i ON i.hgnc_symbol = b.gene_symbol
"""
# NOTE: no WHERE filter — we pull ALL genes (gating happens locally on the
# OPTIMIZED vote, below). Filtering in SQL on the initial vote would drop
# genes that only the optimized UniProt cutoff flags.

# Optimized cutoffs: accession -> (uniprot_optimized, cspa_optimized).
_opt: dict[str, tuple[int, int]] = {}
with open(OPT_CUTOFFS) as f:
    for r in csv.DictReader(f, delimiter="\t"):
        acc = (r.get("accession") or "").strip()
        if acc:
            _opt[acc] = (
                1 if str(r.get("uniprot_optimized", "")).strip() in ("1", "1.0") else 0,
                1 if str(r.get("cspa_optimized", "")).strip() in ("1", "1.0") else 0,
            )

def _i(v) -> int:
    return 1 if str(v).strip() in ("1", "1.0") else 0

def _opt_votes(r) -> int:
    """5-DB vote under the bench-optimized cutoffs: UniProt + CSPA from the
    recalibrated set (fallback to the initial flag when the accession isn't
    in the cutoff table); GO / HPA / SURFY unchanged."""
    acc = (r.get("uniprot_acc") or "").strip()
    up, cs = _opt.get(acc, (_i(r["uniprot_flag"]), _i(r["cspa_flag"])))
    return up + cs + _i(r["go_flag"]) + _i(r["surfy_flag"]) + _i(r["hpa_flag"])

with D1Client(config=D1Config.from_env_public()) as d1:
    all_rows = d1.query(SQL, [RUN, RUN_PM])

# Guard against a silently-truncated pull — the table is the full cohort.
N_EXPECTED = 19_324
assert len(all_rows) >= N_EXPECTED - 50, (
    f"pulled only {len(all_rows):,} rows from candidate_universe_public "
    f"(expected ~{N_EXPECTED:,}) — possible truncation; aborting before "
    f"writing a short universe."
)

# Stamp the optimized vote + per-DB flags + apply the universe gate locally.
# uniprot_flag/cspa_flag are overwritten with the optimized values so every
# column in the row is on the same (optimized) cutoff as n_db_votes.
for r in all_rows:
    acc = (r.get("uniprot_acc") or "").strip()
    up, cs = _opt.get(acc, (_i(r["uniprot_flag"]), _i(r["cspa_flag"])))
    r["uniprot_flag"] = up
    r["cspa_flag"] = cs
    r["n_db_votes"] = _opt_votes(r)
def _yc(r) -> bool:
    return r["sonnet_verdict"] in ("yes", "contextual") or r["pubmed_verdict"] in ("yes", "contextual")
rows = [r for r in all_rows if r["n_db_votes"] >= 1 or _yc(r)]

def is_trim(r):
    return (
        r["sonnet_verdict"] == "no"
        and r["sonnet_confidence"] == "high"
        and r["n_db_votes"] == 1
    )

keep = [r for r in rows if not is_trim(r)]
drop = [r for r in rows if is_trim(r)]

# Source label: 'sonnet_only' (DBs all zero, Sonnet/pubmed rescued)
#               'm1_only' (Sonnet=no but in DBs)
#               'm1_and_sonnet' (both vote yes-ish)
def source_of(r):
    sonnet_yes = r["sonnet_verdict"] in ("yes", "contextual") \
              or r["pubmed_verdict"] in ("yes", "contextual")
    if r["n_db_votes"] == 0 and sonnet_yes:
        return "sonnet_only"
    if sonnet_yes:
        return "m1_and_sonnet"
    return "m1_only"

cols = [
    "gene_symbol", "hgnc_id", "uniprot_acc", "ensembl_gene", "ncbi_gene_id",
    "n_db_votes", "uniprot_flag", "go_flag", "surfy_flag", "cspa_flag", "hpa_flag",
    "deeptmhmm_flag", "compartments_flag",
    "sonnet_verdict", "sonnet_confidence", "sonnet_reason",
    "pubmed_verdict", "pubmed_confidence", "source",
]

OUT_DIR.mkdir(parents=True, exist_ok=True)

def write_tsv(path, rs):
    with open(path, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=cols, delimiter="\t", extrasaction="ignore")
        w.writeheader()
        for r in sorted(rs, key=lambda x: x["gene_symbol"]):
            r["source"] = source_of(r)
            w.writerow(r)

write_tsv(OUT_KEEP, keep)
write_tsv(OUT_DROP, drop)

# Summary
print(f"Base candidate set (live D1): {len(rows):,} genes")
print(f"  Trimmed (Sonnet=no/high + 1-of-5-DB): {len(drop):,}")
print(f"  Kept (v3 universe): {len(keep):,}")
print()
print("Source breakdown in v3:")
src = Counter(source_of(r) for r in keep)
for s, n in src.most_common():
    print(f"  {s:<16s} {n:>6,d}")
print()
print("Wrote:")
print(f"  {OUT_KEEP}   ({len(keep):,} rows)")
print(f"  {OUT_DROP}   ({len(drop):,} rows)")
