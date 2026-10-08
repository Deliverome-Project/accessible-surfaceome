"""Score committed tag-site records against data/tag_sites/positive_controls.tsv.

Recall against curated truth, which diffing a run against the pipeline's own
prior output cannot measure. Free — reads JSON, makes no model calls.

    uv run python scripts/score_tag_sites_vs_controls.py
    uv run python scripts/score_tag_sites_vs_controls.py --provenance any --tolerance 3
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from accessible_surfaceome.agents.tag_site.benchmark import load_controls, score_predictions

ROOT = Path(__file__).resolve().parents[1]
TAG_SITES = ROOT / "viewer/public/tag-sites"
CONTROLS = ROOT / "data/tag_sites/positive_controls.tsv"


def predictions(provenance: str) -> dict[str, list[int]]:
    """{gene_symbol: [junction, ...]} from the committed records."""
    out: dict[str, list[int]] = {}
    for p in sorted(TAG_SITES.glob("*.json")):
        rec = json.loads(p.read_text())
        res = [
            s["insert_after_residue"]
            for s in rec.get("sites", [])
            if s.get("insert_after_residue") is not None
            and (provenance == "any" or s.get("provenance") == provenance)
        ]
        if res:
            out[rec.get("gene_symbol") or p.stem] = sorted(set(res))
    return out


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--provenance", default="literature_retrieved",
                    help="'literature_retrieved' (default), 'deterministic_computed', or 'any'")
    ap.add_argument("--tolerance", type=int, default=3,
                    help="residues within which a prediction counts as 'near' (default 3)")
    args = ap.parse_args()

    controls = load_controls(CONTROLS)
    preds = predictions(args.provenance)
    rep = score_predictions(preds, controls, tolerance=args.tolerance)

    by_id = {c.id: c for c in controls}
    print(f"provenance={args.provenance}  tolerance=±{args.tolerance}\n")
    print(f"{'id':<5} {'gene':<9} {'want':>5}  {'outcome':<7} predicted")
    for cid, outcome in sorted(rep.outcomes.items()):
        c = by_id[cid]
        got = preds.get(c.gene_symbol) or []
        mark = {"exact": "HIT ", "near": "near", "miss": "MISS"}[outcome]
        print(f"{cid:<5} {c.gene_symbol:<9} {c.junction:>5}  {mark:<7} {got if got else '-'}")
    print(f"\n  exact {rep.n_exact}/{rep.n_total}"
          f"   near {rep.n_near}/{rep.n_total}"
          f"   miss {rep.n_miss}/{rep.n_total}")


if __name__ == "__main__":
    main()
