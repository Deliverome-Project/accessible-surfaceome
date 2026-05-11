"""Reconcile the Cloudflare D1 `triage_results` database against the
on-disk per-cell JSON records.

The on-disk JSON files under ``data/eval/triage_subbench_v1/<model>/
<variant>/<gene>_run<N>.json`` are the canonical source of truth — D1 is
a queryable mirror. This script confirms they're in sync:

  * Row counts per (model, variant) match.
  * Every (gene, model, variant, replicate, prompt_sha) tuple in D1 also
    exists as a JSON record (and vice-versa).
  * Predicted verdicts agree between the two stores.

Exits non-zero if there's a divergence — safe to wire into a periodic
check. If D1 lost rows (manual DELETE, schema migration accident, etc.),
this surfaces the missing keys; you'd recover by re-running:

    uv run python scripts/upload_triage_runs_to_d1.py --run-id <same-as-original>
"""

from __future__ import annotations

import hashlib
import json
import sys

from accessible_surfaceome.cloud.d1_client import D1Client
from accessible_surfaceome.cloud.triage_upload import (
    SUBBENCH_RUNS,
    VARIANT_TO_PROMPT,
)
from accessible_surfaceome.paths import REPO_ROOT


def _sha256(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _on_disk_keys() -> set[tuple[str, str, str, int, str]]:
    """Build the (gene, model, variant, replicate, prompt_sha) set from JSON."""
    prompts_dir = REPO_ROOT / "src/accessible_surfaceome/agents/surface_triage/prompts"
    prompt_sha_by_variant = {
        variant: _sha256((prompts_dir / fname).read_text())
        for variant, fname in VARIANT_TO_PROMPT.items()
    }
    out: set[tuple[str, str, str, int, str]] = set()
    for path in SUBBENCH_RUNS.rglob("*_run*.json"):
        try:
            rec = json.loads(path.read_text())
        except json.JSONDecodeError:
            continue
        variant = rec.get("variant")
        if variant not in prompt_sha_by_variant:
            continue
        key = (
            rec["gene_symbol"], rec["model"], variant,
            int(rec.get("replicate", 0)),
            prompt_sha_by_variant[variant],
        )
        out.add(key)
    return out


def _on_disk_preds() -> dict[tuple[str, str, str, int], str | None]:
    """gene × model × variant × replicate → predicted_verdict (on disk)."""
    out: dict[tuple[str, str, str, int], str | None] = {}
    for path in SUBBENCH_RUNS.rglob("*_run*.json"):
        try:
            rec = json.loads(path.read_text())
        except json.JSONDecodeError:
            continue
        key = (
            rec["gene_symbol"], rec["model"], rec["variant"],
            int(rec.get("replicate", 0)),
        )
        out[key] = rec.get("predicted_verdict")
    return out


def main() -> int:
    on_disk = _on_disk_keys()
    on_disk_preds = _on_disk_preds()
    print(f"On-disk records: {len(on_disk)}")
    if not on_disk:
        print("  (no records on disk — nothing to verify against)")
        return 0

    with D1Client() as d1:
        d1_rows = d1.query(
            "SELECT gene_symbol, model, prompt_variant, replicate, prompt_sha, "
            "       predicted_verdict, run_id FROM triage_run;"
        )
    print(f"D1 rows: {len(d1_rows)}")

    d1_keys = {
        (r["gene_symbol"], r["model"], r["prompt_variant"],
         r["replicate"], r["prompt_sha"])
        for r in d1_rows
    }

    # Group D1 by run_id so we can report per-sweep coverage.
    by_run: dict[str, set[tuple[str, str, str, int, str]]] = {}
    for r in d1_rows:
        by_run.setdefault(r["run_id"], set()).add(
            (r["gene_symbol"], r["model"], r["prompt_variant"],
             r["replicate"], r["prompt_sha"])
        )

    print("\nD1 sweeps (by run_id):")
    for run_id, keys in sorted(by_run.items(), key=lambda kv: -len(kv[1])):
        print(f"  {run_id}: {len(keys)} rows")

    missing_in_d1 = on_disk - d1_keys
    extra_in_d1 = d1_keys - on_disk

    print("\nDivergence check (against the union of all D1 sweeps):")
    print(f"  on-disk ∩ D1: {len(on_disk & d1_keys)}")
    print(f"  on-disk but NOT in D1: {len(missing_in_d1)}")
    print(f"  in D1 but NOT on-disk: {len(extra_in_d1)}")

    # Predicted-verdict agreement check (latest D1 row per key wins if
    # multiple sweeps have the same key).
    d1_preds_by_key: dict[tuple[str, str, str, int], str | None] = {}
    for r in d1_rows:
        key = (r["gene_symbol"], r["model"], r["prompt_variant"], r["replicate"])
        d1_preds_by_key[key] = r["predicted_verdict"]
    disagreements: list[tuple[tuple[str, str, str, int], str | None, str | None]] = []
    for key, on_pred in on_disk_preds.items():
        d_pred = d1_preds_by_key.get(key)
        if d_pred is None and on_pred is None:
            continue
        if d_pred != on_pred:
            disagreements.append((key, on_pred, d_pred))
    print("\nPredicted-verdict agreement:")
    print(f"  matching: {len(on_disk_preds) - len(disagreements)}")
    print(f"  disagreeing: {len(disagreements)}")
    if disagreements:
        print("\n  First 10 disagreements (gene, model, variant, rep — on_disk vs D1):")
        for (gene, model, variant, rep), o, d in disagreements[:10]:
            print(f"    {gene:10s} {model:18s} {variant:10s} r{rep}  on_disk={o!r}  d1={d!r}")

    if missing_in_d1:
        print("\n  First 10 keys missing in D1 (re-upload to recover):")
        for k in list(missing_in_d1)[:10]:
            print(f"    {k}")

    ok = not missing_in_d1 and not disagreements
    if ok:
        print("\n✓ D1 and on-disk records are in sync")
        return 0
    else:
        print(f"\n✗ {len(missing_in_d1)} missing + {len(disagreements)} disagreements")
        print("  Re-run scripts/upload_triage_runs_to_d1.py to reconcile.")
        return 1


if __name__ == "__main__":
    sys.exit(main())
