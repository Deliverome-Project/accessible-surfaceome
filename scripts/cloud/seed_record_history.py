#!/usr/bin/env python3
"""One-off: seed record history from the 2026-08-15 Zenodo deposit.

Writes each record in deep_dives_all.tar.gz (Zenodo record 20805384) as
revision 1 (source seed:zenodo-1.0.0, evidence inline, no .md), then
creates data release 1.0.0 over them. Refuses if record_revision already
has rows. Run the sweep afterwards: changed genes get revision 2, genes
annotated after 2026-08-15 start at revision 1.

    uv run python scripts/cloud/seed_record_history.py --tarball PATH             # dry-run
    uv run python scripts/cloud/seed_record_history.py --tarball PATH --execute

Download the tarball first (116 MB, gitignored location):
    curl -L -o data/external/zenodo/deep_dives_all_1.0.0.tar.gz \\
      "https://zenodo.org/records/20805384/files/deep_dives_all.tar.gz?download=1"
"""

from __future__ import annotations

import argparse
import json
import tarfile
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from accessible_surfaceome.cloud.record_history.hashing import content_hash_record
from accessible_surfaceome.cloud.record_history.releases import create_release
from accessible_surfaceome.cloud.record_history.store import (
    CloudRevisionStore,
    blob_key,
)
from accessible_surfaceome.env import load_env

SEED_SOURCE = "seed:zenodo-1.0.0"
SEED_AT = "2026-08-15T00:00:00Z"
SEED_DOI = "10.5281/zenodo.20805384"

# Number of D1 / R2 round trips to run concurrently. Serial writes at
# cohort scale (5,130 records) would be 5,130+ blocking HTTP calls each
# way; a small pool amortizes the per-request latency without hammering
# either service the way an unbounded fan-out would.
POOL_WORKERS = 8


def read_records(tarball: Path) -> list[tuple[str, bytes, dict]]:
    out = []
    with tarfile.open(tarball) as tf:
        for m in tf.getmembers():
            if not (m.isfile() and m.name.endswith(".json")):
                continue
            raw = tf.extractfile(m).read()  # type: ignore[union-attr]
            rec = json.loads(raw)
            out.append((rec["gene"]["hgnc_symbol"], raw, rec))
    return sorted(out, key=lambda t: t[0])


def check_unique_case_insensitive(records: list[tuple[str, bytes, dict]]) -> None:
    """Refuse a tarball with two records for the same gene under different
    casing — ``record_revision.gene_symbol`` is ``COLLATE NOCASE``, so two
    such rows would race for "revision 1" of the same logical gene. Must
    run before anything is written to R2 or D1.
    """
    seen: set[str] = set()
    for sym, _raw, _rec in records:
        key = sym.casefold()
        if key in seen:
            raise SystemExit(f"duplicate symbol (case-insensitive) in tarball: {sym!r}")
        seen.add(key)


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--tarball", type=Path, required=True)
    ap.add_argument("--execute", action="store_true")
    args = ap.parse_args()

    records = read_records(args.tarball)
    print(f"{len(records)} records in {args.tarball.name}")
    check_unique_case_insensitive(records)
    if not args.execute:
        print("[dry-run] pass --execute to write revision 1 + release 1.0.0")
        return

    load_env()
    with CloudRevisionStore.from_env() as store:
        # Must run before any R2 write below — a non-empty table means a
        # previous seed (partial or complete) already ran.
        if store.d1.query("SELECT 1 FROM record_revision LIMIT 1", []):
            raise SystemExit("record_revision is not empty — refusing to seed twice")

        def put(item: tuple[str, bytes, dict]) -> None:
            _, raw, rec = item
            store.put_blob(
                blob_key(content_hash_record(rec), "json"), raw, "application/json"
            )

        with ThreadPoolExecutor(POOL_WORKERS) as pool:
            list(pool.map(put, records))
        print("R2 blobs written")

        def insert_one(item: tuple[str, bytes, dict]) -> tuple[str, int]:
            sym, _, rec = item
            rev = store.insert_revision(
                [
                    sym,
                    rec["gene"].get("hgnc_id"),
                    content_hash_record(rec),
                    None,
                    None,
                    SEED_AT,
                    SEED_SOURCE,
                    rec.get("schema_version"),
                    rec.get("prompt_corpus_version"),
                ]
            )
            if rev != 1:
                raise SystemExit(f"{sym}: expected revision 1, got {rev}")
            return sym, rev

        with ThreadPoolExecutor(POOL_WORKERS) as pool:
            members: list[tuple[str, int]] = list(pool.map(insert_one, records))

        create_release(
            store.d1,
            version="1.0.0",
            cut_at=SEED_AT,
            github_tag=None,
            zenodo_version_doi=SEED_DOI,
            notes=(
                "Initial data deposit (Zenodo record 20805384); records as "
                "deposited, evidence inline, no Markdown."
            ),
            members=members,
        )
    print(
        f"seeded {len(members)} genes; release 1.0.0 created. "
        "Now run sweep_record_history.py --execute"
    )


if __name__ == "__main__":
    main()
