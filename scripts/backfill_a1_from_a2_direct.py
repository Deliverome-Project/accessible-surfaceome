"""Backfill: reclaim mis-routed direct-surface methods from A2 into A1.

Fixes the ICAM1-class bug where a non-permeabilized flow / surface-biotinylation
/ surface-MS observation was filed into the A2 (biological-context) ledger, so
the A1-only ``evidence_grade`` defaulted to ``weak``. Re-tags the qualifying A2
claims into A1 on the cached intermediates blob and replays builders+synth
(~$0.7/gene, no plan-trim-select cost). Core logic:
``accessible_surfaceome.agents.surfaceome_v2.a1_recovery``.

SAFETY: the executor targets only genes whose CURRENT published grade is
``weak`` / ``supportive_but_indirect`` — re-grading those can only improve.
Genes already graded ``direct_*`` are excluded (the strict perm rule is
stricter than the LLM grader, so re-grading a direct gene risks a downgrade).

Usage:
    # 1. (re)generate the manifest by scanning D1 intermediates ($0, no LLM)
    uv run python scripts/backfill_a1_from_a2_direct.py --scan --out data/analysis/a1_recovery/manifest.json

    # 2. dry-run: what would be processed (default; no LLM, no publish)
    uv run python scripts/backfill_a1_from_a2_direct.py --manifest data/analysis/a1_recovery/manifest.json

    # 3. one gene, compute-only (prints before/after grade + cost; NOT published)
    uv run python scripts/backfill_a1_from_a2_direct.py --gene ICAM1 --execute

    # 4. one gene, publish the corrected record to D1
    uv run python scripts/backfill_a1_from_a2_direct.py --gene ICAM1 --execute --publish

For the full 400+ gene sweep use the Modal app (modal/a1_recovery_app.py) —
this local driver is for the manifest, dry-runs, and single-gene checks.
"""
from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

from accessible_surfaceome.agents.surfaceome_v2.a1_recovery import (
    claim_is_direct_surface,
    ensure_d1_env,
    recover_one,
)
from accessible_surfaceome.cloud.d1_client import D1Client, D1Config
from accessible_surfaceome.env import load_env

# Grades whose re-grade can only improve — the safe executor target.
_RECOVERABLE_GRADES = ("weak", "supportive_but_indirect")
_METHOD_LITERAL = (
    "('flow_cytometry','immunofluorescence','surface_biotinylation',"
    "'mass_spec_surfaceome','proximity_labeling')"
)


def _catalog_genes() -> dict[str, str | None]:
    """{gene_symbol: evidence_grade} for every deep-dive gene, from the public
    catalog Worker (no creds needed). Grade is None on malformed records."""
    import httpx

    with httpx.Client(timeout=60) as c:
        rows = c.get("https://api.deliverome.org/surfaceome/v1/catalog").json()["rows"]
    return {
        r["symbol"]: (r.get("ddf") or {}).get("evidence_grade")
        for r in rows
        if r.get("deep_dive") and r.get("ddf")
    }


def scan(out_path: Path) -> dict:
    """Scan D1 intermediates for A1-recoverable genes; write the manifest."""
    ensure_d1_env()
    grades = _catalog_genes()
    genes = sorted(grades)
    with D1Client(D1Config.from_env()) as d1:
        latest = {
            r["gene_symbol"]: r["mc"]
            for r in d1.query(
                "SELECT gene_symbol, MAX(created_at) mc "
                "FROM agent_run_intermediates GROUP BY gene_symbol"
            )
        }
        a1pap: dict[str, set] = {g: set() for g in genes}
        a2pap: dict[str, set] = {g: set() for g in genes}
        a2meth: dict[str, Counter] = {g: Counter() for g in genes}

        def _scan_side(side: str, path: str) -> None:
            batch = 80
            for i in range(0, len(genes), batch):
                chunk = genes[i : i + batch]
                ph = "(" + ",".join("?" * len(chunk)) + ")"
                sql = (
                    "SELECT i.gene_symbol g, i.created_at ca, "
                    "json_extract(je.value,'$.evidence_type') et, "
                    "json_extract(je.value,'$.assay_context.permeabilized') perm, "
                    "json_extract(je.value,'$.direction') dr, "
                    "json_extract(je.value,'$.evidence_tier') tier, "
                    "json_extract(je.value,'$.source_id') src "
                    "FROM agent_run_intermediates i, "
                    f"json_each(COALESCE(json_extract(i.intermediates_json,'{path}'),'[]')) je "
                    f"WHERE i.gene_symbol IN {ph} "
                    f"AND json_extract(je.value,'$.evidence_type') IN {_METHOD_LITERAL}"
                )
                for r in d1.query(sql, chunk):
                    if r["ca"] != latest.get(r["g"]):
                        continue
                    claim = {
                        "evidence_type": r["et"],
                        "direction": r["dr"],
                        "evidence_tier": r["tier"],
                        "assay_context": {
                            "permeabilized": {1: True, 0: False}.get(r["perm"], r["perm"])
                        },
                    }
                    if claim_is_direct_surface(claim):
                        (a1pap if side == "a1" else a2pap)[r["g"]].add(r["src"])
                        if side == "a2":
                            a2meth[r["g"]][r["et"]] += 1

        _scan_side("a1", "$.plan_trim_select.a1.claims")
        _scan_side("a2", "$.plan_trim_select.a2.claims")

    # Class 1 — empty A1-direct ledger + >=1 A2 direct-surface method. Emitted
    # for ALL grades (transparency); only weak/supportive are a safe target.
    class1 = [
        {
            "gene": g,
            "cur_grade": grades[g],
            "n_a2_direct_papers": len(a2pap[g]),
            "multi": len(a2pap[g]) >= 2,
            "methods": dict(a2meth[g]),
        }
        for g in genes
        if len(a1pap[g]) == 0 and len(a2pap[g]) >= 1
    ]
    class1.sort(key=lambda x: (-x["n_a2_direct_papers"], x["gene"]))
    # Class 2 — direct_single genes whose A2 carries a direct-surface paper NOT
    # already in A1: re-tagging it can lift the grade single -> multi.
    class2 = [
        {
            "gene": g,
            "cur_grade": grades[g],
            "a1_papers": len(a1pap[g]),
            "a2_new_papers": len(a2pap[g] - a1pap[g]),
        }
        for g in genes
        if grades[g] == "direct_single_method"
        and len(a1pap[g]) >= 1
        and (a2pap[g] - a1pap[g])
        and len(a1pap[g] | a2pap[g]) >= 2
    ]
    class2.sort(key=lambda x: (-x["a2_new_papers"], x["gene"]))
    manifest = {
        "generated_by": "backfill_a1_from_a2_direct.py --scan",
        "class1": class1,
        "class2": class2,
    }
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(manifest, indent=1))
    return manifest


