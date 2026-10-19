"""End-to-end validation of the deterministic surface-loop method on the real
TFRC AlphaFold model (AF-P02786-F1-model_v6), shipped gzipped as a fixture.

Proves the in-repo pipeline recovers the EndoNB-validated internal ALFA site at
TFRC I290/V291 — the ordered, surface-exposed loop that the low-pLDDT disorder
screen structurally misses.
"""
import gzip
import shutil
from pathlib import Path

from accessible_surfaceome.tag_sites.signals import (
    merge_signals,
    per_residue_plddt,
    per_residue_rsa,
    per_residue_ss,
)
from accessible_surfaceome.tag_sites.surface_loop import surface_loop_candidates

FIXTURE = Path(__file__).parent / "fixtures" / "AF-P02786.pdb.gz"


def _model(tmp_path) -> str:
    out = tmp_path / "AF-P02786.pdb"
    with gzip.open(FIXTURE, "rb") as src, open(out, "wb") as dst:
        shutil.copyfileobj(src, dst)
    return str(out)


def test_structural_signals_reproduce_tfrc_i290(tmp_path):
    p = _model(tmp_path)
    plddt = per_residue_plddt(p)
    rsa = per_residue_rsa(p)
    ss = per_residue_ss(p)
    # I290/V291: confidently folded (ordered), not disordered.
    assert plddt[290] > 90 and plddt[291] > 90
    # V291 is a solvent-exposed flank; I290's own side chain is buried.
    assert rsa[291] > 0.5 and rsa[290] < 0.2
    # loop/coil, not helix or strand.
    assert ss[290] == "C" and ss[291] == "C"


def test_surface_loop_gate_recovers_tfrc_i290(tmp_path):
    p = _model(tmp_path)
    n = 760  # TFRC canonical length
    sig = merge_signals(
        {"plddt": per_residue_plddt(p), "rsa": per_residue_rsa(p), "ss": per_residue_ss(p)},
        {
            # type-II: ectodomain 89..760 extracellular
            "topology": {r: ("O" if 89 <= r <= n else "I") for r in range(1, n + 1)},
            "feature_dist": {r: 30.0 for r in range(1, n + 1)},  # veto deferred; I290 ~35A clear
            "conservation": {r: 0.2 for r in range(1, n + 1)},
            "sequence": "X" * n,
        },
    )
    picks = surface_loop_candidates(sig, gene_symbol="TFRC", uniprot_acc="P02786")
    residues = {s["insert_after_residue"] for s in picks}
    # The gate snaps the insertion to the solvent-EXPOSED residue of the loop
    # (V291, RSA 0.88), +1 from the EndoNB "after I290" control (I290's own side
    # chain is buried, RSA 0.02) — the same exposed loop tip, within the
    # residue-exactness tolerance. The low-pLDDT disorder screen misses it entirely.
    assert 291 in residues                       # the exposed V291 junction
    assert any(289 <= r <= 291 for r in residues)  # recovers the I290/V291 loop
