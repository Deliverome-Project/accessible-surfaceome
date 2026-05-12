"""Registry of custom tools the surface-annotator exposes to its agent.

Each entry binds together (a) the JSON-Schema input contract registered with
the agent on creation, (b) the agent-facing description (the primary lever on
selection quality — the agent picks tools by description), and (c) the
host-side handler the orchestrator dispatches when the agent emits an
``agent.custom_tool_use`` event.

Today: ``gene_lookup`` and ``gene_literature``. ``patent_lookup`` was retired in the v0.4.0 refocus. Future tools slot in
here when they're built.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable

from accessible_surfaceome.tools._shared.http import CachedHTTP
from accessible_surfaceome.tools._shared.retraction_watch import RetractionIndex
from accessible_surfaceome.tools._shared.source_text import SourceTextStore
from accessible_surfaceome.tools.gene_literature import gene_literature
from accessible_surfaceome.tools.gene_lookup import gene_lookup

from .source_registration import register_from_tool_return


@dataclass(frozen=True)
class HandlerContext:
    """Per-session bundle threaded into every tool handler.

    Captures the dependencies tool handlers need beyond the raw HTTP client:
    the source-text store (so handlers register source bodies for the
    promotion step) and the retraction index (so ``gene_literature`` can
    flip ``is_retracted`` when Retraction Watch says so).
    """

    http: CachedHTTP
    source_store: SourceTextStore | None
    retraction_index: RetractionIndex


@dataclass(frozen=True)
class ToolSpec:
    name: str
    description: str
    input_schema: dict[str, Any]
    handler_factory: Callable[[HandlerContext], Callable[[dict[str, Any]], Any]]


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


def _make_gene_lookup_handler(ctx: HandlerContext) -> Callable[[dict[str, Any]], Any]:
    def _call(payload: dict[str, Any]) -> Any:
        result = gene_lookup(
            mode=payload["mode"],
            symbol_or_acc=payload["symbol_or_acc"],
            http=ctx.http,
        )
        if ctx.source_store is not None:
            register_from_tool_return(
                tool="gene_lookup", result=result, store=ctx.source_store
            )
        return result

    return _call


GENE_LITERATURE_DESCRIPTION = (
    "Retrieve literature for a gene from NCBI gene2pubmed and Europe PMC. "
    "Always start with mode='gene2pubmed' (pass uniprot_acc) — returns "
    "NCBI's curated PMID list, far higher precision than keyword search. "
    "Use mode='topic_search' (pass uniprot_acc + topic_anchors) when "
    "gene2pubmed has <5 PMIDs or you need surface-method-specific evidence "
    "(flow cytometry, surface biotinylation, IHC, surfaceome MS, shedding). "
    "Use mode='fetch_abstract' for a single PMID. Use mode='fetch_fulltext' "
    "ONLY for PMC OA papers (is_pmc_oa==True) and only when an abstract is "
    "ambiguous — full text is capped at ~10k tokens with truncation flags. "
    "Every paper carries topic_tags, is_review, is_retracted, is_pmc_oa "
    "computed before tokens reach you so you can prioritize cheaply."
)

GENE_LITERATURE_INPUT_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "mode": {
            "type": "string",
            "enum": ["gene2pubmed", "topic_search", "fetch_abstract", "fetch_fulltext"],
            "description": (
                "Which literature mode to run. gene2pubmed first; topic_search for "
                "recall fill; fetch_abstract / fetch_fulltext for individual PMIDs / "
                "PMCIDs surfaced by the prior modes."
            ),
        },
        "uniprot_acc": {
            "type": "string",
            "description": (
                "Required for gene2pubmed and topic_search (used to resolve symbol + "
                "aliases internally). Take this from the prior gene_lookup resolve."
            ),
        },
        "topic_anchors": {
            "type": "array",
            "items": {
                "type": "string",
                "enum": [
                    "surface_expression",
                    "topology",
                    "ihc",
                    "flow_cytometry",
                    "surface_biotinylation",
                    "mass_spec_surfaceome",
                    "structure",
                    "ptm",
                    "shedding",
                ],
            },
            "description": (
                "Required for topic_search. Pick the anchors that match the evidence "
                "kind you need (e.g. ['surface_expression', 'flow_cytometry'] for ADC "
                "target validation, ['shedding'] to check decoy risk)."
            ),
        },
        "pmid": {
            "type": "integer",
            "description": "Required for fetch_abstract.",
        },
        "pmcid": {
            "type": "string",
            "description": (
                "Required for fetch_fulltext (e.g. 'PMC2195717'). Take this from the "
                "Paper.pmc_id of a prior gene2pubmed / topic_search / fetch_abstract "
                "result; only PMC OA papers can be fetched in full."
            ),
        },
        "max_results": {
            "type": "integer",
            "description": "Cap the number of papers returned. Defaults to 25.",
        },
    },
    "required": ["mode"],
}


def _make_gene_literature_handler(
    ctx: HandlerContext,
) -> Callable[[dict[str, Any]], Any]:
    def _call(payload: dict[str, Any]) -> Any:
        result = gene_literature(
            mode=payload["mode"],
            uniprot_acc=payload.get("uniprot_acc"),
            ncbi_gene_id=payload.get("ncbi_gene_id"),
            hgnc_symbol=payload.get("hgnc_symbol"),
            aliases=payload.get("aliases"),
            pmid=payload.get("pmid"),
            pmcid=payload.get("pmcid"),
            topic_anchors=payload.get("topic_anchors"),
            max_results=payload.get("max_results", 25),
            http=ctx.http,
            retraction_index=ctx.retraction_index,
        )
        if ctx.source_store is not None:
            register_from_tool_return(
                tool="gene_literature", result=result, store=ctx.source_store
            )
        return result

    return _call


SPECS: list[ToolSpec] = [
    ToolSpec(
        name="gene_lookup",
        description=GENE_LOOKUP_DESCRIPTION,
        input_schema=GENE_LOOKUP_INPUT_SCHEMA,
        handler_factory=_make_gene_lookup_handler,
    ),
    ToolSpec(
        name="gene_literature",
        description=GENE_LITERATURE_DESCRIPTION,
        input_schema=GENE_LITERATURE_INPUT_SCHEMA,
        handler_factory=_make_gene_literature_handler,
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


def build_handlers(
    http: CachedHTTP,
    *,
    source_store: SourceTextStore | None = None,
    retraction_index: RetractionIndex | None = None,
) -> dict[str, Callable[[dict[str, Any]], Any]]:
    """Live tool name → handler dispatch table for the orchestrator.

    Pass ``source_store`` when running under the orchestrator so tool returns
    register the bodies the substring check will need. One-off scripts that
    don't care about evidence promotion can omit it.

    Pass ``retraction_index`` to enable Retraction Watch cross-referencing in
    ``gene_literature`` results. ``None`` falls back to the empty index — PMC's
    own ``"Retracted Publication"`` marker is the only signal in that case.
    """

    from accessible_surfaceome.tools._shared import retraction_watch as _rw

    ctx = HandlerContext(
        http=http,
        source_store=source_store,
        retraction_index=retraction_index if retraction_index is not None else _rw.empty(),
    )
    return {spec.name: spec.handler_factory(ctx) for spec in SPECS}
