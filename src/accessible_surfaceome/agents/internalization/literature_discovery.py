"""Discover internalization papers: union EuropePMC free-text + PubTator
entity search, merged by PMID. Bypasses the closed TopicAnchor enum (which has
no ``internalization`` member) by querying the search backends directly."""

from __future__ import annotations

from typing import Any

from accessible_surfaceome.tools._shared.europepmc import (
    europepmc_bulk_by_pmid,
    europepmc_search,
    paper_from_europepmc,
)
from accessible_surfaceome.tools._shared.http import CachedHTTP
from accessible_surfaceome.tools._shared.models import IdentifierBundle, Paper
from accessible_surfaceome.tools._shared.pubtator import (
    build_gene_entity_query,
    pubtator_search,
)

_INTERNALIZATION_TERMS = (
    'internali* OR endocytos* OR "receptor-mediated uptake" OR '
    '"antibody internalization" OR "ADC internalization" OR '
    '"receptor recycling" OR "clathrin-mediated"'
)
_MAX_PER_SOURCE = 40


def build_internalization_query(aliases: list[str]) -> str:
    alias_or = " OR ".join(sorted({a for a in aliases if a}))
    return f"({alias_or}) AND ({_INTERNALIZATION_TERMS})"


def discover_internalization_papers(
    bundle: IdentifierBundle,
    *,
    http: CachedHTTP,
    retraction_index: Any,
) -> dict[int, Paper]:
    aliases = [bundle.hgnc_symbol, *bundle.aliases, *bundle.previous_symbols]
    discovered: dict[int, Paper] = {}

    # EuropePMC free-text search over aliases × internalization terms.
    payload = europepmc_search(
        http=http,
        query=build_internalization_query(aliases),
        page_size=_MAX_PER_SOURCE,
    )
    for rec in payload.get("resultList", {}).get("result", []):
        try:
            paper = paper_from_europepmc(rec, retraction_index=retraction_index)
        except LookupError:
            # Non-integer PMID (e.g. a preprint id like "PPR1220047") — we can't
            # PMID-anchor a citation to it, so skip rather than abort discovery.
            continue
        if paper.pmid:
            discovered.setdefault(paper.pmid, paper)

    # PubTator entity search, hydrated to full Paper objects via EuropePMC.
    hits = pubtator_search(
        http=http,
        query=build_gene_entity_query(bundle.hgnc_symbol, "internalization endocytosis"),
        sort="date desc",
    ).hits
    pmids = [h.pmid for h in hits if h.pmid and h.pmid not in discovered][
        :_MAX_PER_SOURCE
    ]
    for paper in europepmc_bulk_by_pmid(
        http=http, pmids=pmids, retraction_index=retraction_index
    ):
        if paper.pmid:
            discovered.setdefault(paper.pmid, paper)

    return discovered
