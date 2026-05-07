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
"""

from __future__ import annotations

import logging
import os
import re
import xml.etree.ElementTree as ET
from datetime import UTC, datetime
from collections.abc import Sequence
from typing import Any, Literal

from ._shared.http import CachedHTTP, open_default_client
from ._shared.models import (
    LiteratureMode,
    LiteraturePack,
    Paper,
    PaperSection,
    PublicationType,
    TopicAnchor,
)
from ._shared.retraction_watch import RetractionIndex, empty as _empty_retraction_index
from .gene_lookup import resolve as _resolve

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------


_NCBI_TTL = 30
_EUROPEPMC_TTL = 30
_FULLTEXT_TTL = 365  # PMC OA articles don't change after deposition

_DEFAULT_PAGE_SIZE = 25
_FULLTEXT_TOKEN_CAP = 10_000  # ~40k chars at 4 chars/token
_FULLTEXT_CHAR_CAP = _FULLTEXT_TOKEN_CAP * 4

_NCBI_ELINK = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/elink.fcgi"
_EUROPEPMC_SEARCH = "https://www.ebi.ac.uk/europepmc/webservices/rest/search"
_EUROPEPMC_FULLTEXT = "https://www.ebi.ac.uk/europepmc/webservices/rest/{pmcid}/fullTextXML"


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
    max_results: int = _DEFAULT_PAGE_SIZE,
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
            return _fetch_fulltext(http=client, pmcid=pmcid, retraction_index=index)
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
    papers = _europepmc_bulk_by_pmid(
        http=http, pmids=pmids_to_fetch, retraction_index=retraction_index
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

    payload = _europepmc_search(http=http, query=query, page_size=max_results)
    hits = (payload.get("resultList") or {}).get("result") or []
    papers = [_paper_from_europepmc(record, retraction_index=retraction_index) for record in hits]
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
    payload = _europepmc_search(
        http=http, query=f"EXT_ID:{pmid} AND SRC:MED", page_size=1
    )
    hits = (payload.get("resultList") or {}).get("result") or []
    if not hits:
        raise LookupError(f"PMID:{pmid} not found in Europe PMC (MED source)")
    return _paper_from_europepmc(hits[0], retraction_index=retraction_index)


def _fetch_fulltext(
    *, http: CachedHTTP, pmcid: str, retraction_index: RetractionIndex
) -> Paper:
    cleaned = pmcid.strip().upper()
    if not cleaned.startswith("PMC"):
        cleaned = f"PMC{cleaned}"
    if not re.fullmatch(r"PMC\d+", cleaned):
        raise ValueError(f"unrecognized pmcid {pmcid!r}; expected 'PMC' + digits")

    # First fetch the metadata so we have title/year/journal/authors etc.
    # Search across MED (PMID-indexed) and PMC (PMC-only-indexed) — most papers
    # surface in MED with pmcid attached; older PMC-only deposits without a
    # PMID need the PMC source.
    metadata_payload = _europepmc_search(
        http=http, query=f"PMCID:{cleaned}", page_size=1
    )
    hits = (metadata_payload.get("resultList") or {}).get("result") or []
    if not hits:
        raise LookupError(
            f"{cleaned} not found in Europe PMC search — may not be indexed yet"
        )
    base = _paper_from_europepmc(hits[0], retraction_index=retraction_index)

    xml_text = http.get_text(
        _EUROPEPMC_FULLTEXT.format(pmcid=cleaned),
        source="europepmc_fulltext",
        ttl_days=_FULLTEXT_TTL,
    )
    sections, truncated_section_names = _parse_jats_sections(xml_text)

    # Re-tag using the full text rather than just the abstract.
    full_text_for_tags = (base.abstract or "") + "\n" + "\n".join(s.text for s in sections)
    base.topic_tags = _detect_topic_tags(full_text_for_tags, base.title)
    base.sections = sections
    base.truncated_sections = truncated_section_names
    return base


# ---------------------------------------------------------------------------
# Europe PMC client helpers
# ---------------------------------------------------------------------------


def _europepmc_search(
    *, http: CachedHTTP, query: str, page_size: int = _DEFAULT_PAGE_SIZE
) -> dict[str, Any]:
    params = {
        "query": query,
        "format": "json",
        "pageSize": str(page_size),
        "resultType": "core",
    }
    return http.get_json(
        _EUROPEPMC_SEARCH, source="europepmc", ttl_days=_EUROPEPMC_TTL, params=params
    )


def _europepmc_bulk_by_pmid(
    *, http: CachedHTTP, pmids: Sequence[int | str], retraction_index: RetractionIndex
) -> list[Paper]:
    if not pmids:
        return []
    # Europe PMC search supports OR'd EXT_ID queries up to a few hundred terms.
    pmid_disjunction = " OR ".join(f"EXT_ID:{p}" for p in pmids)
    payload = _europepmc_search(
        http=http,
        query=f"({pmid_disjunction}) AND SRC:MED",
        page_size=len(pmids),
    )
    hits = (payload.get("resultList") or {}).get("result") or []
    return [_paper_from_europepmc(record, retraction_index=retraction_index) for record in hits]


def _paper_from_europepmc(
    record: dict[str, Any], *, retraction_index: RetractionIndex
) -> Paper:
    pmid_raw = record.get("pmid") or record.get("id")
    if pmid_raw is None:
        raise LookupError("Europe PMC record missing pmid/id")
    try:
        pmid = int(pmid_raw)
    except (TypeError, ValueError) as exc:
        raise LookupError(f"non-integer PMID in Europe PMC record: {pmid_raw!r}") from exc

    pmcid = record.get("pmcid") or None
    doi = record.get("doi") or None
    year = _safe_int(record.get("pubYear"))
    title = (record.get("title") or "").rstrip(".")
    abstract = record.get("abstractText") or None
    journal = record.get("journalTitle") or None
    pub_type_list = (record.get("pubTypeList") or {}).get("pubType") or []
    if isinstance(pub_type_list, str):
        pub_type_list = [pub_type_list]

    publication_type = _classify_publication_type(pub_type_list)
    is_review = any("review" in p.lower() for p in pub_type_list) or publication_type == "review"
    is_retracted, retraction_checked_at = _check_retraction(
        pub_type_list, pmid=pmid, doi=doi, index=retraction_index
    )
    is_pmc_oa = (record.get("isOpenAccess") or "N") == "Y" and bool(pmcid)
    authors = _extract_authors(record)

    topic_tags = _detect_topic_tags(abstract or "", title)

    return Paper(
        pmid=pmid,
        pmc_id=pmcid,
        doi=doi,
        year=year,
        journal=journal,
        title=title,
        abstract=abstract,
        authors=authors,
        publication_type=publication_type,
        is_review=is_review,
        is_retracted=is_retracted,
        retraction_checked_at=retraction_checked_at,
        is_pmc_oa=is_pmc_oa,
        topic_tags=topic_tags,
    )


def _extract_authors(record: dict[str, Any]) -> list[str]:
    """Pull authors from Europe PMC's ``authorList.author[].fullName`` (preferred,
    structured) with a fallback to splitting ``authorString`` (comma-separated)
    when the structured list is missing.
    """

    structured = ((record.get("authorList") or {}).get("author") or [])
    if structured:
        out: list[str] = []
        for a in structured:
            name = (a.get("fullName") or "").strip()
            if name:
                out.append(name)
        if out:
            return out
    raw = record.get("authorString") or ""
    return [a.strip().rstrip(".") for a in raw.split(",") if a.strip()]


# ---------------------------------------------------------------------------
# NCBI E-utils helpers
# ---------------------------------------------------------------------------


def _ncbi_elink_gene_pubmed(*, http: CachedHTTP, ncbi_gene_id: int) -> list[str]:
    params = {
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


# ---------------------------------------------------------------------------
# JATS XML parser
# ---------------------------------------------------------------------------


_SectionName = Literal["intro", "methods", "results", "discussion", "figure_legends"]


# Map JATS @sec-type and section-title keywords to our enum.
_SEC_TYPE_MAP: dict[str, _SectionName] = {
    "intro": "intro",
    "introduction": "intro",
    "background": "intro",
    "materials|methods": "methods",
    "methods": "methods",
    "experimental-procedures": "methods",
    "results": "results",
    "discussion": "discussion",
    "conclusions": "discussion",
}

_TITLE_KEYWORD_MAP: list[tuple[re.Pattern[str], _SectionName]] = [
    (re.compile(r"\bintroduct", re.IGNORECASE), "intro"),
    (re.compile(r"\bbackground", re.IGNORECASE), "intro"),
    (re.compile(r"\bmaterials? and methods\b", re.IGNORECASE), "methods"),
    (re.compile(r"\bmethods\b", re.IGNORECASE), "methods"),
    (re.compile(r"\bexperimental procedures\b", re.IGNORECASE), "methods"),
    (re.compile(r"\bresults\b", re.IGNORECASE), "results"),
    (re.compile(r"\bdiscussion\b", re.IGNORECASE), "discussion"),
    (re.compile(r"\bconclusions?\b", re.IGNORECASE), "discussion"),
]


def _parse_jats_sections(xml_text: str) -> tuple[list[PaperSection], list[str]]:
    """Parse JATS XML into our PaperSection list.

    Returns the section list and the names of any sections truncated to fit the
    per-paper character budget. Bibliography (``<ref-list>``), tables, and
    quotation-style figures are deliberately excluded.
    """

    try:
        root = ET.fromstring(xml_text)
    except ET.ParseError as exc:
        logger.warning("JATS parse failed: %s", exc)
        return [], []

    body = root.find(".//body")
    sections_by_name: dict[_SectionName, list[str]] = {}
    figure_legends: list[str] = []

    if body is not None:
        for sec in body.findall(".//sec"):
            name = _classify_section(sec)
            if name is None:
                continue
            text = _extract_section_text(sec)
            if text:
                sections_by_name.setdefault(name, []).append(text)
        for fig in root.findall(".//fig"):
            caption = fig.find(".//caption")
            if caption is None:
                continue
            text = _extract_node_text(caption)
            if text:
                figure_legends.append(text)
    if figure_legends:
        sections_by_name["figure_legends"] = figure_legends

    # Build the ordered list and apply the char cap proportionally.
    ordered_names: list[_SectionName] = ["intro", "methods", "results", "discussion", "figure_legends"]
    raw: list[tuple[_SectionName, str]] = []
    for n in ordered_names:
        chunks = sections_by_name.get(n) or []
        if chunks:
            raw.append((n, "\n\n".join(chunks)))

    sections, truncated = _apply_char_cap(raw, _FULLTEXT_CHAR_CAP)
    return sections, truncated


def _classify_section(sec: ET.Element) -> _SectionName | None:
    sec_type = (sec.attrib.get("sec-type") or "").lower()
    if sec_type in _SEC_TYPE_MAP:
        return _SEC_TYPE_MAP[sec_type]
    title_el = sec.find("title")
    title = (title_el.text or "") if title_el is not None else ""
    for pattern, name in _TITLE_KEYWORD_MAP:
        if pattern.search(title):
            return name
    return None


def _extract_section_text(sec: ET.Element) -> str:
    parts: list[str] = []
    for p in sec.findall(".//p"):
        text = _extract_node_text(p)
        if text:
            parts.append(text)
    return "\n".join(parts)


def _extract_node_text(node: ET.Element) -> str:
    """Concatenate all text content under a node, stripping XML markup and
    collapsing whitespace runs."""

    return " ".join(" ".join(node.itertext()).split())


def _apply_char_cap(
    raw: list[tuple[_SectionName, str]], cap: int
) -> tuple[list[PaperSection], list[str]]:
    total = sum(len(t) for _, t in raw)
    if total <= cap:
        return [PaperSection(name=n, text=t, truncated=False) for n, t in raw], []

    # Truncate sections proportionally to their original size; flag every
    # section that lost content.
    sections: list[PaperSection] = []
    truncated: list[str] = []
    for n, t in raw:
        share = max(int(cap * (len(t) / total)), 200)
        if len(t) > share:
            t = t[: share - 1].rstrip() + "…"
            truncated.append(n)
            sections.append(PaperSection(name=n, text=t, truncated=True))
        else:
            sections.append(PaperSection(name=n, text=t, truncated=False))
    return sections, truncated


# ---------------------------------------------------------------------------
# Topic tag detection + classification helpers
# ---------------------------------------------------------------------------


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


def _classify_publication_type(pub_types: list[str]) -> PublicationType:
    """Map Europe PMC's pubTypeList to our compact PublicationType literal."""

    lower = [p.lower() for p in pub_types]
    if any("preprint" in p for p in lower):
        return "preprint"
    if any("meta-analysis" in p for p in lower):
        return "meta_analysis"
    if any("review-article" == p or "systematic review" in p or "review" == p for p in lower):
        return "review"
    if any("research-article" == p for p in lower):
        return "primary_research"
    if any("case-report" in p or "letter" in p or "editorial" in p for p in lower):
        return "other"
    return "other"


def _check_retraction(
    pub_types: list[str],
    *,
    pmid: int | None = None,
    doi: str | None = None,
    index: RetractionIndex | None = None,
) -> tuple[bool, datetime]:
    """Two-step retraction check: PMC's pubTypeList + Retraction Watch index.

    Either signal flips ``is_retracted`` to ``True``. The timestamp is
    *now* whenever we ran the check — the cached Retraction Watch CSV's
    age is bounded by its TTL, so a fresh check timestamp accurately
    reflects the latest indexed state.
    """

    now = datetime.now(UTC)
    for p in pub_types:
        lower = p.lower()
        if "retracted publication" in lower or "retraction of publication" in lower:
            return True, now
    if index is not None and index.is_retracted(pmid=pmid, doi=doi):
        return True, now
    return False, now


def _safe_int(value: Any) -> int | None:
    try:
        return int(value) if value is not None else None
    except (TypeError, ValueError):
        return None


__all__ = ["gene_literature"]
