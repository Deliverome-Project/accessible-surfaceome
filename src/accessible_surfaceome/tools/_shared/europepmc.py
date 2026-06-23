"""Shared Europe PMC / PMC OA client helpers.

Lifted out of ``gene_literature.py`` so ``evidence_retrieval`` can reuse
the same search + full-text + JATS-parsing pipeline without circular
imports. ``gene_literature`` re-exports these names for back-compat.

Two surfaces:

* :func:`europepmc_search` — POST/GET against Europe PMC's REST search
  (cached). Generic enough to drive ``gene_literature``'s topic-search
  and ``evidence_retrieval``'s category-specific queries.
* :func:`fetch_fulltext` — single-PMCID full-text fetch with JATS-XML
  section parsing + char-cap truncation. Returns the same ``Paper``
  model both callers consume.

Topic-tag detection helpers stay private to ``gene_literature`` (they
encode the agent-facing anchor vocabulary; new tools that need
category-specific term lists should ship their own).
"""

from __future__ import annotations

import logging
import re
import xml.etree.ElementTree as ET
from collections.abc import Callable, Sequence
from datetime import UTC, datetime
from typing import Any, Literal

import httpx

from .http import CachedHTTP
from .models import Paper, PaperSection, PublicationType, TopicAnchor
from .ncbi import add_ncbi_api_key_param
from .retraction_watch import RetractionIndex

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------


EUROPEPMC_TTL = 30
FULLTEXT_TTL = 365  # PMC OA articles don't change after deposition

DEFAULT_PAGE_SIZE = 25
FULLTEXT_TOKEN_CAP = 10_000  # ~40k chars at 4 chars/token
FULLTEXT_CHAR_CAP = FULLTEXT_TOKEN_CAP * 4

EUROPEPMC_SEARCH = "https://www.ebi.ac.uk/europepmc/webservices/rest/search"
EUROPEPMC_FULLTEXT = "https://www.ebi.ac.uk/europepmc/webservices/rest/{pmcid}/fullTextXML"
NCBI_PMC_EFETCH = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/efetch.fcgi"
NCBI_PUBMED_ESEARCH = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi"
NCBI_PUBMED_EFETCH = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/efetch.fcgi"


# ---------------------------------------------------------------------------
# Search + bulk PMID lookup
# ---------------------------------------------------------------------------


def europepmc_search(
    *, http: CachedHTTP, query: str, page_size: int = DEFAULT_PAGE_SIZE
) -> dict[str, Any]:
    """Issue one search request against Europe PMC's REST API.

    Returns the raw JSON payload (the caller decodes ``resultList.result``
    into Papers via :func:`paper_from_europepmc`).
    """
    params = {
        "query": query,
        "format": "json",
        "pageSize": str(page_size),
        "resultType": "core",
    }
    return http.get_json(
        EUROPEPMC_SEARCH, source="europepmc", ttl_days=EUROPEPMC_TTL, params=params
    )


def europepmc_bulk_by_pmid(
    *,
    http: CachedHTTP,
    pmids: Sequence[int | str],
    retraction_index: RetractionIndex,
    topic_tagger: "TopicTagger | None" = None,
) -> list[Paper]:
    """Resolve a PMID batch to :class:`Paper` records.

    Europe PMC is the convenience path because it returns compact JSON with
    PMCID/OA metadata in one request. NCBI PubMed ``efetch`` is the fallback:
    it keeps PubTator / gene2pubmed / recent_corpus usable when Europe PMC is
    flaky, and also backfills individual PMIDs missing from an otherwise
    successful Europe PMC batch response.
    """
    if not pmids:
        return []
    ordered_pmids = _dedupe_pmids(pmids)
    pmid_disjunction = " OR ".join(f"EXT_ID:{p}" for p in ordered_pmids)
    papers_by_pmid: dict[int, Paper] = {}
    try:
        payload = europepmc_search(
            http=http,
            query=f"({pmid_disjunction}) AND SRC:MED",
            page_size=len(ordered_pmids),
        )
        hits = (payload.get("resultList") or {}).get("result") or []
        for record in hits:
            paper = paper_from_europepmc(
                record, retraction_index=retraction_index, topic_tagger=topic_tagger
            )
            papers_by_pmid[paper.pmid] = paper
    except Exception as exc:  # noqa: BLE001
        logger.warning(
            "Europe PMC PMID batch lookup failed for %d PMIDs; falling back to NCBI: %s",
            len(ordered_pmids),
            exc,
        )

    missing = [p for p in ordered_pmids if p not in papers_by_pmid]
    if missing:
        for paper in _ncbi_pubmed_fetch_by_pmids(
            http=http,
            pmids=missing,
            retraction_index=retraction_index,
            topic_tagger=topic_tagger,
        ):
            papers_by_pmid.setdefault(paper.pmid, paper)

    return [papers_by_pmid[p] for p in ordered_pmids if p in papers_by_pmid]