def _targets(manifest: dict) -> list[str]:
    """Safe target set: class1 restricted to weak/supportive (re-grade can only
    improve) + all class2 direct_single upgrade candidates. Already-`direct_multi`
    and `conflicting` empty-A1 genes stay in the manifest for transparency but
    are never processed."""
    c1 = [e["gene"] for e in manifest["class1"] if e["cur_grade"] in _RECOVERABLE_GRADES]
    c2 = [e["gene"] for e in manifest.get("class2", [])]
    # dedup preserving order (a gene can't be in both, but be defensive)
    seen: set[str] = set()
    return [g for g in c1 + c2 if not (g in seen or seen.add(g))]


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--scan", action="store_true", help="Regenerate the manifest from D1 ($0)")
    ap.add_argument("--out", type=Path, default=Path("data/analysis/a1_recovery/manifest.json"))
    ap.add_argument("--manifest", type=Path, help="Manifest to dry-run / execute over")
    ap.add_argument("--gene", help="Single gene shortcut")
    ap.add_argument("--execute", action="store_true", help="Run the replay (spends LLM $)")
    ap.add_argument("--publish", action="store_true", help="Persist corrected records to D1")
    ap.add_argument("--limit", type=int)
    ap.add_argument("--workers", type=int, default=4)
    args = ap.parse_args()
    load_env()

    if args.scan:
        m = scan(args.out)
        safe1 = [e for e in m["class1"] if e["cur_grade"] in _RECOVERABLE_GRADES]
        n_targets = len(safe1) + len(m["class2"])
        print(f"manifest -> {args.out}")
        print(f"  class1 empty-A1 (all grades): {len(m['class1'])}  "
              f"| weak/supportive (recover): {len(safe1)}")
        print(f"  class2 direct_single -> multi upgrade: {len(m['class2'])}")
        print(f"  by grade: {Counter(e['cur_grade'] for e in m['class1'])}")
        print(f"  total safe target set: {n_targets}  "
              f"(est. ${n_targets * 0.74:.0f} @ $0.74/gene)")
        return 0

    if args.gene:
        if not args.execute:
            print(f"[dry-run] would recover {args.gene} (add --execute to run). No LLM spent.")
            return 0
        print(json.dumps(recover_one(args.gene, publish=args.publish), indent=1))
        return 0

    if not args.manifest:
        ap.error("provide --scan, --gene, or --manifest")
    manifest = json.loads(args.manifest.read_text())
    targets = _targets(manifest)
    if args.limit:
        targets = targets[: args.limit]

    if not args.execute:
        print(f"[dry-run] {len(targets)} target genes "
              f"(weak/supportive empty-A1 + direct_single upgrades)")
        print(f"  est. cost @ $0.74/gene: ${len(targets) * 0.74:.0f}")
        print(f"  publish={args.publish}  workers={args.workers}")
        print(f"  sample: {', '.join(targets[:25])}")
        print("  add --execute to run.")
        return 0

    print(f"executing {len(targets)} genes (publish={args.publish}, workers={args.workers})...")
    results, done = [], 0
    with ThreadPoolExecutor(max_workers=args.workers) as ex:
        futs = {ex.submit(recover_one, g, publish=args.publish): g for g in targets}
        for fut in as_completed(futs):
            g = futs[fut]
            try:
                r = fut.result()
            except Exception as e:  # noqa: BLE001 — one gene must not kill the sweep
                r = {"gene": g, "status": "error", "error": str(e)[:200]}
            results.append(r)
            done += 1
            print(f"  [{done}/{len(targets)}] {g}: {r.get('status')} "
                  f"{r.get('evidence_grade','')} ${r.get('cost_usd','')}", flush=True)
    ok = [r for r in results if r.get("status") == "ok"]
    print(f"\ndone: {len(ok)}/{len(results)} ok  total ${sum(r.get('cost_usd', 0) for r in ok):.2f}")
    print(f"  grade after: {Counter(r.get('evidence_grade') for r in ok)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
