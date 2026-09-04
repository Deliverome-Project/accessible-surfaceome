"""Emit viewer/public/data/tedman-surface.json — a small {SYMBOL: pme} overlay of
Tedman GPCR canonical HA-immunostaining surface expression, for the gene-page
"low surface" chip (Tedman only measured GPCRs, so non-GPCRs are simply absent).

    uv run python scripts/build_tedman_surface_overlay.py

Reads data/tag_sites/tedman_gpcr_controls.tsv (canonical rows). No network.
"""
from __future__ import annotations

import csv
import json

from accessible_surfaceome.paths import REPO_ROOT

TSV = REPO_ROOT / "data" / "tag_sites" / "tedman_gpcr_controls.tsv"
OUT = REPO_ROOT / "viewer" / "public" / "data" / "tedman-surface.json"


def main() -> int:
    pme: dict[str, float] = {}
    for r in csv.DictReader(TSV.open(), delimiter="\t"):
        if r["is_canonical"] != "true":
            continue
        v = r.get("surface_expression_pme", "")
        if v in ("", "None"):
            continue
        pme[r["gene_symbol"]] = round(float(v), 1)
    OUT.parent.mkdir(parents=True, exist_ok=True)
    # threshold documented alongside the data so the viewer + any consumer agree.
    payload = {"low_surface_threshold": 1000, "source": "Tedman et al. Nat Commun 2026", "pme": pme}
    OUT.write_text(json.dumps(payload, indent=0) + "\n")
    n_low = sum(1 for v in pme.values() if v <= 1000)
    print(f"wrote {OUT} — {len(pme)} GPCRs, {n_low} low (<=1000)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
