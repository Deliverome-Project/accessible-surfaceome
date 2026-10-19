"""Carrying a previously-cited clip forward, so a transient fetch failure
cannot lose a site.

The pool is not monotonic across runs. SLC6A3 returned 7 sites in the first
library sweep and 3 in the depth spike, and the cause was not the menu: 9 of its
12 previously-cited clips were still in the pool and all 9 reached the selector.
The 3 that vanished were absent from the pool entirely, because **179 papers
degraded to abstract-only across the 20-gene sweep** (EuropePMC `fullTextXML`
returning 500). A paper that degrades contributes no methods clips, so a correct
site becomes unreachable for a reason that has nothing to do with the search.

A rerun holding less evidence than its predecessor is therefore the NORMAL case
under transient failure, not a signal. Seeding the pool from the prior run's
cited clips removes the failure mode at the source rather than compensating for
it downstream.

The honesty constraint: a carried-forward clip was span-verified *then*, not
now. Registering its archived quote as the source body makes the span check pass
trivially, which is correct in substance — it genuinely was verified — but would
make ``entailment_verified`` mean two different things if the inheritance were
invisible. So carried clips are marked, and a fresh body always wins over an
archived quote.
"""

from __future__ import annotations

import json

from accessible_surfaceome.agents.tag_site.prior_ledger import (
    CARRIED_PREFIX,
    PriorClip,
    is_carried,
    parse_prior_clips,
    seed_pool,
)
from accessible_surfaceome.tools._shared.models import EvidenceClaimDraft
from accessible_surfaceome.tools._shared.source_text import SourceTextStore


def draft(clip_id: str, quote: str, source_id: str = "PMC:PMC1") -> EvidenceClaimDraft:
    return EvidenceClaimDraft(
        suggested_evidence_id=clip_id,
        quote=quote,
        source_id=source_id,
        section="methods",
        hallmark_phrase="tag insertion",
        score=1.0,
    )


# --------------------------------------------------------------------------
# parsing the archived ledger
# --------------------------------------------------------------------------


def test_parses_the_archived_ledger_rows() -> None:
    rows = [
        {
            "run_id": "tag_site_library_v1",
            "ledger_json": json.dumps(
                [
                    {"source_id": "PMC:PMC9", "claim": "a claim", "quote": "a quote"},
                    {"source_id": "PMID:12", "claim": "b claim", "quote": "b quote"},
                ]
            ),
        }
    ]
    clips = parse_prior_clips(rows)
    assert [c.source_id for c in clips] == ["PMC:PMC9", "PMID:12"]
    assert clips[0].run_id == "tag_site_library_v1"


def test_skips_rows_with_no_ledger_and_clips_with_no_quote() -> None:
    """A clip with no quote has nothing to anchor a span check against, so it
    cannot be carried — and an empty ledger is the common case (1,106 of the
    first sweep's genes found nothing)."""
    rows = [
        {"run_id": "r", "ledger_json": None},
        {"run_id": "r", "ledger_json": "[]"},
        {"run_id": "r", "ledger_json": json.dumps([{"source_id": "X", "quote": ""}])},
        {"run_id": "r", "ledger_json": "not json at all"},
    ]
    assert parse_prior_clips(rows) == []


def test_dedupes_the_same_clip_archived_by_several_runs() -> None:
    """A gene re-run under a new prompt has the same clip in several rows. It is
    one piece of evidence, not three."""
    entry = {"source_id": "PMC:PMC9", "claim": "c", "quote": "the same quote"}
    rows = [
        {"run_id": "run_a", "ledger_json": json.dumps([entry])},
        {"run_id": "run_b", "ledger_json": json.dumps([entry])},
    ]
    assert len(parse_prior_clips(rows)) == 1


# --------------------------------------------------------------------------
# seeding the pool
# --------------------------------------------------------------------------


def test_a_prior_clip_missing_from_the_pool_is_carried_in() -> None:
    """The failure this exists for: the paper degraded to abstract-only this
    run, so its methods clip is simply not in the pool."""
    pool = {"draft_PMC2_methods_1": draft("draft_PMC2_methods_1", "unrelated text")}
    store = SourceTextStore()
    carried = seed_pool(
        pool,
        [PriorClip(source_id="PMC:PMC9", claim="c", quote="a tag was inserted after T436", run_id="r")],
        store=store,
    )
    assert len(carried) == 1
    cid = next(iter(carried))
    assert cid.startswith(CARRIED_PREFIX)
    assert is_carried(cid)
    assert pool[cid].quote == "a tag was inserted after T436"
    assert pool[cid].source_id == "PMC:PMC9"


def test_a_prior_clip_already_in_the_pool_is_not_duplicated() -> None:
    """The fresh clip wins. It came from a real body this run, so it has a real
    char offset; the archived copy would only add a second menu entry saying the
    same thing and spend menu budget to do it."""
    quote = "a tag was inserted after T436"
    pool = {"draft_PMC9_methods_3": draft("draft_PMC9_methods_3", quote, "PMC:PMC9")}
    carried = seed_pool(
        pool,
        [PriorClip(source_id="PMC:PMC9", claim="c", quote=quote, run_id="r")],
        store=SourceTextStore(),
    )
    assert carried == set()
    assert len(pool) == 1


