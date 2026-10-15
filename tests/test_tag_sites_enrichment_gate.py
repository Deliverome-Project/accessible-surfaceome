"""The enrichment pass's control flow: what counts as new, and when to stop.

A second literature pass over a gene the first pass already read is mostly
re-reading. The menu is the scarce resource — the selector sees ~100 clips of a
median 315 — so spending it on text a previous run already examined is the
difference between finding a new site and paying to be told the old one again.

Two filters and a gate:

* clips already EXAMINED by an earlier run are dropped, so the menu budget goes
  to unseen text;
* clips that only name residues we ALREADY publish a site at are dropped, since
  they corroborate rather than add — but a clip naming one covered and one
  uncovered residue is kept, because that is a new site with a citation that
  happens to mention a known one;
* if nothing new survives, the run stops BEFORE the selector and the
  synthesizer. That is the expensive half of a run, and a gene with no new
  evidence has a known answer already.
"""

from __future__ import annotations

from accessible_surfaceome.agents.tag_site.enrichment import (
    EnrichmentScope,
    count_new,
    covered_clip_ids,
    seen_key,
)
from accessible_surfaceome.tools._shared.models import EvidenceClaimDraft


def draft(clip_id: str, quote: str, source_id: str = "PMC:PMC1") -> EvidenceClaimDraft:
    return EvidenceClaimDraft(
        suggested_evidence_id=clip_id,
        quote=quote,
        source_id=source_id,
        section="methods",
        hallmark_phrase="x",
        score=1.0,
    )


#: 1-based: T at 10, G at 11, K at 21. (Position 20 is F — an earlier
#: draft of these tests used "Lys-20", which the sequence DENIES, so the
#: clip named no confirmed residue and the test passed for the wrong reason.)
SEQ = "MKTAYIAKQTGQISFVKSHFK" + "A" * 400


# --------------------------------------------------------------------------
# seen_key: identifying a clip across runs
# --------------------------------------------------------------------------


def test_seen_key_is_stable_across_typographic_variation() -> None:
    """The same sentence re-extracted from a re-fetched body must key the same,
    or every run re-examines everything. NFKC does not fold a curly apostrophe
    to a straight one, which is the variation that actually occurs."""
    a = seen_key("PMC:PMC9", "the receptor’s ectodomain was tagged")
    b = seen_key("PMC:PMC9", "the receptor's ectodomain  was tagged")
    assert a == b


def test_seen_key_separates_the_same_sentence_in_different_sources() -> None:
    """Two papers can share a boilerplate methods sentence, and examining it in
    one does not mean we examined the other's."""
    assert seen_key("PMC:PMC9", "cells were fixed") != seen_key(
        "PMC:PMC8", "cells were fixed"
    )


# --------------------------------------------------------------------------
# covered_clip_ids: dropping clips that only restate sites we have
# --------------------------------------------------------------------------


def test_a_clip_naming_only_a_covered_junction_is_dropped() -> None:
    pool = {"c1": draft("c1", "a tag was inserted after Thr-10")}
    dropped = covered_clip_ids(
        pool, sequence=SEQ, covered_junctions={10}, tolerance=2
    )
    assert dropped == {"c1"}


def test_a_clip_naming_an_uncovered_junction_is_kept() -> None:
    pool = {"c1": draft("c1", "a tag was inserted after Lys-21")}
    assert covered_clip_ids(pool, sequence=SEQ, covered_junctions={10}) == set()


def test_a_clip_naming_both_covered_and_uncovered_is_kept() -> None:
    """The case that makes this a filter rather than a blocklist: a clip that
    corroborates a known site AND names a new one is new evidence."""
    pool = {"c1": draft("c1", "tags at Thr-10 and Lys-21 were compared")}
    assert covered_clip_ids(pool, sequence=SEQ, covered_junctions={10}) == set()


