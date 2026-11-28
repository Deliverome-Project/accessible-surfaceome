"""$0 backfill: populate ``paper_metadata`` for newly cited tag-site PMIDs and
re-enrich ``tag_site_public.sources_json`` so every citation on the viewer
shows author / journal / year / title instead of a bare ``PMID 12345678``.

Uses the exact NCBI E-utilities ``esummary`` row schema from
``scripts/build/build_paper_metadata_table.py`` (1 batch call per 200 PMIDs)
and ``enrich_sources_with_paper_metadata`` from ``cloud.tag_sites``.

DRY-RUN by default — pass ``--execute`` to write to public D1.

Usage:
    uv run python scripts/cloud/backfill_tag_site_paper_metadata.py
    uv run python scripts/cloud/backfill_tag_site_paper_metadata.py --execute
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from typing import Any

from accessible_surfaceome.cloud.d1_client import D1Client
from accessible_surfaceome.cloud.tag_sites import enrich_sources_with_paper_metadata
from accessible_surfaceome.env import REPO_ROOT, load_env
from accessible_surfaceome.tools._shared.http import open_default_client

sys.path.insert(0, str(REPO_ROOT / "scripts" / "build"))
import build_paper_metadata_table as bpmt  # type: ignore[import-not-found]


def _bare_source_rows(
    d1: D1Client, *, provenances: tuple[str, ...]
) -> tuple[list[dict[str, Any]], set[str]]:
    """Return tag_site_public rows with at least one PMID source missing metadata."""
    marks = ", ".join(["?"] * len(provenances))
    rows = d1.query(
        f"SELECT site_id, gene_symbol, provenance, sources_json "
        f"FROM tag_site_public WHERE provenance IN ({marks}) AND sources_json IS NOT NULL;",
        list(provenances),
    )
    need_update: list[dict[str, Any]] = []
    pmids: set[str] = set()
    for row in rows:
        try:
            srcs = json.loads(row.get("sources_json") or "[]")
        except Exception:  # noqa: BLE001
            continue
        if not isinstance(srcs, list):
            continue
        row_missing = False
        for s in srcs:
            if not isinstance(s, dict):
                continue
            pmid = s.get("pmid")
            if pmid and (not s.get("title") or not s.get("authors") or not s.get("journal")):
                pmids.add(str(pmid))
                row_missing = True
        if row_missing:
            need_update.append(row)
    return need_update, pmids


def _existing_pmids(d1: D1Client, pmids: set[str]) -> set[str]:
    have: set[str] = set()
    ordered = sorted(pmids)
    for i in range(0, len(ordered), 50):
        chunk = ordered[i : i + 50]
        marks = ", ".join(["?"] * len(chunk))
        for r in d1.query(
            f"SELECT pmid FROM paper_metadata WHERE pmid IN ({marks});", chunk
        ):
            if r.get("pmid"):
                have.add(str(r["pmid"]))
    return have


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument(
        "--provenance",
        action="append",
        dest="provenances",
        help="Provenance(s) to scan (default: literature_enriched and literature_retrieved).",
    )
    ap.add_argument("--execute", action="store_true", help="Write updates to public D1.")
    args = ap.parse_args(argv)
    provenances = tuple(
        args.provenances or ("literature_enriched", "literature_retrieved")
    )

    load_env()
    with D1Client.public() as d1:
        rows, cited_pmids = _bare_source_rows(d1, provenances=provenances)
        have = _existing_pmids(d1, cited_pmids)
        missing = sorted(cited_pmids - have)
        print(
            f"tag_site_public ({', '.join(provenances)}): "
            f"{len(rows)} row(s) with bare PMID citations, "
            f"{len(cited_pmids)} distinct PMID(s), "
            f"{len(have)} already in paper_metadata, "
            f"{len(missing)} missing from paper_metadata"
        )

        fetched_rows: list[dict[str, Any]] = []
        if missing:
            with open_default_client() as http:
                for i in range(0, len(missing), 150):
                    chunk = [f"PMID:{p}" for p in missing[i : i + 150]]
                    fetched_rows.extend(bpmt._fetch_batch(http, chunk, "pubmed"))
            print(f"Fetched {len(fetched_rows)}/{len(missing)} missing PMIDs via NCBI esummary")

        if not args.execute:
            if fetched_rows:
                sample = fetched_rows[0]
                print(
                    f"  sample: PMID:{sample['pmid']} -> "
                    f"{sample['authors_short']} ({sample['year']}) {sample['journal']} — {sample['title']}"
                )
            print("DRY RUN — pass --execute to upsert paper_metadata and enrich tag_site_public.")
            return 0

        upserted = 0
        for i in range(0, len(fetched_rows), 8):  # 8 × 12 cols = 96 params (< D1 100 cap)
            upserted += bpmt._upsert_chunk(d1, fetched_rows[i : i + 8])
        print(f"Upserted {upserted} row(s) into paper_metadata")

        before = {r["site_id"]: r["sources_json"] for r in rows}
        enriched_sources = enrich_sources_with_paper_metadata(rows, client=d1)
        changed = [r for r in rows if r["sources_json"] != before[r["site_id"]]]
        # Batch 20 rows per CASE UPDATE (60 params < D1 100-param cap) so we stay
        # well below D1's 10-second burst limit.
        updated_rows = 0
        for i in range(0, len(changed), 20):
            batch = changed[i : i + 20]
            whens = " ".join("WHEN ? THEN ?" for _ in batch)
            marks = ", ".join(["?"] * len(batch))
            params: list[Any] = []
            for r in batch:
                params.extend([r["site_id"], r["sources_json"]])
            params.extend(r["site_id"] for r in batch)
            d1.query(
                f"UPDATE tag_site_public SET sources_json = CASE site_id {whens} END "
                f"WHERE site_id IN ({marks});",
                params,
            )
            updated_rows += len(batch)
            if i + 20 < len(changed):
                time.sleep(0.5)
        print(
            f"Enriched {enriched_sources} source citation(s) across "
            f"{updated_rows} tag_site_public row(s)."
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
