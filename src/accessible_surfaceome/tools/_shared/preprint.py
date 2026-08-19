"""Direct DOI -> Paper hydration for bioRxiv / medRxiv preprints.

EuropePMC indexes most preprints, but not all — and often with a lag. A recent
bioRxiv/medRxiv preprint that ``web_search`` surfaces by DOI but EuropePMC has
NOT indexed (e.g. a methods/screen preprint that studies a protein as one
example) would otherwise be dropped at hydration, because the EuropePMC
``DOI:"..."`` lookup returns nothing. This resolves such a DOI to a real
:class:`Paper` directly via the public bioRxiv details API, so it flows through
the SAME triage -> full-text fetch (DataCite/Unpaywall PDF) -> span-verify
pipeline as any indexed paper.

Shared on purpose: the internalization + tag-site literature tracks (and any
future web-discovery caller) use one preprint-hydration implementation.
"""

from __future__ import annotations

from accessible_surfaceome.tools._shared.http import CachedHTTP
from accessible_surfaceome.tools._shared.models import Paper
from accessible_surfaceome.tools._shared.retraction_watch import RetractionIndex

# bioRxiv/medRxiv share the Cold Spring Harbor Laboratory DOI prefix; the details
# API is keyed by server, so we try both (a bioRxiv DOI 404s on the medrxiv path
# and vice-versa — cheap, cached).
_BIORXIV_DETAILS = "https://api.biorxiv.org/details"
_PREPRINT_SERVERS = ("biorxiv", "medrxiv")
_CSHL_DOI_PREFIX = "10.1101/"
_PREPRINT_TTL_DAYS = 30


def _normalize_doi(doi: str) -> str:
    d = doi.strip().lower()
    for pre in ("https://doi.org/", "http://doi.org/", "doi:"):
        if d.startswith(pre):
            d = d[len(pre) :]
    return d.strip()


def _year_from_date(date: str | None) -> int | None:
    if date and len(date) >= 4 and date[:4].isdigit():
        return int(date[:4])
    return None


def paper_from_preprint_doi(
    doi: str,
    *,
    http: CachedHTTP,
    retraction_index: RetractionIndex | None = None,
) -> Paper | None:
    """Resolve a bioRxiv/medRxiv preprint DOI to a :class:`Paper` via the bioRxiv
    details API.

    Returns ``None`` for a non-CSHL (non-``10.1101/``) DOI or when neither server
    has a record — the caller then treats the citation as unresolvable, so nothing
    unverifiable enters the pipeline. On success, ``is_preprint=True`` and the
    DOI/title/abstract are populated so downstream body-fetch (DataCite/Unpaywall
    PDF) + span-verification proceed exactly as for an EuropePMC-hydrated preprint.
    """
    doi = _normalize_doi(doi)
    if not doi.startswith(_CSHL_DOI_PREFIX):
        return None
    for server in _PREPRINT_SERVERS:
        try:
            payload = http.get_json(
                f"{_BIORXIV_DETAILS}/{server}/{doi}",
                source="biorxiv",
                ttl_days=_PREPRINT_TTL_DAYS,
            )
        except Exception:  # noqa: BLE001 — a network/parse miss falls through to the next server
            continue
        collection = payload.get("collection") or []
        if not collection:
            continue
        rec = collection[-1]  # latest version wins
        title = (rec.get("title") or "").strip().rstrip(".")
        if not title:
            continue
        retracted = bool(retraction_index and retraction_index.is_retracted(doi=doi))
        return Paper(
            doi=doi,
            title=title,
            abstract=(rec.get("abstract") or "").strip() or None,
            is_preprint=True,
            year=_year_from_date(rec.get("date")),
            journal=f"{server} (preprint)",
            is_retracted=retracted,
        )
    return None
