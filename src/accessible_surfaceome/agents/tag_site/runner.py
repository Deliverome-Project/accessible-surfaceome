"""End-to-end runner for the literature tag-site agent.

Composes the hybrid literature track:
  1. repo lit-search discovery (``literature_discovery.discover_tag_site_papers``)
     -> PMID-grounded candidate papers;
  2. Sonnet with the tag-site system prompt + those papers + server-side
     ``web_search`` (for the preprints / vocabulary-mismatch papers the abstract
     index misses), via the shared ``call_builder`` repair loop;
  3. post-process: drop non-validated sites, then rank by validation strength
     (surface+function first) then source tier (paper > patent > vendor).

Mirrors ``agents/surfaceome_v2/builders/_common.call_builder`` — same repair
loop, usage sink, and web_search tool wiring the other agents use.
"""
from __future__ import annotations

from typing import Any

from anthropic import Anthropic

from accessible_surfaceome.agents._support.client import get_client
from accessible_surfaceome.agents.surfaceome_v2.builders._common import call_builder
from accessible_surfaceome.tools._shared.http import CachedHTTP, open_default_client
from accessible_surfaceome.tools._shared.models import Paper

from .literature_discovery import SOURCE_TIERS, discover_tag_site_papers
from .prompt import SYSTEM_PROMPT, build_user_prompt, keep_validated_sites
from .schema import VALIDATION_LEVELS, VALIDATION_RANK, TagSiteProposal, TagSiteResult

# Same server-side web_search recipe the methods builder uses (see
# surfaceome_v2/builders/methods.py). call_builder degrades to a cite-only call
# if web_search is not enabled on the account.
_WEB_SEARCH_TOOL: list[dict[str, Any]] = [
    {
        "type": "web_search_20250305",
        "name": "web_search",
        "max_uses": 8,
        "cache_control": {"type": "ephemeral"},
    }
]
_MAX_PROMPT_PAPERS = 25
_MAX_ABSTRACT_CHARS = 700
_TOPO_CHAR = {"extracellular": "O", "intracellular": "I", "membrane": "M", "signal": "S"}


def format_candidate_papers(papers: dict[int, Paper]) -> str:
    """Render the discovered papers as a prompt block the agent reads first."""
    if not papers:
        return "CANDIDATE PAPERS: none retrieved by the lit-search; rely on web_search."
    lines = [
        "CANDIDATE PAPERS (pre-retrieved via EuropePMC + PubTator; PMID-grounded — "
        "read these FIRST and set supporting_pmid when a site comes from one):"
    ]
    for pmid, p in list(papers.items())[:_MAX_PROMPT_PAPERS]:
        abstract = " ".join((p.abstract or "").split())[:_MAX_ABSTRACT_CHARS]
        lines.append(f"- PMID {pmid} ({p.year or '?'}) {p.title}\n  {abstract}")
    return "\n".join(lines)


def _sort_key(s: TagSiteProposal) -> tuple[int, int, int]:
    """Validation strength first (surface+function best), then source tier
    (paper > patent > vendor), then the model's own rank."""
    return (
        VALIDATION_RANK.get(s.validation_level, len(VALIDATION_LEVELS)),
        SOURCE_TIERS.index(s.source_tier) if s.source_tier in SOURCE_TIERS else len(SOURCE_TIERS),
        s.rank,
    )


def rank_sites(result: TagSiteResult) -> TagSiteResult:
    """Drop non-validated sites, sort by validation+tier, renumber ``rank``."""
    keep_validated_sites(result)
    result.sites.sort(key=_sort_key)
    for i, s in enumerate(result.sites, start=1):
        s.rank = i
    return result


def run_tag_site_agent(
    *,
    gene_symbol: str,
    protein_name: str,
    uniprot_accession: str,
    aliases: list[str],
    sequence: str,
    topology: str,
    client: Anthropic | None = None,
    http: CachedHTTP | None = None,
    mode: str = "production",
    usage_sink: list[Any] | None = None,
) -> TagSiteResult:
    """Discover papers, run the agent (papers + web_search), return a validated,
    validation-ranked :class:`TagSiteResult`. ``aliases`` should include the
    protein name(s) — methods papers rarely use the gene symbol."""
    client = client or get_client()
    http = http or open_default_client()
    usage_sink = usage_sink if usage_sink is not None else []

    papers = discover_tag_site_papers(http=http, gene_symbol=gene_symbol, aliases=aliases)
    user_prompt = build_user_prompt(
        gene_symbol, protein_name, mode=mode, sequence=sequence, topology=topology
    )
    user_prompt = f"{user_prompt}\n\n{format_candidate_papers(papers)}"

    result = call_builder(
        client,
        system_prompt=SYSTEM_PROMPT,
        user_prompt=user_prompt,
        schema=TagSiteResult,
        usage_sink=usage_sink,
        label=f"tag_site:{gene_symbol}",
        tools=_WEB_SEARCH_TOOL,
    )
    if result is None:
        return TagSiteResult(
            gene_symbol=gene_symbol,
            uniprot_accession=uniprot_accession,
            sequence_length=len(sequence or ""),
        )
    assert isinstance(result, TagSiteResult)  # expect_array=False → single instance
    return rank_sites(result)


def to_viewer_sites(result: TagSiteResult, *, uniprot_acc: str) -> list[dict[str, Any]]:
    """Convert to the viewer's ``literature_retrieved`` TaggedSite shape
    (viewer/lib/tag-sites-types.ts). Agent-only fields (validation_level,
    position_evidence, source_tier) fold into ``rationale``/``sources`` so the
    viewer contract is unchanged."""
    out: list[dict[str, Any]] = []
    for s in result.sites:
        sources: list[dict[str, Any]] = []
        if s.supporting_pmid:
            sources.append(
                {"pmid": s.supporting_pmid, "citation": f"PMID {s.supporting_pmid}"}
            )
        out.append(
            {
                "site_id": f"{result.gene_symbol}-{s.site_type}-{s.insert_after_residue}-lit",
                "gene_symbol": result.gene_symbol,
                "uniprot_acc": uniprot_acc,
                "provenance": "literature_retrieved",
                "det_path": None,
                "site_kind": s.site_type,
                "insert_after_residue": s.insert_after_residue,
                "residue_before": s.residue_before,
                "residue_after": s.residue_after,
                "topology_state": _TOPO_CHAR.get(s.topology_state, "O"),
                "extracellular": s.topology_state == "extracellular",
                "compartment": s.topology_state,
                "tag_type": s.tag_type,
                "tag_length_aa": None,
                "linker": None,
                "evidence_type": s.evidence_type,
                "functional_impact_measured": s.functional_or_expression_impact_measured,
                "confidence": s.confidence,
                "rationale": (
                    f"{s.rationale} [validation: {s.validation_level}; "
                    f"position: {s.position_evidence}; source: {s.source_tier}]"
                ),
                "sources": sources,
                "plddt": None,
                "conservation_rank": None,
                "median_conservation": None,
            }
        )
    return out