def ncbi_pubmed_search(
    *,
    http: CachedHTTP,
    query: str,
    page_size: int = DEFAULT_PAGE_SIZE,
    retraction_index: RetractionIndex,
    topic_tagger: "TopicTagger | None" = None,
) -> list[Paper]:
    """Search PubMed via NCBI ESearch, then hydrate PMIDs via efetch.

    This is a fallback for Europe PMC keyword discovery outages. It accepts
    the same fieldless boolean query strings our Europe PMC callers build and
    strips the Europe-PMC-only ``SRC:MED`` clause before sending to PubMed.
    """

    params: dict[str, Any] = {
        "db": "pubmed",
        "term": _pubmed_term_from_europepmc_query(query),
        "retmode": "json",
        "retmax": str(page_size),
        "sort": "relevance",
    }
    add_ncbi_api_key_param(params)
    try:
        payload = http.get_json(
            NCBI_PUBMED_ESEARCH,
            source="ncbi_pubmed_esearch",
            ttl_days=EUROPEPMC_TTL,
            params=params,
        )
    except Exception as exc:  # noqa: BLE001
        logger.warning("NCBI PubMed esearch failed for fallback query: %s", exc)
        return []
    ids = ((payload.get("esearchresult") or {}).get("idlist") or [])[:page_size]
    return _ncbi_pubmed_fetch_by_pmids(
        http=http,
        pmids=[int(p) for p in ids if str(p).isdigit()],
        retraction_index=retraction_index,
        topic_tagger=topic_tagger,
    )


# ---------------------------------------------------------------------------
# Full text
# ---------------------------------------------------------------------------


