#!/usr/bin/env python3
"""One-off: seed record history from the 2026-08-15 Zenodo deposit.

Writes each record in deep_dives_all.tar.gz (Zenodo record 20805384) as
revision 1 (source seed:zenodo-1.0.0, evidence inline, no .md), then
creates data release 1.0.0 over them.

    uv run python scripts/cloud/seed_record_history.py --tarball PATH             # dry-run
    uv run python scripts/cloud/seed_record_history.py --tarball PATH --execute

Download the tarball first (116 MB, gitignored location):
    curl -L -o data/external/zenodo/deep_dives_all_1.0.0.tar.gz \\
      "https://zenodo.org/records/20805384/files/deep_dives_all.tar.gz?download=1"

RESUMABLE, not refuse-on-nonempty. A re-run first reads every existing
``record_revision`` row (read-only, no writes yet) and refuses — listing
the offending genes — if ANY row isn't exactly what this seed itself
would have written: a source other than ``seed:zenodo-1.0.0``, a
revision other than 1, a symbol this tarball doesn't carry, or a
``json_hash`` that doesn't match what this tarball's record hashes to
(a stale or swapped-out tarball). Everything that passes that check is
"already done"; only the remaining genes get written. R2 puts are
separately idempotent (content-addressed, ``head_object``-gated inside
``CloudRevisionStore.put_blob``). If ``data_release`` already has
1.0.0 with every tarball gene accounted for, the script prints
"already seeded" and exits 0 having written nothing.

Ordering matters for the rest of the record-history rollout: this seed
must run BEFORE anything ever archives a *served* record for these
genes. Publishing a gene, or running sweep_record_history.py --execute,
before this seed has run would land "revision 1" as the served shape
rather than the Zenodo deposit's shape — defeating the point of pinning
the deposit as history's starting point. Sequence: apply the D1/R2
schema → run this seed → THEN set ARCHIVE_BYPASS_TOKEN locally and run
sweep_record_history.py --execute.

Expect that first real sweep to give EVERY seeded gene a revision 2,
not just the ones that actually changed since 2026-08-15: the served
API shape differs from the deposit's shape by construction — evidence
is split out into its own route instead of inlined, deterministic-
feature enrichment has landed since the deposit, and a Markdown export
now exists where the deposit had none — so the hashes will differ for
essentially every gene on that first sweep. That's expected, not a bug
in this script or in the hashing.
"""

from __future__ import annotations

import argparse
import json
import tarfile
import threading
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Any

from accessible_surfaceome.cloud.record_history.hashing import content_hash_record
from accessible_surfaceome.cloud.record_history.releases import create_release
from accessible_surfaceome.cloud.record_history.store import (
    CloudRevisionStore,
    blob_key,
)
from accessible_surfaceome.cloud.surface_annotation import purge_paths
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


