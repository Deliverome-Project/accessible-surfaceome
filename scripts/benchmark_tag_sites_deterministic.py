"""ACTUALLY run the deterministic tag-site pipeline on the positive-control genes,
using their real cached AlphaFold models + real DeepTMHMM topology from
deliverome-internal's viewer_dataset.json. Reports true recovery + a per-gate
diagnosis at each control residue. No fabrication — every number comes from a run.
"""

import glob
import json
import os
import re
import tempfile

from accessible_surfaceome.tag_sites import features as F
from accessible_surfaceome.tag_sites.run import run_gene
from accessible_surfaceome.tag_sites.signals import (
    per_residue_plddt,
    per_residue_rsa,
    per_residue_ss,
)
from accessible_surfaceome.tag_sites.surface_loop import (
    PLDDT_MIN,
    RSA_MIN,
    FEATURE_DIST_MIN,
    LOOP_SS,
    _window_max,
)
from accessible_surfaceome.tag_sites.features import feature_distances

DATASET = "/Users/rebeccacarlson/Git/deliverome-internal/cloudflare/surfaceome_structure_site_viewer/deploy_static/viewer_dataset.json"
CACHE = "/Users/rebeccacarlson/Git/deliverome-internal/data/external/afdb_surfaceome_expressed/afdb_pdb_cache"

# (gene, canonical acc, control after-residue, expected letter) from positive_controls.tsv
CONTROLS = [
    ("ITGB1", "P05556", 101, "G"),
    ("ITGB5", "P18084", 102, "A"),
    ("AXL", "P30530", 184, "P"),
    ("TMEM123", "Q8N131", 33, "A"),
    ("TFRC", "P02786", 290, "I"),
]


def canonical_pdb(acc):
    # canonical model file is "{acc}-{hex}.pdb"; isoforms are "{acc}-{n}-{hex}.pdb"
    for f in sorted(glob.glob(f"{CACHE}/{acc}-*.pdb")):
        rest = os.path.basename(f)[len(acc) + 1 : -4]
        if re.fullmatch(r"[0-9a-f]+", rest):  # no extra '-' → canonical
            return f
    return None


def main():
    ds = {e["accession"]: e for e in json.load(open(DATASET))["entries"]}
    print(
        f"gates: pLDDT>={PLDDT_MIN}  RSA(window)>={RSA_MIN}  feature_dist>={FEATURE_DIST_MIN}  loop_ss={sorted(LOOP_SS)}\n"
    )
    for gene, acc, ctrl, exp in CONTROLS:
        e = ds.get(acc)
        pdb = canonical_pdb(acc)
        if not e or not pdb:
            print(f"== {gene} {acc}: MISSING (entry={bool(e)} pdb={bool(pdb)})\n")
            continue
        seq = e["full_sequence"]
        topo = {i + 1: c for i, c in enumerate(e["topology"])}
        try:
            hazard = F.hazard_residues(F.fetch_uniprot_features(acc))
            hz = f"{len(hazard)} hazard residues"
        except Exception as ex:
            hazard = set()
            hz = f"UniProt features unavailable ({type(ex).__name__}) -> empty"

        # real structural signals at the control residue
        plddt = per_residue_plddt(pdb)
        rsa = per_residue_rsa(pdb)
        ss = per_residue_ss(pdb)
        fdist = feature_distances(pdb, hazard)
        seq_ok = (1 <= ctrl <= len(seq)) and seq[ctrl - 1] == exp

        with tempfile.TemporaryDirectory() as out:
            run_gene(
                gene,
                acc,
                sequence=seq,
                topology=topo,
                ortholog_seqs=[],
                pdb_path=pdb,
                hazard_res=hazard,
                out_dir=out,
            )
            data = json.load(open(os.path.join(out, f"{gene}.json")))
        sites = data["sites"] if isinstance(data, dict) and "sites" in data else data
        det = [s for s in sites if s["provenance"] == "deterministic_computed"]
        residues = sorted(s["insert_after_residue"] for s in det)
        exact = ctrl in residues
        near = [r for r in residues if abs(r - ctrl) <= 3]
        hit = next((s for s in det if abs(s["insert_after_residue"] - ctrl) <= 3), None)

        print(
            f"== {gene} {acc}  control: after {exp}{ctrl}  (seq[{ctrl}]={seq[ctrl - 1] if seq_ok or 1 <= ctrl <= len(seq) else '?'}, seq_ok={seq_ok})  [{hz}]"
        )
        wmax = _window_max(rsa, ctrl)
        print(
            f"   signals @ {ctrl}: pLDDT={plddt.get(ctrl, 0):.1f}  RSA_own={rsa.get(ctrl, 0):.2f}  RSA_window={wmax:.2f}  ss={ss.get(ctrl, '?')}  topo={topo.get(ctrl, '?')}  feat_dist={fdist.get(ctrl, 0):.1f}A"
        )
        # per-gate pass/fail at the control residue (surface_loop gate)
        gates = {
            "extracellular(O)": topo.get(ctrl) == "O",
            f"pLDDT>={PLDDT_MIN}": plddt.get(ctrl, 0) >= PLDDT_MIN,
            "loop_ss": ss.get(ctrl, "?") in LOOP_SS,
            f"RSAwin>={RSA_MIN}": wmax >= RSA_MIN,
            f"featdist>={FEATURE_DIST_MIN}": fdist.get(ctrl, 0) >= FEATURE_DIST_MIN,
        }
        failed = [k for k, v in gates.items() if not v]
        print(
            f"   surface_loop gate @ {ctrl}: {'ALL PASS' if not failed else 'FAILS ' + ', '.join(failed)}"
        )
        verdict = "EXACT HIT" if exact else (f"NEAR HIT ({near})" if near else "MISS")
        by = f" via {hit['det_path']} (tag_fit={hit.get('tag_type')})" if hit else ""
        print(f"   -> {verdict}{by}")
        print(f"   nominated deterministic residues ({len(residues)}): {residues}\n")


if __name__ == "__main__":
    main()
