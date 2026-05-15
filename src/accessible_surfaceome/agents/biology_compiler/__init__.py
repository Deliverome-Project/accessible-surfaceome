"""A2 — Biology Compiler (v1.0.0 deep-dive topology).

One of three agents in the deep-dive topology that replaces the single
``surface_annotator``. See ``docs/plans/2026-05-13-deep-dive-redesign-surface-accessibility.md``
— "Agent topology (multi-agent)" — for the full design.

**Role:** evidence-grounded write of ``biological_context``. Tissue /
cell-type / cell-state synthesis, subcellular + anatomical accessibility,
and ``accessibility_modulation`` entries with the triage-aligned
closed-enum sub-fields (``cell_state_trigger`` / ``restricted_lineage`` /
``dual_loc_partner_compartment``). Runs in parallel with the
``surface_evidence_compiler`` agent.

**Implementation:** Messages-API tool-use loop in :mod:`runner`, mirroring
A1. Not a Managed Agent — same reasoning as A1 (writes no files, runs no
bash, orchestrator owns persistence + ledger merging).
"""
