"""Overlay every literature-rescue triage lane onto the whole-proteome catalog.

``data/processed/catalog/whole_proteome_catalog.tsv`` carries one
``sonnet_verdict`` / ``sonnet_reason`` per gene, exported from the
canonical NCBI run by ``export_whole_proteome_catalog_to_tsv.py``. The
genome-wide rescue figures read those columns directly, so every rescue
lane has to be folded back in here or its flips are invisible to them.

Reconciliation, unchanged from the single-lane version: a lane wins only
when it is strictly more inclusive than the verdict already in hand — a
lane ``no`` never overturns a canonical ``yes``/``contextual``.

    lane verdict ∈ {yes, contextual} AND current verdict == 'no'
        → sonnet_verdict / sonnet_reason ← the lane's
          verdict_source                ← 'pubmed_rescue'
          rescue_run                    ← that lane's run_id

This replaces the one-shot ``apply_pubmed_ncbi_rescue_to_catalog.py``
(archived in the scripts/ reorg), which hardcoded a single lane. There
are two now and there will be more, so ``RESCUE_RUNS`` is a list and the
script always rebuilds the verdict from the canonical run rather than
mutating whatever is in the file — re-running it is a no-op, and a lane
can be added or removed without the committed TSV going stale.

``verdict_source`` stays two-valued for back-compat: downstream figure
code tests ``== "pubmed_rescue"`` to count rescues, and a third value
would silently undercount. Which lane did it lives in ``rescue_run``.

Run after any rescue sweep:

    uv run python scripts/tsv-export/apply_triage_rescue_lanes_to_catalog.py
"""

from __future__ import annotations

import csv
from collections import Counter

from accessible_surfaceome.cloud.d1_client import D1Client
from accessible_surfaceome.env import load_env
from accessible_surfaceome.paths import REPO_ROOT

CATALOG_TSV = REPO_ROOT / "data/processed/catalog/whole_proteome_catalog.tsv"
FLIPS_TSV = REPO_ROOT / "data/processed/catalog/pubmed_rescue_flips.tsv"

CANONICAL_RUN = "genome_full_sonnet_ncbi_v2"
# Applied in order; a later lane can only add to what an earlier one did.
RESCUE_RUNS = [
    # Ambiguous-reason zero-DB "no" calls (endomembrane / secreted /
    # inner-leaflet / pMHC / nuclear-envelope), n=2,626.
    "genome_full_sonnet_pubmed_ncbi_v1",
    # The confidently intracellular buckets the first lane skipped
    # (cytoplasmic / nuclear / mitochondrial), n=10,287.
    "genome_intracellular_pubmed_ncbi_v1",
    "genome_1db_trim_pubmed_ncbi_v1",
    "genome_optcut_zerodb_pubmed_ncbi_v1",
]

POSITIVE = ("yes", "contextual")


def _verdicts(d1: D1Client, run_id: str) -> dict[str, tuple[str, str]]:
    rows = d1.query(
        "SELECT gene_symbol, predicted_verdict, predicted_reason "
        "FROM triage_run_public WHERE run_id = ? AND predicted_verdict IS NOT NULL;",
        [run_id],
    )
    return {
        r["gene_symbol"]: (r["predicted_verdict"], r["predicted_reason"] or "")
        for r in rows
    }


def main() -> int:
    load_env()

    with CATALOG_TSV.open(newline="", encoding="utf-8") as fh:
        reader = csv.DictReader(fh, delimiter="\t")
        fields = list(reader.fieldnames or [])
        rows = [dict(r) for r in reader]
    print(f"catalog rows: {len(rows):,}")

    with D1Client.public() as d1:
        canonical = _verdicts(d1, CANONICAL_RUN)
        lanes = {run: _verdicts(d1, run) for run in RESCUE_RUNS}
    print(f"canonical {CANONICAL_RUN}: {len(canonical):,}")
    for run, v in lanes.items():
        print(f"  lane {run}: {len(v):,}")

    for col in ("verdict_source", "rescue_run"):
        if col not in fields:
            fields.append(col)

    flips: list[dict[str, str]] = []
    by_lane: Counter[str] = Counter()
    for r in rows:
        sym = (r.get("hgnc_symbol") or "").strip()
        # Always start from the canonical call so the run is idempotent.
        if sym in canonical:
            r["sonnet_verdict"], r["sonnet_reason"] = canonical[sym]
        r["verdict_source"] = "ncbi"
        r["rescue_run"] = ""
        base_v, base_reason = r.get("sonnet_verdict", ""), r.get("sonnet_reason", "")
        for run in RESCUE_RUNS:
            lane_v, lane_reason = lanes[run].get(sym, ("", ""))
            if lane_v in POSITIVE and (r.get("sonnet_verdict") or "") == "no":
                r["sonnet_verdict"] = lane_v
                r["sonnet_reason"] = lane_reason
                r["verdict_source"] = "pubmed_rescue"
                r["rescue_run"] = run
                by_lane[run] += 1
                flips.append({
                    "symbol": sym,
                    "ncbi_verdict": base_v,
                    "ncbi_reason": base_reason,
                    "pubmed_verdict": lane_v,
                    "pubmed_reason": lane_reason,
                    "rescue_run": run,
                })

    total = sum(by_lane.values())
    print(f"\nrescued: {total:,}")
    for run in RESCUE_RUNS:
        print(f"  {by_lane[run]:>5,}  {run}")

    with CATALOG_TSV.open("w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=fields, delimiter="\t", extrasaction="ignore")
        w.writeheader()
        w.writerows(rows)
    with FLIPS_TSV.open("w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(
            fh,
            fieldnames=["symbol", "ncbi_verdict", "ncbi_reason",
                        "pubmed_verdict", "pubmed_reason", "rescue_run"],
            delimiter="\t",
        )
        w.writeheader()
        w.writerows(sorted(flips, key=lambda x: x["symbol"]))
    print(f"\nwrote {CATALOG_TSV.relative_to(REPO_ROOT)}")
    print(f"wrote {FLIPS_TSV.relative_to(REPO_ROOT)}  ({len(flips):,} flips)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
