"""v1.0.0 deep-dive orchestrator — the 3-agent topology in one entry point.

This package is the entry point for the v1.0.0 deep-dive pipeline. It runs
A1 (Surface Evidence Compiler) and A2 (Biology Compiler) in parallel, merges
their evidence ledgers, dispatches B (Surfaceome Synthesizer) over the merged
ledger (B has no tools — cite-only), promotes A1+A2's ``EvidenceClaim`` records
to substring-anchored ``Evidence``, derives the deterministic ``filters``
rollups, stubs ``deterministic_features`` (the DeepTMHMM / Compara / AlphaFold
fetchers are intentionally deferred), and assembles a full ``SurfaceomeRecord``.

The CLI cutover that replaces ``surface_annotator/orchestrator.py`` lands in
sub-step 2; this module is additive and does not yet touch the old path.

See ``docs/plans/2026-05-13-deep-dive-redesign-surface-accessibility.md``,
"Orchestrator flow" and "Agent topology (multi-agent)".
"""

from accessible_surfaceome.agents.surfaceome_v1.orchestrator import (
    AnnotateResult,
    annotate,
)

__all__ = ["annotate", "AnnotateResult"]
