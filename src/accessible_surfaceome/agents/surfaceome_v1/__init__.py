"""Shared deep-dive helpers (formerly the v1 deep-dive orchestrator).

The v1 Managed-Agent deep-dive (Surface Evidence Compiler + Biology Compiler
+ the v1 ``annotate`` entry point) was removed — it is deprecated; the
production path is ``surfaceome_v2``. What remains here are the deterministic,
agent-agnostic helpers that v2 still imports directly from
:mod:`accessible_surfaceome.agents.surfaceome_v1.orchestrator` and
:mod:`accessible_surfaceome.agents.surfaceome_v1.d1_deterministic`:
``_derive_filters``, ``_attach_deterministic_families``,
``scrub_headline_risks``, the triage-record loaders,
``_stub_deterministic_features``, and the DeepTMHMM / Compara / AlphaFold
fetchers.

TODO (follow-up): relocate these helpers to a non-``surfaceome_v1`` module
(e.g. ``agents/_support/``) and delete this package shell.
"""
