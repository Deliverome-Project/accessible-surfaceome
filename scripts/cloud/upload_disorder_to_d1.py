"""Publish a disorder sweep into ``disorder_public``.

One predictor per invocation, so a re-run of one does not disturb the others:

    uv run python scripts/cloud/upload_disorder_to_d1.py \
        --run-dir <dir> --predictor metapredict --dry-run

Provenance is recorded per row: the Modal app id, the git commit the sweep ran from, and
whether that tree was dirty. The bare app id only -- the console URL embeds the workspace
slug and this database is served publicly.
"""

from __future__ import annotations

import argparse
import gzip
import json
import subprocess
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

from accessible_surfaceome.cloud.d1_client import D1Client
from accessible_surfaceome.env import load_env
from accessible_surfaceome.sources.disorder import PARSERS, Row

DEFAULT_COHORTS = "human_canonical,human_isoforms"
BATCH = 200  # raised from 50; one writer, larger batches
TOOL_VERSIONS = {
    "metapredict": "metapredict-3.0.2",
    "netsurfp-3.0": "netsurfp-3.0-standalone",
    "alphafold-disorder": "alphafold-disorder-rsa25+plddt (AFDB v6)",
}


def _git(*args: str) -> str:
    return subprocess.run(["git", *args], capture_output=True, text=True).stdout.strip()


