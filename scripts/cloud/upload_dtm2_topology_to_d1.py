"""Publish a DeepTMHMM2 sweep into ``topology_public`` under a fresh topology_version.

Deliberately separate from the sweep. The sweep streams to a Modal Volume and writes
nothing; this is the only step that touches the public database with data, so it is run
knowingly, after the output has been looked at.

    uv run python scripts/cloud/upload_dtm2_topology_to_d1.py --run-dir <dir> --dry-run
    uv run python scripts/cloud/upload_dtm2_topology_to_d1.py --run-dir <dir> --execute

Safety, in order of how much it matters:

* **v1 is never rewritten.** The primary key is
  ``(topology_version, cohort, uniprot_acc_full)`` and v2 lands under its own version, so
  the two occupy disjoint key space. Inserts use ``INSERT OR IGNORE``.
* **The total row count is asserted either side**, not just the v1 tool_version's. The
  table also holds 57 ``uniprot_features_v1`` fallback rows in the mouse and cyno cohorts
  that are not DeepTMHMM output at all and would be invisible to a narrower guard.
* **Identity columns are carried from the v1 row**, never re-derived. The sweep's input
  *was* that row's stored sequence, so re-deriving the accession, cohort or sequence here
  would only be a second chance to disagree with it.
* **Sequence length is re-checked** per row: a v2 topology string that is not exactly
  ``protein_length`` long means the prediction and the row are about different proteins.
"""

from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

from accessible_surfaceome.cloud.d1_client import D1Client
from accessible_surfaceome.env import load_env
from accessible_surfaceome.sources import deeptmhmm2 as d2

# Default is the human set; pass --cohorts for the mouse / cyno ortholog runs.
DEFAULT_COHORTS = "human_canonical,human_isoforms"
CARRIED = (
    "cohort",
    "hgnc_id",
    "uniprot_acc",
    "uniprot_acc_full",
    "isoform_id",
    "gene_symbol",
    "species",
    "is_canonical",
    "sequence",
    "protein_length",
)
BATCH = 40


def load_predictions(run_dir: Path) -> dict[str, d2.Prediction]:
    preds: dict[str, d2.Prediction] = {}
    files = sorted(run_dir.rglob("predictions.json"))
    if not files:
        sys.exit(f"no predictions.json under {run_dir}")
    for f in files:
        for rec in json.loads(f.read_text()):
            if "metadata" in rec:
                continue
            p = d2.parse_record(rec)
            if p.accession in preds:
                sys.exit(f"{p.accession} predicted twice — shards overlap, refusing")
            preds[p.accession] = p
    print(f"{len(preds):,} predictions from {len(files)} shards")
    return preds


def target_rows(d1: D1Client, cohorts: tuple[str, ...]) -> list[dict]:
    """One v1 row per (cohort, uniprot_acc_full) to hang a v2 row on.

    A proteoform present in both cohorts gets a row in each: the prediction depends only
    on the sequence, but ``cohort`` is part of the key and consumers filter on it.
    """
    ph = ", ".join(["?"] * len(cohorts))
    rows = d1.query(
        f"SELECT {', '.join(CARRIED)} FROM topology_public "
        f"WHERE cohort IN ({ph}) GROUP BY cohort, uniprot_acc_full",
        list(cohorts),
    )
    print(f"{len(rows):,} (cohort, accession) targets across {cohorts}")
    return rows


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--run-dir", required=True, type=Path)
    ap.add_argument("--topology-version", default="topo_2026_09_27_dtm2")
    ap.add_argument(
        "--tool-version", required=True, help="from `modal run ...::fingerprint`"
    )
    ap.add_argument(
        "--resume",
        action="store_true",
        help="finish an interrupted publish instead of refusing",
    )
    ap.add_argument("--cohorts", default=DEFAULT_COHORTS)
    group = ap.add_mutually_exclusive_group(required=True)
    group.add_argument("--dry-run", action="store_true")
    group.add_argument("--execute", action="store_true")
    args = ap.parse_args()

    load_env()
    cohorts = tuple(c.strip() for c in args.cohorts.split(","))
    preds = load_predictions(args.run_dir)

    with D1Client.public() as d1:
        before = d1.query("SELECT COUNT(*) n FROM topology_public")[0]["n"]
        clash = d1.query(
            "SELECT COUNT(*) n FROM topology_public WHERE topology_version=?",
            [args.topology_version],
        )[0]["n"]
        print(
            f"\ntable holds {before:,} rows; {clash:,} already under "
            f"{args.topology_version!r}"
        )
        if clash and not args.resume:
            sys.exit(
                f"refusing: {clash:,} rows already under that topology_version. "
                "Pass --resume to finish an interrupted publish (rows already written "
                "are skipped; INSERT OR IGNORE makes each row idempotent)."
            )
        targets = target_rows(d1, cohorts)

        missing = [r for r in targets if r["uniprot_acc_full"] not in preds]
        if missing:
            sys.exit(
                f"refusing: {len(missing):,} targets have no prediction, "
                f"e.g. {[m['uniprot_acc_full'] for m in missing[:5]]}"
            )

        payload, lengths = [], 0
        for r in targets:
            p = preds[r["uniprot_acc_full"]]
            if len(p.topology_string) != r["protein_length"]:
                lengths += 1
                continue
            row = {k: r[k] for k in CARRIED}
            row.update(p.columns())
            row["topology_version"] = args.topology_version
            row["tool_version"] = args.tool_version
            row["retrieved_at"] = datetime.now(timezone.utc).isoformat(
                timespec="seconds"
            )
            payload.append(row)
        if lengths:
            sys.exit(
                f"refusing: {lengths} rows where the v2 string length != protein_length"
            )

        print(f"\n{len(payload):,} rows prepared")
        print("  label      :", dict(Counter(r["deeptmhmm_label"] for r in payload)))
        print("  plasma memb:", sum(r["dtm2_plasma_membrane"] for r in payload))
        print("  lossy proj :", sum(r["dtm2_v1_alphabet_lossy"] for r in payload))
        print("  tool_version:", args.tool_version)

        if args.dry_run:
            print("\ndry run — nothing written")
            print(
                json.dumps(
                    {
                        k: (v[:60] + "…" if isinstance(v, str) and len(v) > 60 else v)
                        for k, v in payload[0].items()
                    },
                    indent=2,
                )[:1400]
            )
            return

        cols = list(payload[0])
        stmt = (
            f"INSERT OR IGNORE INTO topology_public ({', '.join(cols)}) "
            f"VALUES ({', '.join(['?'] * len(cols))})"
        )
        written = 0
        for i in range(0, len(payload), BATCH):
            chunk = payload[i : i + BATCH]
            d1.batch([(stmt, [r[c] for c in cols]) for r in chunk])
            written += len(chunk)
            if written % 2000 < BATCH:
                print(f"  {written:,}/{len(payload):,}")

        after = d1.query("SELECT COUNT(*) n FROM topology_public")[0]["n"]
        new = d1.query(
            "SELECT COUNT(*) n FROM topology_public WHERE topology_version=?",
            [args.topology_version],
        )[0]["n"]
        print(f"\nrows before {before:,}  after {after:,}  (+{after - before:,})")
        print(f"rows under {args.topology_version}: {new:,}")
        if after - before != new:
            sys.exit("ALARM: total growth does not equal the new version's row count")
        surviving = after - new
        if surviving != before:
            sys.exit(f"ALARM: {before - surviving:,} pre-existing rows are gone")
        print(f"all {before:,} pre-existing rows intact")


if __name__ == "__main__":
    main()
