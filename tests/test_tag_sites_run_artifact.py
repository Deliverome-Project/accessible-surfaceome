"""The run artifact has to answer "why was this clip not picked" without a re-run.

`data/external/tag_site_runs/{id}.json` is documented as holding the clip pool,
and it did not: across 26 members of a live sweep, `pool` was empty in all 26
while `n_clips` recorded 60-214. The size was saved and the contents were not,
so the one question the artifact exists for still cost a fresh run.

It also recorded `outcome: "incomplete"` on 10 of those 26 — runs that cost
money, that the sweep logged `ok`, and whose own record could not say what
happened. `incomplete` is the initial value: three `_empty()` return paths never
set an outcome at all.

Two constraints shape the pool record:

* It must be BOUNDED. `EvidenceClaimDraft.context_excerpt` runs to 1500 chars
  and one member's pool held 2,175 clips, so persisting drafts verbatim is
  megabytes per gene and hundreds of megabytes across the cohort.
* It must still answer the question. Clip id, source, section, score rank,
  whether the residue-boost lifted it, whether the selector took it, and enough
  quote to recognise it.
"""

from __future__ import annotations

from accessible_surfaceome.agents.tag_site import runner as R


class _Draft:
    """The fields the index reads off an `EvidenceClaimDraft`."""

    def __init__(self, source_id: str, quote: str, section: str = "Methods") -> None:
        self.source_id = source_id
        self.quote = quote
        self.section = section
        self.context_excerpt = "x" * 1500  # must NOT be persisted


def pool() -> dict[str, object]:
    return {
        "c1": _Draft("PMID:111", "a myc tag was inserted after residue 246"),
        "c2": _Draft("PMID:222", "the receptor was expressed in HEK cells"),
        "c3": _Draft("PMID:333", "surface biotinylation was performed"),
    }


def test_every_clip_in_the_pool_is_recorded() -> None:
    """The gap this closes: 26 of 26 artifacts had an empty pool."""
    idx = R._pool_index(pool(), boosted={}, selected=set())
    assert {e["clip_id"] for e in idx} == {"c1", "c2", "c3"}


def test_the_selector_decision_is_recorded_per_clip() -> None:
    """"Why wasn't clip X picked" is unanswerable without this."""
    idx = {e["clip_id"]: e for e in R._pool_index(pool(), boosted={}, selected={"c1"})}
    assert idx["c1"]["selected"] is True
    assert idx["c2"]["selected"] is False


def test_the_residue_boost_is_recorded() -> None:
    """A clip naming an extracellular residue is lifted before the menu cap.
    Whether the lift happened is the difference between "the model saw it and
    passed" and "the model never saw it"."""
    idx = {e["clip_id"]: e
           for e in R._pool_index(pool(), boosted={"c1": {246}}, selected=set())}
    assert idx["c1"]["boosted_residues"] == [246]
    assert idx["c2"]["boosted_residues"] == []


def test_the_source_and_section_are_recorded() -> None:
    idx = {e["clip_id"]: e for e in R._pool_index(pool(), boosted={}, selected=set())}
    assert idx["c1"]["source_id"] == "PMID:111"
    assert idx["c1"]["section"] == "Methods"


def test_enough_quote_to_recognise_the_clip() -> None:
    idx = {e["clip_id"]: e for e in R._pool_index(pool(), boosted={}, selected=set())}
    assert "inserted after residue 246" in idx["c1"]["quote_head"]


def test_the_record_is_bounded() -> None:
    """`context_excerpt` is up to 1500 chars per draft and must never be
    persisted — 2,175 clips of it is megabytes for one gene."""
    idx = R._pool_index(pool(), boosted={}, selected=set())
    blob = repr(idx)
    assert "x" * 200 not in blob, "context_excerpt leaked into the artifact"
    for entry in idx:
        assert len(entry["quote_head"]) <= R._POOL_QUOTE_CHARS


def test_a_long_quote_is_truncated_not_dropped() -> None:
    long_pool = {"c1": _Draft("PMID:111", "y" * 5000)}
    idx = R._pool_index(long_pool, boosted={}, selected=set())
    assert len(idx[0]["quote_head"]) == R._POOL_QUOTE_CHARS
    assert idx[0]["quote_chars"] == 5000, "the true length is still recorded"


def test_an_empty_pool_records_an_empty_list_not_a_crash() -> None:
    assert R._pool_index({}, boosted={}, selected=set()) == []


# --------------------------------------------------------------------------
# outcome: every exit has to say what happened
# --------------------------------------------------------------------------


def test_every_empty_return_sets_an_outcome_first() -> None:
    """Structural, because `run_tag_site_agent` cannot be driven without network
    and model calls. 10 of 26 live runs recorded `incomplete`, which is the
    initial value — so a path returned without stamping. This pins that every
    `return _empty()` is preceded by an outcome assignment within a few lines.
    """
    import inspect

    src = inspect.getsource(R).splitlines()
    returns = [i for i, line in enumerate(src) if "return _empty()" in line]
    assert returns, "no _empty() returns found — did the function move?"
    for i in returns:
        window = "\n".join(src[max(0, i - 8) : i])
        assert '_progress["outcome"]' in window, (
            f"the _empty() return at source line {i + 1} does not set an outcome; "
            f"it would record the initial 'incomplete'"
        )


def test_the_outcomes_are_distinct() -> None:
    """Three different reasons for an empty result — no papers, no span-verified
    evidence, synthesis returned nothing — plus the deliberate pause. Collapsing
    them to one string would make the artifact say 'empty' without saying why."""
    import inspect
    import re

    values = set(
        re.findall(r'_progress\["outcome"\]\s*=\s*"([^"]+)"', inspect.getsource(R))
    )
    assert len(values) >= 4, f"expected >=4 distinct outcomes, got {sorted(values)}"
    assert "incomplete" not in values, "'incomplete' is the initial value, not a result"
