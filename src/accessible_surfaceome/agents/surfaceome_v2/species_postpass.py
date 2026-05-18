"""Deterministic species post-pass over a built BiologicalContext / SurfaceEvidence.

Walks ``TissueContext`` / ``CellTypeContextV1`` /
``AccessibilityModulationObservation`` rows under ``biological_context``
and ``ExpressionObservation`` rows nested under
``surface_evidence.methods[].expression_observations``. For each row
whose ``species == "unspecified"``, scans the row's free-text fields
for a known cell-line token via
``tools._shared.cell_line_species.infer_species_from_text``. On a
match, fills ``species`` and sets ``species_inferred = True``.

Rows whose agent-set ``species`` is anything other than ``"unspecified"``
are left alone — the agent had context the post-pass doesn't and its
call wins.

Module is standalone so it can be:
* called inline by the v2 orchestrator after block-builders finish,
* called by a one-shot script over already-committed sample JSONs to
  backfill species without re-running the full pipeline,
* tested in isolation against built-in row instances.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass

from accessible_surfaceome.tools._shared.cell_line_species import (
    infer_species_from_text,
)
from accessible_surfaceome.tools._shared.models import (
    AccessibilityModulationObservation,
    BiologicalContext,
    CellTypeContextV1,
    ExpressionObservation,
    SurfaceEvidence,
    TissueContext,
)

logger = logging.getLogger(__name__)


@dataclass
class SpeciesPostPassStats:
    """Tallies of how many rows the post-pass touched, by row type."""

    tissues_filled: int = 0
    cell_types_filled: int = 0
    modulation_filled: int = 0
    expression_obs_filled: int = 0

    @property
    def total_filled(self) -> int:
        return (
            self.tissues_filled
            + self.cell_types_filled
            + self.modulation_filled
            + self.expression_obs_filled
        )


def _tissue_haystack(row: TissueContext) -> str:
    return " ".join(
        [
            row.tissue,
            *row.cell_types,
            *row.cell_states,
        ]
    )


def _cell_type_haystack(row: CellTypeContextV1) -> str:
    return " ".join([row.cell_type, *row.present_in_tissues])


def _modulation_haystack(row: AccessibilityModulationObservation) -> str:
    return " ".join([row.baseline_context, row.modulating_state, row.change])


def _expression_obs_haystack(row: ExpressionObservation) -> str:
    return row.context


def _fill_one(
    row: TissueContext | CellTypeContextV1 | AccessibilityModulationObservation | ExpressionObservation,
    haystack: str,
) -> bool:
    """Fill species on one row from its haystack. Returns True if filled."""
    if row.species != "unspecified":
        return False  # agent already set it; defer to the agent
    inferred = infer_species_from_text(haystack)
    if inferred is None:
        return False
    row.species = inferred
    row.species_inferred = True
    return True


def apply_species_post_pass(
    *,
    biological_context: BiologicalContext,
    surface_evidence: SurfaceEvidence,
) -> SpeciesPostPassStats:
    """Mutates rows in place; returns stats."""
    stats = SpeciesPostPassStats()
    for tissue in biological_context.tissues:
        if _fill_one(tissue, _tissue_haystack(tissue)):
            stats.tissues_filled += 1
    for ct in biological_context.cell_types:
        if _fill_one(ct, _cell_type_haystack(ct)):
            stats.cell_types_filled += 1
    for mod in biological_context.accessibility_modulation:
        if _fill_one(mod, _modulation_haystack(mod)):
            stats.modulation_filled += 1
    for method in surface_evidence.methods:
        for obs in method.expression_observations:
            if _fill_one(obs, _expression_obs_haystack(obs)):
                stats.expression_obs_filled += 1
    if stats.total_filled:
        logger.info(
            "species post-pass filled %d row(s): tissues=%d cell_types=%d "
            "modulation=%d expression_obs=%d",
            stats.total_filled,
            stats.tissues_filled,
            stats.cell_types_filled,
            stats.modulation_filled,
            stats.expression_obs_filled,
        )
    return stats


__all__ = ["SpeciesPostPassStats", "apply_species_post_pass"]