def test_dedupe_survives_typographic_punctuation() -> None:
    """The repo's known quote failure: NFKC does not fold a curly apostrophe to
    a straight one, and a 448-character quote was once deleted over exactly
    that. The pool comparison normalizes, so the archived and fresh forms of one
    sentence are one clip."""
    pool = {
        "draft_PMC9_methods_3": draft(
            "draft_PMC9_methods_3", "the receptor’s ectodomain was tagged", "PMC:PMC9"
        )
    }
    carried = seed_pool(
        pool,
        [
            PriorClip(
                source_id="PMC:PMC9",
                claim="c",
                quote="the receptor's ectodomain was tagged",
                run_id="r",
            )
        ],
        store=SourceTextStore(),
    )
    assert carried == set()


def test_the_archived_quote_is_registered_so_the_span_check_can_pass() -> None:
    """Promotion drops any clip whose quote is not locatable in a registered
    body. A carried clip's body did not fetch this run, so the archived quote
    becomes the body — inheriting the earlier verification rather than
    re-performing it."""
    store = SourceTextStore()
    seed_pool(
        {},
        [PriorClip(source_id="PMC:PMC9", claim="c", quote="inserted after T436", run_id="r")],
        store=store,
    )
    registered = store.get("PMC:PMC9")
    assert registered is not None
    assert "inserted after T436" in registered.raw_text


def test_a_real_body_already_in_the_store_is_never_replaced() -> None:
    """A fetched body is strictly richer than a single archived sentence, and
    the span check wants the real surrounding text. First-write-wins, so a
    carried clip must not clobber it."""
    store = SourceTextStore()
    pool: dict[str, EvidenceClaimDraft] = {}
    seed_pool(
        pool,
        [PriorClip(source_id="PMC:PMC9", claim="c", quote="first sentence", run_id="r")],
        store=store,
    )
    before = store.get("PMC:PMC9")
    assert before is not None
    seed_pool(
        pool,
        [PriorClip(source_id="PMC:PMC9", claim="c", quote="second sentence", run_id="r")],
        store=store,
    )
    after = store.get("PMC:PMC9")
    assert after is not None
    assert after.raw_text == before.raw_text


def test_carried_clips_are_identifiable_so_they_do_not_count_as_new() -> None:
    """The pause gate stops a run that found no NEW evidence. A carried clip is
    by definition not new, so counting it would defeat the gate and pay for a
    synthesis call on evidence the previous run already used."""
    pool: dict[str, EvidenceClaimDraft] = {
        "draft_PMC2_methods_1": draft("draft_PMC2_methods_1", "fresh text", "PMC:PMC2")
    }
    carried = seed_pool(
        pool,
        [PriorClip(source_id="PMC:PMC9", claim="c", quote="old text", run_id="r")],
        store=SourceTextStore(),
    )
    new_clips = [cid for cid in pool if cid not in carried]
    assert len(new_clips) == 1
    assert not any(is_carried(cid) for cid in new_clips)
    assert all(is_carried(cid) for cid in carried)


def test_carried_clips_score_high_enough_to_reach_the_menu() -> None:
    """A clip carried forward because its paper failed to fetch must not then
    be cut by the menu cap — that would reintroduce the loss it exists to
    prevent. It was good enough to cite last time, so it outranks fresh
    unselected clips."""
    pool = {f"d{i}": draft(f"d{i}", f"text {i}") for i in range(5)}
    for i, d in enumerate(pool.values()):
        object.__setattr__(d, "score", 1.0)  # pydantic model, but mutable field
    carried = seed_pool(
        pool,
        [PriorClip(source_id="PMC:PMC9", claim="c", quote="cited last time", run_id="r")],
        store=SourceTextStore(),
    )
    cid = next(iter(carried))
    assert pool[cid].score > max(
        d.score for k, d in pool.items() if k != cid
    )


def test_the_registered_url_matches_the_accession_namespace() -> None:
    """The cited corpus is not all PMC. A real carried clip in the first
    validation run was `DOI:10.1101/712448`, a bioRxiv preprint — giving it a
    PMC article URL would persist a link that 404s into the field citation
    display reads, and the repo's rule is that a cited source must be one click
    from itself."""
    store = SourceTextStore()
    seed_pool(
        {},
        [
            PriorClip(source_id="PMC:PMC9", claim="c", quote="pmc quote", run_id="r"),
            PriorClip(source_id="PMID:12345", claim="c", quote="pmid quote", run_id="r"),
            PriorClip(
                source_id="DOI:10.1101/712448", claim="c", quote="doi quote", run_id="r"
            ),
        ],
        store=store,
    )
    for source_id, expected in (
        ("PMC:PMC9", "https://www.ncbi.nlm.nih.gov/pmc/articles/PMC9/"),
        ("PMID:12345", "https://pubmed.ncbi.nlm.nih.gov/12345/"),
        ("DOI:10.1101/712448", "https://doi.org/10.1101/712448"),
    ):
        registered = store.get(source_id)
        assert registered is not None, source_id
        assert registered.url == expected
