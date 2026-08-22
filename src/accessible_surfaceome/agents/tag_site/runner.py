"""End-to-end runner for the literature tag-site agent.

Composes the hybrid literature track:
  1. repo lit-search discovery (``literature_discovery``) — EuropePMC (alias +
     methods vocabulary, default + citation-sorted passes) + PubTator, RETRACTION
     filtered, PLUS preprints (bioRxiv/medRxiv PPR records the PMID path skips);
  2. relevance triage -> fetch METHODS/RESULTS full text for the top papers;
  3. Sonnet with the tag-site prompt + those papers/preprints (+ full text) +
     server-side ``web_search``, via the shared ``call_builder`` repair loop;
  4. post-process: verify each site's supporting_quote against the source text
     (entailment), drop non-validated sites, rank by validation strength then
     source tier then entailment.

Mirrors ``agents/surfaceome_v2/builders/_common.call_builder`` — same repair loop,
usage sink, and web_search tool wiring the other agents use.
"""
from __future__ import annotations

from typing import Any

from anthropic import Anthropic

from accessible_surfaceome.agents._support.client import get_client
from accessible_surfaceome.agents._support.web_literature import web_discover_papers
from accessible_surfaceome.agents.surfaceome_v2.builders._common import call_builder
from accessible_surfaceome.tools._shared.http import CachedHTTP, open_default_client
from accessible_surfaceome.tools._shared.europepmc import europepmc_bulk_by_pmid
from accessible_surfaceome.tools._shared.models import Paper, paper_source_id
from accessible_surfaceome.tools._shared.retraction_watch import empty as _empty_retraction
from accessible_surfaceome.tools._shared.retraction_watch import from_http as _retraction_from_http

from .literature_discovery import (
    SOURCE_TIERS,
    discover_tag_site_papers,
    fetch_fulltext_sections,
    quote_supported,
)
from .prompt import SYSTEM_PROMPT, build_user_prompt, keep_validated_sites
from .schema import VALIDATION_LEVELS, VALIDATION_RANK, TagSiteProposal, TagSiteResult

# web_search discovery is delegated to the shared ``web_literature`` module
# (agents/_support), so the tag-site and internalization tracks share ONE
# implementation. This is the tag-site topic phrase passed to it.
_TAG_SITE_INTENT = (
    "epitope / peptide tag insertion for surface display — ecto-tagging and "
    "knock-in constructs that place a tag (HA, FLAG, Myc, ALFA, HiBiT, SpyTag, "
    "bungarotoxin-binding site, snorkel) in an extracellular loop or terminus, "
    "and their surface-display / functional validation"
)
_MAX_PROMPT_PAPERS = 25
_MAX_ABSTRACT_CHARS = 700
_MAX_FULLTEXT_CHARS = 1400
_MAX_FULLTEXT_PAPERS = 8
# Lightweight relevance triage: score a paper by how many tagging-methods terms it
# hits in title+abstract, so the full-text budget goes to the most on-topic papers.
_RELEVANCE_TERMS = (
    "epitope", "tag", "ha ", "flag", "myc", "alfa", "insert", "extracellular",
    "surface", "knock-in", "ectodomain", "loop", "fusion", "non-permeabilized",
)
_TOPO_CHAR = {"extracellular": "O", "intracellular": "I", "membrane": "M", "signal": "S"}


def _tag_relevance(paper: Paper) -> int:
    """Count of tagging-methods terms in title+abstract — the triage score."""
    text = f"{paper.title or ''} {paper.abstract or ''}".lower()
    return sum(term in text for term in _RELEVANCE_TERMS)


