#!/usr/bin/env python
"""Backfill the deep-block ``Filters`` rollups onto existing records.

Three flat catalog facets were promoted from the deep blocks:
``tumor_associated``, ``induction_trigger``, ``has_live_cell_surface_evidence``.
New annotations get them from ``_derive_filters``; this script computes them
for records that predate the fields. They are DETERMINISTIC functions of the
deep blocks (``biological_context.tissues`` / ``.accessibility_modulation``,
``surface_evidence.methods``) — all of which are already in every record — so
no LLM re-run is needed.

The derivation here MUST mirror
``surfaceome_v1/orchestrator.py:_derive_filters``. (Pinned by
``tests/test_deep_block_rollups.py``, which checks the orchestrator path.)

Writes only the three new keys into each record's ``filters`` block; the rest
of the record is re-serialized unchanged. Dry-run by default.

    uv run python scripts/backfill_deep_block_rollups.py            # dry-run
    uv run python scripts/backfill_deep_block_rollups.py --execute  # write
"""
from __future__ import annotations

import argparse
import json
from typing import Any

import httpx

from accessible_surfaceome.cloud.surface_annotation import (
    _post,
    _public_config_from_env,
)
from accessible_surfaceome.env import load_env
from accessible_surfaceome.paths import REPO_ROOT

DISK_DIRS = [
    REPO_ROOT / "viewer" / "public" / "data" / "surfaceome",
    REPO_ROOT / "data" / "annotations",
]

# Mirror of orchestrator._derive_filters. -----------------------------------
_TRIGGER_BUCKET = {
    "oncogenic_transformation": "oncogenic",
    "immune_activation": "immune",
    "antigen_stimulation": "immune",
    "cytokine_stimulation": "immune",
    "ER_stress": "stress_hypoxia",
    "heat_shock": "stress_hypoxia",
    "oxidative_stress": "stress_hypoxia",
    "DNA_damage_response": "stress_hypoxia",
    "hypoxia": "stress_hypoxia",
    "nutrient_deprivation": "stress_hypoxia",
    "hyperthermia": "stress_hypoxia",
    "mechanical_stress": "stress_hypoxia",
    "apoptosis": "cell_death",
    "necroptosis": "cell_death",
    "infection_viral": "infection",
    "infection_bacterial": "infection",
    "other": "other",
    "unknown": "other",
}
_TRIGGER_PRIORITY = ("oncogenic", "immune", "stress_hypoxia", "cell_death", "infection", "other")
_TUMOR_CTX = {"tumor", "tumor_adjacent"}
_PRESENT_LEVELS = {"high", "moderate", "low", "mixed"}
_LIVE_CELL_FAMILIES = {"flow_cytometry", "biotinylation", "proximity_labeling"}
_ENDOG_SYSTEMS = {"endogenous", "mixed"}


def derive_rollups(rec: dict[str, Any]) -> dict[str, Any]:
    bc = rec.get("biological_context") or {}
    se = rec.get("surface_evidence") or {}
    tumor = any(
        t.get("disease_context") in _TUMOR_CTX and t.get("present") in _PRESENT_LEVELS
        for t in bc.get("tissues", [])
    )
    buckets = {
        _TRIGGER_BUCKET.get(m.get("cell_state_trigger"), "other")
        for m in bc.get("accessibility_modulation", [])
        if m.get("cell_state_trigger") is not None
    }
    trigger = next((b for b in _TRIGGER_PRIORITY if b in buckets), "none")
    live_cell = any(
        m.get("method_family") in _LIVE_CELL_FAMILIES
        and m.get("accessibility_relevance") == "direct_surface_accessibility"
        and m.get("expression_system") in _ENDOG_SYSTEMS
        for m in se.get("methods", [])
    )
    return {
        "tumor_associated": tumor,
        "induction_trigger": trigger,
        "has_live_cell_surface_evidence": live_cell,
    }


def _needs_update(rec: dict[str, Any]) -> dict[str, Any] | None:
    """Return the rollups if any differ from what's stored, else None."""
    f = rec.get("filters")
    if not isinstance(f, dict):
        return None
    new = derive_rollups(rec)
    if all(f.get(k) == v for k, v in new.items()):
        return None
    return new


def backfill_disk(*, execute: bool) -> int:
    touched = 0
    for d in DISK_DIRS:
        if not d.exists():
            print(f"  (skip, missing) {d}")
            continue
        for path in sorted(d.glob("*.json")):
            rec = json.loads(path.read_text())
            new = _needs_update(rec)
            if new is None:
                continue
            touched += 1
            print(
                f"  {'patched' if execute else 'would patch'} "
                f"{path.relative_to(REPO_ROOT)} -> {new}"
            )
            if execute:
                rec["filters"].update(new)
                path.write_text(json.dumps(rec, indent=2))
    return touched


def backfill_d1(*, execute: bool) -> int:
    cfg = _public_config_from_env()
    if cfg is None:
        print("  (skip) public D1 creds not set (CLOUDFLARE_*)")
        return 0
    touched = 0
    with httpx.Client(timeout=60) as client:
        rows = _post(
            cfg,
            "SELECT gene_symbol, schema_version, annotation_json FROM surface_annotation",
            [],
            client=client,
        )["result"][0]["results"]
        for r in rows:
            rec = json.loads(r["annotation_json"])
            new = _needs_update(rec)
            if new is None:
                continue
            touched += 1
            print(
                f"  {'patched' if execute else 'would patch'} D1 "
                f"{r['gene_symbol']}@{r['schema_version']} -> {new}"
            )
            if execute:
                rec["filters"].update(new)
                _post(
                    cfg,
                    "UPDATE surface_annotation SET annotation_json = ? "
                    "WHERE gene_symbol = ? AND schema_version = ?",
                    [json.dumps(rec, separators=(",", ":")), r["gene_symbol"], r["schema_version"]],
                    client=client,
                )
    return touched


def main() -> None:
    ap = argparse.ArgumentParser(description="Backfill deep-block Filters rollups.")
    ap.add_argument("--execute", action="store_true", help="write changes (default: dry-run)")
    ap.add_argument("--skip-disk", action="store_true")
    ap.add_argument("--skip-d1", action="store_true")
    args = ap.parse_args()
    load_env()
    mode = "EXECUTE" if args.execute else "DRY-RUN"
    print(f"=== deep-block rollup backfill [{mode}] ===")
    print("disk (viewer snapshots + data/annotations):")
    disk = 0 if args.skip_disk else backfill_disk(execute=args.execute)
    if args.skip_disk:
        print("  (skipped)")
    print("public D1 surface_annotation:")
    d1 = 0 if args.skip_d1 else backfill_d1(execute=args.execute)
    if args.skip_d1:
        print("  (skipped)")
    print(f"\n{'patched' if args.execute else 'would patch'}: {disk} disk file(s), {d1} D1 row(s)")
    if not args.execute:
        print("(dry-run — re-run with --execute to apply)")


if __name__ == "__main__":
    main()
