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
  * D1 ``triage_run`` rows under ``run_id='genome_full_sonnet_ncbi_v2'``
    (the canonical 2026-06 Sonnet/ncbi sweep over the M1 candidate
    universe with the canonical prompt — superseded v1).
  * D1 ``triage_run`` rows under
    ``run_id='genome_full_sonnet_pubmed_ncbi_v1'`` — the PubMed-
    augmented rescue lane over the 2,626-gene ambiguous-reason
    zero-DB Sonnet-no slice. The same read-side rule the catalog
    applies is used here: if PubMed says yes/contextual and NCBI
    says no, the PubMed verdict wins.

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
SONNET_NCBI_RUN_ID = "genome_full_sonnet_ncbi_v2"
SONNET_PUBMED_RUN_ID = "genome_full_sonnet_pubmed_ncbi_v1"

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
    """Return all gene_symbols where the reconciled Sonnet verdict is
    yes/contextual.

    Reconciliation rule (matches the catalog Worker):
      reconciled = pubmed_verdict if pubmed in {yes, contextual} and
                                    ncbi   == 'no'
                   else ncbi_verdict

    Equivalent to: a gene lands in the universe if EITHER its ncbi
    verdict or its pubmed_ncbi verdict is yes/contextual. PubMed
    never overrides an ncbi yes/contextual since the rescue is
    additive — pubmed-no is not evidence of absence.
    """
    with D1Client() as d1:
        ncbi_rows = d1.query(
            "SELECT gene_symbol, uniprot_acc, hgnc_id, ensembl_gene, "
            "       predicted_verdict, predicted_reason, "
            "       predicted_confidence "
            "FROM triage_run "
            "WHERE run_id = ? "
            "  AND predicted_verdict IN ('yes', 'contextual');",
            [SONNET_NCBI_RUN_ID],
        )
        # PubMed rescue run_id only contains pubmed_ncbi cells, so a
        # single run_id filter is enough.
        pubmed_rows = d1.query(
            "SELECT gene_symbol, uniprot_acc, hgnc_id, ensembl_gene, "
            "       predicted_verdict, predicted_reason, "
            "       predicted_confidence "
            "FROM triage_run "
            "WHERE run_id = ? "
            "  AND predicted_verdict IN ('yes', 'contextual');",
            [SONNET_PUBMED_RUN_ID],
        )
    out: dict[str, dict] = {r["gene_symbol"]: r for r in ncbi_rows}
    # PubMed rescues — add genes the ncbi pass didn't already cover.
    # The reason field captures the more-inclusive verdict for the
    # added rows; existing ncbi-yes/contextual rows stay as-is.
    rescued = 0
    for r in pubmed_rows:
        if r["gene_symbol"] not in out:
            out[r["gene_symbol"]] = r
            rescued += 1
    print(f"  ncbi yes/contextual: {len(ncbi_rows):,}")
    print(f"  pubmed rescues (new): {rescued:,}")
    return out


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
