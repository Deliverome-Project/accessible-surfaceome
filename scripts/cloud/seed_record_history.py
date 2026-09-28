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
separately idempotent (content-addressed, probed with ``head_object``
before every write — see below). If ``data_release`` already has 1.0.0
with every tarball gene accounted for, the script prints "already seeded"
and exits 0 having written nothing.

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

Write path (both R2 and D1 favor few, wide round trips over cohort-scale
per-gene ones — the account's shared Cloudflare API budget is 1,200
requests / 5 min, covering every ``api.cloudflare.com`` call including
R2 REST ops and D1 queries):

* **R2** — each record is uploaded through the S3-compatible API
  (``CloudRevisionStore.put_blob``; see ``cloud/r2_s3.py``), a separate
  API surface from ``api.cloudflare.com`` that doesn't touch the shared
  budget at all — so the existence probe (``head_object``) stays on for
  every key, keeping the bucket strictly write-once, at no cost against
  that budget. ``r2_s3_client()`` is built ONCE up front, before the pool
  starts (``main`` exits non-zero with a clear message if that fails) —
  the store is also constructed with ``require_s3=True``, so a later
  failure to reach the S3 client raises loudly instead of silently
  falling back to the REST ``r2_client`` path (which WOULD compete for
  the shared budget, defeating the point). Runs from a
  ``POOL_WORKERS``-wide thread pool.
* **D1** — revision-1 rows are written with multi-row
  ``INSERT ... VALUES (...),(...) ON CONFLICT(gene_symbol, revision) DO
  NOTHING`` statements (see ``bulk_insert_seed_rows``), sized to D1's
  100-bound-parameter cap, instead of one ``insert_revision`` call per
  gene. ``CloudRevisionStore`` also paces every D1 call through
  ``RECORD_HISTORY_D1_QPS`` (default 2.5 qps) so a seed run doesn't
  compete with concurrent sessions for the shared budget. A single
  verification query afterwards (``verify_seeded_rows``) confirms every
  tarball symbol landed at revision 1 with the expected ``json_hash``.
"""

from __future__ import annotations

import argparse
import json
import tarfile
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Any

from accessible_surfaceome.cloud.r2_s3 import R2S3CredentialError, r2_s3_client
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

# Number of R2 upload round trips to run concurrently. R2 uploads now go
# through the S3-compatible API (a separate API surface from
# api.cloudflare.com, with its own — much higher — limits), so this can run
# wider than the old REST-API pool did.
POOL_WORKERS = 16

# record_revision has 10 columns; D1 caps a statement at 100 bound
# parameters, so this is the widest multi-row INSERT that stays legal.
SEED_COLUMNS = (
    "gene_symbol",
    "hgnc_id",
    "revision",
    "json_hash",
    "evidence_hash",
    "md_hash",
    "published_at",
    "source",
    "schema_version",
    "prompt_corpus_version",
)
SEED_ROWS_PER_INSERT = 100 // len(SEED_COLUMNS)


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


def _seed_insert_sql(n_rows: int) -> str:
    row_placeholder = "(" + ",".join(["?"] * len(SEED_COLUMNS)) + ")"
    return (
        f"INSERT INTO record_revision ({', '.join(SEED_COLUMNS)}) "
        f"VALUES {','.join([row_placeholder] * n_rows)} "
        "ON CONFLICT(gene_symbol, revision) DO NOTHING"
    )


def bulk_insert_seed_rows(
    d1: Any,
    todo: list[tuple[str, bytes, dict]],
    *,
    expected_hash: dict[str, str],
) -> None:
    """Write revision-1 rows for ``todo`` in wide multi-row INSERTs.

    Batches sized to D1's 100-bound-parameter cap (see ``SEED_ROWS_PER_
    INSERT``, and ``releases.MEMBER_ROWS_PER_INSERT`` /
    ``build_paper_metadata_table.py`` for the same pattern elsewhere).
    ``ON CONFLICT(gene_symbol, revision) DO NOTHING`` makes a replayed
    batch (an at-least-once HTTP retry replaying a statement that already
    landed) a harmless no-op rather than an error or a duplicate.
    """
    for i in range(0, len(todo), SEED_ROWS_PER_INSERT):
        chunk = todo[i : i + SEED_ROWS_PER_INSERT]
        params: list[Any] = []
        for sym, _raw, rec in chunk:
            params += [
                sym,
                rec["gene"].get("hgnc_id"),
                1,
                expected_hash[sym.casefold()],
                None,
                None,
                SEED_AT,
                SEED_SOURCE,
                rec.get("schema_version"),
                rec.get("prompt_corpus_version"),
            ]
        d1.query(_seed_insert_sql(len(chunk)), params)


def verify_seeded_rows(
    d1: Any,
    *,
    expected_hash: dict[str, str],
    display_symbol: dict[str, str],
) -> None:
    """ONE query confirming every tarball symbol has revision 1 with the
    expected ``json_hash``. Raises, listing every mismatch, if not.

    Covers the whole tarball (not just genes written this run) — a
    resumed seed's earlier-written rows get the same confirmation a fresh
    run's rows do, in the same single query.
    """
    rows = d1.query(
        "SELECT gene_symbol, json_hash FROM record_revision "
        "WHERE revision = 1 AND source = ?",
        [SEED_SOURCE],
    )
    have = {r["gene_symbol"].casefold(): r["json_hash"] for r in rows}
    bad: list[str] = []
    for key, expected in expected_hash.items():
        actual = have.get(key)
        sym = display_symbol[key]
        if actual is None:
            bad.append(f"{sym}: missing revision 1")
        elif actual != expected:
            bad.append(f"{sym}: json_hash mismatch (got {actual!r})")
    if bad:
        raise SystemExit(
            "seed verification failed for: " + "; ".join(sorted(bad))
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
    display_symbol = {sym.casefold(): sym for sym, _raw, _rec in records}
    tarball_symbols = set(expected_hash)

    load_env()
    # Build (and cache) the S3 client ONCE, here in the main thread, before
    # the R2 upload pool starts below — so every pooled worker finds it
    # already built (one client, one credential-derivation call) instead of
    # racing a cold cache, and so a broken/missing CLOUDFLARE_API_TOKEN
    # fails loudly right now instead of thousands of workers each hitting
    # the (require_s3=True) ArchiveError individually.
    try:
        r2_s3_client()
    except R2S3CredentialError as exc:
        raise SystemExit(
            f"R2 S3 client unavailable ({exc}) — the seed refuses to fall "
            "back to the REST r2_client path at cohort scale (it would "
            "compete for the shared Cloudflare account API budget). Set "
            "CLOUDFLARE_ACCOUNT_ID + CLOUDFLARE_API_TOKEN (or "
            "R2_ACCESS_KEY_ID/R2_SECRET_ACCESS_KEY) and retry."
        ) from exc

    with CloudRevisionStore.from_env(require_s3=True) as store:
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

        bulk_insert_seed_rows(store.d1, todo, expected_hash=expected_hash)
        verify_seeded_rows(
            store.d1, expected_hash=expected_hash, display_symbol=display_symbol
        )

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
