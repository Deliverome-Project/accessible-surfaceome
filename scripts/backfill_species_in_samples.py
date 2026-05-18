#!/usr/bin/env python3
"""Backfill species on existing data/eval/surfaceome_v2_samples/*.json.

Walks each ``surfaceome_v2_<GENE>.json`` at the JSON-dict level (NOT
via SurfaceomeRecord re-validation, because the sample files carry
orchestrator-only fields like ``timing`` / ``total_elapsed_s`` that
strict ``extra='forbid'`` would reject on re-load — those fields aren't
part of the public schema, but they're useful in the committed samples
and we don't want to drop them).

For each row in ``biological_context.tissues`` /
``biological_context.cell_types`` /
``biological_context.accessibility_modulation`` /
``surface_evidence.methods[].expression_observations`` that has no
``species`` set OR has ``species="unspecified"``, scan the row's
free-text fields for a known cell-line token via the gazetteer and
fill the field deterministically. Also bumps top-level
``schema_version`` to ``"1.1.0"``.

Idempotent. Re-renders the HTML viewer after each backfill.

Prints a per-file summary table.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

from accessible_surfaceome.agents.surfaceome_v2.render_html import render_html
from accessible_surfaceome.tools._shared.cell_line_species import (
    infer_species_from_text,
)


SAMPLES_DIR = Path("data/eval/surfaceome_v2_samples")


def _fill_row(row: dict[str, Any], haystack: str) -> bool:
    """Set row['species'] from the haystack if currently absent/unspecified.

    Returns True if the post-pass changed anything.
    """
    current = row.get("species") or "unspecified"
    if current != "unspecified":
        return False
    inferred = infer_species_from_text(haystack)
    if inferred is None:
        # Still populate the missing-field default so the file is
        # schema_version=1.1.0-shaped.
        if "species" not in row:
            row["species"] = "unspecified"
            row["species_inferred"] = False
        return False
    row["species"] = inferred
    row["species_inferred"] = True
    return True


def _tissue_haystack(row: dict[str, Any]) -> str:
    parts: list[str] = [row.get("tissue", "")]
    parts += row.get("cell_types") or []
    parts += row.get("cell_states") or []
    return " ".join(p for p in parts if p)


def _cell_type_haystack(row: dict[str, Any]) -> str:
    parts: list[str] = [row.get("cell_type", "")]
    parts += row.get("present_in_tissues") or []
    return " ".join(p for p in parts if p)


def _mod_haystack(row: dict[str, Any]) -> str:
    return " ".join(
        p for p in [
            row.get("baseline_context", ""),
            row.get("modulating_state", ""),
            row.get("change", ""),
        ] if p
    )


def _obs_haystack(row: dict[str, Any]) -> str:
    return row.get("context", "")


def _aggregate_cited_species(
    cited_ids: list[str], evidence_by_id: dict[str, dict[str, Any]]
) -> str | None:
    """Pass-2 helper: aggregate ``species`` across cited evidence rows.

    Returns the unique non-unspecified species if all cited rows agree,
    otherwise ``None``. Same single-value-set policy as the in-orchestrator
    post-pass.
    """
    seen: set[str] = set()
    for eid in cited_ids:
        e = evidence_by_id.get(eid)
        if not e:
            continue
        sp = (e.get("assay_context") or {}).get("species") or "unspecified"
        if sp != "unspecified":
            seen.add(sp)
    if len(seen) == 1:
        return next(iter(seen))
    return None


def _fill_row_from_cites(
    row: dict[str, Any], evidence_by_id: dict[str, dict[str, Any]]
) -> bool:
    """Pass-2 fill on rows still unspecified after the gazetteer pass."""
    current = row.get("species") or "unspecified"
    if current != "unspecified":
        return False
    inferred = _aggregate_cited_species(
        row.get("cited_evidence_ids") or [], evidence_by_id
    )
    if inferred is None:
        return False
    row["species"] = inferred
    row["species_inferred"] = True
    return True


def process_one(json_path: Path) -> tuple[str, dict[str, int]]:
    payload = json.loads(json_path.read_text())
    payload["schema_version"] = "1.1.0"

    stats = {
        "tissues_filled": 0,
        "cell_types_filled": 0,
        "modulation_filled": 0,
        "expression_obs_filled": 0,
        "filled_by_gazetteer": 0,
        "filled_by_cite_aggregation": 0,
    }
    bc = payload.get("biological_context") or {}

    # ---- Pass 1: cell-line gazetteer ----
    for t in bc.get("tissues") or []:
        if _fill_row(t, _tissue_haystack(t)):
            stats["tissues_filled"] += 1
            stats["filled_by_gazetteer"] += 1
    for c in bc.get("cell_types") or []:
        if _fill_row(c, _cell_type_haystack(c)):
            stats["cell_types_filled"] += 1
            stats["filled_by_gazetteer"] += 1
    for m in bc.get("accessibility_modulation") or []:
        if _fill_row(m, _mod_haystack(m)):
            stats["modulation_filled"] += 1
            stats["filled_by_gazetteer"] += 1
    for method in (payload.get("surface_evidence") or {}).get("methods") or []:
        for obs in method.get("expression_observations") or []:
            if _fill_row(obs, _obs_haystack(obs)):
                stats["expression_obs_filled"] += 1
                stats["filled_by_gazetteer"] += 1

    # ---- Pass 2: cite-aggregation ----
    evidence_by_id = {
        e["evidence_id"]: e for e in (payload.get("evidence") or [])
    }
    for t in bc.get("tissues") or []:
        if _fill_row_from_cites(t, evidence_by_id):
            stats["tissues_filled"] += 1
            stats["filled_by_cite_aggregation"] += 1
    for c in bc.get("cell_types") or []:
        if _fill_row_from_cites(c, evidence_by_id):
            stats["cell_types_filled"] += 1
            stats["filled_by_cite_aggregation"] += 1
    for m in bc.get("accessibility_modulation") or []:
        if _fill_row_from_cites(m, evidence_by_id):
            stats["modulation_filled"] += 1
            stats["filled_by_cite_aggregation"] += 1
    for method in (payload.get("surface_evidence") or {}).get("methods") or []:
        for obs in method.get("expression_observations") or []:
            if _fill_row_from_cites(obs, evidence_by_id):
                stats["expression_obs_filled"] += 1
                stats["filled_by_cite_aggregation"] += 1

    stats["total_filled"] = (
        stats["filled_by_gazetteer"] + stats["filled_by_cite_aggregation"]
    )

    json_path.write_text(json.dumps(payload, indent=2) + "\n")
    html_path = json_path.with_suffix(".html")
    html_path.write_text(render_html(payload))
    gene = (payload.get("gene") or {}).get("hgnc_symbol", json_path.stem)
    return gene, stats


def main() -> int:
    samples = sorted(SAMPLES_DIR.glob("surfaceome_v2_*.json"))
    if not samples:
        print(f"no surfaceome_v2_*.json files found under {SAMPLES_DIR}")
        return 1
    print(f"backfilling {len(samples)} sample file(s)...")
    print()
    print(
        f"{'gene':<10s} {'tissues':>8s} {'cell_types':>11s} "
        f"{'modulation':>11s} {'expr_obs':>9s} {'gazet':>6s} {'cite':>5s} "
        f"{'total':>6s}"
    )
    print("-" * 72)
    grand_total = 0
    for json_path in samples:
        try:
            gene, stats = process_one(json_path)
        except Exception as exc:  # noqa: BLE001
            print(f"{json_path.name:30s} ERROR {type(exc).__name__}: {exc}")
            continue
        grand_total += stats["total_filled"]
        print(
            f"{gene:<10s} {stats['tissues_filled']:>8d} "
            f"{stats['cell_types_filled']:>11d} "
            f"{stats['modulation_filled']:>11d} "
            f"{stats['expression_obs_filled']:>9d} "
            f"{stats['filled_by_gazetteer']:>6d} "
            f"{stats['filled_by_cite_aggregation']:>5d} "
            f"{stats['total_filled']:>6d}"
        )
    print("-" * 72)
    print(
        f"{'TOTAL':<10s} {'':>8s} {'':>11s} {'':>11s} {'':>9s} {'':>6s} {'':>5s} "
        f"{grand_total:>6d}"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
