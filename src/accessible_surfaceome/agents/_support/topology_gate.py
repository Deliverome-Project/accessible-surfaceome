"""Shared topology predicates for membrane / secreted-form gating.

Single source of truth for the thresholds that decide whether a protein
is "membrane-anchored with a usable ectodomain" (drives the soluble-form
and surface-reachability retrieval axes in the deterministic kickoff) and
whether an isoform is "secreted" (drives the deterministic ``secreted_form``
upgrade post-pass in the v2 orchestrator). Both call sites import these
predicates so the ``1 TM`` / ``30 aa`` thresholds can never drift apart.
"""

from __future__ import annotations

# Smallest ectodomain that can carry a folded, antibody-addressable
# epitope. Below this an "extracellular" stretch is a loop, not a domain a
# binder or a shed soluble fragment could meaningfully engage.
MIN_ECD_RESIDUES = 30


def is_likely_membrane_with_ecd(n_tmh: int | None, ecd_aa: int | None) -> bool:
    """True when topology says membrane-anchored with a usable ectodomain.

    Used to gate the membrane-specific retrieval axes (surface-reachability
    barriers, soluble/shed-form literature). ``None`` for either input means
    "topology unknown" and returns ``False`` — callers that want
    recall-biased behavior on unknown topology must test the unknown case
    explicitly (the kickoff fires the gated axes when topology is unknown).
    """
    return (n_tmh or 0) >= 1 and (ecd_aa or 0) >= MIN_ECD_RESIDUES


def is_secreted_isoform(n_tmh: int | None, ecd_aa: int | None) -> bool:
    """True when an isoform is TM-less yet retains a substantial soluble length.

    The secreted-form mirror of :func:`is_likely_membrane_with_ecd`: a 0-TM
    isoform with a ≥30 aa extracellular length is a candidate soluble species
    produced by alternative splicing. Consumed by the v2 orchestrator's
    deterministic ``secreted_form`` upgrade.
    """
    return (n_tmh or 0) == 0 and (ecd_aa or 0) >= MIN_ECD_RESIDUES


__all__ = [
    "MIN_ECD_RESIDUES",
    "is_likely_membrane_with_ecd",
    "is_secreted_isoform",
]
