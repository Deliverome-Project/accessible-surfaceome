"""Apply the pubmed_ncbi rescue lane to the whole-proteome catalog TSV.

The catalog TSV at ``data/processed/catalog/whole_proteome_catalog.tsv``
carries one ``sonnet_verdict`` / ``sonnet_reason`` per gene — the
canonical ncbi-variant Sonnet call from
``run_id=genome_full_sonnet_ncbi_v2``. The genome-wide rescue figures
(``zero_db_rescues_by_triage``, ``db_vs_sonnet_whole_proteome``) read
those columns directly.

After the pubmed_ncbi rescue sweep
(``run_id=genome_full_sonnet_pubmed_ncbi_v1``) runs over the
2,626-gene ambiguous-reason zero-DB slice, this script joins the new
verdicts into the catalog TSV under the read-time reconciliation rule
we settled on:

    if pubmed_ncbi verdict ∈ {yes, contextual} AND
       ncbi      verdict  == 'no':
        sonnet_verdict / sonnet_reason ← pubmed_ncbi's
        verdict_source                ← 'pubmed_rescue'

Otherwise the canonical ncbi verdict stays. A new ``verdict_source``
column records ``ncbi`` vs ``pubmed_rescue`` per row so downstream
analyses can split or audit the rescue contribution.

Run after the sweep finishes:

    uv run python scripts/apply_pubmed_ncbi_rescue_to_catalog.py
"""
from __future__ import annotations

import csv
import sys
from collections import Counter
from pathlib import Path

from accessible_surfaceome.cloud.d1_client import D1Client, D1Config
from accessible_surfaceome.env import load_env
from accessible_surfaceome.paths import REPO_ROOT

CATALOG_TSV = REPO_ROOT / "data/processed/catalog/whole_proteome_catalog.tsv"
PUBMED_RUN_ID = "genome_full_sonnet_pubmed_ncbi_v1"
NCBI_RUN_ID = "genome_full_sonnet_ncbi_v2"


def _load_pubmed_verdicts() -> dict[str, tuple[str, str]]:
    """Map ``hgnc_symbol`` → ``(pubmed_verdict, pubmed_reason)``.

    Reads from the **agents** D1 (private) — the rescue sweep hasn't
    been mirrored to public D1 yet. Only rows with a non-null verdict
    count; nulled (errored) cells fall through to the ncbi verdict.
    """
    cfg = D1Config._from_env_db("CLOUDFLARE_D1_SURFACEOME_AGENTS_ID")
    with D1Client(cfg) as d1:
        rows = d1.query(
            "SELECT gene_symbol, predicted_verdict, predicted_reason "
            "FROM triage_run "
            "WHERE run_id = ? AND predicted_verdict IS NOT NULL",
            [PUBMED_RUN_ID],
        )
    return {
        r["gene_symbol"]: (r["predicted_verdict"], r["predicted_reason"])
        for r in rows
    }


def _is_more_inclusive(pubmed_v: str, ncbi_v: str) -> bool:
    """The reconciliation rule. Returns True iff pubmed's verdict
    rescues (is more inclusive than) the ncbi verdict."""
    return pubmed_v in ("yes", "contextual") and ncbi_v == "no"


def main() -> int:
    load_env()

    print(f"Reading {CATALOG_TSV.relative_to(REPO_ROOT)} …")
    with CATALOG_TSV.open() as fh:
        reader = csv.DictReader(fh, delimiter="\t")
        fields = list(reader.fieldnames or [])
        rows = [dict(r) for r in reader]
    print(f"  {len(rows):,} catalog rows")

    print(f"Loading pubmed_ncbi verdicts from D1 (run_id={PUBMED_RUN_ID}) …")
    pubmed = _load_pubmed_verdicts()
    print(f"  {len(pubmed):,} pubmed_ncbi rows with non-null verdict")

    if "verdict_source" not in fields:
        fields.append("verdict_source")

    flips = []
    by_flip = Counter()
    n_pubmed_no = 0
    n_pubmed_agree = 0
    for r in rows:
        sym = (r.get("hgnc_symbol") or "").strip()
        ncbi_v = (r.get("sonnet_verdict") or "").strip()
        r.setdefault("verdict_source", "ncbi")
        if sym not in pubmed:
            continue
        pubmed_v, pubmed_reason = pubmed[sym]
        if _is_more_inclusive(pubmed_v, ncbi_v):
            flips.append({
                "symbol": sym,
                "ncbi_verdict": ncbi_v,
                "ncbi_reason": r.get("sonnet_reason", ""),
                "pubmed_verdict": pubmed_v,
                "pubmed_reason": pubmed_reason,
            })
            by_flip[(ncbi_v, pubmed_v)] += 1
            r["sonnet_verdict"] = pubmed_v
            r["sonnet_reason"] = pubmed_reason
            r["verdict_source"] = "pubmed_rescue"
        elif pubmed_v == "no":
            n_pubmed_no += 1
        else:
            n_pubmed_agree += 1

    print(f"\nRescue tally: {len(flips):,} flips from ncbi-no to pubmed-{{yes,contextual}}")
    for (ncbi_v, pubmed_v), n in sorted(by_flip.items(), key=lambda x: -x[1]):
        print(f"  {ncbi_v:11s} → {pubmed_v:11s}: {n:>5,}")
    print(f"\nPubmed confirmed ncbi-no:     {n_pubmed_no:,}")
    print(f"Pubmed agreed with ncbi-other: {n_pubmed_agree:,}")
    print(f"Genes outside the pubmed slice (kept ncbi verdict): "
          f"{len(rows) - len(pubmed):,}")

    print(f"\nWriting {CATALOG_TSV.relative_to(REPO_ROOT)} (with verdict_source col) …")
    with CATALOG_TSV.open("w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=fields, delimiter="\t",
                           lineterminator="\n")
        w.writeheader()
        for r in rows:
            w.writerow({k: r.get(k, "") for k in fields})

    # Dump the flip list so downstream scripts / sanity checks can read it.
    flip_path = REPO_ROOT / "data/processed/catalog/pubmed_rescue_flips.tsv"
    flip_path.parent.mkdir(parents=True, exist_ok=True)
    with flip_path.open("w", newline="") as fh:
        w = csv.DictWriter(
            fh,
            fieldnames=["symbol", "ncbi_verdict", "ncbi_reason",
                        "pubmed_verdict", "pubmed_reason"],
            delimiter="\t", lineterminator="\n",
        )
        w.writeheader()
        for f in flips:
            w.writerow(f)
    print(f"Wrote per-gene flip list → {flip_path.relative_to(REPO_ROOT)}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
