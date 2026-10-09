"""The triage cache is the resume path: it must reuse only what is still valid."""
from __future__ import annotations

import types

from accessible_surfaceome.agents.tag_site import triage_cache as tc


def _paper(title: str = "T", abstract: str = "A"):
    return types.SimpleNamespace(title=title, abstract=abstract)


def _outcome(pid: str, decision: str = "worth_fetching", error: str | None = None):
    resp = None if error else types.SimpleNamespace(decision=decision, reason="r")
    return types.SimpleNamespace(
        paper_id=pid, response=resp, usage=None, elapsed_s=0.1, error=error
    )


def test_a_cached_verdict_is_reused_and_the_rest_still_run(tmp_path) -> None:
    sha = "abc123"
    papers = {"PMC:1": _paper("t1"), "PMC:2": _paper("t2"), "PMC:3": _paper("t3")}
    tc.save(
        "GENE", [_outcome("PMC:1"), _outcome("PMC:2")], prompt_sha=sha,
        inputs={k: tc.input_sha(v) for k, v in papers.items()}, cache_dir=tmp_path,
    )
    cached = tc.load("GENE", cache_dir=tmp_path)

    todo, reused = tc.split(papers, cached, prompt_sha=sha)
    assert len(reused) == 2 and len(todo) == 1
    assert {o.paper_id for o in reused} == {"PMC:1", "PMC:2"}
    assert all(o.usage is None for o in reused)  # reused verdicts cost nothing


def test_a_changed_triage_prompt_invalidates_every_verdict(tmp_path) -> None:
    """The provenance rule is explicit: a record written under a different
    prompt_sha is re-run, never silently reused. Editing the triage prompt must
    therefore discard the cache with no flag to remember."""
    tc.save("GENE", [_outcome("PMC:1")], prompt_sha="old", cache_dir=tmp_path)
    cached = tc.load("GENE", cache_dir=tmp_path)

    todo, reused = tc.split({"PMC:1": object()}, cached, prompt_sha="NEW")
    assert len(todo) == 1 and not reused


def test_a_failed_triage_is_not_cached(tmp_path) -> None:
    """An error is a timeout or a rate limit. Caching it would make one bad
    minute permanent for that paper."""
    n = tc.save("GENE", [_outcome("PMC:1", error="timeout")], prompt_sha="s", cache_dir=tmp_path)
    assert n == 0
    assert tc.load("GENE", cache_dir=tmp_path) == {}


def test_saving_merges_rather_than_replaces(tmp_path) -> None:
    """A run that triaged a subset must not discard verdicts for papers it
    never looked at — otherwise resuming a partial run loses ground."""
    tc.save("GENE", [_outcome("PMC:1")], prompt_sha="s", cache_dir=tmp_path)
    tc.save("GENE", [_outcome("PMC:2")], prompt_sha="s", cache_dir=tmp_path)
    assert set(tc.load("GENE", cache_dir=tmp_path)) == {"PMC:1", "PMC:2"}


def test_a_corrupt_cache_is_ignored_not_fatal(tmp_path) -> None:
    (tmp_path / "GENE.json").write_text("{not json")
    assert tc.load("GENE", cache_dir=tmp_path) == {}


def test_the_sha_tracks_the_triage_prompt() -> None:
    from accessible_surfaceome.agents.plan_trim_select import abstract_triage as at

    before = tc.triage_prompt_sha()
    original = at._SYSTEM_PROMPT_CACHED
    try:
        at._SYSTEM_PROMPT_CACHED = original + "\n(edit)"
        assert tc.triage_prompt_sha() != before
    finally:
        at._SYSTEM_PROMPT_CACHED = original
    assert tc.triage_prompt_sha() == before


def test_a_changed_abstract_invalidates_the_verdict(tmp_path) -> None:
    """The prompt is only half of what produced a verdict. A paper whose
    abstract is corrected, de-truncated on a later fetch, or replaced when the
    preprint is published is a DIFFERENT input, and a verdict formed on the old
    text is as stale as one formed under the old prompt."""
    old, new = _paper(abstract="original abstract"), _paper(abstract="corrected abstract")
    tc.save(
        "GENE", [_outcome("PMC:1")], prompt_sha="s",
        inputs={"PMC:1": tc.input_sha(old)}, cache_dir=tmp_path,
    )
    cached = tc.load("GENE", cache_dir=tmp_path)

    _, reused = tc.split({"PMC:1": old}, cached, prompt_sha="s")
    assert len(reused) == 1  # unchanged input → reused

    todo, reused = tc.split({"PMC:1": new}, cached, prompt_sha="s")
    assert len(todo) == 1 and not reused  # changed abstract → re-run


def test_whitespace_only_differences_do_not_churn_the_cache(tmp_path) -> None:
    a, b = _paper(abstract="  same text  "), _paper(abstract="same text")
    assert tc.input_sha(a) == tc.input_sha(b)


def test_an_entry_without_an_input_sha_is_re_run(tmp_path) -> None:
    """Entries written before input_sha existed cannot say what they saw, so
    the cheap correct reading is to re-run them."""
    tc.save("GENE", [_outcome("PMC:1")], prompt_sha="s", cache_dir=tmp_path)  # no inputs=
    cached = tc.load("GENE", cache_dir=tmp_path)
    todo, reused = tc.split({"PMC:1": _paper()}, cached, prompt_sha="s")
    assert len(todo) == 1 and not reused
