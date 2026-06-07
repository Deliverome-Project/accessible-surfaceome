"""Surface-triage agent — first-pass surface-protein judgment per gene.

NOT a Managed Agent. The triage runs in-process via
:mod:`scripts.triage_runner`, which builds a per-gene task with
:func:`accessible_surfaceome.agents.surface_triage.task.render_task` and
invokes the model directly through ``anthropic.Anthropic().messages.create``
with the system prompt loaded from
``src/accessible_surfaceome/agents/surface_triage/prompts/``.

Canonical production sweep (the rows the catalog + the v2 deep-dive's
``_load_triage_record`` actually consume):

* model:   ``claude-sonnet-4-6``  (= ``triage_runner.CANONICAL_TRIAGE_MODEL``)
* run_id:  ``genome_full_sonnet_ncbi_v2``  (= ``triage_runner.CANONICAL_TRIAGE_RUN_ID``)
* variant: ``ncbi``  (NCBI gene_info context block, no live web search)

The runner also supports Haiku and Opus on the same prompt for bench
comparisons (see :mod:`scripts.triage_runner`'s module docstring); those
are evaluation tiers, not production. NOTE: do not confuse this
gene-level surface_triage with
:mod:`accessible_surfaceome.agents.plan_trim_select.abstract_triage`,
which is a Haiku call inside the deep-dive's retrieval loop that triages
paper *abstracts* (a different thing entirely).
"""
