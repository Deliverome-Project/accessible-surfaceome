"""ACTUALLY run the deterministic tag-site pipeline on the positive-control genes,
using ONLY in-repo sources — no deliverome-internal dependency:

  * sequence + per-residue topology: the committed DeepTMHMM prediction
    (``data/external/deeptmhmm_surfaceome_predictions/human_canonical_non_hla/
    predicted_topologies.3line``), the same topology source the main pipeline uses;
  * AlphaFold model: fetched from AFDB via ``tools.afdb_plddt.read_afdb_model_links``
    (the repo's own AF approach), cached under ``data/cache/afdb_pdb/`` (gitignored);
  * UniProt feature vetoes: fetched live.

Reports true recovery + a per-gate diagnosis at each control residue. No fabrication —
every number comes from a run. Reproduce:  uv run python scripts/benchmark_tag_sites_deterministic.py
"""
import json
import os
import tempfile
import urllib.request
from pathlib import Path

from accessible_surfaceome.tag_sites import features as F
from accessible_surfaceome.tag_sites.run import (
    compute_signals,
    derive_deterministic_sites,
    run_gene,
)
from accessible_surfaceome.tag_sites.surface_loop import (
    FEATURE_DIST_MIN,
    LOOP_SS,
    PLDDT_MIN,
    RSA_MIN,
    _window_max,
)
from accessible_surfaceome.tools.afdb_plddt import read_afdb_model_links

ROOT = Path(__file__).resolve().parents[1]
THREELINE = (
    ROOT
    / "data/external/deeptmhmm_surfaceome_predictions"
    / "human_canonical_non_hla/predicted_topologies.3line"
)
PDB_CACHE = Path(os.environ.get("TAG_SITE_AF_CACHE", ROOT / "data/cache/afdb_pdb"))

# (gene, canonical acc, control after-residue, expected letter) from positive_controls.tsv
CONTROLS = [
    ("ITGB1", "P05556", 101, "G"),
    ("ITGB5", "P18084", 102, "A"),
    ("AXL", "P30530", 184, "P"),
    ("TMEM123", "Q8N131", 33, "A"),
    ("TFRC", "P02786", 290, "I"),
]


def load_3line() -> dict[str, tuple[str, str]]:
    """Parse DeepTMHMM 3-line output -> {uniprot_acc: (sequence, topology_string)}.

    Records are ``>sp|ACC|NAME | LABEL`` / sequence / per-residue topology (I/O/M/S)."""
    recs: dict[str, tuple[str, str]] = {}
    lines = THREELINE.read_text().splitlines()
    i = 0
    while i < len(lines) - 2:
        if lines[i].startswith(">"):
            acc = lines[i].split("|")[1]
            recs[acc] = (lines[i + 1].strip(), lines[i + 2].strip())
            i += 3
        else:
            i += 1
    return recs


def af_pdb(acc: str) -> str:
    """Fetch the AFDB PDB model for ``acc`` (repo's AF approach), cached locally."""
    PDB_CACHE.mkdir(parents=True, exist_ok=True)
    path = PDB_CACHE / f"{acc}.pdb"
    if not path.exists():
        url = read_afdb_model_links(acc).get("model_pdb_url")
        if not url:
            raise RuntimeError(f"AFDB returned no pdb URL for {acc}")
        urllib.request.urlretrieve(url, path)
    return str(path)


def main() -> None:
    recs = load_3line()
    print(
        f"gates: pLDDT>={PLDDT_MIN}  RSA(window)>={RSA_MIN}  "
        f"feature_dist>={FEATURE_DIST_MIN}  loop_ss={sorted(LOOP_SS)}\n"
    )
    for gene, acc, ctrl, exp in CONTROLS:
        if acc not in recs:
            print(f"== {gene} {acc}: not in committed 3line topology\n")
            continue
        seq, topo_s = recs[acc]
        topo = {i + 1: c for i, c in enumerate(topo_s)}
        pdb = af_pdb(acc)
        try:
            hazard = F.hazard_residues(F.fetch_uniprot_features(acc))
            hz = f"{len(hazard)} hazard residues"
        except Exception as ex:  # noqa: BLE001 — diagnostic script
            hazard = set()
            hz = f"UniProt features unavailable ({type(ex).__name__}) -> empty"

        sig = compute_signals(
            pdb, topology=topo, sequence=seq, ortholog_seqs=[], hazard_res=hazard
        )
        plddt, rsa, ss, fdist = sig["plddt"], sig["rsa"], sig["ss"], sig["feature_dist"]
        seq_ok = (1 <= ctrl <= len(seq)) and seq[ctrl - 1] == exp

        # candidate pool (pre-NMS) vs surfaced representatives (post-NMS via run_gene)
        cand = sorted(s["insert_after_residue"] for s in derive_deterministic_sites(gene, acc, signals=sig))
        with tempfile.TemporaryDirectory() as out:
            run_gene(
                gene, acc, sequence=seq, topology=topo, ortholog_seqs=[],
                pdb_path=pdb, hazard_res=hazard, out_dir=out,
            )
            data = json.load(open(os.path.join(out, f"{gene}.json")))
        sites = data["sites"] if isinstance(data, dict) and "sites" in data else data
        det = [s for s in sites if s["provenance"] == "deterministic_computed"]
        residues = sorted(s["insert_after_residue"] for s in det)
        exact = ctrl in residues
        near = [r for r in residues if abs(r - ctrl) <= 3]
        hit = next((s for s in det if abs(s["insert_after_residue"] - ctrl) <= 3), None)
        cand_near = [r for r in cand if abs(r - ctrl) <= 3]

        got = seq[ctrl - 1] if 1 <= ctrl <= len(seq) else "?"
        print(f"== {gene} {acc}  control: after {exp}{ctrl}  (seq[{ctrl}]={got}, seq_ok={seq_ok})  [{hz}]")
        wmax = _window_max(rsa, ctrl)
        print(
            f"   signals @ {ctrl}: pLDDT={plddt.get(ctrl, 0):.1f}  RSA_own={rsa.get(ctrl, 0):.2f}  "
            f"RSA_window={wmax:.2f}  ss={ss.get(ctrl, '?')}  topo={topo.get(ctrl, '?')}  "
            f"feat_dist={fdist.get(ctrl, 0):.1f}A"
        )
        gates = {
            "extracellular(O)": topo.get(ctrl) == "O",
            f"pLDDT>={PLDDT_MIN}": plddt.get(ctrl, 0) >= PLDDT_MIN,
            "loop_ss": ss.get(ctrl, "?") in LOOP_SS,
            f"RSAwin>={RSA_MIN}": wmax >= RSA_MIN,
            f"featdist>={FEATURE_DIST_MIN}": fdist.get(ctrl, 0) >= FEATURE_DIST_MIN,
        }
        failed = [k for k, v in gates.items() if not v]
        print(f"   surface_loop gate @ {ctrl}: {'ALL PASS' if not failed else 'FAILS ' + ', '.join(failed)}")
        verdict = "EXACT HIT" if exact else (f"NEAR HIT ({near})" if near else "MISS")
        by = f" via {hit['det_path']} (tag_fit={hit.get('tag_type')})" if hit else ""
        cand_note = (
            f"candidate={'YES ' + str(cand_near) if cand_near else 'no'} (pre-NMS)"
        )
        print(f"   -> representative: {verdict}{by}  |  {cand_note}")
        print(f"   nominated deterministic residues ({len(residues)}): {residues}\n")


if __name__ == "__main__":
    main()