def fetch_fulltext(
    *,
    http: CachedHTTP,
    pmcid: str,
    retraction_index: RetractionIndex,
    topic_tagger: "TopicTagger | None" = None,
) -> Paper:
    """Fetch metadata + JATS XML full text for one PMC accession.

    Returns the same ``Paper`` shape ``gene_literature`` emits — ``sections``
    populated, ``truncated_sections`` flags any sections trimmed to fit
    the per-paper char budget. Caller decides whether to re-tag topics
    using full text vs abstract.

    Three-layer fallback chain (NCBI-first, post-2026-05-16):

    1. **NCBI E-utilities** ``efetch.fcgi?db=pmc`` (preferred). NCBI is
       the authoritative PMC source; EuropePMC is a downstream mirror.
       Survey on GPR75 (44 unique PMCIDs, 2026-05-16) found EuropePMC's
       ``fullTextXML`` endpoint 404'd on 58/58 fulltext attempts while
       NCBI succeeded on 40/40 — so NCBI was promoted to first-line to
       cut wasted HTTP roundtrips and surface the authoritative content
       directly.
    2. **EuropePMC** ``fullTextXML`` endpoint when NCBI returns a
       non-fatal HTTP error or an empty article-set. Some EuropePMC-
       only OAI ingestions may not yet be in NCBI's PMC; this layer
       catches them.
    3. **Abstract-only** graceful degrade when both fulltext sources
       fail or return an empty/error JATS body. ``sections`` is empty
       and the caller should treat the abstract (already populated on
       the returned ``Paper``) as the body.

    The decision is surfaced on the returned ``Paper`` via
    ``fulltext_fetch_source`` so callers (per-search audit logs,
    figure provenance, etc.) can see which layer fired. The metadata
    lookup at the top of this function still uses EuropePMC's search
    API — that endpoint is independent of the fulltext mirror and
    remains reliable.
    """
    cleaned = pmcid.strip().upper()
    if not cleaned.startswith("PMC"):
        cleaned = f"PMC{cleaned}"
    if not re.fullmatch(r"PMC\d+", cleaned):
        raise ValueError(f"unrecognized pmcid {pmcid!r}; expected 'PMC' + digits")

    base: Paper | None = None
    try:
        metadata_payload = europepmc_search(
            http=http, query=f"PMCID:{cleaned}", page_size=1
        )
        hits = (metadata_payload.get("resultList") or {}).get("result") or []
        if hits:
            base = paper_from_europepmc(
                hits[0], retraction_index=retraction_index, topic_tagger=topic_tagger
            )
    except Exception as exc:  # noqa: BLE001
        logger.warning(
            "Europe PMC metadata lookup failed for %s; trying NCBI PMC efetch: %s",
            cleaned,
            exc,
        )

    sections: list[PaperSection] = []
    truncated_section_names: list[str] = []
    fulltext_source: Literal["europepmc", "ncbi", "abstract_only"] = "abstract_only"

    # Layer 1: NCBI efetch (preferred — authoritative source).
    ncbi_xml = _fetch_fulltext_xml_ncbi(http, cleaned)
    if ncbi_xml is not None:
        if base is None:
            base = paper_from_ncbi_pmc_xml(
                ncbi_xml,
                pmcid=cleaned,
                retraction_index=retraction_index,
                topic_tagger=topic_tagger,
            )
        sections, truncated_section_names = parse_jats_sections(ncbi_xml)
        if sections:
            fulltext_source = "ncbi"

    # Layer 2: EuropePMC fullTextXML — used when NCBI returned nothing usable.
    if fulltext_source == "abstract_only":
        if base is None:
            try:
                metadata_payload = europepmc_search(
                    http=http, query=f"PMCID:{cleaned}", page_size=1
                )
                hits = (metadata_payload.get("resultList") or {}).get("result") or []
            except Exception as exc:  # noqa: BLE001
                raise LookupError(
                    f"{cleaned} not found via Europe PMC metadata or NCBI PMC efetch"
                ) from exc
            if not hits:
                raise LookupError(
                    f"{cleaned} not found in Europe PMC search or NCBI PMC efetch"
                )
            base = paper_from_europepmc(
                hits[0], retraction_index=retraction_index, topic_tagger=topic_tagger
            )
        epmc_xml = _fetch_fulltext_xml_europepmc(http, cleaned)
        if epmc_xml is not None:
            sections, truncated_section_names = parse_jats_sections(epmc_xml)
            if sections:
                fulltext_source = "europepmc"

    # Layer 3: abstract-only — sections stays [], fulltext_source records degrade.
    if base is None:
        raise LookupError(f"{cleaned} not found in Europe PMC search or NCBI PMC efetch")
    if topic_tagger is not None:
        full_text_for_tags = (base.abstract or "") + "\n" + "\n".join(s.text for s in sections)
        base.topic_tags = topic_tagger(full_text_for_tags, base.title)
    base.sections = sections
    base.truncated_sections = truncated_section_names
    base.fulltext_fetch_source = fulltext_source
    return base


# ---------------------------------------------------------------------------
# Fulltext-source helpers (NCBI = layer 1, EuropePMC = layer 2)
# ---------------------------------------------------------------------------


def _fetch_fulltext_xml_europepmc(http: CachedHTTP, pmcid: str) -> str | None:
    """Layer 2 of the fulltext chain (fallback when NCBI fails).

    Returns the raw JATS XML on success, ``None`` on any recoverable
    HTTP failure (4xx / 5xx). Non-HTTP errors (network failures,
    timeouts) also degrade to ``None`` — they trip Layer 3
    (abstract-only).
    """
    try:
        return http.get_text(
            EUROPEPMC_FULLTEXT.format(pmcid=pmcid),
            source="europepmc_fulltext",
            ttl_days=FULLTEXT_TTL,
        )
    except httpx.HTTPStatusError as exc:
        logger.info(
            "EuropePMC fullTextXML returned %s for %s; degrading to abstract-only",
            exc.response.status_code,
            pmcid,
        )
        return None
    except httpx.RequestError as exc:
        logger.warning(
            "EuropePMC fullTextXML request error for %s: %s; degrading to abstract-only",
            pmcid,
            exc,
        )
        return None


