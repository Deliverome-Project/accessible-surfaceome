# Main Figure 4 — `deep_dive_flow`

Schematic SVG of the per-gene deep-dive pipeline (three sequential
stages: Stage 1 deterministic evidence retrieval, Stage 2 nine
Sonnet 4.6 block builders in two parallel waves, Stage 3 Sonnet 4.6
synthesizer; ~$0.40–$0.60 per gene, 90–180 s wall-clock at the
Sonnet 4.6 tier).

This figure is an author-drawn SVG mockup — there is no reproduction
script or data TSV. The gist bundles the SVG alone for direct
embedding into the manuscript / blog. The pipeline architecture it
describes lives in the project repo at
[`scripts/surfaceome_v2_annotate.py`](https://github.com/Deliverome-Project/accessible-surfaceome/blob/main/scripts/surfaceome_v2_annotate.py)
→
[`src/accessible_surfaceome/agents/surfaceome_v2/orchestrator.py`](https://github.com/Deliverome-Project/accessible-surfaceome/blob/main/src/accessible_surfaceome/agents/surfaceome_v2/orchestrator.py),
with the architectural narrative in the `## v2 publishes records by
default` section of
[CLAUDE.md](https://github.com/Deliverome-Project/accessible-surfaceome/blob/main/CLAUDE.md).
