"""Registry of custom tools the surface-annotator exposes to its agent.

Each entry binds together (a) the JSON-Schema input contract registered with
the agent on creation, (b) the agent-facing description (the primary lever on
selection quality — the agent picks tools by description), and (c) the
host-side handler the orchestrator dispatches when the agent emits an
``agent.custom_tool_use`` event.

Today: ``gene_lookup`` only. ``gene_literature`` and ``patent_lookup`` slot in
here when they're built.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable

from accessible_surfaceome.tools._shared.http import CachedHTTP
from accessible_surfaceome.tools.gene_lookup import gene_lookup
from accessible_surfaceome.tools.patent_lookup import patent_lookup


@dataclass(frozen=True)
class ToolSpec:
    name: str
    description: str
    input_schema: dict[str, Any]
    handler_factory: Callable[[CachedHTTP], Callable[[dict[str, Any]], Any]]


# Tool descriptions follow the published guidance: 3–4 sentences (~150 words),
# cover what the tool does, when to use it, when *not* to use it, parameter
# semantics, caveats. Lifted from docs/tools-design.md.

GENE_LOOKUP_DESCRIPTION = (
    "Look up a single gene's identifiers, database votes, UniProt summary, or "
    "candidate-universe miss diagnosis. Use this tool first whenever you start "
    "work on a new gene — call mode='resolve' with a symbol or accession to "
    "canonicalize the identifiers before any other tool call. Use mode='db_panel' "
    "once per gene to get the structured per-source surface-vote panel from local "
    "processed data (SURFY, CSPA, UniProt query match, GO, HPA, DeepTMHMM, "
    "JensenLab COMPARTMENTS, patent-handle lane). Use mode='uniprot_summary' to "
    "get distilled subcellular-location, topology features, PTMs, tissue "
    "specificity, and cross-references — do not call web_fetch against UniProt "
    "directly; this tool is faster, cached, and Pydantic-validated. Use "
    "mode='miss_diagnosis' only when a gene is in the controls panel but absent "
    "from the candidate universe; it returns a structured per-source explanation "
    "of why each rule failed to fire."
)


GENE_LOOKUP_INPUT_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "mode": {
            "type": "string",
            "enum": ["resolve", "db_panel", "uniprot_summary", "miss_diagnosis"],
            "description": (
                "Which lookup mode to run. Always call 'resolve' first for a new gene; "
                "later modes accept either the canonical UniProt accession or the symbol "
                "(the tool resolves implicitly, but explicit accs avoid ambiguity)."
            ),
        },
        "symbol_or_acc": {
            "type": "string",
            "description": (
                "HGNC symbol (e.g. 'KAAG1'), UniProt accession (e.g. 'Q9UBP8'), or "
                "Ensembl gene ID. For modes other than 'resolve', prefer the UniProt "
                "accession returned by the prior 'resolve' call."
            ),
        },
    },
    "required": ["mode", "symbol_or_acc"],
}


def _make_gene_lookup_handler(http: CachedHTTP) -> Callable[[dict[str, Any]], Any]:
    def _call(payload: dict[str, Any]) -> Any:
        return gene_lookup(
            mode=payload["mode"],
            symbol_or_acc=payload["symbol_or_acc"],
            http=http,
        )

    return _call


PATENT_LOOKUP_DESCRIPTION = (
    "Look up a patent disclosure on Google Patents. Use this whenever a gene's "
    "db_panel shows patent_handle.vote=true (or miss_diagnosis surfaces a "
    "patent_handle candidate_lane), or when conventional sources return no "
    "surface evidence but the gene appears in our patent-delivery-handle "
    "controls panel. Returns the patent's title, applicant, priority and "
    "publication dates, and a short claims_summary derived from the abstract. "
    "Use the WO numbers returned by db_panel's patent_handle.evidence as input. "
    "Patent claims are NOT peer-reviewed primary evidence — the returned record "
    "carries evidence_provenance='patent' and the surfaceome record's evidence "
    "tier should respect this when grading. Do not use this tool for scientific "
    "literature; for that, use gene_literature (when available)."
)

PATENT_LOOKUP_INPUT_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "wo_number": {
            "type": "string",
            "description": (
                "Patent number with WO/EP/US prefix (e.g. 'WO2024036333A2'). Take "
                "this directly from db_panel patent_handle.evidence.wo_numbers."
            ),
        },
    },
    "required": ["wo_number"],
}


def _make_patent_lookup_handler(http: CachedHTTP) -> Callable[[dict[str, Any]], Any]:
    def _call(payload: dict[str, Any]) -> Any:
        return patent_lookup(wo_number=payload["wo_number"], http=http)

    return _call


SPECS: list[ToolSpec] = [
    ToolSpec(
        name="gene_lookup",
        description=GENE_LOOKUP_DESCRIPTION,
        input_schema=GENE_LOOKUP_INPUT_SCHEMA,
        handler_factory=_make_gene_lookup_handler,
    ),
    ToolSpec(
        name="patent_lookup",
        description=PATENT_LOOKUP_DESCRIPTION,
        input_schema=PATENT_LOOKUP_INPUT_SCHEMA,
        handler_factory=_make_patent_lookup_handler,
    ),
]


def custom_tool_definitions() -> list[dict[str, Any]]:
    """Tool entries for ``agents.create(tools=...)``."""

    return [
        {
            "type": "custom",
            "name": spec.name,
            "description": spec.description,
            "input_schema": spec.input_schema,
        }
        for spec in SPECS
    ]


def build_handlers(http: CachedHTTP) -> dict[str, Callable[[dict[str, Any]], Any]]:
    """Live tool name → handler dispatch table for the orchestrator."""

    return {spec.name: spec.handler_factory(http) for spec in SPECS}
