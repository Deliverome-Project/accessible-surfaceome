"""Solvent accessibility measured on the OLIGOMER, not the lone monomer.

`surface_loop` admits a junction when its RSA clears 0.40, and that RSA is
computed on the AlphaFold monomer. For a protein that functions as a dimer the
monomer is the wrong structure: a residue packed against the partner subunit
reads as freely exposed, and the gate lets a tag be placed straight into the
interface.

TFRC is the worked case. It is an obligate homodimer, the Schweke model has both
chains, and 26 of its residues lose more than 0.15 RSA on dimerisation. One of
its thirteen deterministic candidates — P688, from `surface_loop` — sits on that
interface: monomer RSA 0.60, dimer RSA 0.25. The gate saw 0.60. Both of TFRC's
published tag sites avoid the interface, which is the behaviour we want to
reproduce rather than merely hope for.

The ligand-contact veto does NOT cover this. `contact_observation` records
heterologous partners — for TFRC, serotransferrin, HFE, ferritin, viral
glycoproteins — and carries no self-interface entry for any protein. Homodimer
burial is only visible in the coordinates.

Schweke models number residues in UniProt coordinates (verified residue-by-residue
on TFRC: 604/604 identical at offset 0), so positions need no remapping.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

#: R2 bucket and prefix holding the Schweke coordinate models.
STRUCTURES_BUCKET = "surfaceome-structures"
KEY_PREFIX = "schweke"

#: An RSA loss larger than this on assembly means the residue is packed against
#: the partner subunit rather than merely near it. Chosen to be well clear of
#: freesasa's numerical noise while still catching partial burial — TFRC's P688
#: loses 0.35 and the smallest real interface residues there lose about 0.16.
INTERFACE_RSA_DROP = 0.15


def pdb_key(dimer_pdb_filename: str) -> str:
    """R2 object key for a Schweke model file name."""
    return f"{KEY_PREFIX}/{dimer_pdb_filename}"


def split_first_chain(pdb_text: str) -> tuple[str, str]:
    """``(chain_id, pdb_text_for_that_chain_alone)``.

    The lone-chain structure is what the monomer RSA is computed on, so the
    comparison isolates the effect of assembly rather than of a different model
    or a different numbering."""
    chains = [
        ln[21] for ln in pdb_text.splitlines() if ln.startswith(("ATOM", "HETATM"))
    ]
    if not chains:
        return "", pdb_text
    first = chains[0]
    kept = [
        ln
        for ln in pdb_text.splitlines()
        if not ln.startswith(("ATOM", "HETATM")) or ln[21] == first
    ]
    return first, "\n".join(kept)


def _rsa_for_chain(pdb_path: str | Path, chain: str) -> dict[int, float]:
    """Per-residue RSA for ONE chain, Tien-2013 normalised.

    `signals.per_residue_rsa` keys by residue number across every chain, so on a
    homodimer — where both chains share a numbering — the second silently
    overwrites the first. Harmless for a symmetric dimer, wrong in general, and
    wrong in a way that would not show up as an error."""
    import freesasa  # ty: ignore[unresolved-import]

    from .signals import _MAX_ASA

    areas = freesasa.calc(freesasa.Structure(str(pdb_path))).residueAreas()
    out: dict[int, float] = {}
    for ch in areas:
        if ch != chain:
            continue
        for resnum, ra in areas[ch].items():
            try:
                res = int(resnum)
            except ValueError:
                continue
            mx = _MAX_ASA.get(getattr(ra, "residueType", ""), None)
            out[res] = (ra.total / mx) if mx else 0.0
    return out


def interface_residues(
    dimer_pdb: str | Path,
    monomer_pdb: str | Path,
    *,
    chain: str,
    min_drop: float = INTERFACE_RSA_DROP,
) -> dict[str, Any]:
    """What assembly buries.

    Returns the dimer RSA (what the gate SHOULD have judged), the monomer RSA
    (what it did judge), and the residues whose exposure collapses on assembly."""
    dimer = _rsa_for_chain(dimer_pdb, chain)
    mono = _rsa_for_chain(monomer_pdb, chain)
    shared = set(dimer) & set(mono)
    buried = {r for r in shared if mono[r] - dimer[r] > min_drop}
    return {
        "chain": chain,
        "n_residues": len(shared),
        "rsa_oligomer": {r: dimer[r] for r in shared},
        "rsa_monomer": {r: mono[r] for r in shared},
        "interface_residues": buried,
        # The subset a 0.40 gate would get WRONG: it passes on the monomer and
        # fails on the assembly.
        "falsely_exposed": {r for r in shared if mono[r] >= 0.40 > dimer[r]},
    }
