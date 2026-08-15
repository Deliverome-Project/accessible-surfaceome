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

# Broad, modality-agnostic internalization terms. Deliberately NOT antibody/ADC-
# centric — internalization matters for every delivery modality — and dropping
# "acid strip" (niche) and "receptor downregulation" (mostly matches expression
# downregulation, not endocytosis).
_INTERNALIZATION_TERMS = (
    'internali* OR endocytos* OR "receptor-mediated endocytosis" OR '
    '"receptor-mediated uptake" OR "receptor internalization" OR '
    '"receptor recycling" OR "internalization rate" OR "endocytic rate" OR '
    '"uptake kinetics" OR "surface half-life" OR "clathrin-mediated" OR '
    '"caveolin-mediated" OR macropinocytosis'
)
# A tighter, measurement-focused query spanning DELIVERY MODALITIES (not just
# ADCs) — antibody/ADC, siRNA / oligonucleotide (incl. GalNAc), lipid
# nanoparticle, AAV / viral entry, and peptide receptor-mediated uptake — so
# genes whose literature is dominated by other themes (AXL=signaling/EMT,
# BCMA=CAR-T) still surface their internalization-measurement papers.
_MEASUREMENT_TERMS = (
    '"receptor-mediated endocytosis" OR "receptor internalization" OR '
    '"internalization assay" OR "internalization kinetics" OR '
    '"internalization rate" OR "receptor endocytosis" OR '
    '"antibody internalization" OR "ADC internalization" OR '
    '"oligonucleotide uptake" OR "siRNA uptake" OR "antisense oligonucleotide" OR '
    'GalNAc OR "lipid nanoparticle" OR "nanoparticle uptake" OR '
    '"adeno-associated virus" OR "viral entry" OR "entry receptor" OR '
    '"cell-penetrating peptide" OR "peptide uptake"'
)
_MAX_PER_SOURCE = 60
# A quantitative-kinetics query run under CITATION sort (not the default
# recency/relevance sort). The default EuropePMC sort floods the top-60 with
# 2024-26 delivery papers and never surfaces the classic rate-constant
# literature — for a well-studied receptor the hard k_e / t½ values live in
# heavily-cited pre-2010 papers whose FULL TEXT is often unretrievable (PMC
# 404) but whose ABSTRACTS state the numbers. Citation-ranking pulls those in
# so the abstract-triage path can extract the quant. Kept tight (rate/kinetics
# terms only) so citation-sort doesn't drag in highly-cited off-topic papers.
_KINETICS_TERMS = (
    '"rate constant" OR "internalization rate" OR "endocytic rate" OR '
    '"half-time" OR "t1/2" OR "percent internalized" OR "% internalized"'
)
_MAX_KINETICS = 30


def _alias_or(aliases: list[str]) -> str:
    """OR-join aliases, PHRASE-quoting any multi-word alias. Unquoted, a
    multi-word alias like ``transferrin receptor`` is parsed as
    ``transferrin AND receptor`` across all fields — inflating the match set
    ~50x and drowning the citation-sorted kinetics pass in off-topic
    high-impact papers. Quoting keeps the gene scope tight."""
    parts = [f'"{a}"' if " " in a else a for a in sorted({a for a in aliases if a})]
    return " OR ".join(parts)


def build_internalization_query(aliases: list[str]) -> str:
    return f"({_alias_or(aliases)}) AND ({_INTERNALIZATION_TERMS})"


def build_measurement_query(aliases: list[str]) -> str:
    return f"({_alias_or(aliases)}) AND ({_MEASUREMENT_TERMS})"


def build_kinetics_query(aliases: list[str]) -> str:
    return f"({_alias_or(aliases)}) AND ({_KINETICS_TERMS})"


def discover_internalization_papers(
    bundle: IdentifierBundle,
    *,
    http: CachedHTTP,
    retraction_index: Any,
) -> dict[int, Paper]:
    aliases = [bundle.hgnc_symbol, *bundle.aliases, *bundle.previous_symbols]
    # Name-based aliases for the citation-sorted kinetics pass: the FULL protein
    # name ("transferrin receptor") is what the classic rate-constant papers use,
    # and it is NOT in the HGNC symbol list. Just as important, we DROP the noisy
    # short symbols (e.g. TR / T9 / p90 — bundle.alias_collision_risk == "high")
    # here: under CITATION sort they match thousands of off-topic high-impact
    # papers and drown the classics. Names only → precise gene scope.
    kinetics_aliases = [
        a
        for a in (bundle.hgnc_symbol, bundle.approved_name, *(bundle.alias_names or []))
        if a
    ]
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

    # Citation-sorted kinetics pass: surfaces the heavily-cited classic
    # rate-constant literature the recency-default queries above never reach.
    payload = europepmc_search(
        http=http,
        query=build_kinetics_query(kinetics_aliases),
        page_size=_MAX_KINETICS,
        sort="CITED desc",
    )
    for rec in payload.get("resultList", {}).get("result", []):
        try:
            paper = paper_from_europepmc(rec, retraction_index=retraction_index)
        except LookupError:
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
            bundle.hgnc_symbol, "internalization endocytosis receptor-mediated uptake"
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
