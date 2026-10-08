"""Verify the PMIDs a triage run cites actually concern the gene they back.

The ``pubmed_ncbi`` triage variant reads literature and cites PMIDs inline in
``verdict_reasoning``. Those citations are the only externally-checkable part
of a verdict, and they are **not** validated anywhere in the pipeline.

The failure mode this catches is *misattribution*, not invented identifiers.
On the ``genome_intracellular_pubmed_ncbi_v1`` sweep every cited PMID resolved
to a real PubMed record — but 7% of them were real papers about something
entirely unrelated (a BLCAP surface-topology claim backed by a paper on horse
heart myoglobin). A resolving PMID passes a naive existence check and renders
as a working link, so only a subject check surfaces this.

Method: extract ``PMID:NNNNNNN`` tokens per gene, batch-fetch title+abstract,
and check whether the gene symbol appears. A gene symbol absent from the
title+abstract is a **flag, not a proof** — a proteomics screen may not name
every protein it measured — so ``suspect`` rows want a human read. In practice
the signal is sharp: on the sweep above, failures clustered completely, with
5 genes where *every* citation failed and 143 where at least one checked out.
"Every citation fails" is therefore a usable automated signal that a rescue is
confabulated.

Usage::

    uv run python scripts/audit/audit_triage_citations.py \\
        --run-id genome_intracellular_pubmed_ncbi_v1 \\
        --out data/processed/intracellular_rescue_v1/citation_audit.tsv
"""

from __future__ import annotations

import argparse
import csv
import os
import re
import time
import urllib.request
from pathlib import Path

from accessible_surfaceome.cloud.d1_client import D1Client
from accessible_surfaceome.env import load_env

PMID_RE = re.compile(r"PMID[:\s]*(\d{7,9})")
EFETCH = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/efetch.fcgi"
# NCBI caps efetch POST-less GETs well above this, but 150 keeps the URL short
# and the per-request latency predictable.
_BATCH = 150


def _api_key() -> str:
    pool = os.environ.get("NCBI_API_KEYS") or os.environ.get("NCBI_API_KEY") or ""
    keys = [k for k in re.split(r"[,;\s]+", pool) if k]
    return keys[0] if keys else ""


def _fetch_records(pmids: list[str]) -> dict[str, str]:
    """``{pmid: lowercased title+abstract+metadata text}``."""
    key = _api_key()
    out: dict[str, str] = {}
    for i in range(0, len(pmids), _BATCH):
        chunk = pmids[i : i + _BATCH]
        url = (
            f"{EFETCH}?db=pubmed&rettype=abstract&retmode=xml&id={','.join(chunk)}"
            + (f"&api_key={key}" if key else "")
        )
        xml = urllib.request.urlopen(url).read().decode("utf-8", "replace")
        for art in xml.split("<PubmedArticle>")[1:]:
            m = re.search(r"<PMID[^>]*>(\d+)</PMID>", art)
            if m:
                out[m.group(1)] = re.sub(r"<[^>]+>", " ", art).lower()
        time.sleep(0.4)
    return out


def main(argv: list[str] | None = None) -> int:
    load_env()
    ap = argparse.ArgumentParser()
    ap.add_argument("--run-id", required=True)
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument(
        "--verdicts",
        default="yes,contextual",
        help="Comma-separated verdicts to audit (default: the rescues).",
    )
    args = ap.parse_args(argv)

    verdicts = tuple(v.strip() for v in args.verdicts.split(",") if v.strip())
    placeholders = ",".join("?" for _ in verdicts)
    with D1Client() as d1:
        rows = d1.query(
            f"""SELECT gene_symbol, predicted_verdict, predicted_reason, verdict_reasoning
                FROM triage_run
                WHERE run_id = ? AND predicted_verdict IN ({placeholders});""",
            [args.run_id, *verdicts],
        )

    cites = {
        r["gene_symbol"]: sorted(set(PMID_RE.findall(r["verdict_reasoning"] or "")))
        for r in rows
    }
    meta = _fetch_records(sorted({p for v in cites.values() for p in v}))

    args.out.parent.mkdir(parents=True, exist_ok=True)
    n_ok = n_suspect = n_missing = 0
    fully_unverified: list[str] = []
    no_citation: list[str] = []

    with args.out.open("w", newline="") as fh:
        w = csv.writer(fh, delimiter="\t", lineterminator="\n")
        w.writerow(
            ["gene_symbol", "predicted_verdict", "predicted_reason",
             "n_cited", "n_verified", "n_suspect", "n_unresolvable",
             "verified_pmids", "suspect_pmids"]
        )
        for r in sorted(rows, key=lambda x: x["gene_symbol"]):
            g = r["gene_symbol"]
            pms = cites[g]
            ok, suspect, missing = [], [], []
            for p in pms:
                if p not in meta:
                    missing.append(p)
                elif re.search(rf"\b{re.escape(g.lower())}\b", meta[p]):
                    ok.append(p)
                else:
                    suspect.append(p)
            n_ok += len(ok)
            n_suspect += len(suspect)
            n_missing += len(missing)
            if not pms:
                no_citation.append(g)
            elif not ok:
                fully_unverified.append(g)
            w.writerow(
                [g, r["predicted_verdict"], r["predicted_reason"],
                 len(pms), len(ok), len(suspect), len(missing),
                 ",".join(ok), ",".join(suspect)]
            )

    total = n_ok + n_suspect + n_missing
    print(f"run_id:              {args.run_id}")
    print(f"genes audited:       {len(rows)}")
    print(f"citations:           {total}")
    if total:
        print(f"  verified:          {n_ok:4d}  ({n_ok / total:.0%})")
        print(f"  suspect:           {n_suspect:4d}  ({n_suspect / total:.0%})  gene absent from title+abstract")
        print(f"  unresolvable:      {n_missing:4d}")
    print(f"genes citing nothing:            {len(no_citation)}")
    print(f"genes with 0 verified citations: {len(fully_unverified)}  {fully_unverified}")
    print(f"\nwrote {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
