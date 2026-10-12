"""Export the ProDomino comparison set with an 80/20 split BY GENE.

Split by gene, never by site: two sites on one protein share its sequence,
structure and conservation, so splitting by site would put near-identical
examples on both sides and flatter every scorer equally. The seed is fixed so
the split is the same each time anyone reproduces it.

Only the TRAIN half is written by default. The test half stays unscored until
there is something worth spending it on — looking at it early is how a held-out
set quietly becomes a validation set.

    uv run python scripts/probes/export_prodomino_set.py            # train only
    uv run python scripts/probes/export_prodomino_set.py --include-test
"""

from __future__ import annotations

import argparse
import json
import random
import sys
from pathlib import Path

from accessible_surfaceome.env import load_env

load_env()

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from accessible_surfaceome.cloud.d1_client import D1Client  # noqa: E402

SEED = 20261011
ROOT = Path(__file__).resolve().parents[2]


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--out", default=str(ROOT / "data/analysis/prodomino"))
    ap.add_argument("--include-test", action="store_true")
    ap.add_argument("--limit", type=int, default=0)
    args = ap.parse_args()

    import regenerate_tag_site_lit as G

    with D1Client.public() as d1:
        genes = [
            r["gene_symbol"]
            for r in d1.query(
                "SELECT DISTINCT gene_symbol FROM tag_site_public "
                "WHERE provenance='literature_retrieved' AND insert_after_residue IS NOT NULL "
                "ORDER BY gene_symbol;",
                [],
            )
        ]
    rng = random.Random(SEED)
    rng.shuffle(genes)
    cut = int(len(genes) * 0.8)
    split = {"train": genes[:cut], "test": genes[cut:]}
    print(
        f"{len(genes)} genes with a published junction -> train {len(split['train'])}, "
        f"test {len(split['test'])} (seed {SEED}, split BY GENE)"
    )

    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    (out / "split.json").write_text(json.dumps(split, indent=2))

    wanted = ["train"] + (["test"] if args.include_test else [])
    for half in wanted:
        recs, missing = [], 0
        names = split[half][: args.limit] if args.limit else split[half]
        for i, g in enumerate(names, 1):
            try:
                rec = G.fetch_record(g)
                acc, seq, _topo = G.extract_from_record(rec)
            except Exception:  # noqa: BLE001
                missing += 1
                continue
            if not seq:
                missing += 1
                continue
            recs.append({"gene": g, "acc": acc, "sequence": seq})
            if i % 50 == 0:
                print(f"  {half}: {i}/{len(names)}")
        path = out / f"sequences_{half}.json"
        path.write_text(json.dumps(recs, indent=2))
        print(
            f"  wrote {len(recs)} sequences -> {path}  ({missing} without a sequence)"
        )
    if not args.include_test:
        print(
            "test sequences deliberately NOT exported — the split file records which genes they are"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