def _fetch_fulltext_xml_ncbi(http: CachedHTTP, pmcid: str) -> str | None:
    """Layer 1 of the fulltext chain (preferred — authoritative PMC source).

    Hits NCBI E-utilities ``efetch.fcgi?db=pmc&rettype=xml``. Strips the
    ``PMC`` prefix per the efetch contract. Returns the JATS XML on
    success, or ``None`` if NCBI 404s, times out, 5xx's, or returns an
    empty ``<pmc-articleset/>`` (NCBI's stand-in for "article not
    accessible via this endpoint"). Same JATS schema as EuropePMC so
    ``parse_jats_sections`` works unchanged. When NCBI fails, the
    caller falls through to Layer 2 (EuropePMC) and Layer 3
    (abstract-only).
    """
    numeric = pmcid.removeprefix("PMC")
    params: dict[str, Any] = {
        "db": "pmc",
        "id": numeric,
        "rettype": "xml",
    }
    # NCBI lifts the request cap when an api_key is presented. The helper
    # rotates through NCBI_API_KEYS when a collaborator key pool is configured.
    add_ncbi_api_key_param(params)
    try:
        xml_text = http.get_text(
            NCBI_PMC_EFETCH,
            source="ncbi_pmc_efetch",
            ttl_days=FULLTEXT_TTL,
            params=params,
        )
    except httpx.HTTPStatusError as exc:
        logger.info(
            "NCBI efetch returned %s for %s; degrading to abstract-only",
            exc.response.status_code,
            pmcid,
        )
        return None
    except httpx.RequestError as exc:
        logger.warning(
            "NCBI efetch request error for %s: %s; degrading to abstract-only",
            pmcid,
            exc,
        )
        return None

    if _is_empty_pmc_articleset(xml_text):
        logger.info(
            "NCBI efetch returned empty pmc-articleset for %s; degrading to abstract-only",
            pmcid,
        )
        return None
    return xml_text


def _dedupe_pmids(pmids: Sequence[int | str]) -> list[int]:
    out: list[int] = []
    seen: set[int] = set()
    for raw in pmids:
        try:
            pmid = int(raw)
        except (TypeError, ValueError):
            continue
        if pmid in seen:
            continue
        seen.add(pmid)
        out.append(pmid)
    return out


def _pubmed_term_from_europepmc_query(query: str) -> str:
    """Remove Europe-PMC-only syntax from a fieldless query string."""

    term = re.sub(r"\s+AND\s+SRC:MED\b", "", query, flags=re.IGNORECASE)
    term = re.sub(r"\bSRC:MED\s+AND\s+", "", term, flags=re.IGNORECASE)
    term = re.sub(r"\bSRC:MED\b", "", term, flags=re.IGNORECASE)
    return " ".join(term.split())


def _ncbi_pubmed_fetch_by_pmids(
    *,
    http: CachedHTTP,
    pmids: Sequence[int],
    retraction_index: RetractionIndex,
    topic_tagger: "TopicTagger | None" = None,
) -> list[Paper]:
    """Resolve PMIDs via NCBI PubMed efetch XML."""

    clean_pmids = _dedupe_pmids(pmids)
    if not clean_pmids:
        return []
    params: dict[str, Any] = {
        "db": "pubmed",
        "id": ",".join(str(p) for p in clean_pmids),
        "retmode": "xml",
    }
    add_ncbi_api_key_param(params)
    try:
        xml_text = http.get_text(
            NCBI_PUBMED_EFETCH,
            source="ncbi_pubmed_efetch",
            ttl_days=EUROPEPMC_TTL,
            params=params,
        )
    except Exception as exc:  # noqa: BLE001
        logger.warning("NCBI PubMed efetch failed for %d PMIDs: %s", len(clean_pmids), exc)
        return []

    try:
        root = ET.fromstring(xml_text)
    except ET.ParseError as exc:
        logger.warning("NCBI PubMed efetch XML parse failed: %s", exc)
        return []

    papers: list[Paper] = []
    for article in root.findall(".//PubmedArticle"):
        try:
            papers.append(
                paper_from_ncbi_pubmed_article(
                    article,
                    retraction_index=retraction_index,
                    topic_tagger=topic_tagger,
                )
            )
        except LookupError as exc:
            logger.info("Skipping malformed NCBI PubMed article record: %s", exc)
    by_pmid = {p.pmid: p for p in papers}
    return [by_pmid[p] for p in clean_pmids if p in by_pmid]


