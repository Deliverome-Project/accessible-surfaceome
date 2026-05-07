"""Retraction Watch cross-reference.

Europe PMC's ``pubTypeList`` already flags many retractions via the
``"Retracted Publication"`` marker, but the index lags the underlying
literature by weeks-to-months. The Retraction Watch dataset (now hosted
by Crossref Labs) is the authoritative ground truth for retracted
publications across all of biomedicine; we cross-reference it at fetch
time so a paper retracted yesterday gets caught even if PMC hasn't
rebuilt its index yet.

Design:

- :class:`RetractionIndex` is a frozen set of retracted PMIDs (and
  optionally DOIs) plus a ``checked_at`` timestamp.
- :func:`from_http` fetches the dataset CSV through the shared
  :class:`CachedHTTP` (same SQLite cache, weekly TTL) and parses every
  column whose header mentions "PubMedID" / "PMID" — defensively, since
  the Retraction Watch schema occasionally adds columns.
- :func:`empty` returns an empty index — used by tests and as the
  fallback when ``from_http`` fails (we never block annotation on the
  Retraction Watch network round-trip).

The orchestrator builds one index per session (or re-uses a process-wide
cached one) and threads it through the tool dispatcher into
``gene_literature``.
"""

from __future__ import annotations

import csv
import io
import logging
import os
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Iterable

from .http import CachedHTTP

logger = logging.getLogger(__name__)


# Crossref Labs hosts the Retraction Watch dataset as a CSV feed. Documented at
# https://www.crossref.org/blog/news-crossref-and-retraction-watch/ — the
# canonical URL has been stable since the 2024 handover. Override via env if
# Crossref ever moves it (URL shifts shouldn't require a code change).
DEFAULT_RETRACTION_WATCH_URL = (
    "https://api.labs.crossref.org/data/retractionwatch"
)
RETRACTION_WATCH_TTL_DAYS = 7
_HTTP_SOURCE = "retraction_watch"


@dataclass(frozen=True)
class RetractionIndex:
    """Set of retracted PMIDs + retrieval timestamp.

    DOIs are tracked separately so a paper that didn't make it into PubMed
    can still be flagged via DOI lookup. The empty index — produced by
    :func:`empty` or returned by :func:`from_http` on fetch failure — is a
    valid no-op: every ``is_retracted`` query returns ``False`` and
    ``checked_at`` reflects when the lookup was attempted.
    """

    pmids: frozenset[int] = field(default_factory=frozenset)
    dois: frozenset[str] = field(default_factory=frozenset)
    checked_at: datetime = field(default_factory=lambda: datetime.now(UTC))

    def is_retracted(
        self, *, pmid: int | None = None, doi: str | None = None
    ) -> bool:
        """``True`` if the given identifier appears in the index.

        Either argument may be ``None`` — callers typically have one but
        not the other. DOI matching is case-insensitive (the dataset
        normalizes to lowercase, but upstream callers don't always).
        """

        if pmid is not None and pmid in self.pmids:
            return True
        if doi is not None and doi.lower() in self.dois:
            return True
        return False

    def __len__(self) -> int:
        return len(self.pmids) + len(self.dois)


def empty() -> RetractionIndex:
    """An index with no entries. Used in tests and as a safe fallback."""

    return RetractionIndex()


def from_pmids(pmids: Iterable[int]) -> RetractionIndex:
    """Construct an index directly from a PMID iterable. Test seam."""

    return RetractionIndex(pmids=frozenset(int(p) for p in pmids))


def from_http(
    http: CachedHTTP, *, url: str | None = None, ttl_days: int = RETRACTION_WATCH_TTL_DAYS
) -> RetractionIndex:
    """Fetch + parse the Retraction Watch CSV via :class:`CachedHTTP`.

    On any failure (network, HTTP error, parse error) returns
    :func:`empty` — the substring + PMC pubType paths still catch most
    retractions, so a Crossref outage degrades gracefully.

    The CSV column layout is permissive: any column whose header includes
    "PubMedID" or "PMID" is treated as a comma-separated list of PMIDs;
    any column whose header includes "DOI" or "Doi" is treated as a DOI
    (one per row). Columns naming the *retraction notice* (e.g.
    ``RetractionPubMedID``) and the *original paper* (e.g.
    ``OriginalPaperPubMedID``) are both indexed — both should be flagged.
    """

    target = url or os.environ.get("RETRACTION_WATCH_URL") or DEFAULT_RETRACTION_WATCH_URL
    try:
        body = http.get_text(target, source=_HTTP_SOURCE, ttl_days=ttl_days)
    except Exception as exc:
        logger.warning("Retraction Watch fetch failed: %s; using empty index", exc)
        return empty()

    try:
        return _parse_csv(body)
    except Exception as exc:
        logger.warning("Retraction Watch parse failed: %s; using empty index", exc)
        return empty()


def _parse_csv(body: str) -> RetractionIndex:
    """Permissive parser: collects PMIDs and DOIs from any column that looks
    like one. Returns the resulting :class:`RetractionIndex` with the current
    UTC timestamp.
    """

    reader = csv.DictReader(io.StringIO(body))
    pmids: set[int] = set()
    dois: set[str] = set()

    headers = reader.fieldnames or []
    pmid_columns = [
        h for h in headers if h and ("PubMedID" in h or "PMID" in h.upper())
    ]
    doi_columns = [h for h in headers if h and ("DOI" in h.upper())]

    for row in reader:
        for col in pmid_columns:
            value = (row.get(col) or "").strip()
            if not value:
                continue
            for token in value.replace(";", ",").split(","):
                token = token.strip()
                if token.isdigit():
                    pmids.add(int(token))
        for col in doi_columns:
            value = (row.get(col) or "").strip()
            if value:
                dois.add(value.lower())

    return RetractionIndex(
        pmids=frozenset(pmids),
        dois=frozenset(dois),
        checked_at=datetime.now(UTC),
    )


__all__ = [
    "DEFAULT_RETRACTION_WATCH_URL",
    "RETRACTION_WATCH_TTL_DAYS",
    "RetractionIndex",
    "empty",
    "from_http",
    "from_pmids",
]
