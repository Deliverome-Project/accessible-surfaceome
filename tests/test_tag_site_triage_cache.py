"""The triage cache is the resume path: it must reuse only what is still valid."""
from __future__ import annotations

import types

from accessible_surfaceome.agents.tag_site import triage_cache as tc


def _outcome(pid: str, decision: str = "worth_fetching", error: str | None = None):
    resp = None if error else types.SimpleNamespace(decision=decision, reason="r")
    return types.SimpleNamespace(
        paper_id=pid, response=resp, usage=None, elapsed_s=0.1, error=error
    )


def test_a_cached_verdict_is_reused_and_the_rest_still_run(tmp_path) -> None:
    sha = "abc123"
    tc.save("GENE", [_outcome("PMC:1"), _outcome("PMC:2")], prompt_sha=sha, cache_dir=tmp_path)
    cached = tc.load("GENE", cache_dir=tmp_path)
    papers = {"PMC:1": object(), "PMC:2": object(), "PMC:3": object()}

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
