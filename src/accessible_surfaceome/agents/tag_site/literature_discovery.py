"""Hybrid literature discovery for tag sites.

Uses the repo's own EuropePMC + PubTator stack (same primitives as
``agents/internalization/literature_discovery.py``), tuned for tagging-methods
papers, so the tag-site agent stops relying on ``web_search`` alone. A
``web_search`` complement is still valuable — it reaches preprints and
vocabulary-mismatch methods papers the abstract index misses (e.g. hERG's Kanner
2018, whose abstract says "optical monitoring", not "tag") — but its results are
*ranked* by source tier here, not filtered: peer-reviewed papers and preprints
first, then patents, then vendor catalog pages (kept, just lowest tier).

Query tuning is benchmark-validated against ``data/tag_sites/positive_controls.tsv``
(16 controls with identifiable papers):

* EuropePMC alias-expanded + tagging-methods vocabulary: recall 5/16 -> 9/16.
  Synonyms matter most — methods papers say "hERG"/"transferrin receptor", not
  the gene symbol.
* PubTator entity search: keep the free-text MINIMAL. Its NER already resolves
  synonyms; overloading the query with methods terms tanked recall 8/16 -> 1/16.

The union with a paper-ranked ``web_search`` beat either backend alone on every
co-tested control (union 11/11 vs web 10/11 vs lit 9/11).
"""
from __future__ import annotations

from urllib.parse import urlparse

from accessible_surfaceome.tools._shared.europepmc import (
    europepmc_bulk_by_pmid,
    europepmc_search,
    paper_from_europepmc,
)
from accessible_surfaceome.tools._shared.http import CachedHTTP
from accessible_surfaceome.tools._shared.models import Paper
from accessible_surfaceome.tools._shared.pubtator import (
    build_gene_entity_query,
    pubtator_search,
)
from accessible_surfaceome.tools._shared.retraction_watch import (
    RetractionIndex,
    empty as _empty_retraction_index,
)

# Tagging-methods vocabulary. Deliberately broad: many surface-labeling constructs
# are never called "tags" in the abstract, so we OR in the concrete modalities.
_TAG_METHODS = (
    '"epitope tag" OR "HA tag" OR "FLAG tag" OR "Myc tag" OR "ecto-tagged" OR '
    '"epitope-tagged" OR "extracellular epitope" OR "surface labeling" OR '
    '"cell surface expression" OR "knock-in" OR pHluorin OR HiBiT OR HaloTag OR '
    'ALFA OR DogTag OR SpyTag OR bungarotoxin OR "extracellular loop"'
)
_MAX_PER_SOURCE = 30


def _alias_or(aliases: list[str]) -> str:
    """OR-join aliases, PHRASE-quoting multi-word ones. Unquoted, ``transferrin
    receptor`` parses as ``transferrin AND receptor`` across all fields and
    inflates the match set — quoting keeps the gene scope tight."""
    parts = [f'"{a}"' if " " in a else a for a in sorted({a for a in aliases if a})]
    return " OR ".join(parts)


def build_tag_site_query(aliases: list[str]) -> str:
    """EuropePMC boolean: (gene aliases) AND (tagging-methods vocabulary)."""
    return f"({_alias_or(aliases)}) AND ({_TAG_METHODS})"


def discover_tag_site_papers(
    *,
    http: CachedHTTP,
    gene_symbol: str,
    aliases: list[str],
    retraction_index: RetractionIndex | None = None,
) -> dict[int, Paper]:
    """Return ``{pmid: Paper}`` for tagging-methods papers on this gene, via the
    repo lit-search: EuropePMC (alias + methods vocabulary) UNION PubTator entity
    search (minimal query), hydrated to full :class:`Paper` objects. ``aliases``
    should include the protein name(s) — methods papers rarely use the symbol."""
    ri = retraction_index or _empty_retraction_index()
    discovered: dict[int, Paper] = {}

    # EuropePMC keyword: alias-expanded + tagging-methods vocabulary.
    payload = europepmc_search(
        http=http,
        query=build_tag_site_query([gene_symbol, *aliases]),
        page_size=_MAX_PER_SOURCE,
    )
    for rec in payload.get("resultList", {}).get("result", []):
        try:
            paper = paper_from_europepmc(rec, retraction_index=ri)
        except LookupError:
            # Non-integer PMID (e.g. a preprint id "PPR...") — can't PMID-anchor.
            continue
        if paper.pmid:
            discovered.setdefault(paper.pmid, paper)

    # PubTator entity search — MINIMAL free text (overloading it tanks recall),
    # hydrated to Paper objects via EuropePMC.
    hits = pubtator_search(
        http=http, query=build_gene_entity_query(gene_symbol, "epitope tag")
    ).hits
    pmids = [h.pmid for h in hits if h.pmid and h.pmid not in discovered][:_MAX_PER_SOURCE]
    for paper in europepmc_bulk_by_pmid(http=http, pmids=pmids, retraction_index=ri):
        if paper.pmid:
            discovered.setdefault(paper.pmid, paper)

    return discovered


# --- source tiering for the web_search complement ---------------------------
# We RANK web results, we do NOT filter them: vendor pages are kept as the lowest
# tier (they still confirm a construct exists), patents are mid, papers/preprints
# lead. This is per the user's rule: prioritize papers, keep patents/vendor.
_PAPER_HOSTS = (
    "pubmed", "ncbi.nlm.nih.gov", "biorxiv.org", "medrxiv.org", "nature.com",
    "science.org", "cell.com", "elifesciences.org", "sciencedirect.com", "wiley.com",
    "springer.com", "embopress.org", "jbc.org", "plos.org", "frontiersin.org",
    "rupress.org", "pnas.org", "oup.com", "tandfonline.com", "mdpi.com",
    "biochemj.org", "portlandpress.com", "doi.org", "researchgate.net", "researchsquare.com",
)
_PATENT_HOSTS = ("uspto.gov", "patents.google.com", "patentscope", "espacenet", "freepatentsonline")
_VENDOR_HOSTS = (
    "origene.com", "dnasu.org", "sigmaaldrich.com", "thermofisher.com", "alomone.com",
    "abcam.com", "genecards.org", "multispaninc.com", "synthelis.com",
    "atlasgeneticsoncology.org", "labome.com", "7tmantibodies.com", "rcsb.org",
)

SOURCE_TIERS = ("paper", "patent", "other", "vendor")
SOURCE_TIER_RANK = {t: i for i, t in enumerate(SOURCE_TIERS)}


def source_tier(url: str) -> str:
    """Classify a web_search result URL: 'paper' > 'patent' > 'other' > 'vendor'.
    Used to RANK the web_search complement (papers first), never to drop results."""
    host = (urlparse(url).hostname or url).lower()
    if any(h in host for h in _PAPER_HOSTS):
        return "paper"
    if any(h in host for h in _PATENT_HOSTS):
        return "patent"
    if any(h in host for h in _VENDOR_HOSTS):
        return "vendor"
    return "other"
