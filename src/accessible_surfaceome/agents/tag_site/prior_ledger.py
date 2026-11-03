"""Carry a previously-cited clip forward into this run's pool.

The clip pool is **not monotonic across runs**, and not because of anything the
search does. SLC6A3 returned 7 sites in the first library sweep and 3 in the
depth spike; 9 of its 12 previously-cited clips were still in the pool and all 9
reached the selector, while the 3 that decided its best sites were absent from
the pool *entirely*. The cause was upstream: **179 papers degraded to
abstract-only across that 20-gene sweep** (EuropePMC ``fullTextXML`` returning
500). A paper that degrades contributes no methods clips, so a correct site
becomes unreachable for a reason unrelated to depth, dedupe or the menu.

So a rerun holding less evidence than its predecessor is the normal case under
transient failure rather than a signal, and compensating for it downstream —
a shrink guard on the sync, a provenance-scoped publish — only stops the loss
from being *destructive*. Seeding the pool from the prior run's archived ledger
removes it at the source: a clip good enough to cite once is in front of the
model again, whatever the publisher's server is doing today.

**The honesty constraint.** A carried clip was span-verified when it was first
promoted, not now. Registering its archived quote as the source body makes this
run's span check pass trivially — correct in substance, since it genuinely was
verified against a real body — but it would make ``entailment_verified`` mean
two different things if the inheritance were invisible. Hence:

* carried clips are prefixed (:data:`CARRIED_PREFIX`) so every downstream reader
  can tell, and so the pause gate does not count them as new evidence;
* a body fetched *this* run always wins over an archived quote, because the real
  surrounding text is strictly richer and the offset is real.
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from datetime import UTC, datetime

from accessible_surfaceome.tools._shared.models import EvidenceClaimDraft
from accessible_surfaceome.tools._shared.normalize import (
    normalize_for_quote_matching,
)
from accessible_surfaceome.tools._shared.source_text import (
    SourceText,
    SourceTextStore,
)

#: Clip-id prefix marking a clip carried forward from an earlier run rather than
#: extracted from a body fetched now. Load-bearing: the pause gate excludes
#: these from "new evidence", and a record built on one inherits its span
#: verification instead of claiming a fresh one.
CARRIED_PREFIX = "carried_"

#: Score given to a carried clip. It has to clear the menu cap — a clip carried
#: forward *because* its paper failed to fetch, then cut by the cap, would
#: reintroduce exactly the loss this module prevents. It was good enough to cite
#: last time, so it outranks any fresh clip the extractor merely scored well.
_CARRIED_SCORE = 1_000.0


@dataclass(frozen=True)
class PriorClip:
    """One clip an earlier run cited, as archived in ``tag_site_run``."""

    source_id: str
    claim: str
    quote: str
    run_id: str


def is_carried(clip_id: str) -> bool:
    """Whether ``clip_id`` names a clip carried forward from an earlier run."""
    return clip_id.startswith(CARRIED_PREFIX)


def parse_prior_clips(rows: Iterable[Mapping[str, object]]) -> list[PriorClip]:
    """Every distinct clip cited by the archived runs in ``rows``.

    ``rows`` are ``tag_site_run`` records carrying ``run_id`` and
    ``ledger_json``. A row whose ledger is absent, empty or unparseable
    contributes nothing — an empty ledger is the common case, since 1,106 of the
    first sweep's 1,824 genes legitimately found nothing — and a clip with no
    quote is skipped because there is nothing for a span check to anchor to.

    Deduped on the normalized quote: a gene re-run under a later prompt has the
    same clip archived several times, and that is one piece of evidence.
    """
    out: list[PriorClip] = []
    seen: set[str] = set()
    for row in rows:
        raw = row.get("ledger_json")
        if not raw:
            continue
        try:
            entries = json.loads(str(raw))
        except (ValueError, TypeError):
            continue
        if not isinstance(entries, list):
            continue
        for entry in entries:
            if not isinstance(entry, dict):
                continue
            quote = str(entry.get("quote") or "").strip()
            source_id = str(entry.get("source_id") or "").strip()
            if not quote or not source_id:
                continue
            key = normalize_for_quote_matching(quote)
            if not key or key in seen:
                continue
            seen.add(key)
            out.append(
                PriorClip(
                    source_id=source_id,
                    claim=str(entry.get("claim") or ""),
                    quote=quote,
                    run_id=str(row.get("run_id") or ""),
                )
            )
    return out


def _url_for(source_id: str) -> str:
    """A locator matching the accession's own namespace.

    The archive holds no URL, so this is derived from the id — and it has to
    branch, because the cited corpus is not all PMC. A real carried clip in the
    first validation run was ``DOI:10.1101/712448``, a bioRxiv preprint; giving
    it a PMC article URL would persist a link that 404s into the field citation
    display reads. The repo's citation rule is that a cited source must be one
    click from itself.
    """
    prefix, _, rest = source_id.partition(":")
    if prefix == "PMC" and rest:
        return f"https://www.ncbi.nlm.nih.gov/pmc/articles/{rest}/"
    if prefix == "PMID" and rest:
        return f"https://pubmed.ncbi.nlm.nih.gov/{rest}/"
    if prefix == "DOI" and rest:
        return f"https://doi.org/{rest}"
    return source_id


def _register_archived_quote(clip: PriorClip, store: SourceTextStore) -> None:
    """Register the archived quote as this source's body, if nothing better is.

    ``store.put`` is first-write-wins by default and that is exactly the
    precedence wanted: when the paper *did* fetch this run its real body is
    already registered and richer, and must not be replaced by a single
    sentence.
    """
    if store.has(clip.source_id):
        return
    raw = clip.quote
    norm = normalize_for_quote_matching(raw)
    now = datetime.now(UTC)
    store.put(
        SourceText(
            source_id=clip.source_id,
            source_type="pubmed",
            url=_url_for(clip.source_id),
            title=None,
            raw_text=raw,
            normalized_text=norm,
            content_sha256=hashlib.sha256(raw.encode("utf-8")).hexdigest(),
            normalized_source_sha256=hashlib.sha256(norm.encode("utf-8")).hexdigest(),
            retrieved_at=now,
            # The archived ledger records source_id, claim and quote — not the
            # publication type. "other" is the honest value: inferring
            # "preprint" from a DOI prefix or "primary_research" from a PMC id
            # would persist provenance we never observed, into a field that
            # feeds source-tier ranking.
            publication_type="other",
            is_retracted=False,
            retraction_checked_at=now,
            license="unknown",
        )
    )


def seed_pool(
    pool: dict[str, EvidenceClaimDraft],
    prior: Iterable[PriorClip],
    *,
    store: SourceTextStore,
) -> set[str]:
    """Add every prior clip the pool does not already hold, and return their ids.

    A clip the current run re-derived is left alone: the fresh draft came from a
    body fetched now, so it has a real char offset, and adding the archived copy
    would spend menu budget restating it. Comparison is on the NORMALIZED quote,
    because the one difference that matters here is invisible otherwise — NFKC
    does not fold a curly apostrophe to a straight one, and a 448-character
    quote was once deleted over exactly that.

    The returned ids are what the pause gate subtracts to count new evidence.
    """
    have = {normalize_for_quote_matching(d.quote) for d in pool.values()}
    carried: set[str] = set()
    for i, clip in enumerate(prior, start=1):
        key = normalize_for_quote_matching(clip.quote)
        if not key or key in have:
            continue
        clip_id = f"{CARRIED_PREFIX}{i:03d}_{clip.source_id.replace(':', '')}"
        while clip_id in pool:
            clip_id += "_x"
        pool[clip_id] = EvidenceClaimDraft(
            suggested_evidence_id=clip_id,
            quote=clip.quote,
            source_id=clip.source_id,
            section="methods",
            hallmark_phrase="carried forward from a previous run",
            score=_CARRIED_SCORE,
        )
        _register_archived_quote(clip, store)
        have.add(key)
        carried.add(clip_id)
    return carried
