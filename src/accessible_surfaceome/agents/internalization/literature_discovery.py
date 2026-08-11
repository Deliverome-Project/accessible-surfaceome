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
    '"receptor recycling" OR "clathrin-mediated" OR '
    # measurement-weighted terms so relevance ranking favors papers that
    # actually quantify internalization over qualitative / delivery mentions.
    '"internalization rate" OR "endocytic rate" OR "uptake kinetics" OR '
    '"surface half-life" OR "acid strip" OR "receptor downregulation"'
)
# A tighter, measurement/ADC-focused query so that genes whose literature is
# dominated by other themes (AXL=signaling/EMT, BCMA=CAR-T/expression) still
# surface their internalization-measurement papers, which the broad query buries.
_MEASUREMENT_TERMS = (
    '"antibody internalization" OR "ADC internalization" OR '
    '"antibody-drug conjugate" OR "receptor internalization" OR '
    '"internalization assay" OR "internalization kinetics" OR '
    '"internalization rate" OR "receptor endocytosis" OR "receptor downregulation"'
)
_MAX_PER_SOURCE = 60


def build_internalization_query(aliases: list[str]) -> str:
    alias_or = " OR ".join(sorted({a for a in aliases if a}))
    return f"({alias_or}) AND ({_INTERNALIZATION_TERMS})"


def build_measurement_query(aliases: list[str]) -> str:
    alias_or = " OR ".join(sorted({a for a in aliases if a}))
    return f"({alias_or}) AND ({_MEASUREMENT_TERMS})"


def discover_internalization_papers(
    bundle: IdentifierBundle,
    *,
    http: CachedHTTP,
    retraction_index: Any,
) -> dict[int, Paper]:
    aliases = [bundle.hgnc_symbol, *bundle.aliases, *bundle.previous_symbols]
    discovered: dict[int, Paper] = {}

    # EuropePMC free-text: the broad internalization query PLUS a tighter
    # measurement/ADC-internalization query. The second rescues genes whose
    # corpus is dominated by other themes (signaling, CAR-T) so the broad query
    # buries their internalization-measurement papers.
    for query in (
        build_internalization_query(aliases),
        build_measurement_query(aliases),
    ):
        payload = europepmc_search(http=http, query=query, page_size=_MAX_PER_SOURCE)
        for rec in payload.get("resultList", {}).get("result", []):
            try:
                paper = paper_from_europepmc(rec, retraction_index=retraction_index)
            except LookupError:
                # Non-integer PMID (e.g. a preprint id like "PPR1220047") — we
                # can't PMID-anchor a citation to it, so skip.
                continue
            if paper.pmid:
                discovered.setdefault(paper.pmid, paper)

    # PubTator entity search, hydrated to full Paper objects via EuropePMC.
    # Sort by relevance (score), NOT recency — date-sorting floods the corpus
    # with recent delivery-vehicle / viral-receptor papers over the core
    # internalization-measurement literature. The free-text is measurement-
    # weighted so the relevance score favors papers that quantify uptake.
    hits = pubtator_search(
        http=http,
        query=build_gene_entity_query(
            bundle.hgnc_symbol, "internalization rate endocytosis uptake kinetics"
        ),
        sort="score desc",
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
