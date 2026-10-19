"""Deterministic tag-site computation (Plan 4).

Produces ``deterministic_computed`` TaggedSite records for the surfaceome
viewer from two candidate-generation paths:

* ``disorder`` (path 2a) — ports the incumbent low-pLDDT + KIBBY sites.
* ``surface_loop`` (path 2b) — confidently-folded, solvent-exposed loops the
  low-pLDDT screen misses (e.g. EndoNB TFRC I290/V291).

Record shape matches ``viewer/lib/tag-sites-types.ts``.
"""