def format_candidate_papers(
    papers: dict[str, Paper],
    fulltext: dict[str, dict[str, str]] | None = None,
) -> str:
    """Render discovered papers as a prompt block the agent reads first. Papers are
    keyed by ``paper_source_id`` and now INCLUDE DOI-anchored preprints (the shared
    #143 contract), so there is no separate preprint list. Where METHODS/RESULTS
    full text is given, include it so the agent can pin the EXACT residue, judge
    function PRESERVED vs REDUCED/CONFOUNDED, AND copy a verbatim supporting_quote
    (which the pipeline then verifies)."""
    fulltext = fulltext or {}
    if not papers:
        return "CANDIDATE PAPERS: none retrieved by the lit-search; rely on web_search."
    lines = [
        "CANDIDATE PAPERS (pre-retrieved via EuropePMC + PubTator — read these FIRST and "
        "COPY a verbatim supporting_quote from the text below. For a PMID paper set "
        "supporting_pmid; for a PREPRINT (marked [preprint], no PMID) set "
        "supporting_pmid=null and cite the DOI. Where METHODS/RESULTS full text is given, "
        "use it to pin the EXACT residue AND to judge whether function was PRESERVED vs "
        "REDUCED/CONFOUNDED -> validation_level):"
    ]
    for sid, p in list(papers.items())[:_MAX_PROMPT_PAPERS]:
        ref = f"PMID {p.pmid}" if p.pmid else (f"DOI {p.doi}" if p.doi else sid)
        tag = " [preprint]" if p.is_preprint else ""
        abstract = " ".join((p.abstract or "").split())[:_MAX_ABSTRACT_CHARS]
        lines.append(f"- {ref}{tag} ({p.year or '?'}) {p.title}\n  ABSTRACT: {abstract}")
        for name in ("methods", "results"):
            body = (fulltext.get(sid) or {}).get(name)
            if body:
                lines.append(f"  {name.upper()}: {' '.join(body.split())[:_MAX_FULLTEXT_CHARS]}")
    return "\n".join(lines)


def _sort_key(s: TagSiteProposal) -> tuple[int, int, int, int]:
    """Validation strength first (surface+function best), then source tier
    (paper > patent > vendor), then source-verified citations ahead of unverified,
    then the model's own rank."""
    return (
        VALIDATION_RANK.get(s.validation_level, len(VALIDATION_LEVELS)),
        SOURCE_TIERS.index(s.source_tier) if s.source_tier in SOURCE_TIERS else len(SOURCE_TIERS),
        0 if s.entailment_verified else 1,
        s.rank,
    )


def rank_sites(result: TagSiteResult) -> TagSiteResult:
    """Drop non-validated sites, sort by validation+tier+entailment, renumber ``rank``."""
    keep_validated_sites(result)
    result.sites.sort(key=_sort_key)
    for i, s in enumerate(result.sites, start=1):
        s.rank = i
    return result


def _source_text_for(
    sid: str | None, papers: dict[str, Paper], fulltext: dict[str, dict[str, str]]
) -> str:
    """Abstract + methods + results text for one paper (by ``paper_source_id``) —
    the entailment source."""
    if not sid:
        return ""
    parts: list[str] = []
    p = papers.get(sid)
    if p and p.abstract:
        parts.append(p.abstract)
    ft = fulltext.get(sid) or {}
    parts += [ft.get("methods", ""), ft.get("results", "")]
    return "\n".join(x for x in parts if x)


