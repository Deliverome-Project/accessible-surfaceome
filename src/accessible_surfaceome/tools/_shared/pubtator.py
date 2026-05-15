"""PubTator3 entity-anchored literature search.

PubTator3 (NCBI) pre-annotates all of PubMed with biomedical NER. An
entity-anchored query — ``@GENE_<symbol> <free-text terms>`` — returns
papers where the gene was *tagged as a subject entity*, not merely
mentioned. That subject grounding is what keyword search over Europe
PMC cannot do, and it is the fix for the "method paper that lists the
gene among hundreds of detected proteins" failure mode (F1).

The client is **discovery-only**: PubTator returns PMIDs + bibliographic
metadata + a relevance score, but no abstract or full text. Callers
resolve the returned PMIDs against Europe PMC to get open-access status
and to fetch full text for snippet extraction.
"""

from __future__ import annotations

import logging
from typing import Any

from .http import CachedHTTP
from .models import PubTatorHit, PubTatorSearchResult

logger = logging.getLogger(__name__)


# PubTator3 articles don't change after indexing; a month TTL is plenty
# and keeps the per-protein sweep cheap on re-runs.
PUBTATOR_TTL = 30
PUBTATOR_SEARCH = "https://www.ncbi.nlm.nih.gov/research/pubtator3-api/search/"


def build_gene_entity_query(symbol: str, free_text_terms: str = "") -> str:
    """Compose a PubTator entity-anchored query string.

    ``@GENE_<SYMBOL>`` is PubTator's gene-entity operator — it matches
    papers where NER tagged that gene, not papers that merely contain
    the string. Free-text terms after it narrow the result set the same
    way ordinary search terms would (e.g. ``"immunohistochemistry"``).

    The symbol is upper-cased because PubTator's gene operator expects
    the canonical symbol form.
    """
    sym = symbol.strip().upper()
    if not sym:
        raise ValueError("build_gene_entity_query requires a non-empty symbol")
    entity = f"@GENE_{sym}"
    terms = free_text_terms.strip()
    return f"{entity} {terms}".strip()


def pubtator_search(
    *,
    http: CachedHTTP,
    query: str,
    page: int = 1,
) -> PubTatorSearchResult:
    """Issue one PubTator3 search request.

    Returns at most one page (~10 hits) ordered by PubTator's own
    relevance score. For the evidence-retrieval use case the first page
    is usually enough — the score ordering is strong, and downstream we
    only fetch full text for a handful of top hits anyway.
    """
    payload = http.get_json(
        PUBTATOR_SEARCH,
        source="pubtator",
        ttl_days=PUBTATOR_TTL,
        params={"text": query, "page": str(page)},
    )
    hits = [
        _hit_from_record(record)
        for record in (payload.get("results") or [])
        if record.get("pmid") is not None
    ]
    return PubTatorSearchResult(
        query=query,
        total_count=int(payload.get("count") or 0),
        page=int(payload.get("current") or page),
        hits=hits,
    )


def _hit_from_record(record: dict[str, Any]) -> PubTatorHit:
    authors = [a for a in (record.get("authors") or []) if isinstance(a, str)]
    return PubTatorHit(
        pmid=int(record["pmid"]),
        pmcid=record.get("pmcid") or None,
        doi=record.get("doi") or None,
        title=(record.get("title") or "").rstrip("."),
        journal=record.get("journal") or None,
        year=_year_from_record(record),
        score=float(record.get("score") or 0.0),
        authors=authors,
    )


def _year_from_record(record: dict[str, Any]) -> int | None:
    """Pull the publication year out of a PubTator record.

    ``date`` is an ISO timestamp (``"2023-03-09T00:00:00Z"``) — the
    leading four digits are the year. ``meta_date_publication``
    (``"2023 Mar 9"``) is the fallback when ``date`` is absent.
    """
    for key in ("date", "meta_date_publication"):
        value = record.get(key)
        if isinstance(value, str) and len(value) >= 4 and value[:4].isdigit():
            return int(value[:4])
    return None


__all__ = [
    "PUBTATOR_SEARCH",
    "PUBTATOR_TTL",
    "build_gene_entity_query",
    "pubtator_search",
]
