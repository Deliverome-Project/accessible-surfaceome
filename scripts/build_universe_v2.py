"""Build candidate_universe_v2 — union of M1 (≥1 DB vote) and Sonnet's
genome-wide surface verdicts (yes + contextual).

Each row carries:
  gene_symbol, uniprot_accession, hgnc_id, ensembl_gene,
  m1_n_db_votes, m1_uniprot_flag, m1_go_flag, m1_hpa_flag,
                 m1_surfy_flag, m1_cspa_flag,
  sonnet_verdict, sonnet_reason, sonnet_confidence,
  source ('m1_only' | 'sonnet_only' | 'both')

so downstream callers can filter on any axis. Stable IDs prefer the
M1 row (bench-pinned), falling back to the Sonnet-side resolver IDs
from ``triage_run`` for ``sonnet_only`` symbols.

Source data:
  * candidate_universe.tsv (M1 universe; ≥1 of 5 classical surface DBs)
  * D1 ``triage_run`` rows under ``run_id='genome_full_sonnet_ncbi_v1'``
    (the 2026-05-12 Sonnet/ncbi sweep over 19,464 NCBI protein-coding
    genes with the slim-canonical prompt).

Total output rows: 6,521 (3,381 in both + 2,288 M1-only + 852 Sonnet-only).

Re-run after any genome-wide Sonnet sweep refresh; outputs to
``data/processed/candidate_universe/candidate_universe_v2.tsv``.
"""
from __future__ import annotations

import csv
from collections import Counter

from accessible_surfaceome.cloud.d1_client import D1Client
from accessible_surfaceome.env import load_env
from accessible_surfaceome.paths import REPO_ROOT

load_env()

CAND_IN = REPO_ROOT / "data/processed/candidate_universe/candidate_universe.tsv"
CAND_OUT = REPO_ROOT / "data/processed/candidate_universe/candidate_universe_v2.tsv"
SONNET_RUN_ID = "genome_full_sonnet_ncbi_v1"

DB_FLAGS = [
    ("uniprot_surface_flag", "m1_uniprot_flag"),
    ("go_surface_flag",      "m1_go_flag"),
    ("hpa_surface_flag",     "m1_hpa_flag"),
    ("surfy_surface_flag",   "m1_surfy_flag"),
    ("cspa_surface_flag",    "m1_cspa_flag"),
]


def _load_m1() -> dict[str, dict]:
    out: dict[str, dict] = {}
    with CAND_IN.open() as fh:
        for r in csv.DictReader(fh, delimiter="\t"):
            votes = sum(1 for src, _ in DB_FLAGS if r.get(src, "0") == "1")
            if votes == 0:
                continue
            out[r["gene_symbol"]] = {
                "uniprot_accession": r["uniprot_accession"],
                "hgnc_id":           r.get("hgnc_id", ""),
                "ensembl_gene":      r.get("ensembl_gene", ""),
                "m1_n_db_votes":     str(votes),
                **{dst: r.get(src, "0") for src, dst in DB_FLAGS},
            }
    return out


def _load_sonnet() -> dict[str, dict]:
    with D1Client() as d1:
        rows = d1.query(
            "SELECT gene_symbol, uniprot_acc, hgnc_id, ensembl_gene, "
            "       predicted_verdict, predicted_reason, "
            "       predicted_confidence "
            "FROM triage_run "
            "WHERE run_id = ? "
            "  AND predicted_verdict IN ('yes', 'contextual');",
            [SONNET_RUN_ID],
        )
    return {r["gene_symbol"]: r for r in rows}


def main() -> int:
    m1 = _load_m1()
    sonnet = _load_sonnet()
    all_syms = sorted(set(m1) | set(sonnet))

    out: list[dict] = []
    for sym in all_syms:
        in_m1 = sym in m1
        in_sonnet = sym in sonnet
        source = "both" if (in_m1 and in_sonnet) else ("m1_only" if in_m1 else "sonnet_only")
        m1_data = m1.get(sym, {})
        s_data = sonnet.get(sym, {})
        out.append({
            "gene_symbol":       sym,
            "uniprot_accession": m1_data.get("uniprot_accession") or s_data.get("uniprot_acc") or "",
            "hgnc_id":           m1_data.get("hgnc_id") or s_data.get("hgnc_id") or "",
            "ensembl_gene":      m1_data.get("ensembl_gene") or s_data.get("ensembl_gene") or "",
            "m1_n_db_votes":     m1_data.get("m1_n_db_votes", "0"),
            "m1_uniprot_flag":   m1_data.get("m1_uniprot_flag", "0"),
            "m1_go_flag":        m1_data.get("m1_go_flag", "0"),
            "m1_hpa_flag":       m1_data.get("m1_hpa_flag", "0"),
            "m1_surfy_flag":     m1_data.get("m1_surfy_flag", "0"),
            "m1_cspa_flag":      m1_data.get("m1_cspa_flag", "0"),
            "sonnet_verdict":    s_data.get("predicted_verdict", ""),
            "sonnet_reason":     s_data.get("predicted_reason", ""),
            "sonnet_confidence": s_data.get("predicted_confidence", ""),
            "source":            source,
        })

    CAND_OUT.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = list(out[0].keys())
    with CAND_OUT.open("w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=fieldnames, delimiter="\t",
                           lineterminator="\n", quoting=csv.QUOTE_MINIMAL)
        w.writeheader()
        for row in out:
            w.writerow(row)

    src_counts = Counter(r["source"] for r in out)
    print(f"Wrote {CAND_OUT.relative_to(REPO_ROOT)}  ({len(out):,} rows)")
    for s in ("both", "m1_only", "sonnet_only"):
        print(f"  {s:<12s} {src_counts[s]:,}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
