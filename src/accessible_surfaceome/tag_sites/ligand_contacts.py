"""Residues that contact an ENDOGENOUS ligand or co-receptor — a veto for tag sites.

The deterministic lanes already clear UniProt hazard features (disulfides,
glycosylation, binding/active sites) by 10 A in 3D. That misses the case where a
partner's footprint is known from a STRUCTURE rather than annotated on the
entry: an integrin's ligand face, an HLA's beta-2-microglobulin contact, a
receptor's co-receptor interface. `contact_observation` carries those as
PDB-derived per-residue positions, so they can be vetoed directly.

WHICH partners count is the whole design. Vetoing every contact would be wrong:
the table mixes endogenous biology with therapeutic antibodies, research tools,
viral proteins and crystallisation additives, and a tag that overlaps a
*drug's* epitope is a different (often irrelevant) concern from one that blocks
the protein's own function. Kept:

* ``receptor_partner`` and ``endogenous_large`` — classified as such upstream;
* ``unclassified`` whose partner is a HUMAN UniProt accession — a human protein
  found in complex with this one, which is a co-receptor or binding partner
  whatever the upstream classifier said.

Dropped: ``therapeutic`` (antibodies, Fabs, nanobodies), ``tool``, non-human
accessions (SARS-CoV-2 spike against ACE2 is a real interface but not an
endogenous one), and bare small-molecule codes, which cannot be told apart from
buffers and cryoprotectants without per-ligand curation.

The tolerance is 0 by default, and that is a measured choice rather than a
cautious-looking guess. Calibrated against the 766 published literature sites
that carry a junction:

    +/-0  vetoes 230 surface_loop + 94 disorder candidates, and collides with
          3/766 published sites (0.4%)
    +/-3  vetoes 424 + 202, and collides with 17/766 (2.2%)

People demonstrably do tag within a few residues of an endogenous contact and
get working constructs, so a wider window starts deleting sites that are known
to work. Widen it only with that trade in view.
"""

from __future__ import annotations

import json
import logging
import re
from collections.abc import Iterable
from typing import Any

logger = logging.getLogger(__name__)

#: Upstream categories that are endogenous by classification.
ENDOGENOUS_CATEGORIES = frozenset({"receptor_partner", "endogenous_large"})

#: UniProt accession shape (both the 6- and 10-character forms).
_UNIPROT = re.compile(
    r"^[OPQ][0-9][A-Z0-9]{3}[0-9]$|^[A-NR-Z][0-9]([A-Z][A-Z0-9]{2}[0-9]){1,2}$"
)

#: Default clearance, in residues. See the module docstring for the calibration.
DEFAULT_TOLERANCE = 0


def is_endogenous(observation: dict[str, Any], *, human_accessions: set[str]) -> bool:
    """Whether this contact is with an endogenous ligand or a co-receptor.

    ``human_accessions`` is the cohort's own accession set (gene_identifier),
    which is what distinguishes a human partner from a viral or engineered one
    without needing a taxonomy lookup."""
    category = observation.get("category")
    if category in ENDOGENOUS_CATEGORIES:
        return True
    if category != "unclassified":
        return False  # therapeutic / tool / anything else classified away
    partner = str(observation.get("partner") or "")
    return bool(_UNIPROT.match(partner)) and partner in human_accessions


def veto_residues(
    observations: Iterable[dict[str, Any]],
    *,
    human_accessions: set[str],
    extracellular_only: bool = True,
) -> dict[str, set[int]]:
    """``{uniprot_acc: {residue, ...}}`` to keep tag sites off.

    ``extracellular_only`` because a cytoplasmic contact cannot be blocked by a
    tag on the surface face, and vetoing on it would discard candidates for no
    reason."""
    out: dict[str, set[int]] = {}
    for obs in observations:
        acc = obs.get("uniprot_acc")
        if not acc:
            continue
        context = str(obs.get("context") or "")
        if extracellular_only and not context.startswith("extracellular"):
            continue
        payload = obs.get("observation_json")
        if isinstance(payload, str):
            try:
                payload = json.loads(payload)
            except Exception:  # noqa: BLE001 - a malformed row must not fail a run
                continue
        if not isinstance(payload, dict) or not is_endogenous(
            payload, human_accessions=human_accessions
        ):
            continue
        for pos in payload.get("positions") or []:
            if isinstance(pos, int) and pos > 0:
                out.setdefault(acc, set()).add(pos)
    return out


def blocked(
    residue: int, *, veto: set[int] | None, tolerance: int = DEFAULT_TOLERANCE
) -> bool:
    """Whether a candidate junction is too close to an endogenous contact."""
    if not veto:
        return False
    if tolerance <= 0:
        return residue in veto
    return any(abs(pos - residue) <= tolerance for pos in veto)