def _is_empty_pmc_articleset(xml_text: str) -> bool:
    """True when NCBI returned a placeholder ``<pmc-articleset/>`` body.

    NCBI occasionally returns HTTP 200 with an empty
    ``<pmc-articleset/>`` (or a wrapper containing only error nodes
    and no ``<article>``) when the article isn't accessible via efetch.
    Treated as 404-equivalent by the fallback chain so we move on to
    abstract-only.
    """
    if not isinstance(xml_text, str) or not xml_text.strip():
        return True
    try:
        root = ET.fromstring(xml_text)
    except (ET.ParseError, TypeError):
        return True
    if root.tag != "pmc-articleset":
        # Some response — let parse_jats_sections handle it.
        return False
    return root.find("article") is None


# ---------------------------------------------------------------------------
# Paper construction from Europe PMC's per-record JSON
# ---------------------------------------------------------------------------


def paper_from_europepmc(
    record: dict[str, Any],
    *,
    retraction_index: RetractionIndex,
    topic_tagger: "TopicTagger | None" = None,
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

    publication_type = classify_publication_type(pub_type_list)
    is_review = any("review" in p.lower() for p in pub_type_list) or publication_type == "review"
    is_retracted, retraction_checked_at = check_retraction(
        pub_type_list, pmid=pmid, doi=doi, index=retraction_index
    )
    is_pmc_oa = (record.get("isOpenAccess") or "N") == "Y" and bool(pmcid)
    authors = _extract_authors(record)

    topic_tags: list[TopicAnchor] = []
    if topic_tagger is not None:
        topic_tags = topic_tagger(abstract or "", title)

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


def paper_from_ncbi_pubmed_article(
    article: ET.Element,
    *,
    retraction_index: RetractionIndex,
    topic_tagger: "TopicTagger | None" = None,
) -> Paper:
    """Build :class:`Paper` from one NCBI PubMed efetch ``PubmedArticle``."""

    pmid_text = _first_text(article, ".//MedlineCitation/PMID") or _first_text(
        article, ".//PMID"
    )
    pmid = _safe_int(pmid_text)
    if pmid is None:
        raise LookupError("NCBI PubMed record missing integer PMID")

    article_ids = {
        (el.attrib.get("IdType") or "").lower(): _node_text(el)
        for el in article.findall(".//PubmedData/ArticleIdList/ArticleId")
    }
    pmcid = article_ids.get("pmc") or None
    doi = article_ids.get("doi") or None
    title = _node_text(article.find(".//ArticleTitle")).rstrip(".")
    abstract = _abstract_from_pubmed_article(article)
    journal = _first_text(article, ".//Journal/Title")
    year = _year_from_pubmed_article(article)
    pub_types = [
        _node_text(el)
        for el in article.findall(".//PublicationTypeList/PublicationType")
        if _node_text(el)
    ]
    publication_type = classify_publication_type(pub_types)
    is_review = any("review" in p.lower() for p in pub_types) or publication_type == "review"
    is_retracted, retraction_checked_at = check_retraction(
        pub_types, pmid=pmid, doi=doi, index=retraction_index
    )
    authors = _authors_from_pubmed_article(article)
    topic_tags: list[TopicAnchor] = []
    if topic_tagger is not None:
        topic_tags = topic_tagger(abstract or "", title)

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
        is_pmc_oa=bool(pmcid),
        topic_tags=topic_tags,
    )


