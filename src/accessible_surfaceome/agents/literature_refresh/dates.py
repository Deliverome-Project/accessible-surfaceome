"""Exact publication dates for discovered papers.

``Paper`` carries only a publication *year*, which cannot tell a paper from
March apart from one published after a July record. This module resolves a
calendar date per paper — NCBI esummary for PMID-bearing papers, EuropePMC for
PMC-only ones — with a year-long cache, since a publication date does not
change once assigned.
"""

from __future__ import annotations

import re
from datetime import date

from accessible_surfaceome.tools._shared.http import CachedHTTP
from accessible_surfaceome.tools._shared.models import Paper
from accessible_surfaceome.tools._shared.ncbi import add_ncbi_api_key_param

ESUMMARY_URL = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esummary.fcgi"
EUROPEPMC_SEARCH_URL = "https://www.ebi.ac.uk/europepmc/webservices/rest/search"
DATES_TTL_DAYS = 365
_ESUMMARY_BATCH = 200
_EUROPEPMC_BATCH = 50
_MONTHS = {m: i + 1 for i, m in enumerate(
    ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]
)}
_NCBI_DATE = re.compile(r"(\d{4})(?:[ /-](\w{3}|\d{1,2}))?(?:[ /-](\d{1,2}))?")


def parse_ncbi_date(text: str | None) -> date | None:
    """Parse an esummary date string (``2026 Aug 14``, ``2026 Aug``, ``2026``).

    Missing month or day falls back to the first of the period, so a paper
    dated only ``2026 Aug`` is treated as published on 1 August — the earliest
    it could have appeared, which keeps borderline papers *inside* a refresh.
    """
    if not text:
        return None
    m = _NCBI_DATE.match(text.strip())
    if not m:
        return None
    month_token = m.group(2)
    if month_token is None:
        month = 1
    elif month_token.isdigit():
        month = int(month_token)
    else:
        month = _MONTHS.get(month_token[:3].title(), 1)
    day = int(m.group(3)) if m.group(3) else 1
    try:
        return date(int(m.group(1)), month, day)
    except ValueError:
        return date(int(m.group(1)), month, 1)


def _pmid_dates(pmids: list[int], http: CachedHTTP) -> dict[int, date]:
    out: dict[int, date] = {}
    for i in range(0, len(pmids), _ESUMMARY_BATCH):
        batch = pmids[i : i + _ESUMMARY_BATCH]
        params = {"db": "pubmed", "id": ",".join(map(str, batch)), "retmode": "json"}
        add_ncbi_api_key_param(params)
        payload = http.get_json(
            ESUMMARY_URL, source="ncbi_pubdate", ttl_days=DATES_TTL_DAYS, params=params
        )
        result = payload.get("result", {}) if isinstance(payload, dict) else {}
        for pmid in batch:
            entry = result.get(str(pmid)) or {}
            # epubdate is when the paper first became readable online; fall
            # back to the issue date for print-only records.
            parsed = parse_ncbi_date(entry.get("epubdate")) or parse_ncbi_date(
                entry.get("pubdate")
            )
            if parsed is not None:
                out[pmid] = parsed
    return out


def _pmc_dates(pmc_ids: list[str], http: CachedHTTP) -> dict[str, date]:
    out: dict[str, date] = {}
    for i in range(0, len(pmc_ids), _EUROPEPMC_BATCH):
        batch = pmc_ids[i : i + _EUROPEPMC_BATCH]
        query = " OR ".join(f"PMCID:{p}" for p in batch)
        payload = http.get_json(
            EUROPEPMC_SEARCH_URL,
            source="europepmc_pubdate",
            ttl_days=DATES_TTL_DAYS,
            params={"query": query, "format": "json", "resultType": "lite",
                    "pageSize": str(len(batch))},
        )
        results = (payload.get("resultList") or {}).get("result") or [] if isinstance(
            payload, dict
        ) else []
        for r in results:
            pmcid = r.get("pmcid")
            raw = r.get("firstPublicationDate")
            if pmcid and raw:
                try:
                    out[pmcid] = date.fromisoformat(raw[:10])
                except ValueError:
                    continue
    return out


def resolve_publication_dates(
    papers: dict[str, Paper | None], http: CachedHTTP
) -> dict[str, date]:
    """Map pipeline source ids (``PMC:PMC…`` / ``PMID:…``) → first-online date.

    ``papers`` is keyed by the same source id the clip pool and a record's
    citations use (:func:`paper_source_id`); the value may be ``None`` for a
    body-clip source with no ``Paper`` object, in which case the id itself is
    parsed. A paper with a PMID is dated through NCBI; a PMC-only one through
    EuropePMC. Ids that cannot be dated are absent from the result — callers
    decide how to treat them.
    """
    pmid_for: dict[str, int] = {}
    pmc_for: dict[str, str] = {}
    for sid, paper in papers.items():
        pmid = paper.pmid if paper is not None else 0
        pmc = paper.pmc_id if paper is not None else None
        if not pmid and sid.startswith("PMID:") and sid[5:].isdigit():
            pmid = int(sid[5:])
        if not pmc and sid.startswith("PMC:"):
            pmc = sid[4:]
        if pmid:
            pmid_for[sid] = pmid
        elif pmc:
            pmc_for[sid] = pmc
    by_pmid = _pmid_dates(sorted(set(pmid_for.values())), http) if pmid_for else {}
    by_pmc = _pmc_dates(sorted(set(pmc_for.values())), http) if pmc_for else {}
    out: dict[str, date] = {}
    for sid, pmid in pmid_for.items():
        if pmid in by_pmid:
            out[sid] = by_pmid[pmid]
    for sid, pmc in pmc_for.items():
        if pmc in by_pmc:
            out[sid] = by_pmc[pmc]
    return out
