"""Tests for `apply_triage_outcomes` — the action layer that turns triage
decisions into pool mutations.

Covers the three decisions plus the worth_fetching fetch outcomes:
successful body fetch, fetch exception (→ abstract fallback), and the
defensive empty-body case (fetch returned [] → abstract fallback, so the
paper isn't silently dropped).
"""

from __future__ import annotations

from collections import defaultdict
from datetime import UTC, datetime
from typing import Literal, cast

from accessible_surfaceome.agents.plan_trim_select import abstract_triage
from accessible_surfaceome.agents.plan_trim_select.abstract_triage import (
    TriageOutcome,
    apply_triage_outcomes,
    paper_source_id,
)
from accessible_surfaceome.agents.plan_trim_select.runner import _add_to_pool
from accessible_surfaceome.agents.plan_trim_select.schemas import AbstractTriageResponse
from accessible_surfaceome.tools._shared.http import CachedHTTP
from accessible_surfaceome.tools._shared.models import EvidenceClaimDraft, Paper
from accessible_surfaceome.tools._shared.retraction_watch import RetractionIndex

_Decision = Literal["discard", "keep_abstract", "worth_fetching"]


def _paper(pmid: int = 21444918, pmc_id: str | None = None) -> Paper:
    return Paper(
        pmid=pmid,
        pmc_id=pmc_id,
        title="CD20 surface biology",
        abstract="CD20 was detected at the B-cell surface by flow cytometry. "
        "Surface MFI correlated with rituximab response in the cohort.",
        retraction_checked_at=datetime.now(UTC),
    )


def _outcome(paper: Paper, decision: _Decision) -> TriageOutcome:
    return TriageOutcome(
        paper_id=paper_source_id(paper),
        response=AbstractTriageResponse(
            paper_id=paper_source_id(paper), decision=decision, reason="t"
        ),
        usage=None,
        elapsed_s=0.1,
    )


def _apply(outcome: TriageOutcome, paper: Paper):
    pool: dict[str, EvidenceClaimDraft] = {}
    by_source: dict[str, list[EvidenceClaimDraft]] = defaultdict(list)
    actions = apply_triage_outcomes(
        [outcome],
        {paper_source_id(paper): paper},
        pool=pool,
        by_source=by_source,
        # discard / keep_abstract never touch http; worth_fetching tests
        # monkeypatch _fetch_body_drafts, so the real client is never used.
        http=cast(CachedHTTP, None),
        retraction_index=cast(RetractionIndex, None),
        add_to_pool_fn=_add_to_pool,
    )
    return actions, pool


def test_discard_adds_nothing() -> None:
    paper = _paper()
    actions, pool = _apply(_outcome(paper, "discard"), paper)
    assert len(actions) == 1
    assert actions[0].decision == "discard"
    assert not pool


def test_keep_abstract_adds_preview_clips() -> None:
    paper = _paper()
    actions, pool = _apply(_outcome(paper, "keep_abstract"), paper)
    assert actions[0].decision == "keep_abstract"
    assert actions[0].drafts_added >= 1
    assert len(pool) >= 1
    assert all(d.hallmark_phrase == "abstract_preview" for d in pool.values())


def test_worth_fetching_success_adds_body_clips(monkeypatch) -> None:
    paper = _paper(pmc_id="PMC9398497")
    body = [
        EvidenceClaimDraft(
            suggested_evidence_id="draft_PMC9398497_results_01",
            quote="CD20 was biotinylated at the surface.",
            source_id="PMC:PMC9398497",
            section="results",
            hallmark_phrase="paper_level",
            score=1.8,
        )
    ]
    monkeypatch.setattr(
        abstract_triage,
        "_fetch_body_drafts",
        lambda *a, **k: abstract_triage._BodyFetch(drafts=body, source="pmc_xml"),
    )
    actions, pool = _apply(_outcome(paper, "worth_fetching"), paper)
    assert actions[0].fetched_body is True
    assert actions[0].fetch_source == "pmc_xml"
    assert actions[0].drafts_added == 1
    assert "draft_PMC9398497_results_01" in pool


