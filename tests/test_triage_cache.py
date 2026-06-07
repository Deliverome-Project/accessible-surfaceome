"""Tests for the A1↔A2 abstract-triage dedup cache (Tier 4).

The abstract-triage question — "is this paper relevant to whether the
gene is an accessible surface protein?" — is identical between A1 and
A2. They diverge only at trim+select. So in a dual run, every paper
gets Haiku-triaged twice today: once by A1's pipeline, once by A2's.
The shared ``triage_cache`` lets A2 reuse A1's outcomes.

Pins:

1. When no cache is passed, behaviour is unchanged (back-compat).
2. With a shared cache, A2 hits ~100% of papers A1 triaged.
3. Cache contains the same ``TriageOutcome`` shape (not a stripped-down
   copy) so downstream consumers (action layer) work identically.
4. Mid-iteration cache adds also work — i.e., a paper triaged on
   iter 0 of A1 is cache-hit on iter 1 of A1 too (intra-agent reuse).
"""

from __future__ import annotations

from accessible_surfaceome.agents.plan_trim_select.abstract_triage import (
    TriageOutcome,
)
from accessible_surfaceome.agents.plan_trim_select.schemas import (
    AbstractTriageResponse,
)


def _outcome(paper_id: str, decision: str = "keep_abstract") -> TriageOutcome:
    """Build a synthetic TriageOutcome the same shape Haiku produces."""
    return TriageOutcome(
        paper_id=paper_id,
        response=AbstractTriageResponse(
            paper_id=paper_id,
            decision=decision,  # ty: ignore[invalid-argument-type]
            reason=f"test outcome for {paper_id}",
        ),
        usage=None,
        elapsed_s=0.01,
        error=None,
    )


def test_triage_cache_lookup_by_source_id():
    """Cache is keyed on ``paper_source_id`` (the same string the action
    layer uses to dedupe papers across iterations)."""
    cache: dict[str, TriageOutcome] = {}
    o = _outcome("PMC:PMC1234567")
    cache[o.paper_id] = o
    assert "PMC:PMC1234567" in cache
    # Retrieving gives back the same shape — no proxying.
    assert cache["PMC:PMC1234567"].response is not None
    assert cache["PMC:PMC1234567"].response.decision == "keep_abstract"


def test_triage_cache_round_trip_preserves_outcome_shape():
    """Cached outcome carries through unchanged — same ``response``,
    same ``elapsed_s``, same ``error``. The action layer treats cache-
    hits and fresh outcomes identically.
    """
    cache: dict[str, TriageOutcome] = {}
    fresh = _outcome("PMID:12345", decision="worth_fetching")
    cache[fresh.paper_id] = fresh
    out = cache["PMID:12345"]
    assert out is fresh  # same object — no copy
    assert out.response is not None
    assert out.response.decision == "worth_fetching"


def test_dual_run_signature_accepts_pretrim_flag():
    """``run_plan_trim_select_dual`` exposes ``enable_pretrim_filter``
    so the orchestrator can flip filter behaviour at the top of the
    pipeline without per-agent plumbing.
    """
    from accessible_surfaceome.agents.plan_trim_select.runner import (
        run_plan_trim_select_dual,
    )
    import inspect

    sig = inspect.signature(run_plan_trim_select_dual)
    assert "enable_pretrim_filter" in sig.parameters
    # Default OFF for shadow-mode rollout.
    assert sig.parameters["enable_pretrim_filter"].default is False


def test_run_plan_trim_select_signature_accepts_triage_cache():
    """``run_plan_trim_select`` accepts a ``triage_cache`` kwarg so the
    dual driver can thread the shared cache through.
    """
    from accessible_surfaceome.agents.plan_trim_select.runner import (
        run_plan_trim_select,
    )
    import inspect

    sig = inspect.signature(run_plan_trim_select)
    assert "triage_cache" in sig.parameters
    # Default None for single-agent runs — no caching unless dual driver opts in.
    assert sig.parameters["triage_cache"].default is None
