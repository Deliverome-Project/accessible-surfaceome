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
5. ``mode="recent_corpus"`` — PubTator entity-anchored ``@GENE_<SYMBOL>``
   sweep sorted by date (no topic narrowing), paginated, then pre-filtered
   on the abstract for surface/membrane keywords. Catches verdict-shifting
   recent papers whose core concept the planner couldn't have keyword-
   anchored (e.g. a paper introducing new vocabulary). See the SRC sample:
   Delaveris 2026 *Science* — "Autophagolysosomal exocytosis inverts Src
   kinase onto the cell surface in cancer" — was indexed by PubTator but
   scored low on every methodology-category query because its concepts
   ("inverts", "autophagolysosomal exocytosis") were absent from the
   per-category terms.

Each return carries deterministic ``topic_tags``, ``is_review``, and
``is_retracted`` flags computed in our process before tokens reach the agent
— so the agent prioritizes without re-reading.

The Europe PMC HTTP plumbing (search, full-text, JATS parsing) is in
``_shared/europepmc.py`` so the ``evidence_retrieval`` tool can reuse it.
"""

from __future__ import annotations

import logging
import os
import re
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
from ._shared.pubtator import build_gene_entity_query, pubtator_search
from ._shared.retraction_watch import RetractionIndex, empty as _empty_retraction_index
from .evidence_retrieval import extract_paper_drafts
from .gene_lookup import resolve as _resolve

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------


_NCBI_TTL = 30

_NCBI_ELINK = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/elink.fcgi"


# recent_corpus tuning. The query uses ``@GENE_<SYMBOL> surface`` (not
# bare ``@GENE_<SYMBOL>``) so PubTator's per-token relevance scoring
# biases the date-sorted return toward surface-relevant papers. Empirical
# calibration over the hard-gene set (SRC, WT1, CD81, GPR75, ATP5F1B,
# HSPA5, EGFR, VIM, CLDN18):
#
# * The one-term suffix shrinks SRC's PubTator hit count from 55,418
#   → 22,646 *and* moves the Delaveris 2026 *Science* verdict-shifter
#   (PMID 41818370) from rank #174 → rank #38. Five pages × 10 hits =
#   50 candidates safely covers it.
# * Adding *more* terms (``surface membrane extracellular shed
#   exocytosis ectodomain``) is counterproductive — PubTator collapses
#   to multi-topic review papers that hit every term, and Delaveris
#   drops out of the top 20. One term is the sweet spot.
# * On quiet/orphan genes the suffix doesn't starve results: GPR75
#   still returns 99 hits, ATP5F1B 522, CLDN18 640 — plenty to fill
#   50 candidates without needing a bare-gene fallback.
#
# The abstract filter below is a coarse safety net (defense-in-depth
# against papers PubTator ranks in for ``surface`` reasons unrelated
# to surface biology — e.g. a paper about "tumor surface area") but
# is mostly a no-op now that the query itself is surface-biased.
_RECENT_CORPUS_PAGES = 5
_RECENT_CORPUS_QUERY_SUFFIX = "surface"
_RECENT_CORPUS_SURFACE_FILTER = re.compile(
    r"\b(surface|membrane|extracellular|"
    r"surfaceome|ectopic|inverted|externaliz|"
    r"localiz|accessib|cell[-\s]surface|plasma\s*membrane|"
    r"shed(?:ding)?|exocytos|ectodomain)\b",
    re.IGNORECASE,
)


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
        # Soluble/shed TARGET measured in circulation — the signal that
        # distinguishes a real decoy from a merely-annotated soluble isoform.
        "soluble ectodomain",
        "circulating",
        "serum level",
        "plasma level",
    ],
    "normal_tissue_expression": [
        # Six high-consequence tox organs, anchored on SURFACE expression —
        # NOT a tissue-distribution / microarray (RNA-atlas) survey. Surface
        # proof comes from the always-on protein method categories; this anchor
        # supplies the organ-coverage literature for on-target/off-tumor tox.
        "surface expression",
        "liver",
        "lung",
        "kidney",
        "intestine",
        "heart",
        "brain",
    ],
    "surface_reachability": [
        # Physical access barriers — a protein can be surface-present yet
        # unreachable by a systemically dosed binder.
        "blood-brain barrier",
        "tumor penetration",
        "luminal",
        "abluminal",
        # Binder-access vocabulary (qualified — bare "accessibility" would
        # pull chromatin-accessibility / ATAC-seq noise).
        "surface accessibility",
        "antibody accessibility",
        "epitope accessibility",
    ],
    "partner_dependency": [
        # Does a partner have to be present for the target to reach the
        # surface? Feeds co_receptor_requirements.
        "obligate heterodimer",
        "co-receptor",
        "coreceptor",
        "escort protein",
        "chaperone-assisted",
        "trafficking partner",
        "accessory subunit",
        "auxiliary subunit",
        "required for surface expression",
    ],
    "membrane_subdomain": [
        # Where in the plasma membrane — a binder may not reach a restricted
        # subdomain. Feeds restricted_subdomain + anatomical accessibility.
        "lipid raft",
        "membrane microdomain",
        "tight junction",
        "apical membrane",
        "basolateral",
        "lateral membrane",
        "primary cilium",
        "ciliary membrane",
        "polarized epithelial",
        "immunological synapse",
    ],
    "epitope_masking": [
        # Evidence the extracellular epitope is occluded, spanning the three
        # mechanism axes the epitope_masking risk records. Feeds
        # epitope_masking.mechanism (homo / hetero / other).
        "epitope masking",
        "steric occlusion",
        # HOMO — the target's own homodimer / homo-oligomer interface
        "homodimer",
        "homodimerization",
        "oligomerization",
        "self-association",
        # HETERO — a partner protein in a complex covers the epitope
        "heterodimer",
        # OTHER — glycan shield / conformational occlusion
        "glycan shield",
        "conformational masking",
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
    previous_symbols: list[str] | None = None,
    pmid: int | None = None,
    pmcid: str | None = None,
    topic_anchors: list[TopicAnchor] | None = None,
    max_results: int = DEFAULT_PAGE_SIZE,
    retraction_index: RetractionIndex | None = None,
) -> LiteraturePack | Paper:
    """Single dispatcher mirroring the registered tool schema.

    ``uniprot_acc`` is the simplest input: when provided we resolve it
    internally to ``ncbi_gene_id`` + ``hgnc_symbol`` + ``aliases`` +
    ``previous_symbols`` via the cached gene_lookup pipeline. Callers who
    already have those values can pass them directly to skip the resolve hop.

    ``previous_symbols`` are HGNC's prior approved symbols (HGNC's
    ``prev_symbol`` field). Renamed genes (e.g. STING1 was TMEM173until
    2020) lose their pre-rename Europe PMC hits unless these are OR'd into
    the topic-search disjunction alongside ``hgnc_symbol`` + ``aliases``.
    PubTator's NER (used by ``recent_corpus``) + NCBI's gene2pubmed link
    table (used by ``gene2pubmed``) both normalize across symbol revisions
    upstream, so this param only affects the ``topic_search`` Europe PMC
    path.

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
                previous_symbols=previous_symbols,
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
        if mode == "recent_corpus":
            # Default cap = DEFAULT_PAGE_SIZE (25). The surface-anchored
            # PubTator query + 5 pages caps the upstream candidate pool
            # at ~50; the abstract filter passes most of them since the
            # query is already surface-biased; 25 returned papers is
            # plenty for the selector to see the verdict-shifter.
            return _recent_corpus(
                http=client,
                uniprot_acc=uniprot_acc,
                hgnc_symbol=hgnc_symbol,
                aliases=aliases,
                max_results=max_results,
                retraction_index=index,
            )
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
    previous_symbols: list[str] | None,
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
        if previous_symbols is None:
            previous_symbols = list(bundle.previous_symbols)

    aliases = aliases or []
    previous_symbols = previous_symbols or []
    # Dedup while preserving order. ``aliases`` + ``previous_symbols`` often
    # overlap (HGNC moves rejected aliases into previous_symbols), so a
    # naive concat blows the query length without adding coverage. Drop
    # empties + the current hgnc_symbol from the supplement so it isn't
    # quoted twice. Dedupe case-insensitively because Europe PMC's search
    # is case-insensitive anyway; this just avoids double-quoting the same
    # term in different casings (e.g. "PDL1" vs "PDl1").
    #
    # Note (2026-06-06 audit): we audited adding UniProt protein short
    # names + HGNC descriptive full names and dropped both. HGNC aliases
    # turn out to already cover virtually every paper-canonical short form
    # case-insensitively (CD274's ``PD-L1`` is in aliases; STING1's
    # ``MITA`` / ``ERIS`` / ``hSTING`` are in aliases). UniProt's
    # ``shortNames`` arrays mostly hold obscure historical labels
    # (``MLN 19`` for ERBB2) or repeat what HGNC already covers; the
    # descriptive HGNC names like ``"cholinergic receptor, nicotinic,
    # alpha 7 (neuronal)"`` rarely match paper titles verbatim.
    seen_lower: set[str] = {hgnc_symbol.lower()} if hgnc_symbol else set()
    supplement: list[str] = []
    for n in [*aliases, *previous_symbols]:
        if not n:
            continue
        key = n.lower()
        if key in seen_lower:
            continue
        seen_lower.add(key)
        supplement.append(n)
    name_terms = [hgnc_symbol, *supplement]
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