def test_worth_fetching_batches_pmid_to_pmcid_lookup(monkeypatch) -> None:
    papers = [_paper(pmid=101), _paper(pmid=202)]
    outcomes = [_outcome(p, "worth_fetching") for p in papers]
    body = [
        EvidenceClaimDraft(
            suggested_evidence_id="draft_PMC101_results_01",
            quote="CD20 was biotinylated at the surface.",
            source_id="PMC:PMC101",
            section="results",
            hallmark_phrase="paper_level",
            score=1.8,
        )
    ]
    batch_calls: list[list[int]] = []
    fetch_kwargs: list[dict[str, object]] = []

    def _batch(pmids, **_kwargs):
        batch_calls.append(list(pmids))
        return {101: "PMC101"}

    def _fetch(*_args, **kwargs):
        fetch_kwargs.append(dict(kwargs))
        return abstract_triage._BodyFetch(drafts=body, source="pmc_xml")

    monkeypatch.setattr(abstract_triage, "_lookup_pmcids_for_pmids", _batch)
    monkeypatch.setattr(abstract_triage, "_fetch_body_drafts", _fetch)

    pool: dict[str, EvidenceClaimDraft] = {}
    by_source: dict[str, list[EvidenceClaimDraft]] = defaultdict(list)
    actions = apply_triage_outcomes(
        outcomes,
        {paper_source_id(p): p for p in papers},
        pool=pool,
        by_source=by_source,
        http=cast(CachedHTTP, None),
        retraction_index=cast(RetractionIndex, None),
        add_to_pool_fn=_add_to_pool,
        fetch_concurrency=2,
    )

    assert batch_calls == [[101, 202]]
    assert len(fetch_kwargs) == 2
    assert all(kw["pmcid_lookup_done"] is True for kw in fetch_kwargs)
    assert {kw["pmcid_override"] for kw in fetch_kwargs} == {"PMC101", None}
    assert all(a.fetched_body is True for a in actions)


def test_batch_pmcid_lookup_parses_multiple_linksets() -> None:
    class _HTTP:
        def get_json(self, *_args, **kwargs):
            assert kwargs["params"]["id"] == "101,202,303"
            return {
                "linksets": [
                    {
                        "ids": ["101"],
                        "linksetdbs": [{"dbto": "pmc", "links": ["555"]}],
                    },
                    {"ids": ["202"], "linksetdbs": []},
                    {
                        "ids": ["303"],
                        "linksetdbs": [{"dbto": "pmc", "links": ["777"]}],
                    },
                ]
            }

    got = abstract_triage._lookup_pmcids_for_pmids(
        [303, 101, 101, 202],
        http=cast(CachedHTTP, _HTTP()),
    )

    assert got == {101: "PMC555", 303: "PMC777"}


def test_worth_fetching_exception_falls_back_to_abstract(monkeypatch) -> None:
    paper = _paper()

    def _boom(*a, **k):
        raise RuntimeError("body not available")

    monkeypatch.setattr(abstract_triage, "_fetch_body_drafts", _boom)
    actions, pool = _apply(_outcome(paper, "worth_fetching"), paper)
    assert actions[0].fetched_body is False
    assert actions[0].fell_back_to_abstract is True
    assert "RuntimeError" in (actions[0].fetch_error or "")
    assert len(pool) >= 1  # abstract preview present
    assert all(d.hallmark_phrase == "abstract_preview" for d in pool.values())


def test_worth_fetching_empty_body_falls_back_to_abstract(monkeypatch) -> None:
    # The defensive case: fetch succeeds structurally but yields zero
    # clips. Must fall back to the abstract, not silently drop the paper.
    paper = _paper()
    monkeypatch.setattr(
        abstract_triage,
        "_fetch_body_drafts",
        lambda *a, **k: abstract_triage._BodyFetch(drafts=[], source="pmc_xml"),
    )
    actions, pool = _apply(_outcome(paper, "worth_fetching"), paper)
    assert actions[0].fetched_body is False
    assert actions[0].fell_back_to_abstract is True
    assert actions[0].fetch_error == "fetched body yielded zero clips"
    assert len(pool) >= 1
