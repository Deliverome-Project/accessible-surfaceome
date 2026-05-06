"""``patent_lookup`` — fetch a patent disclosure from Google Patents.

The agent calls this when ``db_panel`` or ``miss_diagnosis`` shows the gene is
in the patent-handle lane. Returns a structured :class:`PatentSummary` with
title, applicants, dates, and a short summary so the agent can populate
``SurfaceomeRecord.therapeutic_landscape.patent_disclosures`` without going
through the patent's full text itself.

Source: ``patents.google.com/patent/{wo_number}/en``. The page exposes
Dublin Core metadata (``DC.title``, ``DC.description``, ``DC.contributor`` with
``scheme="assignee"`` / ``"inventor"``, ``DC.date``) which is a stable,
load-bearing surface — Google maintains it for indexing.

Caveats:

* ``claims_summary`` is populated from the ``DC.description`` (abstract) since
  full claim extraction requires deeper HTML parsing. This is a documented v0
  limitation; the agent has the patent URL if it needs more.
* ``cited_genes`` and ``experimental_evidence_figures`` are not populated yet
  — extracting them reliably would require entity recognition (genes) or
  figure parsing (evidence). Both are deferred to a later milestone.
"""

from __future__ import annotations

import logging
import re
from datetime import datetime
from html import unescape
from typing import Any

from ._shared.http import CachedHTTP, open_default_client
from ._shared.models import PatentSummary

logger = logging.getLogger(__name__)


_TTL_DAYS = 365  # Patents don't change after publication.

_META_RE = re.compile(r"<meta\s+([^>]+?)/?>", re.IGNORECASE)
_ATTR_RE = re.compile(r'(\w+(?:\.\w+)*)\s*=\s*"([^"]*)"')

_PATENT_NUMBER_RE = re.compile(r"\b(?:WO|EP|US)\d{4,}[A-Z]?\d*\b")


def patent_lookup(wo_number: str, *, http: CachedHTTP | None = None) -> PatentSummary:
    """Fetch and parse a patent record by WO/EP/US number.

    The number is normalized to uppercase and stripped of whitespace before
    fetching. Caches aggressively (1-year TTL).
    """

    own_client = http is None
    client = http or open_default_client()
    try:
        return _fetch_and_parse(wo_number, client)
    finally:
        if own_client:
            client.close()


def _fetch_and_parse(wo_number: str, client: CachedHTTP) -> PatentSummary:
    cleaned = wo_number.strip().upper()
    if not _PATENT_NUMBER_RE.fullmatch(cleaned):
        raise ValueError(
            f"unrecognized patent number {wo_number!r}; expected WO/EP/US prefix + digits"
        )

    url = f"https://patents.google.com/patent/{cleaned}/en"
    html = client.get_text(url, source="google_patents", ttl_days=_TTL_DAYS)
    metas = _parse_meta_tags(html)

    title = _clean_text(metas.get_first("DC.title")) or cleaned
    description = _clean_text(metas.get_first("DC.description")) or ""

    assignees = [
        _clean_text(value) for value in metas.get_all("DC.contributor", scheme="assignee")
    ]
    assignees = [a for a in assignees if a]
    applicant = "; ".join(assignees) if assignees else None

    canonical_wo = (
        metas.get_first("citation_patent_publication_number") or cleaned
    ).replace(":", "")

    priority_date = _earliest_date(metas, schemes=["dateSubmitted"])
    publication_date = _earliest_date(metas, schemes=["datePublished"]) or _earliest_date(
        metas, schemes=[None]
    )

    claims_summary = _truncate(description, 400) or "(abstract not available; see patent URL)"

    return PatentSummary(
        wo_number=canonical_wo,
        title=title,
        applicant=applicant,
        priority_date=priority_date,
        publication_date=publication_date,
        claims_summary=claims_summary,
        cited_genes=[],  # deferred — requires entity recognition
        experimental_evidence_figures=[],  # deferred — requires figure parsing
    )


# ---------------------------------------------------------------------------
# meta-tag parsing
# ---------------------------------------------------------------------------


class _MetaTags:
    """Tiny indexed view over the page's ``<meta>`` tags.

    Indexed by ``name`` attribute. ``scheme`` is preserved so callers can
    select e.g. ``DC.contributor`` with ``scheme="assignee"``.
    """

    def __init__(self) -> None:
        self._records: list[dict[str, str]] = []

    def add(self, attrs: dict[str, str]) -> None:
        self._records.append(attrs)

    def get_first(self, name: str, scheme: str | None = None) -> str | None:
        for r in self._records:
            if r.get("name") == name and (scheme is None or r.get("scheme") == scheme):
                return r.get("content")
        return None

    def get_all(self, name: str, scheme: str | None = None) -> list[str]:
        out: list[str] = []
        for r in self._records:
            if r.get("name") == name and (scheme is None or r.get("scheme") == scheme):
                value = r.get("content")
                if value is not None:
                    out.append(value)
        return out

    def get_records(self, name: str) -> list[dict[str, str]]:
        return [r for r in self._records if r.get("name") == name]


def _parse_meta_tags(html: str) -> _MetaTags:
    # Restrict to <head> to skip body text that happens to look like meta tags.
    head_end = html.find("</head>")
    head = html[: head_end + 7] if head_end != -1 else html
    out = _MetaTags()
    for match in _META_RE.finditer(head):
        attrs_text = match.group(1)
        attrs = {k: v for k, v in _ATTR_RE.findall(attrs_text)}
        if "name" in attrs and "content" in attrs:
            out.add(attrs)
    return out


def _earliest_date(metas: _MetaTags, *, schemes: list[str | None]) -> datetime | None:
    candidates: list[datetime] = []
    for r in metas.get_records("DC.date"):
        if r.get("scheme") not in schemes:
            continue
        parsed = _parse_date(r.get("content"))
        if parsed is not None:
            candidates.append(parsed)
    return min(candidates) if candidates else None


def _parse_date(text: str | None) -> datetime | None:
    if not text:
        return None
    text = text.strip()
    for fmt in ("%Y-%m-%d", "%Y/%m/%d", "%Y%m%d", "%Y"):
        try:
            return datetime.strptime(text, fmt)
        except ValueError:
            continue
    return None


def _clean_text(value: Any) -> str:
    if value is None:
        return ""
    if not isinstance(value, str):
        value = str(value)
    return unescape(value).strip()


def _truncate(text: str, max_chars: int) -> str:
    if len(text) <= max_chars:
        return text
    return text[: max_chars - 1].rstrip() + "…"


__all__ = ["patent_lookup"]
