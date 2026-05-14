"""A1 — Surface Evidence Compiler (Managed Agent stub for v1.0.0 deep-dive redesign).

This is one of three agents in the new deep-dive topology, replacing the
single ``surface_annotator`` agent. See
``docs/plans/2026-05-13-deep-dive-redesign-surface-accessibility.md`` —
"Agent topology (multi-agent)" — for the full design.

**Role:** evidence-grounded write of ``surface_evidence``. DB-consensus
interpretation, methods tagging, antibody validation. Runs in parallel
with the ``biology_compiler`` agent before the synthesizer is dispatched.

**Status:** stub only — payload + prompt are placeholders. Wired into the
registry shape but not yet pushed to the Managed Agents API. The full
prompt and the orchestrator changes land with the v1.0.0 implementation
PR; this directory exists so the registry / sync machinery can address
the agent by name during planning.
"""
