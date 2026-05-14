"""B — Synthesizer (Managed Agent stub for v1.0.0 deep-dive redesign).

This is the third of three agents in the new deep-dive topology, replacing
the single ``surface_annotator`` agent. See
``docs/plans/2026-05-13-deep-dive-redesign-surface-accessibility.md`` —
"Agent topology (multi-agent)" — for the full design.

**Role:** cross-section integration. Reads the Compiler outputs (A1 +
A2) and the deterministic features, then writes ``executive_summary``,
``filters`` (all 17 fields), ``accessibility_risks``, and ``confidence``
+ ``confidence_reasoning``. **No tools** — cite-only from the merged
Compiler ledger. The "no tools" constraint enforces "if you can't quote
it from the ledger, you can't claim it."

**Status:** stub only. Real prompt + orchestrator wiring lands with the
v1.0.0 implementation PR.
"""
