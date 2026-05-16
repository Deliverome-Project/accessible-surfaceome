"""v2 deep-dive pipeline — plan-trim-select dual + block-builders + synthesizer.

The v2 orchestrator replaces v1's monolithic A1/A2 Sonnet calls with the
plan-trim-select dual driver that produces verbatim ``EvidenceClaim``
ledgers per agent, then dispatches a constellation of focused
``block_builders`` to extract structured ``SurfaceEvidence`` /
``BiologicalContext`` sub-blocks from those ledgers. The synthesizer
(``surfaceome_synthesizer``) is reused unchanged.

The v1 orchestrator lives alongside this — they share the synthesizer,
evidence-promotion, deterministic-features stub, and filters derivation.
"""

from accessible_surfaceome.agents.surfaceome_v2.orchestrator import (
    AnnotateResultV2,
    annotate,
)

__all__ = ["AnnotateResultV2", "annotate"]
