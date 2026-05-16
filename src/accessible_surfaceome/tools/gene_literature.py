"""``gene_literature`` — NCBI gene2pubmed + Europe PMC search/abstract/fulltext.

Replaces the agent's instinct to call ``web_search`` 5× with different query
phrasings. Operates as a small cascade:

1. ``mode="gene2pubmed"`` — NCBI's curated gene→PMID list (highest precision,
   typically 5–50 PMIDs per gene). The agent should always start here.
2. ``mode="topic_search"`` — Europe PMC topic-anchored fill (recall, when
   gene2pubmed returns <5 PMIDs or you need surface-method-specific evidence).
3. ``mode="fetch_abstract"`` — single PMID with auto-tagged topic categories.
4. ``mode="fetch_fulltext"`` — PMC OA full-text only, capped at ~10k tokens
   with section truncation flags.

Each return carries deterministic ``topic_tags``, ``is_review``, and
``is_retracted`` flags computed in our process before tokens reach the agent
— so the agent prioritizes without re-reading.

The Europe PMC HTTP plumbing (search, full-text, JATS parsing) is in
``_shared/europepmc.py`` so the ``evidence_retrieval`` tool can reuse it.
"""

from __future__ import annotations

import logging
import os
from typing import Any

from ._shared.europepmc import (
    DEFAULT_PAGE_SIZE,
    europepmc_bulk_by_pmid,
    europepmc_search,
    fetch_fulltext,
    paper_from_europepmc,
)
from ._shared.http import CachedHTTP, open_default_client
from ._shared.models import (
    LiteratureMode,
    LiteraturePack,
    Paper,
    TopicAnchor,
)
from ._shared.retraction_watch import RetractionIndex, empty as _empty_retraction_index
from .evidence_retrieval import extract_paper_drafts
from .gene_lookup import resolve as _resolve

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------


_NCBI_TTL = 30

_NCBI_ELINK = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/elink.fcgi"


# Topic-anchor expansions. Used both for Europe PMC search-query construction
# and for post-fetch topic-tag detection. Keep these short and high-precision
# — the agent uses tag matches to prioritize papers, so false positives are
# worse than misses.
_TOPIC_TERMS: dict[TopicAnchor, list[str]] = {
    "surface_expression": [
        "cell surface",
        "cell-surface",
        "plasma membrane",
        "surface expression",
        "surface marker",
    ],
    "topology": [
        "transmembrane",
        "membrane topology",
        "GPI anchor",
        "GPI-anchor",
        "signal peptide",
    ],
    "ihc": [
        "immunohistochemistry",
        "IHC",
    ],
    "flow_cytometry": [
        "flow cytometry",
        "FACS",
    ],
    "surface_biotinylation": [
        "surface biotinylation",
        "cell surface biotinylation",
        "cell-surface biotinylation",
    ],
    "mass_spec_surfaceome": [
        "surfaceome",
        "surface proteome",
        "surface proteomics",
        "cell-surface proteomics",
    ],
    "structure": [
        "crystal structure",
        "cryo-EM",
        "cryo-electron",
        "cryoEM",
    ],
    "ptm": [
        "glycosylation",
        "phosphorylation",
        "lipidation",
        "palmitoylation",
    ],
    "shedding": [
        "shedding",
        "ectodomain",
        "soluble form",
    ],
}


def _detect_topic_tags(*texts: str) -> list[TopicAnchor]:
    """Return the topic anchors whose terms appear in title+abstract.

    Case-insensitive substring match. Order follows ``_TOPIC_TERMS``
    insertion order so the agent gets a stable ordering it can rely on.
    """
    haystack = " ".join(t for t in texts if t).lower()
    if not haystack:
        return []
    matched: list[TopicAnchor] = []
    for anchor, terms in _TOPIC_TERMS.items():
        for term in terms:
            if term.lower() in haystack:
                matched.append(anchor)
                break
    return matched


# ---------------------------------------------------------------------------
# Public dispatch
# ---------------------------------------------------------------------------


