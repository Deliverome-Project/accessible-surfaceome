"""Deterministic species post-pass over a built BiologicalContext / SurfaceEvidence.

Two passes, applied in order:

1. **Cell-line gazetteer pass.** Scans each row's free-text fields for
   known cell-line tokens (MC3T3-E1 → mouse, U251 MG → human, FRTL-5
   → rat) via ``tools._shared.cell_line_species.infer_species_from_text``.
   Catches the rows whose context strings name a specific line.

2. **Cite-aggregation pass.** For rows STILL marked ``"unspecified"``
   after pass 1, looks up each ``cited_evidence_ids`` entry in the
   passed ``evidence`` list and aggregates the cited evidence's
   ``assay_context.species``. If all non-unspecified cited species
   agree, fills the row with that species. Catches abstract rows like
   ``tissue="bone"`` (no cell-line token in the row itself) whose
   cited papers all reported on the same species. This pass requires
   the ``evidence`` arg — call sites without evidence (e.g. unit tests
   on a built ``BiologicalContext`` alone) pass ``None`` and skip
   pass 2.

Rows whose agent-set ``species`` is anything other than ``"unspecified"``
are left alone — the agent had context the post-pass doesn't and its
call wins.

Both passes set ``species_inferred = True`` on filled rows so readers
can tell the value is heuristic.

Module is standalone so it can be:
* called inline by the v2 orchestrator after evidence promotion,
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
    Evidence,
    ExpressionObservation,
    Species,
    SurfaceEvidence,
    TissueContext,
)

logger = logging.getLogger(__name__)


@dataclass
class SpeciesPostPassStats:
    """Tallies of how many rows the post-pass touched, by row type and pass."""

    tissues_filled: int = 0
    cell_types_filled: int = 0
    modulation_filled: int = 0
    expression_obs_filled: int = 0
    # Sub-tally: how many of the fills came from the cite-aggregation
    # pass (vs the cell-line gazetteer pass). Useful for debugging
    # coverage: if a sample fills mostly via cite-aggregation, that's
    # a signal the agent's free-text rows lack cell-line names but
    # the cited evidence's AssayContext.species is well-populated.
    filled_by_gazetteer: int = 0
    filled_by_cite_aggregation: int = 0

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


def _fill_from_gazetteer(
    row: TissueContext | CellTypeContextV1 | AccessibilityModulationObservation | ExpressionObservation,
    haystack: str,
) -> bool:
    """Pass 1: fill species from cell-line gazetteer hits on free text."""
    if row.species != "unspecified":
        return False  # agent already set it; defer to the agent
    inferred = infer_species_from_text(haystack)
    if inferred is None:
        return False
    row.species = inferred
    row.species_inferred = True
    return True


def _aggregate_cited_species(
    cited_evidence_ids: list[str], evidence_by_id: dict[str, Evidence]
) -> Species | None:
    """Pass 2 helper: aggregate species from cited evidence rows.

    Returns the unique non-unspecified species if all cited evidence
    rows agree (single-value set), otherwise ``None``. Missing
    evidence IDs and ``"unspecified"`` values are skipped silently.
    """
    seen: set[Species] = set()
    for eid in cited_evidence_ids:
        e = evidence_by_id.get(eid)
        if e is None:
            continue
        sp = e.assay_context.species
        if sp != "unspecified":
            seen.add(sp)
    if len(seen) == 1:
        return next(iter(seen))
    return None


def _fill_from_cites(
    row: TissueContext | CellTypeContextV1 | AccessibilityModulationObservation | ExpressionObservation,
    evidence_by_id: dict[str, Evidence],
) -> bool:
    """Pass 2: fill species by aggregating cited evidence's assay_context.species.

    Only runs on rows still ``unspecified`` after the gazetteer pass.
    """
    if row.species != "unspecified":
        return False
    inferred = _aggregate_cited_species(row.cited_evidence_ids, evidence_by_id)
    if inferred is None:
        return False
    row.species = inferred
    row.species_inferred = True
    return True


def apply_species_post_pass(
    *,
    biological_context: BiologicalContext,
    surface_evidence: SurfaceEvidence,
    evidence: list[Evidence] | None = None,
) -> SpeciesPostPassStats:
    """Mutates rows in place; returns stats.

    Pass 1 (cell-line gazetteer) always runs. Pass 2 (cite-aggregation)
    runs only if ``evidence`` is provided — call sites without evidence
    available (e.g. unit tests on bare contexts) get pass 1 only.
    """
    stats = SpeciesPostPassStats()

    # ---- Pass 1: cell-line gazetteer ----
    for tissue in biological_context.tissues:
        if _fill_from_gazetteer(tissue, _tissue_haystack(tissue)):
            stats.tissues_filled += 1
            stats.filled_by_gazetteer += 1
    for ct in biological_context.cell_types:
        if _fill_from_gazetteer(ct, _cell_type_haystack(ct)):
            stats.cell_types_filled += 1
            stats.filled_by_gazetteer += 1
    for mod in biological_context.accessibility_modulation:
        if _fill_from_gazetteer(mod, _modulation_haystack(mod)):
            stats.modulation_filled += 1
            stats.filled_by_gazetteer += 1
    for method in surface_evidence.methods:
        for obs in method.expression_observations:
            if _fill_from_gazetteer(obs, _expression_obs_haystack(obs)):
                stats.expression_obs_filled += 1
                stats.filled_by_gazetteer += 1

    # ---- Pass 2: cite-aggregation ----
    if evidence is not None:
        evidence_by_id = {e.evidence_id: e for e in evidence}
        for tissue in biological_context.tissues:
            if _fill_from_cites(tissue, evidence_by_id):
                stats.tissues_filled += 1
                stats.filled_by_cite_aggregation += 1
        for ct in biological_context.cell_types:
            if _fill_from_cites(ct, evidence_by_id):
                stats.cell_types_filled += 1
                stats.filled_by_cite_aggregation += 1
        for mod in biological_context.accessibility_modulation:
            if _fill_from_cites(mod, evidence_by_id):
                stats.modulation_filled += 1
                stats.filled_by_cite_aggregation += 1
        for method in surface_evidence.methods:
            for obs in method.expression_observations:
                if _fill_from_cites(obs, evidence_by_id):
                    stats.expression_obs_filled += 1
                    stats.filled_by_cite_aggregation += 1

    if stats.total_filled:
        logger.info(
            "species post-pass filled %d row(s): tissues=%d cell_types=%d "
            "modulation=%d expression_obs=%d (gazetteer=%d cite_agg=%d)",
            stats.total_filled,
            stats.tissues_filled,
            stats.cell_types_filled,
            stats.modulation_filled,
            stats.expression_obs_filled,
            stats.filled_by_gazetteer,
            stats.filled_by_cite_aggregation,
        )
    return stats


__all__ = ["SpeciesPostPassStats", "apply_species_post_pass"]