def test_tolerance_covers_the_neighbouring_residue() -> None:
    """Papers differ on whether the label is the residue before or after the
    junction, so a clip naming 11 for a site published at 10 is restating it."""
    pool = {"c1": draft("c1", "inserted after Gly-11")}
    assert covered_clip_ids(
        pool, sequence=SEQ, covered_junctions={10}, tolerance=2
    ) == {"c1"}


def test_a_clip_naming_no_residue_is_never_dropped_as_covered() -> None:
    """Most clips name no position at all. They cannot be restating a known
    site, so they are not this filter's business — dropping them would discard
    most of the pool."""
    pool = {"c1": draft("c1", "surface expression was measured by flow cytometry")}
    assert covered_clip_ids(pool, sequence=SEQ, covered_junctions={10}) == set()


def test_nothing_is_dropped_when_no_junction_is_published_yet() -> None:
    pool = {"c1": draft("c1", "inserted after Thr-10")}
    assert covered_clip_ids(pool, sequence=SEQ, covered_junctions=set()) == set()


def test_a_residue_the_sequence_denies_does_not_count_as_covered() -> None:
    """"D10" is not a residue of this protein (position 10 is T), so it is
    noise and must not be read as restating the site at 10 — the same
    sequence-confirmation rule the rest of the pipeline uses."""
    pool = {"c1": draft("c1", "the D10 variant was unaffected")}
    assert covered_clip_ids(pool, sequence=SEQ, covered_junctions={10}) == set()


# --------------------------------------------------------------------------
# count_new + the pause gate
# --------------------------------------------------------------------------


def test_new_excludes_carried_and_already_examined_clips() -> None:
    pool = {
        "fresh": draft("fresh", "a brand new sentence"),
        "carried_001_PMCPMC9": draft("carried_001_PMCPMC9", "cited last time"),
        "seen": draft("seen", "examined by the previous run", "PMC:PMC7"),
    }
    scope = EnrichmentScope(
        carried={"carried_001_PMCPMC9"},
        seen_keys={seen_key("PMC:PMC7", "examined by the previous run")},
        dropped_covered=set(),
    )
    assert count_new(pool, scope) == 1


def test_a_dropped_covered_clip_is_not_new_either() -> None:
    pool = {
        "fresh": draft("fresh", "a brand new sentence"),
        "covered": draft("covered", "inserted after Thr-10"),
    }
    scope = EnrichmentScope(
        carried=set(), seen_keys=set(), dropped_covered={"covered"}
    )
    assert count_new(pool, scope) == 1


def test_the_gate_opens_when_there_is_new_evidence() -> None:
    pool = {"fresh": draft("fresh", "a brand new sentence")}
    scope = EnrichmentScope(carried=set(), seen_keys=set(), dropped_covered=set())
    assert scope.should_pause(pool) is False


def test_the_gate_closes_when_everything_was_already_examined() -> None:
    """The whole point: no selector call, no synthesis call, no spend beyond
    the triage that discovered nothing new."""
    pool = {"seen": draft("seen", "examined before", "PMC:PMC7")}
    scope = EnrichmentScope(
        carried=set(),
        seen_keys={seen_key("PMC:PMC7", "examined before")},
        dropped_covered=set(),
    )
    assert scope.should_pause(pool) is True


def test_the_gate_closes_on_an_empty_pool() -> None:
    scope = EnrichmentScope(carried=set(), seen_keys=set(), dropped_covered=set())
    assert scope.should_pause({}) is True


def test_a_pool_of_only_carried_clips_pauses() -> None:
    """A gene whose every clip is one it already cited has no new evidence, and
    re-synthesizing from the same ledger would re-derive the same sites at full
    price."""
    pool = {"carried_001_PMCPMC9": draft("carried_001_PMCPMC9", "cited last time")}
    scope = EnrichmentScope(
        carried={"carried_001_PMCPMC9"}, seen_keys=set(), dropped_covered=set()
    )
    assert scope.should_pause(pool) is True