def gene_literature(
    *,
    mode: LiteratureMode,
    http: CachedHTTP | None = None,
    uniprot_acc: str | None = None,
    ncbi_gene_id: int | None = None,
    hgnc_symbol: str | None = None,
    aliases: list[str] | None = None,
    pmid: int | None = None,
    pmcid: str | None = None,
    topic_anchors: list[TopicAnchor] | None = None,
    max_results: int = DEFAULT_PAGE_SIZE,
    retraction_index: RetractionIndex | None = None,
) -> LiteraturePack | Paper:
    """Single dispatcher mirroring the registered tool schema.

    ``uniprot_acc`` is the simplest input: when provided we resolve it
    internally to ``ncbi_gene_id`` + ``hgnc_symbol`` + ``aliases`` via the
    cached gene_lookup pipeline. Callers who already have those values can
    pass them directly to skip the resolve hop.

    ``retraction_index`` is consulted alongside Europe PMC's pubTypeList
    "Retracted Publication" marker; when ``None`` we use the empty index
    (PMC's marker is the only signal). Pass an index built via
    :func:`accessible_surfaceome.tools._shared.retraction_watch.from_http`
    when you want Retraction Watch cross-referencing on every fetch.
    """

    own_client = http is None
    client = http or open_default_client()
    index = retraction_index if retraction_index is not None else _empty_retraction_index()
    try:
        if mode == "gene2pubmed":
            return _gene2pubmed(
                http=client,
                uniprot_acc=uniprot_acc,
                ncbi_gene_id=ncbi_gene_id,
                hgnc_symbol=hgnc_symbol,
                max_results=max_results,
                retraction_index=index,
            )
        if mode == "topic_search":
            if not topic_anchors:
                raise ValueError("topic_search requires at least one topic_anchor")
            return _topic_search(
                http=client,
                uniprot_acc=uniprot_acc,
                hgnc_symbol=hgnc_symbol,
                aliases=aliases,
                topic_anchors=topic_anchors,
                max_results=max_results,
                retraction_index=index,
            )
        if mode == "fetch_abstract":
            if pmid is None:
                raise ValueError("fetch_abstract requires a pmid")
            return _fetch_abstract(http=client, pmid=pmid, retraction_index=index)
        if mode == "fetch_fulltext":
            if not pmcid:
                raise ValueError("fetch_fulltext requires a pmcid")
            paper = fetch_fulltext(
                http=client,
                pmcid=pmcid,
                retraction_index=index,
                topic_tagger=_detect_topic_tags,
            )
            # Same paper-level draft extraction as fetch_abstract — covers
            # full-text fetches that don't route through evidence_retrieval.
            source_id = f"PMC:{paper.pmc_id}" if paper.pmc_id else f"PMID:{paper.pmid}"
            paper.evidence_claim_drafts = extract_paper_drafts(
                source_id=source_id,
                abstract=paper.abstract,
                sections=paper.sections,
            )
            return paper
        raise ValueError(f"unknown mode: {mode!r}")
    finally:
        if own_client:
            client.close()


# ---------------------------------------------------------------------------
# Mode implementations
# ---------------------------------------------------------------------------


def _gene2pubmed(
    *,
    http: CachedHTTP,
    uniprot_acc: str | None,
    ncbi_gene_id: int | None,
    hgnc_symbol: str | None,
    max_results: int,
    retraction_index: RetractionIndex,
) -> LiteraturePack:
    if ncbi_gene_id is None or not hgnc_symbol:
        if uniprot_acc is None:
            raise ValueError(
                "gene2pubmed requires ncbi_gene_id (preferred) or uniprot_acc to resolve from"
            )
        bundle = _resolve(uniprot_acc, http=http)
        if bundle.ncbi_gene_id is None:
            raise LookupError(
                f"no NCBI gene ID for {uniprot_acc} — gene2pubmed needs it; this protein "
                f"may have no curated PMIDs (try topic_search instead)."
            )
        ncbi_gene_id = bundle.ncbi_gene_id
        hgnc_symbol = hgnc_symbol or bundle.hgnc_symbol

    pmids = _ncbi_elink_gene_pubmed(http=http, ncbi_gene_id=ncbi_gene_id)
    if not pmids:
        return LiteraturePack(
            hgnc_symbol=hgnc_symbol or "",
            mode="gene2pubmed",
            papers=[],
            n_total=0,
            n_returned=0,
        )

    pmids_to_fetch = pmids[:max_results]
    papers = europepmc_bulk_by_pmid(
        http=http,
        pmids=pmids_to_fetch,
        retraction_index=retraction_index,
        topic_tagger=_detect_topic_tags,
    )
    # Preserve NCBI's ordering rather than Europe PMC's.
    by_pmid = {p.pmid: p for p in papers}
    ordered = [by_pmid[int(pmid)] for pmid in pmids_to_fetch if int(pmid) in by_pmid]
    return LiteraturePack(
        hgnc_symbol=hgnc_symbol or "",
        mode="gene2pubmed",
        papers=ordered,
        n_total=len(pmids),
        n_returned=len(ordered),
    )


