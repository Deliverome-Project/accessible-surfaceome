"""Post-process /tmp/czi_enrichment/*.json — drop noise rows + clamp pct.

The v2 build ranked top_cell_types by raw mean log1p(CP10K) WITHOUT
applying the same noise filter it used for classification, so e.g.
SLC34A2's #1 cell type is "ventricular cardiac muscle cell" with 3
expressing cells. 83.5% of genes are affected.

This script reads each JSON, drops cell types where n_expressing < 10
OR pct_expressing < 0.01, clamps pct to [0,1] (the WMG nnz cache and
cell-count cache come from slightly different snapshots, occasionally
yielding pct > 1), re-ranks, re-caps to 20 common + 10 rare, and
writes back in place. Classification (enrichment_class /
enrichment_cl_ids / fold_change) is preserved as the v2 build computed
it from the already-filtered universe.
"""
from __future__ import annotations
import json
import sys
from pathlib import Path

MIN_N_EXPRESSING = 10
MIN_PCT = 0.01
COMMON_MAX = 20
RARE_MAX = 10
COMMON_N_TOTAL_THRESHOLD = 1000


def _clamp(p: float | None) -> float:
    if p is None:
        return 0.0
    return max(0.0, min(1.0, float(p)))


def _qualifies(row: dict) -> bool:
    n = int(row.get("n_expressing") or 0)
    pct = float(row.get("pct_expressing") or 0)
    if n < MIN_N_EXPRESSING:
        return False
    if pct < MIN_PCT:
        return False
    return True


def fix_record(rec: dict) -> tuple[dict, int]:
    """Return (fixed_record, n_rows_dropped)."""
    original = list(rec.get("top_cell_types") or [])
    qualified = []
    for row in original:
        # Clamp gene-level pct and per-tissue pct
        row["pct_expressing"] = _clamp(row.get("pct_expressing"))
        tissues = row.get("tissues") or []
        for t in tissues:
            t["pct_expressing"] = _clamp(t.get("pct_expressing"))
        if _qualifies(row):
            qualified.append(row)
    dropped = len(original) - len(qualified)

    # Re-rank by mean_log1p_cp10k DESC
    qualified.sort(key=lambda r: -(r.get("mean_log1p_cp10k") or 0))

    # Re-bucket common vs rare based on n_total. is_rare may have been
    # set on the original; recompute deterministically.
    common = []
    rare = []
    for row in qualified:
        n_total = int(row.get("n_total") or 0)
        is_rare = n_total < COMMON_N_TOTAL_THRESHOLD
        row["is_rare"] = is_rare
        if is_rare:
            rare.append(row)
        else:
            common.append(row)

    rec["top_cell_types"] = common[:COMMON_MAX] + rare[:RARE_MAX]
    return rec, dropped


def main() -> int:
    root = Path("/tmp/czi_enrichment")
    files = sorted(root.glob("*.json"))
    if not files:
        print(f"no files in {root}", file=sys.stderr)
        return 2
    n = 0
    total_dropped = 0
    empty = 0
    for f in files:
        try:
            rec = json.loads(f.read_text())
        except Exception as e:
            print(f"skip {f.name}: {e}", file=sys.stderr)
            continue
        fixed, dropped = fix_record(rec)
        total_dropped += dropped
        if not fixed.get("top_cell_types"):
            empty += 1
        # Compact JSON (no indent) to keep D1 row size small.
        f.write_text(json.dumps(fixed, separators=(",", ":")))
        n += 1
        if n % 2000 == 0:
            print(f"{n}/{len(files)} fixed, total dropped rows: {total_dropped}", flush=True)
    print(f"done: {n} files fixed, total dropped rows: {total_dropped}, "
          f"genes with empty top_cell_types after filter: {empty}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
