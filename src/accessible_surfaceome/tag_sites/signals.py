"""Per-residue signals for the deterministic tag-site gates (Plan 4 Task 3).

The gates (``disorder.py``, ``surface_loop.py``) are pure functions over a
per-residue signal dict. This module computes that dict from source, in-repo:

* ``ortholog_conservation`` — per-residue conservation + indel-tolerance from a
  BLOSUM62 alignment of orthologs to the human canonical, reusing the repo's
  ``merge._sequence_identity`` aligner. This is the in-repo, auditable
  replacement for the external KIBBY conservation predictor.

The structural signals (per-residue pLDDT from the AlphaFold model, RSA via
``freesasa``, DSSP via ``pydssp``, and UniProt-feature 3D distances via
biopython) are the network-dependent half and are added alongside as the
orchestrator (Task 6) is wired to real inputs. They are kept out of this pure,
unit-tested core so the conservation signal can be tested without a network.
"""
from __future__ import annotations

from typing import Any

from accessible_surfaceome.merge._sequence_identity import _aligner, _sanitize


def ortholog_conservation(
    human_seq: str, ortholog_seqs: list[str]
) -> dict[str, dict[int, float]]:
    """Per-residue conservation + indel-tolerance from ortholog alignments.

    For each ortholog, globally align it (BLOSUM62) to the human canonical and,
    walking the alignment by human residue position (1-indexed), record whether
    the ortholog residue is identical, substituted, or a gap. Aggregated across
    orthologs:

    * ``conservation[res]`` = fraction of orthologs with an *identical* residue
      at that human position (high = conserved; the gate ranks LOW-conservation
      sites first). With no orthologs it is ``0.0`` — neutral, never blocking.
    * ``gap_freq[res]`` = fraction of orthologs aligned to a *gap* there (high =
      the position naturally tolerates indels — the indel-tolerance signal).
    """
    n = len(human_seq)
    identical = {r: 0 for r in range(1, n + 1)}
    gap = {r: 0 for r in range(1, n + 1)}
    k = len(ortholog_seqs)
    if k == 0:
        return {
            "conservation": {r: 0.0 for r in range(1, n + 1)},
            "gap_freq": {r: 0.0 for r in range(1, n + 1)},
        }

    aligner = _aligner()
    hs = _sanitize(human_seq)
    for orth in ortholog_seqs:
        os_ = _sanitize(orth)
        alignments = aligner.align(hs, os_)
        aln = alignments[0]
        human_row = str(aln[0])   # human canonical with '-' gaps
        orth_row = str(aln[1])    # ortholog aligned, with '-' gaps
        hpos = 0
        for c_h, c_o in zip(human_row, orth_row):
            if c_h == "-":
                continue          # insertion relative to human — no human position
            hpos += 1
            if c_o == "-":
                gap[hpos] += 1
            elif c_o == c_h:
                identical[hpos] += 1
            # else: substitution — counted implicitly (neither identical nor gap)

    return {
        "conservation": {r: identical[r] / k for r in range(1, n + 1)},
        "gap_freq": {r: gap[r] / k for r in range(1, n + 1)},
    }


def merge_signals(*parts: dict[str, Any]) -> dict[str, Any]:
    """Shallow-merge partial signal dicts (e.g. conservation + structural) into
    the single dict the gates consume. Later parts win on key collisions."""
    out: dict[str, Any] = {}
    for p in parts:
        out.update(p)
    return out


# --- Structural signals from the AlphaFold model (network/fixture-backed) ------
# Tien et al. 2013 theoretical max ASA (Å²) per residue, for RSA normalization.
_MAX_ASA = {
    "ALA": 129.0, "ARG": 274.0, "ASN": 195.0, "ASP": 193.0, "CYS": 167.0,
    "GLU": 223.0, "GLN": 225.0, "GLY": 104.0, "HIS": 224.0, "ILE": 197.0,
    "LEU": 201.0, "LYS": 236.0, "MET": 224.0, "PHE": 240.0, "PRO": 159.0,
    "SER": 155.0, "THR": 172.0, "TRP": 285.0, "TYR": 263.0, "VAL": 174.0,
}


def per_residue_plddt(pdb_path: str) -> dict[int, float]:
    """Per-residue pLDDT = the CA B-factor in an AlphaFold model."""
    from Bio.PDB import PDBParser

    struct = PDBParser(QUIET=True).get_structure("m", str(pdb_path))
    out: dict[int, float] = {}
    for res in struct.get_residues():
        if "CA" in res:
            out[res.id[1]] = float(res["CA"].get_bfactor())
    return out


def per_residue_rsa(pdb_path: str) -> dict[int, float]:
    """Per-residue relative solvent accessibility (0..~1), Tien-2013 normalized."""
    import freesasa

    st = freesasa.Structure(str(pdb_path))
    areas = freesasa.calc(st).residueAreas()
    out: dict[int, float] = {}
    for chain in areas:
        for resnum, ra in areas[chain].items():
            try:
                r = int(resnum)
            except ValueError:
                continue
            mx = _MAX_ASA.get(getattr(ra, "residueType", ""), None)
            out[r] = (ra.total / mx) if mx else 0.0
    return out


def per_residue_ss(pdb_path: str) -> dict[int, str]:
    """Per-residue secondary structure as DSSP-style chars via pydssp 3-state
    (H = helix, E = strand, C = loop/coil). Loop = 'C' (in LOOP_SS)."""
    import numpy as np
    import pydssp
    from Bio.PDB import PDBParser

    struct = PDBParser(QUIET=True).get_structure("m", str(pdb_path))
    coords: list[list] = []
    resnums: list[int] = []
    for res in struct.get_residues():
        if all(a in res for a in ("N", "CA", "C", "O")):
            coords.append([res["N"].coord, res["CA"].coord, res["C"].coord, res["O"].coord])
            resnums.append(res.id[1])
    arr = np.array(coords, dtype=float)  # [L, 4, 3]
    ss = pydssp.assign(arr, out_type="c3")  # array of '-'/'H'/'E'
    return {rn: ("C" if s in ("-", "L", "C") else str(s)) for rn, s in zip(resnums, ss)}