def paper_from_ncbi_pmc_xml(
    xml_text: str,
    *,
    pmcid: str,
    retraction_index: RetractionIndex,
    topic_tagger: "TopicTagger | None" = None,
) -> Paper:
    """Build :class:`Paper` from NCBI PMC JATS XML."""

    try:
        root = ET.fromstring(xml_text)
    except ET.ParseError as exc:
        raise LookupError(f"NCBI PMC XML parse failed for {pmcid}: {exc}") from exc
    article = root.find(".//article") if root.tag == "pmc-articleset" else root
    if article is None:
        raise LookupError(f"NCBI PMC XML for {pmcid} did not contain an article")

    meta = article.find(".//article-meta")
    if meta is None:
        raise LookupError(f"NCBI PMC XML for {pmcid} missing article-meta")

    article_ids = {
        (el.attrib.get("pub-id-type") or "").lower(): _node_text(el)
        for el in meta.findall(".//article-id")
    }
    pmid = _safe_int(article_ids.get("pmid"))
    if pmid is None:
        raise LookupError(f"NCBI PMC XML for {pmcid} missing integer PMID")
    resolved_pmcid = article_ids.get("pmc") or pmcid
    if resolved_pmcid and not resolved_pmcid.upper().startswith("PMC"):
        resolved_pmcid = f"PMC{resolved_pmcid}"
    doi = article_ids.get("doi") or None
    title = _node_text(meta.find(".//title-group/article-title")).rstrip(".")
    abstract = _abstract_from_jats_meta(meta)
    journal = _node_text(article.find(".//journal-title-group/journal-title")) or None
    year = _year_from_jats_meta(meta)
    article_type = article.attrib.get("article-type") or ""
    pub_types = [article_type] if article_type else []
    publication_type = classify_publication_type(pub_types)
    is_review = publication_type == "review"
    is_retracted, retraction_checked_at = check_retraction(
        pub_types, pmid=pmid, doi=doi, index=retraction_index
    )
    authors = _authors_from_jats_meta(meta)
    topic_tags: list[TopicAnchor] = []
    if topic_tagger is not None:
        topic_tags = topic_tagger(abstract or "", title)

    return Paper(
        pmid=pmid,
        pmc_id=resolved_pmcid,
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
        is_pmc_oa=True,
        topic_tags=topic_tags,
    )


def _extract_authors(record: dict[str, Any]) -> list[str]:
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


def _first_text(root: ET.Element, path: str) -> str | None:
    return _node_text(root.find(path)) or None


def _node_text(node: ET.Element | None) -> str:
    if node is None:
        return ""
    return " ".join(" ".join(node.itertext()).split())


def _abstract_from_pubmed_article(article: ET.Element) -> str | None:
    chunks = [
        _node_text(el)
        for el in article.findall(".//Abstract/AbstractText")
        if _node_text(el)
    ]
    return " ".join(chunks).strip() or None


def _abstract_from_jats_meta(meta: ET.Element) -> str | None:
    chunks = [_node_text(p) for p in meta.findall(".//abstract//p") if _node_text(p)]
    if not chunks:
        abstract = meta.find(".//abstract")
        text = _node_text(abstract)
        return text or None
    return " ".join(chunks).strip() or None


def _year_from_pubmed_article(article: ET.Element) -> int | None:
    for path in (
        ".//Article/Journal/JournalIssue/PubDate/Year",
        ".//PubMedPubDate[@PubStatus='pubmed']/Year",
        ".//PubMedPubDate/Year",
    ):
        year = _safe_int(_first_text(article, path))
        if year is not None:
            return year
    medline_date = _first_text(article, ".//Article/Journal/JournalIssue/PubDate/MedlineDate")
    if medline_date:
        match = re.search(r"\b(19|20)\d{2}\b", medline_date)
        if match:
            return int(match.group(0))
    return None


def _year_from_jats_meta(meta: ET.Element) -> int | None:
    for pub_date in meta.findall(".//pub-date"):
        year = _safe_int(_first_text(pub_date, "year"))
        if year is not None:
            return year
    return None


def _authors_from_pubmed_article(article: ET.Element) -> list[str]:
    out: list[str] = []
    for author in article.findall(".//AuthorList/Author"):
        collective = _first_text(author, "CollectiveName")
        if collective:
            out.append(collective)
            continue
        last = _first_text(author, "LastName")
        fore = _first_text(author, "ForeName") or _first_text(author, "Initials")
        if last and fore:
            out.append(f"{fore} {last}")
        elif last:
            out.append(last)
    return out


def _authors_from_jats_meta(meta: ET.Element) -> list[str]:
    out: list[str] = []
    for contrib in meta.findall(".//contrib-group/contrib"):
        if contrib.attrib.get("contrib-type") not in (None, "", "author"):
            continue
        collab = _first_text(contrib, "collab")
        if collab:
            out.append(collab)
            continue
        surname = _first_text(contrib, ".//surname")
        given = _first_text(contrib, ".//given-names")
        if surname and given:
            out.append(f"{given} {surname}")
        elif surname:
            out.append(surname)
    return out