def _load_rows_json(path: Path, predictor: str) -> dict[str, Row]:
    """Rebuild Row objects parsed on Modal, refusing a file for another predictor.

    Reconstructed through Row rather than used as plain dicts so the rows published this
    way are the same objects the local path would have produced, and so a field added to
    Row without being added here fails loudly instead of being silently dropped.
    """
    opener = gzip.open if path.suffix == ".gz" else open
    with opener(path, "rt") as fh:
        payload = json.load(fh)
    rows: dict[str, Row] = {}
    for acc, fields in payload.items():
        row = Row(**fields)
        if row.predictor != predictor:
            sys.exit(
                f"{path} holds {row.predictor!r} rows but --predictor is {predictor!r}"
            )
        rows[acc] = row
    return rows


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    src = ap.add_mutually_exclusive_group(required=True)
    src.add_argument("--run-dir", type=Path, help="a sweep directory to parse locally")
    src.add_argument(
        "--rows-json",
        type=Path,
        help=(
            "rows already parsed by modal/disorder_parse_app.py (.json or .json.gz). "
            "The sweeps are far larger than the rows they yield, so parsing on Modal "
            "and fetching only this file avoids a multi-GB download."
        ),
    )
    ap.add_argument("--predictor", required=True, choices=sorted(PARSERS))
    ap.add_argument("--disorder-version", required=True)
    ap.add_argument("--cohorts", default=DEFAULT_COHORTS)
    ap.add_argument(
        "--resume",
        action="store_true",
        help="finish an interrupted publish instead of refusing",
    )
    ap.add_argument("--modal-app-id", default=None, help="bare id, e.g. ap-XXXX")
    ap.add_argument("--tool-version", default=None)
    ap.add_argument(
        "--drop-length-mismatch",
        action="store_true",
        help=(
            "exclude predictions scored over more residues than the stored protein, "
            "instead of refusing the whole publish. Every dropped accession is named. "
            "Use only when the mismatch is understood: it means the predictor saw a "
            "different sequence, so position i no longer maps to residue i+1."
        ),
    )
    g = ap.add_mutually_exclusive_group(required=True)
    g.add_argument("--dry-run", action="store_true")
    g.add_argument("--execute", action="store_true")
    args = ap.parse_args()

    load_env()
    cohorts = tuple(c.strip() for c in args.cohorts.split(","))
    if args.run_dir:
        rows = PARSERS[args.predictor](args.run_dir)
        source = args.run_dir
    else:
        rows = _load_rows_json(args.rows_json, args.predictor)
        source = args.rows_json
    print(f"{len(rows):,} {args.predictor} rows parsed from {source}")

    sha, dirty = _git("rev-parse", "HEAD"), bool(_git("status", "--porcelain"))
    print(
        f"provenance: git {sha[:12]}{' (DIRTY)' if dirty else ''}  "
        f"modal {args.modal_app_id or 'not supplied'}"
    )
    if dirty:
        print(
            "  note: the tree is dirty, so git_dirty=1 marks these rows as "
            "not exactly reproducible from that commit"
        )

    with D1Client.public() as d1:
        if not d1.query(
            "SELECT name FROM sqlite_master WHERE type='table' "
            "AND name='disorder_public'"
        ):
            sys.exit(
                "disorder_public does not exist — apply "
                "cloudflare/migrations/disorder_public.sql first"
            )
        clash = d1.query(
            "SELECT COUNT(*) n FROM disorder_public WHERE disorder_version=? AND predictor=?",
            [args.disorder_version, args.predictor],
        )[0]["n"]
        if clash and not args.resume:
            sys.exit(
                f"refusing: {clash:,} rows already under "
                f"({args.disorder_version}, {args.predictor}). "
                "Pass --resume to finish an interrupted publish"
            )
        before = d1.query("SELECT COUNT(*) n FROM disorder_public")[0]["n"]

        ph = ", ".join(["?"] * len(cohorts))
        ident = {
            r["uniprot_acc_full"]: r
            for r in d1.query(
                "SELECT uniprot_acc_full, uniprot_acc, hgnc_id, gene_symbol, is_canonical, "
                f"protein_length FROM topology_public WHERE cohort IN ({ph}) "
                "GROUP BY uniprot_acc_full",
                list(cohorts),
            )
        }
        print(f"{len(ident):,} identity rows across {cohorts}")

        missing = sorted(set(rows) - set(ident))
        if missing:
            sys.exit(
                f"refusing: {len(missing):,} predictions have no topology row, "
                f"e.g. {missing[:5]}"
            )

        now = datetime.now(timezone.utc).isoformat(timespec="seconds")
        # Collect every mismatch before deciding, so the scale is visible. Dying on the
        # first one tells you nothing about whether it is a stray or a systematic fault.
        mismatched = {
            acc: (row.window_residues, ident[acc]["protein_length"])
            for acc, row in rows.items()
            if row.window_residues > ident[acc]["protein_length"]
        }
        if mismatched:
            print(f"\n{len(mismatched):,} prediction(s) scored more residues than the stored protein:")
            for acc, (w, length) in sorted(mismatched.items(), key=lambda kv: kv[1][1] - kv[1][0]):
                print(f"   {acc:<16} scored {w:>5}  stored {length:>5}  (+{w - length})")
            if not args.drop_length_mismatch:
                sys.exit(
                    "refusing: the predictor saw a different sequence for these, so the "
                    "per-residue offsets do not line up with the stored protein. Pass "
                    "--drop-length-mismatch to publish the rest without them."
                )
            print(f"   dropping all {len(mismatched):,}; the rest publish unchanged\n")

        payload = []
        for acc, row in rows.items():
            if acc in mismatched:
                continue
            i = ident[acc]
            payload.append(
                {
                    "disorder_version": args.disorder_version,
                    "uniprot_acc_full": acc,
                    "uniprot_acc": i["uniprot_acc"],
                    "hgnc_id": i["hgnc_id"],
                    "gene_symbol": i["gene_symbol"],
                    "is_canonical": i["is_canonical"],
                    "protein_length": i["protein_length"],
                    **row.columns(),
                    "tool_version": args.tool_version or TOOL_VERSIONS[args.predictor],
                    "modal_app_id": args.modal_app_id,
                    "git_sha": sha,
                    "git_dirty": int(dirty),
                    "retrieved_at": now,
                }
            )

        partial = sum(1 for r in payload if r["window_residues"] < r["protein_length"])
        subs = sum(r["sequence_substituted"] for r in payload)
        print(f"\n{len(payload):,} rows prepared")
        print(
            f"  scored over less than the full protein: {partial:,} "
            f"({'expected for netsurfp-3.0' if args.predictor == 'netsurfp-3.0' else 'AFDB model shorter than the sequence'})"
        )
        print(f"  sequences substituted: {subs:,}")
        print(f"  cohorts: {dict(Counter(ident[a]['is_canonical'] for a in rows))}")

        if args.dry_run:
            print("\ndry run — nothing written")
            ex = dict(payload[0])
            for k in ("disorder_hex", "rsa_hex", "plddt_hex", "ss3"):
                if ex.get(k):
                    ex[k] = f"<{len(ex[k])} chars>"
            print(json.dumps(ex, indent=2))
            return

        cols = list(payload[0])
        stmt = (
            f"INSERT OR IGNORE INTO disorder_public ({', '.join(cols)}) "
            f"VALUES ({', '.join(['?'] * len(cols))})"
        )
        written = 0
        for i in range(0, len(payload), BATCH):
            chunk = payload[i : i + BATCH]
            d1.batch([(stmt, [r[c] for c in cols]) for r in chunk])
            written += len(chunk)
            if written % 5000 < BATCH:
                print(f"  {written:,}/{len(payload):,}")

        after = d1.query("SELECT COUNT(*) n FROM disorder_public")[0]["n"]
        new = d1.query(
            "SELECT COUNT(*) n FROM disorder_public WHERE disorder_version=? "
            "AND predictor=?",
            [args.disorder_version, args.predictor],
        )[0]["n"]
        print(f"\nrows before {before:,}  after {after:,}  (+{after - before:,})")
        # Under --resume, `before` already holds rows from the interrupted run, so
        # growth is less than the version total. What holds either way is that the
        # version ends up with exactly the rows prepared.
        if new != len(payload) or (not args.resume and after - before != new):
            sys.exit("ALARM: row accounting does not balance")
        print("done")


if __name__ == "__main__":
    main()
