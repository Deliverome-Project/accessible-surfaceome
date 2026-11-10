"""Apply the tag-site literature audit to public D1's ``tag_site_public``.

The 191 live ``literature_retrieved`` internal rows (176 of them the S5E13
ranker's training set) were audited by hand against their cited papers (deliverome-analysis PR 236).
This script loads the audit's corrections as a new ``tag_sites_version`` so
the public API (``/v1/tag-sites/{SYMBOL}``) stops serving the wrong residues.
The pure logic lives in :mod:`accessible_surfaceome.cloud.tag_site_audit`.

Inputs, all under ``data/analysis/tag_site_corpus_audit/``:

* ``audit.tsv`` — the audit, keyed by ``site_id`` (committed copy of
  ``processed://scratch/becca/tag-site-corpus-audit/audit.tsv``).
* ``failed_sites.tsv`` — confirmed sites whose paper shows the construct failed
  (position stands; ``validation_level`` becomes ``function_perturbed``).
* ``added_sites.tsv`` — sites recovered from papers the agent had filed under
  the wrong gene; ``confirmed_*`` rows are minted as new literature rows.
* ``rows_before.json`` — the 191 audited rows exactly as served before the
  correction, captured by ``--export-before``. The corrections are always
  built from THIS snapshot, never from the live table, so a re-run after a
  literature re-sync restores the corrections instead of shifting an already
  corrected residue a second time.
* ``canonical_sequences.json`` / ``per_residue_topology.json`` — human
  canonical sequence and DeepTMHMM per-residue topology (from
  ``topology_public``) for every accession in the snapshot, also captured by
  ``--export-before``; what recomputed flanks and topology states are read from.

Outputs (committed, so a reader can diff the change): ``rows_after.json`` and
``summary.json``.

Modes::

    # 1. once: snapshot the served rows + sequences (also writes a dated
    #    export of EVERY literature_retrieved row for the S3 archive)
    uv run python scripts/cloud/apply_tag_site_audit.py --export-before \
        --full-export /path/to/tag_site_public_literature_rows_YYYY-MM-DD.json

    # 2. build the corrections from the snapshot and print the plan (default)
    uv run python scripts/cloud/apply_tag_site_audit.py

    # 3. write them to public D1 and purge the per-gene edge cache
    uv run python scripts/cloud/apply_tag_site_audit.py --execute

The table keys on ``(uniprot_acc, site_id)`` with no version axis, so the
write is ``INSERT OR REPLACE`` for kept rows and ``DELETE`` for withdrawn
ones; the previous rows survive in ``rows_before.json`` and the S3 export.
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from accessible_surfaceome.cloud.d1_client import D1Client
from accessible_surfaceome.cloud.surface_annotation import purge_paths
from accessible_surfaceome.cloud.tag_site_audit import (
    COLUMNS,
    build_corrections,
    dump_rows,
    read_audit,
    read_tsv,
    summarize,
)
from accessible_surfaceome.env import load_env
from accessible_surfaceome.paths import REPO_ROOT

AUDIT_DIR = REPO_ROOT / "data" / "analysis" / "tag_site_corpus_audit"
AUDIT_TSV = AUDIT_DIR / "audit.tsv"
ROWS_BEFORE = AUDIT_DIR / "rows_before.json"
SEQUENCES = AUDIT_DIR / "canonical_sequences.json"
TOPOLOGIES = AUDIT_DIR / "per_residue_topology.json"
FAILED_TSV = AUDIT_DIR / "failed_sites.tsv"
ADDED_TSV = AUDIT_DIR / "added_sites.tsv"
LIVE_IDS_ADDED = AUDIT_DIR / "live_site_ids_added_genes.json"
ROWS_AFTER = AUDIT_DIR / "rows_after.json"
SUMMARY = AUDIT_DIR / "summary.json"

DEFAULT_VERSION = "2026-11-05-lit-audit"


def _chunks(items: list[str], n: int) -> list[list[str]]:
    return [items[i : i + n] for i in range(0, len(items), n)]


def export_before(
    client: D1Client, audit: list[dict[str, str]], full_export: Path | None
) -> None:
    ids = [a["site_id"] for a in audit]
    rows: list[dict[str, Any]] = []
    for ch in _chunks(ids, 90):
        marks = ", ".join("?" * len(ch))
        rows += client.query(
            f"SELECT * FROM tag_site_public WHERE site_id IN ({marks}) ORDER BY site_id;",
            ch,
        )
    missing = set(ids) - {r["site_id"] for r in rows}
    if missing:
        raise SystemExit(
            f"{len(missing)} audited site_ids are not in tag_site_public: "
            f"{sorted(missing)[:10]}"
        )
    live_cols = [
        c["name"] for c in client.query("PRAGMA table_info(tag_site_public);", [])
    ]
    if set(live_cols) != set(COLUMNS):
        raise SystemExit(
            f"live columns differ from COLUMNS: {sorted(set(live_cols) ^ set(COLUMNS))}"
        )
    dump_rows(rows, ROWS_BEFORE)
    print(f"wrote {len(rows)} rows -> {ROWS_BEFORE.relative_to(REPO_ROOT)}")

    added = read_tsv(ADDED_TSV)
    added_genes = sorted(
        {a["gene"] for a in added if a["verdict"].startswith("confirmed")}
    )
    live_ids: list[str] = []
    if added_genes:
        marks = ", ".join("?" * len(added_genes))
        live_ids = sorted(
            r["site_id"]
            for r in client.query(
                f"SELECT site_id FROM tag_site_public WHERE gene_symbol IN ({marks});",
                added_genes,
            )
        )
    LIVE_IDS_ADDED.write_text(json.dumps(live_ids, indent=1) + "\n", encoding="utf-8")
    print(
        f"wrote {len(live_ids)} live site_ids for the added genes -> {LIVE_IDS_ADDED.relative_to(REPO_ROOT)}"
    )

    accs = sorted(
        {r["uniprot_acc"] for r in rows}
        | {a["uniprot_acc"] for a in added if a["verdict"].startswith("confirmed")}
    )
    seqs: dict[str, str] = {}
    topos: dict[str, str] = {}
    for ch in _chunks(accs, 90):
        marks = ", ".join("?" * len(ch))
        for r in client.query(
            "SELECT uniprot_acc, sequence, per_residue_topology FROM topology_public "
            "WHERE cohort = 'human_canonical' "
            f"AND is_canonical = 1 AND uniprot_acc IN ({marks});",
            ch,
        ):
            seqs[r["uniprot_acc"]] = r["sequence"]
            topos[r["uniprot_acc"]] = r["per_residue_topology"] or ""
    if set(accs) - set(seqs):
        raise SystemExit(f"no canonical sequence for {sorted(set(accs) - set(seqs))}")
    SEQUENCES.write_text(
        json.dumps(seqs, indent=0, sort_keys=True) + "\n", encoding="utf-8"
    )
    print(f"wrote {len(seqs)} sequences -> {SEQUENCES.relative_to(REPO_ROOT)}")
    TOPOLOGIES.write_text(
        json.dumps(topos, indent=0, sort_keys=True) + "\n", encoding="utf-8"
    )
    print(f"wrote {len(topos)} topologies -> {TOPOLOGIES.relative_to(REPO_ROOT)}")

    if full_export is not None:
        every = client.query(
            "SELECT * FROM tag_site_public WHERE provenance = 'literature_retrieved' "
            "ORDER BY gene_symbol, site_id;",
            [],
        )
        dump_rows(every, full_export)
        print(f"wrote {len(every)} literature_retrieved rows -> {full_export}")


def apply(client: D1Client | None, corrections, *, dry_run: bool) -> None:
    upserts = [c for c in corrections if c.action in ("update", "keep", "add")]
    deletes = [c for c in corrections if c.action == "delete"]
    genes = sorted(
        {
            c.gene_symbol
            for c in corrections
            if c.action not in ("keep", "skip_existing")
        }
    )
    if dry_run:
        print(
            f"(dry-run) would upsert {len(upserts)} rows, delete {len(deletes)} rows, "
            f"purge {len(genes)} gene caches — pass --execute"
        )
        return
    assert client is not None
    cols = ", ".join(COLUMNS)
    marks = ", ".join("?" * len(COLUMNS))
    for c in upserts:
        assert c.row is not None
        client.query(
            f"INSERT OR REPLACE INTO tag_site_public ({cols}) VALUES ({marks});",
            [c.row[k] for k in COLUMNS],
        )
    for c in deletes:
        client.query(
            "DELETE FROM tag_site_public WHERE uniprot_acc = ? AND site_id = ?;",
            [c.uniprot_acc, c.site_id],
        )
    print(f"upserted {len(upserts)} rows, deleted {len(deletes)} rows")
    purged = purge_paths([f"/v1/tag-sites/{g}" for g in genes])
    print(f"edge-cache purge for {len(genes)} genes: {purged}")


def main() -> int:
    ap = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    ap.add_argument(
        "--export-before",
        action="store_true",
        help="snapshot the served rows + sequences from live D1, then exit",
    )
    ap.add_argument(
        "--full-export",
        type=Path,
        default=None,
        help="with --export-before: also dump every literature_retrieved row here",
    )
    ap.add_argument(
        "--execute", action="store_true", help="write to public D1 (default: dry-run)"
    )
    ap.add_argument(
        "--version", default=DEFAULT_VERSION, help="tag_sites_version for the new rows"
    )
    args = ap.parse_args()

    load_env()
    audit = read_audit(AUDIT_TSV)

    if args.export_before:
        with D1Client.public() as d1:
            export_before(d1, audit, args.full_export)
        return 0

    before = json.loads(ROWS_BEFORE.read_text(encoding="utf-8"))
    seqs = json.loads(SEQUENCES.read_text(encoding="utf-8"))
    topos = json.loads(TOPOLOGIES.read_text(encoding="utf-8"))
    failed = {r["site_id"]: r["why_failed"] for r in read_tsv(FAILED_TSV)}
    added = read_tsv(ADDED_TSV)
    live_ids = set(json.loads(LIVE_IDS_ADDED.read_text(encoding="utf-8")))
    synced_at = datetime.now(UTC).isoformat()
    corrections = build_corrections(
        before,
        audit,
        seqs,
        version=args.version,
        synced_at=synced_at,
        topologies=topos,
        failed=failed,
        added=added,
        existing_site_ids=live_ids,
    )
    summary = summarize(corrections)
    summary["tag_sites_version"] = args.version
    print(json.dumps(summary, indent=1))

    after = [c.row for c in corrections if c.row is not None]
    for r in after:  # the committed artifact must not churn on every dry run
        r["synced_at"] = "<set at execute time>"
    dump_rows(after, ROWS_AFTER)
    SUMMARY.write_text(
        json.dumps(summary, indent=1, sort_keys=True) + "\n", encoding="utf-8"
    )
    for r in after:
        r["synced_at"] = synced_at

    if args.execute:
        with D1Client.public() as d1:
            apply(d1, corrections, dry_run=False)
    else:
        apply(None, corrections, dry_run=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