def classify_publication_type(pub_types: list[str]) -> PublicationType:
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


def check_retraction(
    pub_types: list[str],
    *,
    pmid: int | None = None,
    doi: str | None = None,
    index: RetractionIndex | None = None,
) -> tuple[bool, datetime]:
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


# ---------------------------------------------------------------------------
# JATS XML section parser
# ---------------------------------------------------------------------------


SectionName = Literal["intro", "methods", "results", "discussion", "figure_legends"]


_SEC_TYPE_MAP: dict[str, SectionName] = {
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

_TITLE_KEYWORD_MAP: list[tuple[re.Pattern[str], SectionName]] = [
    (re.compile(r"\bintroduct", re.IGNORECASE), "intro"),
    (re.compile(r"\bbackground", re.IGNORECASE), "intro"),
    (re.compile(r"\bmaterials? and methods\b", re.IGNORECASE), "methods"),
    (re.compile(r"\bmethods\b", re.IGNORECASE), "methods"),
    (re.compile(r"\bexperimental procedures\b", re.IGNORECASE), "methods"),
    (re.compile(r"\bresults\b", re.IGNORECASE), "results"),
    (re.compile(r"\bdiscussion\b", re.IGNORECASE), "discussion"),
    (re.compile(r"\bconclusions?\b", re.IGNORECASE), "discussion"),
]


def parse_jats_sections(xml_text: str) -> tuple[list[PaperSection], list[str]]:
    """Parse JATS XML into ``PaperSection`` list + names of truncated sections.

    Bibliography (``<ref-list>``), tables, and quotation-style figures are
    excluded; figure captions are concatenated into the ``figure_legends``
    section so reviewers can find caption-anchored quotes by section name.
    """

    try:
        root = ET.fromstring(xml_text)
    except ET.ParseError as exc:
        logger.warning("JATS parse failed: %s", exc)
        return [], []

    body = root.find(".//body")
    sections_by_name: dict[SectionName, list[str]] = {}
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

    ordered_names: list[SectionName] = [
        "intro", "methods", "results", "discussion", "figure_legends"
    ]
    raw: list[tuple[SectionName, str]] = []
    for n in ordered_names:
        chunks = sections_by_name.get(n) or []
        if chunks:
            raw.append((n, "\n\n".join(chunks)))

    sections, truncated = _apply_char_cap(raw, FULLTEXT_CHAR_CAP)
    return sections, truncated


def _classify_section(sec: ET.Element) -> SectionName | None:
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
    return " ".join(" ".join(node.itertext()).split())


def _apply_char_cap(
    raw: list[tuple[SectionName, str]], cap: int
) -> tuple[list[PaperSection], list[str]]:
    total = sum(len(t) for _, t in raw)
    if total <= cap:
        return [PaperSection(name=n, text=t, truncated=False) for n, t in raw], []

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
# Optional topic tagger (caller-supplied)
# ---------------------------------------------------------------------------


# Callable signature: ``(*texts) -> list[TopicAnchor]``. ``gene_literature``
# passes its own ``_detect_topic_tags`` to keep the anchor vocabulary in
# that module; other callers can pass ``None`` to skip tagging.
TopicTagger = Callable[..., list[TopicAnchor]]


__all__ = [
    "EUROPEPMC_TTL",
    "FULLTEXT_TTL",
    "DEFAULT_PAGE_SIZE",
    "FULLTEXT_TOKEN_CAP",
    "FULLTEXT_CHAR_CAP",
    "EUROPEPMC_SEARCH",
    "EUROPEPMC_FULLTEXT",
    "NCBI_PMC_EFETCH",
    "NCBI_PUBMED_ESEARCH",
    "NCBI_PUBMED_EFETCH",
    "SectionName",
    "TopicTagger",
    "europepmc_search",
    "europepmc_bulk_by_pmid",
    "ncbi_pubmed_search",
    "fetch_fulltext",
    "paper_from_europepmc",
    "paper_from_ncbi_pubmed_article",
    "paper_from_ncbi_pmc_xml",
    "classify_publication_type",
    "check_retraction",
    "parse_jats_sections",
]
