"""Shared ``web_search``-backed literature discovery.

A gene-agnostic discovery complement to the deterministic EuropePMC + PubTator
union. It runs one Sonnet call with the server-side ``web_search`` tool to
surface papers/preprints the abstract index misses — recent bioRxiv/medRxiv
preprints, and vocabulary-mismatch methods papers whose abstracts never use the
gene symbol — then **hydrates the model's cited PMIDs/DOIs into real ``Paper``
objects** through the shared EuropePMC path. The hydrated papers flow through the
SAME downstream triage -> full-text fetch -> span-verify pipeline as any other
discovered paper, so the verbatim-quote integrity gate is unchanged: a web hit
that can't be resolved to a fetchable, id-anchored source is simply dropped here.

Extracted from the tag-site agent's web_search recipe (``agents/tag_site``) so the
tag-site and internalization literature tracks share ONE implementation — and one
place to bump the ``web_search`` tool version. ``call_builder`` degrades to a
cite-only (no-tool) call when web_search isn't enabled on the account, so this is
safe to call unconditionally.
"""

from __future__ import annotations

import logging
from typing import Any
from urllib.parse import urlparse

from anthropic import Anthropic
from pydantic import BaseModel, ConfigDict, Field

from accessible_surfaceome.agents.surfaceome_v2.builders._common import call_builder
from accessible_surfaceome.tools._shared.europepmc import (
    europepmc_bulk_by_pmid,
    europepmc_search,
    paper_from_europepmc,
)
from accessible_surfaceome.tools._shared.http import CachedHTTP
from accessible_surfaceome.tools._shared.models import Paper, paper_source_id
from accessible_surfaceome.tools._shared.preprint import paper_from_preprint_doi
from accessible_surfaceome.tools._shared.retraction_watch import RetractionIndex

logger = logging.getLogger(__name__)

# Server-side web_search tool recipe. Centralized so the tag-site + internalization
# tracks (and the deep-dive methods builder, on a later consolidation) share ONE
# definition — bump the tool version in one place. call_builder degrades to a
# cite-only call if web_search isn't enabled on the account.
WEB_SEARCH_TOOL: list[dict[str, Any]] = [
    {
        "type": "web_search_20250305",
        "name": "web_search",
        # Headroom for the multi-query recall strategy (name + preprint + screen
        # angles) the system prompt asks for; web_search is ~$0.01/call.
        "max_uses": 12,
        "cache_control": {"type": "ephemeral"},
    }
]

# Journal / preprint / repository hosts a real primary source is served from.
_PAPER_HOSTS = (
    "ncbi.nlm.nih.gov", "pubmed", "europepmc.org", "nature.com",
    "sciencedirect.com", "cell.com", "pnas.org", "jbc.org", "embopress.org",
    "rupress.org", "elifesciences.org", "wiley.com", "onlinelibrary.wiley.com",
    "springer.com", "oup.com", "academic.oup.com", "tandfonline.com",
    "frontiersin.org", "plos.org", "mdpi.com", "biorxiv.org", "medrxiv.org",
)
_VENDOR_HOSTS = (
    "thermofisher", "sigmaaldrich", "abcam", "cellsignal", "rndsystems",
    "biolegend", "novusbio", "genscript", "addgene",
)


def source_tier(url: str) -> str:
    """Rank a web_search result URL: ``preprint`` > ``paper`` > ``vendor`` > ``other``.

    Used to RANK (never to drop) — a vendor page still confirms a reagent exists.
    Preprints rank first because they are the recall this pass exists to add.
    """
    host = (urlparse(url).netloc or "").lower()
    if "biorxiv.org" in host or "medrxiv.org" in host:
        return "preprint"
    if any(h in host for h in _PAPER_HOSTS):
        return "paper"
    if any(v in host for v in _VENDOR_HOSTS):
        return "vendor"
    return "other"


class WebCitation(BaseModel):
    """One primary source the model surfaced via web_search.

    ``extra="ignore"`` (NOT forbid): the web_search model naturally decorates each
    citation with ``title`` / ``url`` / ``year`` / ``reason`` fields — forbidding
    them fails the WHOLE structured output and silently drops every hit. We keep
    the two we can use (``title``, ``url``) and ignore the rest.
    """

    model_config = ConfigDict(extra="ignore")

    pmid: int | None = None
    doi: str | None = None
    title: str | None = None
    url: str | None = None
    note: str = ""  # one clause: why it's relevant (kept out of the Paper)


class WebDiscoveryResult(BaseModel):
    """Exact shape the model emits — a list of id-anchored primary sources.

    ``extra="ignore"`` (NOT forbid): the model tends to wrap the list in a
    ``{"protein": ..., "topic": ..., "citations": [...]}`` envelope. Forbidding the
    envelope keys fails validation after every repair attempt and returns nothing
    (the TMEM123 silent-zero bug). Ignoring them keeps the ``citations`` we asked
    for and discards the envelope.
    """

    model_config = ConfigDict(extra="ignore")

    citations: list[WebCitation] = Field(default_factory=list)


