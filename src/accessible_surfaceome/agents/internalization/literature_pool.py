"""Pool construction (body fetch via ``apply_triage_outcomes``) + a REAL
``SourceTextStore`` built from fetched body text.

This is the crux of genuine span verification: the deep-dive orchestrator
promotes claims against a *synthetic* store (char-offsets into a concatenated
quote-blob), so its offsets don't point at the real paper. Here we register the
actual fetched full text (or the abstract when no body was fetched) so
``promote_claim`` yields real char offsets into the real source.
"""

from __future__ import annotations

import hashlib
from collections import defaultdict
from datetime import UTC, datetime
from typing import Any

from accessible_surfaceome.agents.plan_trim_select.abstract_triage import (
    TriageAction,
    apply_triage_outcomes,
)
from accessible_surfaceome.tools._shared.europepmc import fetch_fulltext
from accessible_surfaceome.tools._shared.http import CachedHTTP
from accessible_surfaceome.tools._shared.models import EvidenceClaimDraft, Paper
from accessible_surfaceome.tools._shared.normalize import normalize_for_quote_matching
from accessible_surfaceome.tools._shared.source_text import SourceText, SourceTextStore


def _add_to_pool(
    draft: EvidenceClaimDraft,
    pool: dict[str, EvidenceClaimDraft],
    by_source: dict[str, list[EvidenceClaimDraft]],
) -> None:
    """Verbatim copy of ``plan_trim_select.runner._add_to_pool`` (module-private
    there; copied rather than imported). Inserts a draft under a globally-unique
    clip_id with content-dedup within a source."""
    normalized = normalize_for_quote_matching(draft.quote)
    for existing in by_source.get(draft.source_id, []):
        if normalize_for_quote_matching(existing.quote) == normalized:
            return
    clip_id = draft.suggested_evidence_id
    if clip_id in pool:
        k = 2
        while f"{clip_id}_{k}" in pool:
            k += 1
        clip_id = f"{clip_id}_{k}"
    redrafted = draft.model_copy(update={"suggested_evidence_id": clip_id})
    pool[clip_id] = redrafted
    by_source[redrafted.source_id].append(redrafted)


def build_pool(
    outcomes: list[Any],
    papers_by_id: dict[str, Paper],
    *,
    http: CachedHTTP,
    retraction_index: Any,
) -> tuple[dict[str, EvidenceClaimDraft], list[TriageAction]]:
    """Run body fetch for ``worth_fetching`` outcomes and build the clip pool.
    Returns ``(pool, actions)``."""
    pool: dict[str, EvidenceClaimDraft] = {}
    by_source: dict[str, list[EvidenceClaimDraft]] = defaultdict(list)
    actions = apply_triage_outcomes(
        outcomes,
        papers_by_id,
        pool=pool,
        by_source=by_source,
        http=http,
        retraction_index=retraction_index,
        add_to_pool_fn=_add_to_pool,
    )
    return pool, actions


def _body_text(
    paper: Paper,
    *,
    fetched: bool,
    http: CachedHTTP,
    retraction_index: Any,
    drafts: list[EvidenceClaimDraft],
) -> str:
    """Store body for span verification. ALWAYS include the abstract (a paper
    can contribute abstract-derived clips even after it was fetched — e.g. a
    worth_fetching body-fetch that fell back to the abstract), PLUS the
    full-text body when fetched.

    Two full-text sources, by paper kind:

    * **PMC papers** — re-fetch the real JATS body (``fetch_fulltext``), so clip
      offsets point at the real source text.
    * **Non-PMC fetched papers** (bioRxiv/medRxiv preprints, Unpaywall/DataCite
      OA-PDF-only papers) — PMC has nothing for them, so the previous code left
      the store abstract-only and EVERY body-derived clip failed span
      verification (they came from the fetched PDF, not the abstract). That
      silently dropped all full-text evidence from non-PMC sources — fatal for a
      gene whose only internalization evidence is a preprint (the TMEM123/EndoNB
      case). The body-derived clip ``drafts`` in the pool ARE verbatim excerpts
      of that fetched body — exactly what ``select`` picks from — so folding them
      into the source text makes those clips verifiable again, no re-fetch."""
    parts: list[str] = []
    abstract = getattr(paper, "abstract", None)
    if abstract:
        parts.append(abstract)
    if fetched and paper.pmc_id:
        full = fetch_fulltext(http=http, pmcid=paper.pmc_id, retraction_index=retraction_index)
        secs = getattr(full, "sections", None) or []
        parts.extend(s.text for s in secs if getattr(s, "text", None))
    elif fetched:
        # Non-PMC fetched body: reconstruct from the pool's body-derived drafts
        # (verbatim excerpts of the fetched PDF/landing body).
        parts.extend(d.quote for d in drafts if getattr(d, "quote", None))
    return "\n\n".join(parts)


def build_source_store(
    pool: dict[str, EvidenceClaimDraft],
    *,
    papers_by_source_id: dict[str, tuple[Paper, bool]],
    http: CachedHTTP,
    retraction_index: Any,
) -> SourceTextStore:
    """Register a real ``SourceText`` for every source_id present in the pool
    (full body when the paper was fetched, else its abstract)."""
    store = SourceTextStore()
    drafts_by_source: dict[str, list[EvidenceClaimDraft]] = defaultdict(list)
    for draft in pool.values():
        drafts_by_source[draft.source_id].append(draft)
    for source_id in drafts_by_source:
        entry = papers_by_source_id.get(source_id)
        if entry is None:
            continue
        paper, fetched = entry
        raw = _body_text(
            paper,
            fetched=fetched,
            http=http,
            retraction_index=retraction_index,
            drafts=drafts_by_source[source_id],
        )
        if not raw:
            continue
        norm = normalize_for_quote_matching(raw)
        now = datetime.now(UTC)
        url = (
            f"https://pubmed.ncbi.nlm.nih.gov/{paper.pmid}/"
            if paper.pmid
            else f"https://www.ncbi.nlm.nih.gov/pmc/articles/{paper.pmc_id}/"
        )
        store.put(
            SourceText(
                source_id=source_id,
                source_type="pubmed",
                url=url,
                title=paper.title,
                raw_text=raw,
                normalized_text=norm,
                content_sha256=hashlib.sha256(raw.encode("utf-8")).hexdigest(),
                normalized_source_sha256=hashlib.sha256(norm.encode("utf-8")).hexdigest(),
                retrieved_at=now,
                publication_type=paper.publication_type,
                is_retracted=bool(getattr(paper, "is_retracted", False)),
                retraction_checked_at=now,
                license="unknown",
                authors=tuple(getattr(paper, "authors", []) or []),
                year=getattr(paper, "year", None),
                journal=getattr(paper, "journal", None),
            )
        )
    return store
