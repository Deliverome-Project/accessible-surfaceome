"""Backfill ``filters.n_papers_selected`` on already-published
``SurfaceomeRecord`` snapshots.

The field landed in schema 2.14.0 as a viewer-facing filter signal —
the unique-paper count behind each gene's evidence list. For records
annotated *before* the field existed it defaults to 0, which would
make every legacy gene look "understudied" in the new filter.

This script walks ``viewer/public/data/surfaceome/*.json``,
recomputes ``n_papers_selected`` from each record's evidence rows
(``len({span.source.source_id for ev in evidence for span in spans})``),
and writes the populated value back. Pure JSON edit — no LLM calls,
no D1 round-trip. Idempotent: re-running on an already-backfilled
record is a no-op when the computed value matches the stored value.

Sister field ``n_papers_found`` is NOT backfilled by this script —
it requires re-running the discovery step (no LLM but ~30s/gene of
EuropePMC + PubTator + gene2pubmed). Run
``scripts/backfill_n_papers_found.py`` (separate, TODO) for that.

After running, push the updated snapshots to public D1:
    uv run python scripts/upload_viewer_snapshots_to_d1.py --execute
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SNAPSHOTS = ROOT / "viewer/public/data/surfaceome"


def _count_unique_papers(record: dict) -> int:
    """Mirror of ``_count_unique_papers`` in surfaceome_v1.orchestrator,
    operating on the raw JSON shape (no pydantic round-trip)."""
    ids: set[str] = set()
    for ev in record.get("evidence", []) or []:
        for span in ev.get("spans", []) or []:
            sid = (span.get("source") or {}).get("source_id")
            if sid:
                ids.add(sid)
    return len(ids)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--execute",
        action="store_true",
        help="Write the backfilled value to disk (default: dry-run).",
    )
    args = parser.parse_args()

    if not SNAPSHOTS.is_dir():
        print(f"ERROR: snapshot dir not found: {SNAPSHOTS}")
        return 1

    n_updated = 0
    n_unchanged = 0
    n_no_evidence = 0
    for path in sorted(SNAPSHOTS.glob("*.json")):
        raw = json.loads(path.read_text())
        evidence = raw.get("evidence")
        if not evidence:
            n_no_evidence += 1
            continue
        n_papers = _count_unique_papers(raw)
        filters = raw.setdefault("filters", {})
        existing_selected = filters.get("n_papers_selected")
        # n_papers_found is genuinely None on these legacy records — the
        # pre-trim discovery count was never persisted to the
        # SurfaceomeRecord (it lives in the agent's runner state and is
        # shed at publish time). Set explicitly so the JSON makes the
        # "unknown" status visible rather than relying on Pydantic's
        # default-fill on read. Honest backfill requires a
        # discover-only rerun (~30 s/gene).
        needs_found = "n_papers_found" not in filters
        needs_selected = existing_selected != n_papers
        if not needs_selected and not needs_found:
            n_unchanged += 1
            continue
        if needs_selected:
            filters["n_papers_selected"] = n_papers
        if needs_found:
            filters["n_papers_found"] = None
        n_updated += 1
        action = "→ would write" if not args.execute else "→ wrote"
        sel_str = (
            f"n_papers_selected: {('None' if existing_selected is None else existing_selected):>4} → {n_papers:>3}"
            if needs_selected else ""
        )
        found_str = "+ n_papers_found: null" if needs_found else ""
        print(f"  {action} {path.name:<30}  {sel_str}  {found_str}".rstrip())
        if args.execute:
            # Preserve key order; pad with trailing newline (matches existing snapshots).
            path.write_text(json.dumps(raw, indent=2, ensure_ascii=False) + "\n")

    suffix = "" if args.execute else "  (dry-run — pass --execute to write)"
    print()
    print(f"  records changed:   {n_updated}{suffix}")
    print(f"  records unchanged: {n_unchanged}")
    print(f"  no evidence rows:  {n_no_evidence}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
