"""A2 — Biology Compiler (Managed Agent stub for v1.0.0 deep-dive redesign).

This is one of three agents in the new deep-dive topology, replacing the
single ``surface_annotator`` agent. See
``docs/plans/2026-05-13-deep-dive-redesign-surface-accessibility.md`` —
"Agent topology (multi-agent)" — for the full design.

**Role:** evidence-grounded write of ``biological_context``. Tissue / cell
type / cell state synthesis, anatomical_accessibility, and
``accessibility_modulation`` entries with the triage-aligned closed-enum
sub-fields (``cell_state_trigger`` / ``restricted_lineage`` /
``dual_loc_partner_compartment``). Runs in parallel with the
``surface_evidence_compiler`` agent.

**Status:** stub only — same as A1 / B. Full prompt + orchestrator
integration land with the v1.0.0 implementation PR.
"""
