"""What counts as NEW evidence on a second pass, and when to stop.

A second literature pass over a gene the first pass already read is mostly
re-reading. The menu is the scarce resource — the selector sees ~100 clips of a
median 315 — so every slot spent on text an earlier run already examined is a
slot not spent on the clip that might pin a new site.

Three mechanisms, in the order they apply:

1. **Already examined.** A clip an earlier run saw is dropped, keyed on
   :func:`seen_key`. On the first enrichment run this set is only the clips the
   earlier run *cited*, because v1 never persisted its menus — so the first
   pass re-examines some text once and never again. That is a known, bounded
   cost, not a silent one.
2. **Already covered.** A clip whose only sequence-confirmed residues sit on
   junctions we already publish is corroboration rather than addition. A clip
   naming one covered and one uncovered residue is KEPT: that is a new site
   whose citation happens to mention a known one.
3. **The pause gate.** If nothing new survives, the run returns before the
   selector and the synthesizer — the expensive half — because a gene with no
   new evidence already has its answer.

Note what this is *not* protecting against. Publishing is additive: the
enrichment writes under its own provenance and never deletes the earlier run's
rows, so a pass that finds less than its predecessor cannot shrink the
published corpus. These filters are about where the model's attention goes, and
about not paying for a synthesis call that would re-derive a site we already
hold.
"""

from __future__ import annotations

import hashlib
from collections.abc import Iterable
from dataclasses import dataclass, field

from accessible_surfaceome.tools._shared.models import EvidenceClaimDraft
from accessible_surfaceome.tools._shared.normalize import (
    normalize_for_quote_matching,
)

from .literature_discovery import residue_mentions
from .prior_ledger import is_carried

#: How far a clip's named residue may sit from a published junction and still
#: be read as restating it. Papers differ on whether the label is the residue
#: before or after the insertion point, which ``residue_mentions`` documents,
#: so a one-residue gap is the same claim and two is the safe margin.
DEFAULT_COVERED_TOLERANCE = 2


def seen_key(source_id: str, quote: str) -> str:
    """A stable identity for "this clip, in this source", across runs.

    Normalized before hashing, because the same sentence re-extracted from a
    re-fetched body differs in ways that are invisible to a reader and fatal to
    an exact match — NFKC does not fold a curly apostrophe to a straight one,
    and whitespace runs vary with the parser. Without normalization every run
    would re-examine everything.

    Scoped by source, because two papers can share a boilerplate methods
    sentence and examining one says nothing about the other.
    """
    norm = normalize_for_quote_matching(quote or "")
    return hashlib.sha256(f"{source_id}\x00{norm}".encode()).hexdigest()


def covered_clip_ids(
    pool: dict[str, EvidenceClaimDraft],
    *,
    sequence: str,
    covered_junctions: Iterable[int],
    tolerance: int = DEFAULT_COVERED_TOLERANCE,
) -> set[str]:
    """Clips whose every confirmed residue restates a junction we already have.

    Residues are read with the sequence, so a letter-number token the protein
    denies is noise and cannot make a clip look like a restatement — the same
    confirmation rule the rest of the pipeline applies.

    A clip naming no residue at all is never dropped here. Most clips name
    none, and they cannot be restating a known site; dropping them would
    discard most of the pool for a reason that does not apply to them.
    """
    covered = set(covered_junctions)
    if not covered or not sequence:
        return set()
    window = {j + d for j in covered for d in range(-tolerance, tolerance + 1)}
    dropped: set[str] = set()
    for clip_id, draft in pool.items():
        named = residue_mentions(draft.quote, sequence=sequence)
        if named and named <= window:
            dropped.add(clip_id)
    return dropped


@dataclass(frozen=True)
class EnrichmentScope:
    """The three exclusions, and the gate they decide."""

    #: Clip ids carried forward from an earlier run's ledger.
    carried: set[str] = field(default_factory=set)
    #: :func:`seen_key` values an earlier run already examined.
    seen_keys: set[str] = field(default_factory=set)
    #: Clip ids dropped by :func:`covered_clip_ids`.
    dropped_covered: set[str] = field(default_factory=set)

    def is_new(self, clip_id: str, draft: EvidenceClaimDraft) -> bool:
        """Whether this clip is evidence no earlier run has had."""
        if clip_id in self.carried or is_carried(clip_id):
            return False
        if clip_id in self.dropped_covered:
            return False
        return seen_key(draft.source_id, draft.quote) not in self.seen_keys

    def should_pause(self, pool: dict[str, EvidenceClaimDraft]) -> bool:
        """True when the run should stop before the selector and synthesizer.

        An empty pool pauses too: there is nothing to select from, and the
        existing ``_empty()`` path already handles "ran and found nothing" with
        full provenance.
        """
        return count_new(pool, self) == 0


def count_new(
    pool: dict[str, EvidenceClaimDraft], scope: EnrichmentScope
) -> int:
    """How many pool clips are evidence no earlier run has had."""
    return sum(1 for cid, d in pool.items() if scope.is_new(cid, d))


def new_clip_ids(
    pool: dict[str, EvidenceClaimDraft], scope: EnrichmentScope
) -> set[str]:
    """The ids of those clips, for the run archive.

    Recorded so a zero can be read afterwards: "this gene had 1,800 clips and
    none of them were new" is a different fact from "this gene found nothing",
    and only one of them is worth re-running later.
    """
    return {cid for cid, d in pool.items() if scope.is_new(cid, d)}
