"""Repair the tag-site run archive rows that an early return left anonymous.

Before the stamping fix, all three `_empty()` paths in `run_tag_site_agent`
returned BEFORE the intermediates were written, so any gene that legitimately
found zero sites archived a row carrying only cost and provenance — no
`gene_symbol`, no counts, no ledger. The first library sweep produced 759 such
rows out of 1,825: $344 of spend that could not be attributed to a gene, and a
sha-aware resume keys on `gene_symbol`, so every one of them would have been
re-run and paid for twice.

Nothing here re-runs the agent. Everything written is recovered from artifacts
the run already persisted:

* `gene_symbol` — the local artifact is named `{SYMBOL}.json`, and each D1 row
  joins to it on `created_at`, which is the same timestamp the record carries
  (758 of 759 match 1:1 with no collisions; the odd one out is a smoke-test run
  that a later sweep row supersedes, matched on its cost instead).
* `n_papers` — the discovery cache is saved BEFORE every early return, so the
  discovered corpus survives for all 758.
* `n_sites` — counted from the gene's viewer record, literature sites only.
* `uniprot_acc` — from the same record.

`n_clips` and `n_boosted` are NOT recoverable: the clip pool was never
persisted, and that is the whole reason the pool is archived now. They are left
NULL rather than written as 0, because 0 is a measurement and "we did not keep
it" is not. `backfill_note` says so on every repaired row, so a repaired row can
never be mistaken for one a complete run wrote.

    uv run python scripts/backfill_tag_site_run_archive.py            # dry run
    uv run python scripts/backfill_tag_site_run_archive.py --execute
"""

from __future__ import annotations

import argparse
import json
import logging
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

from accessible_surfaceome.env import load_env

load_env()

from accessible_surfaceome.cloud.d1_client import D1Client  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
RUNS_DIR = ROOT / "data/external/tag_site_runs"
DISCOVERY_DIR = ROOT / "data/external/tag_site_discovery"
VIEWER_DIR = ROOT / "viewer/public/tag-sites"

NOTE = (
    "backfilled from local artifacts after the early-return stamping fix; "
    "n_clips/n_boosted not recoverable (pool was never persisted)"
)

log = logging.getLogger("backfill")


def _json(path: Path) -> dict:
    try:
        return json.loads(path.read_text())
    except Exception:  # noqa: BLE001 - a missing artifact just means less to fill
        return {}


def recoverable(symbol: str) -> dict:
    """What the persisted artifacts can prove about this gene's run."""
    disc = _json(DISCOVERY_DIR / f"{symbol}.json")
    rec = _json(VIEWER_DIR / f"{symbol}.json")
    lit = [
        s
        for s in (rec.get("sites") or [])
        if s.get("provenance") == "literature_retrieved"
    ]
    return {
        "gene_symbol": symbol,
        "uniprot_acc": rec.get("uniprot_acc") or "",
        "n_papers": len(disc) if disc else None,
        "n_sites": len(lit),
    }


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--run-id", default="tag_site_library_v1")
    ap.add_argument("--execute", action="store_true", help="write; otherwise dry-run")
    ap.add_argument("--parallel", type=int, default=8)
    args = ap.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(message)s")

    # Local artifacts that lost their identity, keyed by the timestamp that
    # joins them to their D1 row.
    by_ts: dict[str, str] = {}
    stripped: list[str] = []
    for f in sorted(RUNS_DIR.glob("*.json")):
        d = _json(f)
        if d.get("gene_symbol"):
            continue
        stripped.append(f.stem)
        if ts := d.get("generated_at"):
            by_ts[ts] = f.stem

    with D1Client() as d1:
        rows = d1.query(
            "SELECT id, created_at, cost_usd, n_model_calls FROM tag_site_run "
            "WHERE run_id = ? AND gene_symbol = '';",
            [args.run_id],
        )
        log.info("anonymous rows in %s: %d", args.run_id, len(rows))
        log.info("stripped local artifacts: %d", len(stripped))

        plan: list[tuple[int, dict]] = []
        orphans: list[dict] = []
        for r in rows:
            symbol = by_ts.get(r["created_at"])
            if symbol is None:
                orphans.append(r)
                continue
            plan.append((r["id"], recoverable(symbol)))

        # A row whose artifact a later run overwrote: recover the gene from the
        # cost, which is unique enough among the handful this can affect.
        for r in orphans:
            cands = [
                f.stem
                for f in RUNS_DIR.glob("*.json")
                if abs((_json(f).get("cost_usd") or -1) - (r["cost_usd"] or 0)) < 1e-9
            ]
            if len(cands) == 1:
                plan.append((r["id"], recoverable(cands[0])))
                log.info("  orphan row %s matched on cost -> %s", r["id"], cands[0])
            else:
                log.warning(
                    "  orphan row %s unmatched (%d candidates)", r["id"], len(cands)
                )

        log.info("will repair %d/%d rows", len(plan), len(rows))
        filled = sum(1 for _, v in plan if v["n_papers"] is not None)
        log.info("  of which %d also recover n_papers", filled)
        for rid, v in plan[:5]:
            log.info(
                "    id=%-5s %-12s acc=%-8s n_papers=%-5s n_sites=%s",
                rid,
                v["gene_symbol"],
                v["uniprot_acc"],
                v["n_papers"],
                v["n_sites"],
            )
        if not args.execute:
            log.info("dry run — nothing written (pass --execute)")
            return 0

        sql = (
            "UPDATE tag_site_run SET gene_symbol = ?, uniprot_acc = ?, "
            "n_papers = ?, n_sites = ?, backfill_note = ? WHERE id = ?;"
        )

        def write(item: tuple[int, dict]) -> bool:
            rid, v = item
            try:
                d1.query(
                    sql,
                    [
                        v["gene_symbol"],
                        v["uniprot_acc"],
                        v["n_papers"],
                        v["n_sites"],
                        NOTE,
                        rid,
                    ],
                )
                return True
            except Exception as exc:  # noqa: BLE001
                log.warning("  row %s failed: %s", rid, exc)
                return False

        ok = 0
        with ThreadPoolExecutor(max_workers=args.parallel) as pool:
            for fut in as_completed([pool.submit(write, i) for i in plan]):
                ok += bool(fut.result())
        log.info("repaired %d/%d rows", ok, len(plan))

    # Repair the local artifacts too: they are the primary copy, and the next
    # person to read one should not have to know this bug existed.
    repaired = 0
    for symbol in stripped:
        path = RUNS_DIR / f"{symbol}.json"
        d = _json(path)
        if d.get("gene_symbol"):
            continue
        v = recoverable(symbol)
        d.update({k: x for k, x in v.items() if k != "uniprot_acc"})
        d.setdefault("ledger", [])
        d.setdefault("rejected", [])
        d.setdefault("other_positions", [])
        d["backfill_note"] = NOTE
        if args.execute:
            path.write_text(json.dumps(d, indent=2, default=str))
        repaired += 1
    log.info(
        "%s %d local artifacts",
        "repaired" if args.execute else "would repair",
        repaired,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