_SYSTEM = (
    "You are a biomedical literature scout with a web_search tool. Find RECENT "
    "PRIMARY research papers AND bioRxiv / medRxiv preprints on the requested "
    "topic for the given protein.\n"
    "CRITICAL — run MULTIPLE distinct web searches with different query "
    "formulations before you conclude; do not stop after one. At minimum try: "
    "(1) '<protein> <topic keyword from the task below>', "
    "(2) '<protein> bioRxiv' and '<protein> preprint', and (3) a method/screen "
    "angle ('<topic> screen', 'proteome-wide <topic>', a methods paper that "
    "measures the <topic>). Some of the MOST important papers study the protein as "
    "ONE EXAMPLE among many (a methods paper, an endocytosis or proteomic screen) "
    "and DO NOT name it in the title or abstract — only in the results/figures. "
    "For promising bioRxiv/medRxiv hits, open the page and check whether the "
    "protein appears in the RESULTS even when absent from the abstract; keep it "
    "if so.\n"
    "EXCLUDE reviews, news, blog posts, and vendor catalog pages. For every "
    "source you keep, return its PubMed PMID (integer) AND/OR its DOI — at least "
    "one of the two is REQUIRED; a source with neither is useless downstream, so "
    "omit it. Return a JSON object with EXACTLY one top-level key, \"citations\", "
    'whose value is a list of objects each with "pmid" (integer or null), "doi" '
    '(string or null), and "note" (short string). Do NOT wrap the list in any '
    "other top-level keys. Do not fabricate PMIDs or DOIs — copy them from the "
    "web_search results verbatim."
)


def _normalize_doi(doi: str) -> str:
    d = doi.strip().lower()
    for pre in ("https://doi.org/", "http://doi.org/", "doi:"):
        if d.startswith(pre):
            d = d[len(pre) :]
    return d.strip()


def _hydrate_one(
    cit: WebCitation,
    *,
    http: CachedHTTP,
    retraction_index: RetractionIndex,
    include_preprints: bool,
) -> Paper | None:
    """Resolve a web citation to a real ``Paper`` via the shared EuropePMC path.

    PMID first (most reliable), then DOI (anchors DOI-only preprints when
    ``include_preprints``). Returns None if neither resolves — the web hit then
    never enters the pipeline, so nothing unverifiable can be cited.
    """
    if cit.pmid is not None:
        papers = europepmc_bulk_by_pmid(
            http=http, pmids=[cit.pmid], retraction_index=retraction_index
        )
        if papers:
            return papers[0]
    if cit.doi:
        doi = _normalize_doi(cit.doi)
        if doi:
            payload = europepmc_search(http=http, query=f'DOI:"{doi}"', page_size=1)
            for rec in payload.get("resultList", {}).get("result", []):
                try:
                    return paper_from_europepmc(
                        rec,
                        retraction_index=retraction_index,
                        include_preprints=include_preprints,
                    )
                except LookupError:
                    continue
            # EuropePMC didn't index this DOI — typically a recent bioRxiv/medRxiv
            # preprint it hasn't harvested (the exact recall gap this pass exists
            # to close). Hydrate it directly from the bioRxiv details API so a
            # web-surfaced preprint isn't dropped just because the abstract index
            # lags. Downstream body-fetch (DataCite/Unpaywall PDF) + span-verify
            # are unchanged.
            if include_preprints:
                preprint = paper_from_preprint_doi(
                    doi, http=http, retraction_index=retraction_index
                )
                if preprint is not None:
                    return preprint
    return None


def web_discover_papers(
    client: Anthropic,
    *,
    intent: str,
    gene_names: list[str],
    http: CachedHTTP,
    retraction_index: RetractionIndex,
    usage_sink: list[Any] | None = None,
    max_hits: int = 15,
    include_preprints: bool = True,
) -> list[Paper]:
    """Discover papers via one web_search Sonnet call, hydrated to real Papers.

    ``intent`` is the topic phrase (e.g. "internalization / endocytosis
    measurements"); ``gene_names`` is the OR-set of the protein's names/aliases
    (never a single noisy symbol). Returns deduped ``Paper`` objects keyed on
    ``paper_source_id`` (PMC > PMID > DOI); ``[]`` if web_search is unavailable or
    nothing resolves — callers union this into their deterministic pool.
    """
    names = ", ".join(dict.fromkeys(n for n in gene_names if n)) or "(unnamed)"
    user_prompt = (
        f"Protein (names / aliases): {names}\n"
        f"Topic to find primary sources for: {intent}\n\n"
        "Search the web and return the JSON object of id-anchored primary "
        "sources (PMIDs and/or DOIs)."
    )
    sink: list[Any] = usage_sink if usage_sink is not None else []
    result = call_builder(
        client,
        system_prompt=_SYSTEM,
        user_prompt=user_prompt,
        schema=WebDiscoveryResult,
        usage_sink=sink,
        label="web_lit_discover",
        tools=WEB_SEARCH_TOOL,
    )
    if not isinstance(result, WebDiscoveryResult):
        logger.info("web_discover(%s): call returned no parseable result", names)
        return []
    out: dict[str, Paper] = {}
    for cit in result.citations[:max_hits]:
        paper = _hydrate_one(
            cit,
            http=http,
            retraction_index=retraction_index,
            include_preprints=include_preprints,
        )
        if paper is not None:
            out.setdefault(paper_source_id(paper), paper)
    logger.info(
        "web_discover(%s): %d citations -> %d hydrated papers",
        names,
        len(result.citations),
        len(out),
    )
    return list(out.values())