def _topic_search(
    *,
    http: CachedHTTP,
    uniprot_acc: str | None,
    hgnc_symbol: str | None,
    aliases: list[str] | None,
    topic_anchors: list[TopicAnchor],
    max_results: int,
    retraction_index: RetractionIndex,
) -> LiteraturePack:
    if not hgnc_symbol:
        if uniprot_acc is None:
            raise ValueError("topic_search requires hgnc_symbol or uniprot_acc")
        bundle = _resolve(uniprot_acc, http=http)
        hgnc_symbol = bundle.hgnc_symbol
        if aliases is None:
            aliases = list(bundle.aliases)

    aliases = aliases or []
    name_terms = [hgnc_symbol, *aliases]
    name_disjunction = " OR ".join(f'"{n}"' for n in name_terms if n)
    topic_terms: list[str] = []
    for anchor in topic_anchors:
        topic_terms.extend(_TOPIC_TERMS.get(anchor, []))
    if not topic_terms:
        raise ValueError(f"no known terms for topic_anchors={topic_anchors!r}")
    topic_disjunction = " OR ".join(f'"{t}"' for t in topic_terms)
    query = f"({name_disjunction}) AND ({topic_disjunction}) AND SRC:MED"

    payload = europepmc_search(http=http, query=query, page_size=max_results)
    hits = (payload.get("resultList") or {}).get("result") or []
    papers = [
        paper_from_europepmc(
            record, retraction_index=retraction_index, topic_tagger=_detect_topic_tags
        )
        for record in hits
    ]
    return LiteraturePack(
        hgnc_symbol=hgnc_symbol,
        mode="topic_search",
        papers=papers,
        n_total=int(payload.get("hitCount") or len(papers)),
        n_returned=len(papers),
        topic_anchors_used=list(topic_anchors),
    )


def _fetch_abstract(
    *, http: CachedHTTP, pmid: int, retraction_index: RetractionIndex
) -> Paper:
    payload = europepmc_search(
        http=http, query=f"EXT_ID:{pmid} AND SRC:MED", page_size=1
    )
    hits = (payload.get("resultList") or {}).get("result") or []
    if not hits:
        raise LookupError(f"PMID:{pmid} not found in Europe PMC (MED source)")
    paper = paper_from_europepmc(
        hits[0], retraction_index=retraction_index, topic_tagger=_detect_topic_tags
    )
    # Pre-extract verbatim-anchored drafts so A2 can adopt quotes without
    # paraphrasing — GPR75 audit (2026-05-15) found 6/6 unanchored rows
    # came from gene_literature paths where no drafts were emitted.
    source_id = f"PMC:{paper.pmc_id}" if paper.pmc_id else f"PMID:{paper.pmid}"
    paper.evidence_claim_drafts = extract_paper_drafts(
        source_id=source_id, abstract=paper.abstract, sections=paper.sections
    )
    return paper


# ---------------------------------------------------------------------------
# NCBI E-utils helpers
# ---------------------------------------------------------------------------


def _ncbi_elink_gene_pubmed(*, http: CachedHTTP, ncbi_gene_id: int) -> list[str]:
    params: dict[str, Any] = {
        "dbfrom": "gene",
        "db": "pubmed",
        "id": str(ncbi_gene_id),
        "linkname": "gene_pubmed",
        "retmode": "json",
    }
    api_key = os.environ.get("NCBI_API_KEY")
    if api_key:
        params["api_key"] = api_key
    payload = http.get_json(_NCBI_ELINK, source="ncbi", ttl_days=_NCBI_TTL, params=params)
    linksets = payload.get("linksets") or []
    if not linksets:
        return []
    linksetdbs = linksets[0].get("linksetdbs") or []
    if not linksetdbs:
        return []
    return list(linksetdbs[0].get("links") or [])


__all__ = ["gene_literature"]
