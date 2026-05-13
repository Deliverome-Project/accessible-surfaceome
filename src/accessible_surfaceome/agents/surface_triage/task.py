"""Task-message rendering for the surface_triage variants.

Pure-function template renderer that lifts a resolved
``IdentifierBundle`` (HGNC + UniProt + NCBI summary + gene group + CD
designation) into the per-call user message the triage agent sees.

This used to live inside ``orchestrator.py`` next to the Managed Agents
session flow. The Managed Agents path was retired (Anthropic's
``beta.agents`` API does not yet expose ``cache_control``, so the live
``triage run`` path was paying ~$200 of avoidable cost per genome-wide
sweep relative to the direct ``messages.create`` runner). The task
renderer survived the cleanup because the sub-bench runner still uses
it to build the user message for the resolver-anchored variants.
"""

from __future__ import annotations

from pathlib import Path

from accessible_surfaceome.tools._shared.models import IdentifierBundle

_TASK_TEMPLATE_PATH = Path(__file__).parent / "prompts" / "task_template.md"


def render_task(bundle: IdentifierBundle) -> str:
    """Populate the task template with canonical identifiers + NCBI summary.

    The agent has no tools, so the orchestrator pre-cooks the canonical-
    identity context here. We deliberately do NOT inject UniProt's
    subcellular_locations or function_text — that would prime the agent to
    over-defer to UniProt's localization call (which has its own ~70%
    accuracy on the benchmark). Identifiers + NCBI gene summary are
    enough to prevent gross alias hallucinations without contaminating
    the model's independent reasoning.
    """

    template = _TASK_TEMPLATE_PATH.read_text()
    aliases = ", ".join(bundle.aliases) if bundle.aliases else "(none)"
    previous = ", ".join(bundle.previous_symbols) if bundle.previous_symbols else "(none)"
    gene_groups = (
        ", ".join(bundle.hgnc_gene_groups) if bundle.hgnc_gene_groups else "(none assigned)"
    )
    cd = bundle.cd_designation or "(none assigned)"
    summary = bundle.ncbi_summary.strip() if bundle.ncbi_summary else "(no NCBI summary available)"
    return (
        template
        .replace("{gene}", bundle.hgnc_symbol)
        .replace("{hgnc_symbol}", bundle.hgnc_symbol)
        .replace("{approved_name}", bundle.approved_name or "(unknown)")
        .replace("{uniprot_acc}", bundle.uniprot_acc)
        .replace("{aliases}", aliases)
        .replace("{previous_symbols}", previous)
        .replace("{hgnc_gene_groups}", gene_groups)
        .replace("{cd_designation}", cd)
        .replace("{ncbi_summary}", summary)
    )


# Backwards-compat alias for callers that imported the private name from
# the old orchestrator module. New code should call ``render_task``.
_render_task = render_task


__all__ = ["render_task", "_render_task"]
