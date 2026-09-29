"""Publish a SignalP 6 run into ``signalp_public``.

Separate from the sweep on purpose: the sweep streams to a Modal Volume and writes
nothing, so this is the only step that puts data in the public database.

    uv run python scripts/cloud/upload_signalp_to_d1.py --run-dir <dir> --dry-run
    uv run python scripts/cloud/upload_signalp_to_d1.py --run-dir <dir> --execute

Identity columns come from ``topology_public``, which is where the input sequences came
from; re-deriving them from the accession string would only be a chance to disagree with
the row the prediction was actually made on.
"""

from __future__ import annotations

import argparse
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

from accessible_surfaceome.cloud.d1_client import D1Client
from accessible_surfaceome.env import load_env
from accessible_surfaceome.sources.signalp6 import parse_run

# Default is the human set; pass --cohorts for the mouse / cyno ortholog runs.
DEFAULT_COHORTS = "human_canonical,human_isoforms"
BATCH = 60


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--run-dir", required=True, type=Path)
    ap.add_argument("--signalp-version", default="sp6_2026_09_28")
    ap.add_argument("--tool-version", default="signalp-6.0+h")
    ap.add_argument("--mode", default="slow-sequential")
    ap.add_argument("--organism", default="eukarya")
    ap.add_argument("--cohorts", default=DEFAULT_COHORTS)
    g = ap.add_mutually_exclusive_group(required=True)
    g.add_argument("--dry-run", action="store_true")
    g.add_argument("--execute", action="store_true")
    args = ap.parse_args()

    load_env()
    cohorts = tuple(c.strip() for c in args.cohorts.split(","))
    calls = parse_run(args.run_dir)
    print(f"{len(calls):,} SignalP calls parsed")
    print("  ", dict(Counter(c.prediction for c in calls.values())))

    with D1Client.public() as d1:
        exists = d1.query(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='signalp_public'"
        )
        if not exists:
            sys.exit(
                "signalp_public does not exist — apply "
                "cloudflare/migrations/signalp_public.sql first"
            )
        before = d1.query("SELECT COUNT(*) n FROM signalp_public")[0]["n"]
        clash = d1.query(
            "SELECT COUNT(*) n FROM signalp_public WHERE signalp_version=?",
            [args.signalp_version],
        )[0]["n"]
        print(
            f"\nsignalp_public holds {before:,} rows; {clash:,} under "
            f"{args.signalp_version!r}"
        )
        if clash:
            sys.exit("refusing: that signalp_version already has rows")

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
        print(f"{len(ident):,} identity rows from topology_public")

        missing = sorted(set(calls) - set(ident))
        if missing:
            sys.exit(
                f"refusing: {len(missing):,} predictions have no topology row, "
                f"e.g. {missing[:5]}"
            )

        now = datetime.now(timezone.utc).isoformat(timespec="seconds")
        payload = []
        for acc, c in calls.items():
            i = ident[acc]
            if c.cleavage_site and c.cleavage_site >= i["protein_length"]:
                sys.exit(
                    f"refusing: {acc} cleavage site {c.cleavage_site} is not inside "
                    f"a {i['protein_length']}-residue protein"
                )
            row = {
                "signalp_version": args.signalp_version,
                "uniprot_acc_full": acc,
                "uniprot_acc": i["uniprot_acc"],
                "hgnc_id": i["hgnc_id"],
                "gene_symbol": i["gene_symbol"],
                "is_canonical": i["is_canonical"],
                "protein_length": i["protein_length"],
                **c.columns(),
                "organism": args.organism,
                "mode": args.mode,
                "tool_version": args.tool_version,
                "retrieved_at": now,
            }
            payload.append(row)

        sp = [r for r in payload if r["prediction"] == "SP"]
        print(f"\n{len(payload):,} rows prepared ({len(sp):,} SP)")
        if sp:
            cs = sorted(r["cleavage_site"] for r in sp)
            print(f"  cleavage site: median {cs[len(cs) // 2]}, range {cs[0]}-{cs[-1]}")
            hl = [r["h_region_end"] - r["h_region_start"] + 1 for r in sp]
            print(f"  h-region length: median {sorted(hl)[len(hl) // 2]}")

        if args.dry_run:
            print("\ndry run — nothing written")
            import json

            print(json.dumps(sp[0] if sp else payload[0], indent=2))
            return

        cols = list(payload[0])
        stmt = (
            f"INSERT OR IGNORE INTO signalp_public ({', '.join(cols)}) "
            f"VALUES ({', '.join(['?'] * len(cols))})"
        )
        written = 0
        for i in range(0, len(payload), BATCH):
            chunk = payload[i : i + BATCH]
            d1.batch([(stmt, [r[c] for c in cols]) for r in chunk])
            written += len(chunk)
            if written % 3000 < BATCH:
                print(f"  {written:,}/{len(payload):,}")

        after = d1.query("SELECT COUNT(*) n FROM signalp_public")[0]["n"]
        new = d1.query(
            "SELECT COUNT(*) n FROM signalp_public WHERE signalp_version=?",
            [args.signalp_version],
        )[0]["n"]
        print(f"\nrows before {before:,}  after {after:,}  (+{after - before:,})")
        print(f"rows under {args.signalp_version}: {new:,}")
        if after - before != new or new != len(payload):
            sys.exit("ALARM: row accounting does not balance")
        print("done")


if __name__ == "__main__":
    main()