def refuse_on_stale_existing_rows(
    existing_rows: list[dict[str, Any]],
    *,
    expected_hash: dict[str, str],
    tarball_symbols: set[str],
) -> None:
    """Read-only guard, run before any write.

    A resumed seed may only build on rows that this exact seed would
    itself have written. Anything else — a later sweep/publish row, a
    stray revision, a symbol this tarball doesn't carry, or a hash
    mismatch against this tarball's record — means resuming here would
    silently corrupt the "revision 1 = as-deposited" invariant the seed
    exists to establish.
    """
    bad: dict[str, list[str]] = {}

    def flag(symbol: str, reason: str) -> None:
        bad.setdefault(symbol, []).append(reason)

    for row in existing_rows:
        sym = row["gene_symbol"]
        key = sym.casefold()
        if row["source"] != SEED_SOURCE:
            flag(sym, f"source={row['source']!r}")
        if int(row["revision"]) != 1:
            flag(sym, f"revision={row['revision']!r}")
        if key not in tarball_symbols:
            flag(sym, "not present in this tarball")
        elif row["json_hash"] != expected_hash[key]:
            flag(sym, "json_hash differs from this tarball's record")

    if bad:
        detail = "; ".join(
            f"{sym} ({', '.join(rs)})" for sym, rs in sorted(bad.items())
        )
        raise SystemExit(
            "record_revision has rows inconsistent with resuming a 1.0.0 seed "
            f"from this tarball — refusing: {detail}"
        )


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

    expected_hash = {
        sym.casefold(): content_hash_record(rec) for sym, _raw, rec in records
    }
    tarball_symbols = set(expected_hash)

    load_env()
    with CloudRevisionStore.from_env() as store:
        existing_rows = store.d1.query(
            "SELECT gene_symbol, revision, json_hash, source FROM record_revision", []
        )
        refuse_on_stale_existing_rows(
            existing_rows, expected_hash=expected_hash, tarball_symbols=tarball_symbols
        )

        releases = store.d1.query("SELECT version, n_genes FROM data_release", [])
        other_versions = sorted(
            {r["version"] for r in releases if r["version"] != "1.0.0"}
        )
        if other_versions:
            raise SystemExit(
                "data_release already has version(s) other than 1.0.0: "
                f"{', '.join(other_versions)} — refusing to seed underneath a later release"
            )
        release_100 = next((r for r in releases if r["version"] == "1.0.0"), None)
        if release_100 is not None and int(release_100["n_genes"]) == len(records):
            print("already seeded")
            return

        existing_symbols = {row["gene_symbol"].casefold() for row in existing_rows}
        todo = [item for item in records if item[0].casefold() not in existing_symbols]
        if existing_symbols:
            print(f"resuming: {len(todo)} of {len(records)} genes still need writing")
        else:
            print(f"{len(todo)} genes to write")

        def put(item: tuple[str, bytes, dict]) -> None:
            _, raw, rec = item
            store.put_blob(
                blob_key(content_hash_record(rec), "json"), raw, "application/json"
            )

        with ThreadPoolExecutor(POOL_WORKERS) as pool:
            list(pool.map(put, todo))
        print("R2 blobs written" if todo else "R2: nothing left to write")

        # Stop-on-first-failure: the shared Event is checked at the top of
        # every worker call, so once it trips (any exception, from any
        # thread) every task still queued behind it becomes a no-op instead
        # of racing ahead to write more partial state. The pool draining
        # (the `with` block exiting) happens before we look at `errors`, so
        # every worker has either finished or skipped by the time we
        # re-raise.
        stop_event = threading.Event()
        errors: list[BaseException] = []
        errors_lock = threading.Lock()

        def insert_one(item: tuple[str, bytes, dict]) -> None:
            if stop_event.is_set():
                return
            sym, _, rec = item
            try:
                expected = expected_hash[sym.casefold()]
                rev = store.insert_revision(
                    [
                        sym,
                        rec["gene"].get("hgnc_id"),
                        expected,
                        None,
                        None,
                        SEED_AT,
                        SEED_SOURCE,
                        rec.get("schema_version"),
                        rec.get("prompt_corpus_version"),
                    ]
                )
                if rev is None:
                    # Unchanged per insert_revision's own dedup — accept iff
                    # the latest row it saw really is our expected revision
                    # 1, e.g. a retried at-least-once write that actually
                    # landed. Anything else is a genuine conflict.
                    latest = store.latest(sym)
                    if (
                        latest is None
                        or latest.revision != 1
                        or latest.json_hash != expected
                    ):
                        raise RuntimeError(
                            f"{sym}: insert_revision returned None (unchanged) but "
                            "store.latest() doesn't confirm revision 1 with this "
                            "tarball's hash"
                        )
                elif rev != 1:
                    raise RuntimeError(f"{sym}: expected revision 1, got {rev}")
            except BaseException as exc:  # noqa: BLE001 — captured, re-raised below
                stop_event.set()
                with errors_lock:
                    errors.append(exc)

        with ThreadPoolExecutor(POOL_WORKERS) as pool:
            list(pool.map(insert_one, todo))

        if errors:
            raise errors[0]

        members: list[tuple[str, int]] = [(sym, 1) for sym, _, _ in records]
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
        purge_paths(["/v1/releases", "/v1/releases/1.0.0"])
    print(
        f"seeded {len(members)} genes; release 1.0.0 created/confirmed. "
        "Now set ARCHIVE_BYPASS_TOKEN locally and run "
        "sweep_record_history.py --execute"
    )


if __name__ == "__main__":
    main()
