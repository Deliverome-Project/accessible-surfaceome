"""Run the deterministic pipeline on EVERY control in positive_controls.tsv and
bucket the outcome by type. Internal controls only get a pipeline run (the
deterministic pipeline designs internal loop + disordered sites, not terminals).
Repo-native sources: committed DeepTMHMM 3line + AFDB model + UniProt features.
"""
import csv
import os
import sys
import tempfile
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(Path(__file__).resolve().parent))
from benchmark_tag_sites_deterministic import af_pdb, load_3line  # noqa: E402

from accessible_surfaceome.tag_sites import features as F  # noqa: E402
from accessible_surfaceome.tag_sites.run import (  # noqa: E402
    compute_signals,
    derive_deterministic_sites,
    run_gene,
)

TSV = ROOT / "data/tag_sites/positive_controls.tsv"


def load_controls():
    rows = list(csv.DictReader(TSV.open(), delimiter="\t"))
    # dedupe internal controls by (gene, residue); keep terminals separately
    seen = set()
    out = []
    for r in rows:
        key = (r["gene_symbol"], r["site_kind"], r["junction_after_residue"])
        if key in seen:
            continue
        seen.add(key)
        out.append(r)
    return out


def main():
    recs = load_3line()
    controls = load_controls()
    results = []
    for r in controls:
        gene, acc, kind = r["gene_symbol"], r["accession"], r["site_kind"]
        try:
            ctrl = int(r["junction_after_residue"])
        except ValueError:
            ctrl = None
        if kind == "terminal":
            results.append((r["id"], gene, acc, ctrl, "terminal_out_of_scope", ""))
            continue
        if acc not in recs:
            results.append((r["id"], gene, acc, ctrl, "not_in_surfaceome_3line", ""))
            continue
        seq, topo_s = recs[acc]
        topo = {i + 1: c for i, c in enumerate(topo_s)}
        try:
            pdb = af_pdb(acc)
        except Exception as ex:  # noqa: BLE001
            results.append((r["id"], gene, acc, ctrl, "no_af_model", type(ex).__name__))
            continue
        try:
            hazard = F.hazard_residues(F.fetch_uniprot_features(acc))
        except Exception:  # noqa: BLE001
            hazard = set()
        sig = compute_signals(pdb, topology=topo, sequence=seq, ortholog_seqs=[], hazard_res=hazard)
        cand = sorted(s["insert_after_residue"] for s in derive_deterministic_sites(gene, acc, signals=sig))
        with tempfile.TemporaryDirectory() as out:
            run_gene(gene, acc, sequence=seq, topology=topo, ortholog_seqs=[],
                     pdb_path=pdb, hazard_res=hazard, out_dir=out)
            import json
            data = json.load(open(os.path.join(out, f"{gene}.json")))
        det = [s for s in data["sites"] if s["provenance"] == "deterministic_computed"]
        reps = sorted(s["insert_after_residue"] for s in det)
        rep_hit = next((s for s in det if ctrl is not None and abs(s["insert_after_residue"] - ctrl) <= 3), None)
        cand_hit = any(ctrl is not None and abs(c - ctrl) <= 3 for c in cand)
        plddt = sig["plddt"].get(ctrl, 0.0) if ctrl else 0.0
        if rep_hit:
            exact = rep_hit["insert_after_residue"] == ctrl
            cat = f"{rep_hit['det_path']}_{'exact' if exact else 'near'}"
            detail = f"rep {rep_hit['insert_after_residue']} pLDDT{plddt:.0f}"
        elif cand_hit:
            cat = "candidate_only_nms_suppressed"
            detail = f"cand near {ctrl}, pLDDT{plddt:.0f}"
        else:
            cat = "miss"
            detail = f"pLDDT{plddt:.0f} topo={topo.get(ctrl,'?')} nearest={min(reps, key=lambda x: abs(x-ctrl)) if reps and ctrl else '-'}"
        results.append((r["id"], gene, acc, ctrl, cat, detail))

    print(f"{'id':5} {'gene':9} {'ctrl':>5}  {'category':32} detail")
    print("-" * 92)
    for rid, gene, acc, ctrl, cat, detail in results:
        print(f"{rid:5} {gene:9} {str(ctrl):>5}  {cat:32} {detail}")
    print("\n=== BREAKDOWN BY DETERMINISTIC RESULT TYPE ===")
    for cat, n in Counter(c for *_, c, _ in results).most_common():
        print(f"  {n:2}  {cat}")
    runnable = [x for x in results if x[4] not in ("terminal_out_of_scope", "not_in_surfaceome_3line", "no_af_model")]
    rep_hits = [x for x in runnable if x[4].endswith(("_exact", "_near"))]
    cand_hits = [x for x in runnable if x[4].endswith(("_exact", "_near")) or x[4] == "candidate_only_nms_suppressed"]
    print(f"\nRunnable internal controls: {len(runnable)}")
    print(f"  representative recall (emitted, ±3): {len(rep_hits)}/{len(runnable)}")
    print(f"  candidate recall (gates, ±3):        {len(cand_hits)}/{len(runnable)}")


if __name__ == "__main__":
    main()