def verify_entailment(
    result: TagSiteResult,
    *,
    papers: dict[str, Paper],
    fulltext: dict[str, dict[str, str]],
    http: CachedHTTP | None = None,
) -> TagSiteResult:
    """Set ``entailment_verified`` on each site: True iff its supporting_quote is
    found in the cited paper's source text (abstract + full text), falling back to
    the union of all fetched sources (preprints included — they are in ``papers``
    now) — so a hallucinated quote that appears in NO source is flagged. When
    ``http`` is given, a cited PMID that was NOT in the candidate set (e.g. the
    agent found it via web_search) is hydrated on demand and cached, so a real
    web-discovered citation can still be verified. Sites cite by ``supporting_pmid``;
    papers are keyed by ``paper_source_id``, so we map pmid -> source_id first."""
    all_text = "\n".join(_source_text_for(sid, papers, fulltext) for sid in papers)
    by_pmid = {p.pmid: sid for sid, p in papers.items() if p.pmid}
    hydrated: dict[int, str] = {}

    def _resolve(pmid: int | None) -> str:
        if not pmid:
            return ""
        sid = by_pmid.get(pmid)
        if sid is not None:
            return _source_text_for(sid, papers, fulltext)
        if http is None:
            return ""
        if pmid not in hydrated:
            try:
                hp = {
                    paper_source_id(p): p
                    for p in europepmc_bulk_by_pmid(
                        http=http, pmids=[pmid], retraction_index=_empty_retraction()
                    )
                    if p.pmid
                }
                hft = fetch_fulltext_sections(http=http, papers=hp, max_papers=1) if hp else {}
                hsid = next((s for s, pp in hp.items() if pp.pmid == pmid), None)
                hydrated[pmid] = _source_text_for(hsid, hp, hft)
            except Exception:  # noqa: BLE001 - verification is best-effort
                hydrated[pmid] = ""
        return hydrated[pmid]

    for s in result.sites:
        src = _resolve(s.supporting_pmid)
        s.entailment_verified = quote_supported(s.supporting_quote, src) or quote_supported(
            s.supporting_quote, all_text
        )
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
    """Discover papers (+ preprints, retraction-filtered) + full text, run the agent
    (papers + web_search), verify entailment, return a validated, ranked
    :class:`TagSiteResult`. ``aliases`` should include the protein name(s)."""
    client = client or get_client()
    http = http or open_default_client()
    usage_sink = usage_sink if usage_sink is not None else []

    try:
        ri = _retraction_from_http(http)  # best-effort Retraction Watch index
    except Exception:  # noqa: BLE001 - never block on the retraction fetch
        ri = _empty_retraction()

    papers = discover_tag_site_papers(
        http=http, gene_symbol=gene_symbol, aliases=aliases, retraction_index=ri
    )
    # web_search discovery complement (shared module, same as internalization): one
    # web_search pass whose cited PMIDs/DOIs are HYDRATED into real Papers and unioned
    # into the corpus (deterministic pool wins on collision). Web hits thus flow through
    # the SAME triage -> full-text -> entailment path, so the structured call needs NO
    # inline web_search tool and every citation stays id-anchored + verifiable.
    for wp in web_discover_papers(
        client,
        intent=_TAG_SITE_INTENT,
        gene_names=[protein_name, *aliases],
        http=http,
        retraction_index=ri,
        usage_sink=usage_sink,
    ):
        papers.setdefault(paper_source_id(wp), wp)
    # Relevance triage: fetch full text for the most on-topic papers first.
    ranked = dict(sorted(papers.items(), key=lambda kv: -_tag_relevance(kv[1])))
    fulltext = fetch_fulltext_sections(
        http=http, papers=ranked, max_papers=_MAX_FULLTEXT_PAPERS, retraction_index=ri
    )

    user_prompt = build_user_prompt(
        gene_symbol, protein_name, mode=mode, sequence=sequence, topology=topology
    )
    user_prompt = f"{user_prompt}\n\n{format_candidate_papers(ranked, fulltext)}"

    result = call_builder(
        client,
        system_prompt=SYSTEM_PROMPT,
        user_prompt=user_prompt,
        schema=TagSiteResult,
        usage_sink=usage_sink,
        label=f"tag_site:{gene_symbol}",
        max_tokens=32_000,  # 16k default truncated multi-site outputs (e.g. SLC6A4)
    )
    if result is None:
        return TagSiteResult(
            gene_symbol=gene_symbol,
            uniprot_accession=uniprot_accession,
            sequence_length=len(sequence or ""),
        )
    assert isinstance(result, TagSiteResult)  # expect_array=False -> single instance
    verify_entailment(result, papers=papers, fulltext=fulltext, http=http)
    return rank_sites(result)


def to_viewer_sites(result: TagSiteResult, *, uniprot_acc: str) -> list[dict[str, Any]]:
    """Convert to the viewer's ``literature_retrieved`` TaggedSite shape
    (viewer/lib/tag-sites-types.ts). Agent-only fields (validation_level,
    position_evidence, source_tier, entailment) fold into ``rationale``/``sources``
    so the viewer contract is unchanged."""
    out: list[dict[str, Any]] = []
    for s in result.sites:
        sources: list[dict[str, Any]] = []
        if s.supporting_pmid:
            # ``claim`` carries the verbatim supporting_quote (entailment-checked)
            # so the viewer's expandable drawer can show the exact sentence.
            sources.append(
                {
                    "pmid": s.supporting_pmid,
                    "citation": f"PMID {s.supporting_pmid}",
                    "claim": s.supporting_quote or None,
                }
            )
        elif s.supporting_quote:
            # Preprint / DOI-only citation with a quote but no PMID.
            sources.append({"citation": "preprint", "claim": s.supporting_quote})
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
                "residue_label": s.residue_label,
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
                    f"position: {s.position_evidence}; source: {s.source_tier}; "
                    f"entailment_verified: {s.entailment_verified}]"
                ),
                "sources": sources,
                "plddt": None,
                "conservation_rank": None,
                "median_conservation": None,
            }
        )
    return out
