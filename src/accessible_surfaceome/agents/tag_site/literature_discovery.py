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
    fetch_fulltext,
    papers_from_europepmc_records,
)
from accessible_surfaceome.tools._shared.http import CachedHTTP
from accessible_surfaceome.tools._shared.models import Paper, paper_source_id
from accessible_surfaceome.tools._shared.normalize import (
    find_quote_in_normalized,
    normalize_for_quote_matching,
)
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
) -> dict[str, Paper]:
    """Return ``{paper_source_id: Paper}`` for tagging-methods papers on this gene,
    via the repo lit-search: EuropePMC (alias + methods vocabulary) UNION PubTator
    entity search (minimal query), hydrated to full :class:`Paper` objects.

    Keyed on the shared :func:`paper_source_id` (``PMC:`` > ``PMID:`` > ``DOI:``),
    NOT the integer PMID, so DOI-anchored bioRxiv/medRxiv preprints join the same
    corpus — ``papers_from_europepmc_records(..., include_preprints=True)`` keeps
    them (the shared contract from #143) instead of the old PPR skip. ``aliases``
    should include the protein name(s) — methods papers rarely use the symbol."""
    ri = retraction_index or _empty_retraction_index()
    discovered: dict[str, Paper] = {}
    query = build_tag_site_query([gene_symbol, *aliases])

    # Two EuropePMC passes over the same alias+methods query: the default
    # (relevance/recency) sort PLUS a CITATION-sorted pass that surfaces the
    # classic, heavily-cited methods papers the default sort buries. Preprints are
    # kept (DOI-anchored) and retracted papers dropped.
    for sort in (None, "CITED desc"):
        payload = europepmc_search(http=http, query=query, page_size=_MAX_PER_SOURCE, sort=sort)
        records = payload.get("resultList", {}).get("result", [])
        for paper in papers_from_europepmc_records(
            records,
            retraction_index=ri,
            context=f"tag_site:{gene_symbol}",
            include_preprints=True,
        ):
            if not paper.is_retracted:
                discovered.setdefault(paper_source_id(paper), paper)

    # PubTator entity search — MINIMAL free text (overloading it tanks recall),
    # hydrated to Paper objects via EuropePMC. Retracted papers dropped.
    hits = pubtator_search(
        http=http, query=build_gene_entity_query(gene_symbol, "epitope tag")
    ).hits
    known_pmids = {p.pmid for p in discovered.values() if p.pmid}
    pmids = [h.pmid for h in hits if h.pmid and h.pmid not in known_pmids][:_MAX_PER_SOURCE]
    for paper in europepmc_bulk_by_pmid(http=http, pmids=pmids, retraction_index=ri):
        if not paper.is_retracted:
            discovered.setdefault(paper_source_id(paper), paper)

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


_MAX_FULLTEXT_PAPERS = 8


def fetch_fulltext_sections(
    *,
    http: CachedHTTP,
    papers: dict[str, Paper],
    max_papers: int = _MAX_FULLTEXT_PAPERS,
    retraction_index: RetractionIndex | None = None,
) -> dict[str, dict[str, str]]:
    """Fetch full text for the top ``max_papers`` discovered papers that have a
    PMCID, via the repo's ``fetch_fulltext`` (NCBI/PMC, same path evidence_retrieval
    uses), and return ``{paper_source_id: {section: text}}`` for the METHODS +
    RESULTS sections — where the tag construct (exact residue) AND the
    surface/function measurements live. Best-effort: a paper with no PMC-OA full
    text or a fetch error is skipped (preprints have no PMCID -> abstract only), so
    the agent still has the abstract for it. Keyed on ``paper_source_id`` to match
    the ``discover_tag_site_papers`` corpus."""
    ri = retraction_index or _empty_retraction_index()
    out: dict[str, dict[str, str]] = {}
    for sid, paper in list(papers.items())[:max_papers]:
        if not paper.pmc_id:
            continue
        try:
            full = fetch_fulltext(http=http, pmcid=paper.pmc_id, retraction_index=ri)
        except Exception:  # noqa: BLE001 - full text is best-effort
            continue
        secs = {s.name: s.text for s in full.sections if s.name in ("methods", "results")}
        if secs:
            out[sid] = secs
    return out


def quote_supported(quote: str | None, source_text: str) -> bool:
    """True iff ``quote`` (a model-provided verbatim sentence) is found in
    ``source_text`` after the same normalization ``promote_claim`` uses (NFKC +
    Greek + HTML + whitespace + lowercase). The entailment check behind
    ``entailment_verified``: a citation is only trusted if its supporting quote
    actually appears in the fetched source. Quotes under 12 normalized chars are
    too short to anchor and never verify."""
    if not quote or not source_text:
        return False
    nq = normalize_for_quote_matching(quote)
    if len(nq) < 12:
        return False
    return find_quote_in_normalized(nq, normalize_for_quote_matching(source_text)) is not None