def _recent_corpus(
    *,
    http: CachedHTTP,
    uniprot_acc: str | None,
    hgnc_symbol: str | None,
    aliases: list[str] | None,
    max_results: int,
    retraction_index: RetractionIndex,
) -> LiteraturePack:
    """Topic-blind, date-sorted PubTator sweep + abstract-keyword pre-filter.

    Pulls ``_RECENT_CORPUS_PAGES`` pages of PubTator ``@GENE_<SYMBOL>``
    hits sorted by indexing date (descending), resolves PMIDs to abstracts
    via one EuropePMC bulk call, and keeps only papers whose abstract
    contains at least one surface/membrane-vocabulary token (regex defined
    at module scope). The remaining papers are returned as a
    ``LiteraturePack`` so the planner's trim/select pipeline can decide
    which deserve a full-text fetch.

    The point of being topic-blind is to defeat the keyword chicken-and-egg
    problem: a paper that introduces *new* surface-biology vocabulary
    (e.g. Delaveris 2026's "autophagolysosomal exocytosis inverts SRC onto
    the cell surface") will not score high on any pre-defined methodology
    category, so the only way to surface it is to look at the gene's
    recent literature regardless of topic and let an LLM judge relevance.
    The abstract pre-filter is a coarse cost-control gate (drops ~75% of
    pure-signaling-pathway noise on prolific genes), not a quality gate.
    """
    if not hgnc_symbol:
        if uniprot_acc is None:
            raise ValueError("recent_corpus requires hgnc_symbol or uniprot_acc")
        bundle = _resolve(uniprot_acc, http=http)
        hgnc_symbol = bundle.hgnc_symbol
        if aliases is None:
            aliases = list(bundle.aliases)

    query = build_gene_entity_query(hgnc_symbol, _RECENT_CORPUS_QUERY_SUFFIX)
    pmids: list[int] = []
    seen: set[int] = set()
    for page in range(1, _RECENT_CORPUS_PAGES + 1):
        try:
            result = pubtator_search(http=http, query=query, page=page, sort="date desc")
        except Exception as exc:  # noqa: BLE001 — degrade gracefully on partial PubTator failure
            logger.warning(
                "recent_corpus: PubTator page %d failed for %r: %s", page, query, exc
            )
            break
        new_this_page = 0
        for hit in result.hits:
            if hit.pmid in seen:
                continue
            seen.add(hit.pmid)
            pmids.append(hit.pmid)
            new_this_page += 1
        # PubTator returns fewer hits on later pages once the corpus is
        # exhausted; bail early to skip a wasted round-trip.
        if new_this_page == 0:
            break

    if not pmids:
        return LiteraturePack(
            hgnc_symbol=hgnc_symbol,
            mode="recent_corpus",
            papers=[],
            n_total=0,
            n_returned=0,
        )

    try:
        resolved = europepmc_bulk_by_pmid(
            http=http,
            pmids=pmids,
            retraction_index=retraction_index,
            topic_tagger=_detect_topic_tags,
        )
    except Exception as exc:  # noqa: BLE001
        logger.warning("recent_corpus: EuropePMC bulk-by-pmid failed: %s", exc)
        return LiteraturePack(
            hgnc_symbol=hgnc_symbol,
            mode="recent_corpus",
            papers=[],
            n_total=len(pmids),
            n_returned=0,
        )

    # Coarse abstract-keyword pre-filter. Title is included because short
    # Letters / Reports sometimes carry the surface vocabulary only in
    # the title (Delaveris 2026 is one such case).
    papers: list[Paper] = []
    for paper in resolved:
        haystack = f"{paper.title or ''} {paper.abstract or ''}"
        if not _RECENT_CORPUS_SURFACE_FILTER.search(haystack):
            continue
        papers.append(paper)
        if len(papers) >= max_results:
            break

    return LiteraturePack(
        hgnc_symbol=hgnc_symbol,
        mode="recent_corpus",
        papers=papers,
        n_total=len(pmids),
        n_returned=len(papers),
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
