"""Deterministic ``secreted_form`` upgrade — runs after the synthesizer.

The synthesizer authors ``accessibility_risks`` BEFORE isoform topology is
fetched from D1 (an ordering constraint of the v2 pipeline), so it cannot
see a TM-less splice isoform that implies a soluble species. This post-pass
closes that gap deterministically rather than "asking the LLM harder": if D1
topology shows any isoform that is TM-less with a substantial ectodomain
length, and the synthesizer did not already mark ``secreted_form`` present
from the literature, upgrade it to a weak, low-severity, alternative-splicing
call.

It only ever UPGRADES. A literature-backed ``present=True`` (possibly a
higher severity, with cited evidence) is never touched — the topology
inference is the weaker signal and must not overwrite a stronger one. This
mirrors the species post-pass's "agent wins" convention.
"""

from __future__ import annotations

import logging

from accessible_surfaceome.agents._support.topology_gate import is_secreted_isoform
from accessible_surfaceome.tools._shared.models import (
    AccessibilityRisks,
    DeterministicFeatures,
)

logger = logging.getLogger(__name__)


def apply_secreted_form_post_pass(
    *,
    accessibility_risks: AccessibilityRisks,
    deterministic_features: DeterministicFeatures,
) -> bool:
    """Upgrade ``secreted_form`` in place when D1 shows a TM-less isoform.

    Returns ``True`` if an upgrade was applied. No-op (returns ``False``)
    when the synthesizer already marked ``secreted_form`` present, or when no
    isoform satisfies the secreted-isoform predicate (TM=0 with a ≥30 aa
    extracellular length).
    """
    secreted = accessibility_risks.secreted_form
    if secreted.present:
        # A literature-backed call already stands — never downgrade.
        return False

    has_secreted_isoform = any(
        is_secreted_isoform(iso.tm_helix_count, iso.ecd_length_residues)
        for iso in deterministic_features.isoform_topologies
    )
    if not has_secreted_isoform:
        return False

    secreted.present = True
    secreted.severity = "low"
    secreted.evidence_strength = "weak"
    secreted.source = "alternative_splicing"
    logger.info(
        "secreted_form upgraded from topology: a TM-less isoform with a "
        "substantial ectodomain implies a soluble species (weak / low)."
    )
    return True


__all__ = ["apply_secreted_form_post_pass"]
