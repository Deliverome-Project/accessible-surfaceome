"""Unit tests for the two parallel-dispatch paths in v2:

* ``orchestrator._run_builders_concurrently`` fans 9 builder specs
  across a thread pool, gathers outputs, populates ``builder_usage``,
  appends one TimingRecorder row per builder.
* ``runner._run_trim`` fans one Haiku call per paper across
  ``TRIM_CONCURRENCY`` workers, gathers TrimResponse / UsageRecord /
  StepTiming per paper.

Both paths share a single Anthropic client instance across workers
(the SDK is thread-safe via httpx) and a single TimingRecorder
(CPython's ``list.append`` is atomic). Tests:

* Each builder/paper's output ends up in the right slot in the result
  dict (no swaps, no losses).
* Token usage accumulates correctly across all workers.
* The TimingRecorder receives exactly one row per worker.
* Concurrency actually happens (wall clock < sum of per-worker waits).
"""

from __future__ import annotations

import json
import threading
import time
from typing import Any
from unittest.mock import MagicMock

import pytest

from accessible_surfaceome.agents._support.pricing import UsageRecord
from accessible_surfaceome.agents._support.timing import TimingRecorder
from accessible_surfaceome.agents.plan_trim_select.runner import (
    A1_TRIM_PROMPT_PATH,
    TRIM_CONCURRENCY,
    _run_trim,
)
from accessible_surfaceome.agents.surfaceome_v2.orchestrator import (
    BUILDER_CONCURRENCY,
    BlockBuilderUsage,
    _BuilderSpec,
    _run_builders_concurrently,
)
from accessible_surfaceome.tools._shared.models import (
    EvidenceClaim,
    EvidenceClaimDraft,
    MethodObservation,
)


# ---------------------------------------------------------------------------
# Shared mock helpers
# ---------------------------------------------------------------------------


def _mock_client_with_latency(
    *,
    per_call_latency_s: float,
    text_factory: Any,
    input_tokens: int = 100,
    output_tokens: int = 50,
) -> tuple[Any, list[float]]:
    """A MagicMock Anthropic client whose ``messages.create`` sleeps
    ``per_call_latency_s`` before returning. ``text_factory(call_idx)``
    yields the response text per call. Returns (client, call_timestamps).
    """

    call_timestamps: list[float] = []
    call_idx = {"n": 0}
    lock = threading.Lock()

    def _create(**_kwargs: Any) -> Any:
        with lock:
            idx = call_idx["n"]
            call_idx["n"] += 1
            call_timestamps.append(time.perf_counter())
        time.sleep(per_call_latency_s)
        block = MagicMock()
        block.text = text_factory(idx)
        usage = MagicMock()
        usage.input_tokens = input_tokens
        usage.output_tokens = output_tokens
        usage.cache_creation_input_tokens = 0
        usage.cache_read_input_tokens = 0
        resp = MagicMock()
        resp.content = [block]
        resp.usage = usage
        resp.stop_reason = "end_turn"
        return resp

    client = MagicMock()
    client.messages.create.side_effect = _create
    return client, call_timestamps


@pytest.fixture(autouse=True)
def _patch_text_block(monkeypatch: pytest.MonkeyPatch) -> None:
    """Both runner.TextBlock and builders._common.TextBlock need to accept
    MagicMock instances as valid TextBlocks."""
    from accessible_surfaceome.agents.plan_trim_select import runner as runner_mod
    from accessible_surfaceome.agents.surfaceome_v2.builders import (
        _common as common_mod,
    )

    monkeypatch.setattr(
        common_mod, "TextBlock", (common_mod.TextBlock, MagicMock), raising=True
    )
    monkeypatch.setattr(
        runner_mod, "TextBlock", (runner_mod.TextBlock, MagicMock), raising=True
    )


# ---------------------------------------------------------------------------
# Block-builder concurrency
# ---------------------------------------------------------------------------


def _claim(evi_id: str, *, evidence_type: str = "flow_cytometry") -> EvidenceClaim:
    return EvidenceClaim.model_validate(
        {
            "evidence_id": f"a1_evi_{evi_id}",
            "claim": "Synthetic claim",
            "claim_type": "surface_expression",
            "direction": "supports",
            "evidence_type": evidence_type,
            "evidence_tier": "primary",
            "confidence": "moderate",
            "assay_context": {
                "species": "human",
                "cell_type_or_line": "HEK293",
                "permeabilized": False,
            },
            "source_id": "PMID:11111",
            "quote": "Example verbatim quote.",
            "section": "results",
        }
    )


def _method_json_with_citation(evi_id: str) -> str:
    payload = [
        {
            "method_family": "flow_cytometry",
            "method_subclass": "live_cell_flow",
            "permeabilization": "nonpermeabilized",
            "expression_system": "endogenous",
            "antibodies": [],
            "accessibility_relevance": "direct_surface_accessibility",
            "surface_claim_type": "surface_accessible",
            "expression_observations": [],
            "cited_evidence_ids": [evi_id],
        }
    ]
    return f"```json\n{json.dumps(payload)}\n```"


def _stub_builder_fn(label: str):
    """Build a fake builder callable with the same kwargs signature as
    a real builder. Sleeps ``0.1s`` to simulate Sonnet latency so we
    can verify the wall-clock speedup from concurrency."""

    def _fn(
        claims: list[EvidenceClaim],
        *,
        client: Any,
        usage_sink: list[UsageRecord],
        context: dict[str, Any] | None = None,
        meta_sink: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        time.sleep(0.1)
        # Append a stub UsageRecord so the per-builder cost rollup has
        # something to summarize.
        usage_sink.append(
            UsageRecord(
                input_tokens=100,
                output_tokens=50,
                cache_creation_input_tokens=0,
                cache_read_input_tokens=0,
                cost_usd=0.001,
            )
        )
        # Stub a successful repair-loop summary so the orchestrator's
        # ``BlockBuilderUsage`` ends up with ``n_repair_attempts=0`` /
        # ``validation_error=None`` — the real builders write the same
        # shape via ``call_builder``'s ``meta_sink`` plumbing.
        if meta_sink is not None:
            meta_sink["n_repair_attempts"] = 0
            meta_sink["validation_error"] = None
        return {"label": label, "n_claims": len(claims)}

    return _fn


def test_builders_run_concurrently_and_collect_outputs() -> None:
    """All 9 specs land in the result dict by name; total wall clock is
    far less than 9 × per-builder latency (proves real concurrency)."""
    timing = TimingRecorder()
    builder_usage: dict[str, BlockBuilderUsage] = {}
    claims = [_claim(f"{i:02d}") for i in range(3)]
    ctx = {"gene": "TEST"}
    specs = [
        _BuilderSpec(
            name=name,
            phase="builders_a1" if i < 4 else "builders_a2",
            fn=_stub_builder_fn(name),
            claims=claims,
            ctx=ctx,
        )
        for i, name in enumerate(
            [
                "methods",
                "contradictions",
                "evidence_grade",
                "tissues",
                "cell_types",
                "subcellular_localization",
                "anatomical_accessibility",
                "accessibility_modulation",
            ]
        )
    ]

    t0 = time.perf_counter()
    outputs = _run_builders_concurrently(
        specs, client=MagicMock(), timing=timing, builder_usage=builder_usage
    )
    elapsed = time.perf_counter() - t0

    # All 8 outputs land in the dict, each with its own builder's label.
    assert set(outputs.keys()) == {s.name for s in specs}
    for name, payload in outputs.items():
        assert payload["label"] == name

    # builder_usage was populated for every builder, each with one record.
    assert set(builder_usage.keys()) == {s.name for s in specs}
    for label, bu in builder_usage.items():
        assert bu.label == label
        assert bu.n_calls == 1
        assert bu.cost_usd == pytest.approx(0.001, abs=1e-6)

    # Concurrent: 8 × 0.1s = 0.8s sequential. Pool of 8 should finish
    # in well under half that.
    assert elapsed < 0.45, (
        f"expected concurrent dispatch to finish in <0.45s, took {elapsed:.3f}s"
    )

    # Timing recorder got exactly one row per builder; order is
    # non-deterministic so check by name set.
    assert len(timing.entries) == 8
    assert {e.step_name for e in timing.entries} == {
        f"builder:{s.name}" for s in specs
    }


def test_builder_specs_match_pool_concurrency_assumption() -> None:
    """If someone changes the builder list to exceed BUILDER_CONCURRENCY
    the test above degenerates. Pin the relationship explicitly."""
    # 7 builders after the tissues+cell_types → expression merge (3 A1 + 4 A2).
    assert BUILDER_CONCURRENCY >= 7


def test_builder_concurrency_propagates_worker_exception() -> None:
    """A builder that raises should abort the run (matches
    pre-parallel behavior — orchestrator never silently swallowed
    builder errors)."""
    timing = TimingRecorder()
    builder_usage: dict[str, BlockBuilderUsage] = {}

    def _boom(*_args: Any, **_kwargs: Any) -> None:
        raise RuntimeError("synthetic builder failure")

    specs = [
        _BuilderSpec("methods", "builders_a1", _boom, [], {"gene": "X"}),
        _BuilderSpec("tissues", "builders_a2", _stub_builder_fn("tissues"), [], {"gene": "X"}),
    ]
    with pytest.raises(RuntimeError, match="synthetic builder failure"):
        _run_builders_concurrently(
            specs, client=MagicMock(), timing=timing, builder_usage=builder_usage
        )


# ---------------------------------------------------------------------------
# Per-paper Haiku trim concurrency
# ---------------------------------------------------------------------------


def _draft(source_id: str, clip_id: str) -> EvidenceClaimDraft:
    return EvidenceClaimDraft.model_validate(
        {
            "source_id": source_id,
            "section": "results",
            "quote": f"Quote for {clip_id}",
            "score": 1.0,
            "hallmark_phrase": "surface staining",
            "suggested_evidence_id": clip_id,
        }
    )


def _trim_response_json(clip_id: str) -> str:
    body = {
        "paper_id": "ignored",
        "kept": [{"clip_id": clip_id, "reason": "load-bearing"}],
    }
    return f"```json\n{json.dumps(body)}\n```"


def test_trim_runs_per_paper_concurrently_and_returns_all_papers() -> None:
    """20 papers × 0.1s per call should complete in << 20×0.1s when
    fanned out across ``TRIM_CONCURRENCY=10`` workers."""
    n_papers = 20
    clips_by_source: dict[str, list[EvidenceClaimDraft]] = {
        f"PMID:{1000+i}": [_draft(f"PMID:{1000+i}", f"clip_{i}_a")]
        for i in range(n_papers)
    }

    # Each call returns a fenced JSON that keeps the corresponding clip.
    # The order of calls is non-deterministic across threads, so we map
    # call_idx to the source_id deterministically via the call_idx —
    # but the *answer* is the same shape either way: keep one clip.
    def _factory(idx: int) -> str:
        # The clip_id is keyed off the index of the source the call
        # corresponds to, but the actual call ordering doesn't matter
        # because the worker filters by ``known_ids`` from its own
        # ``bounded`` set. So we can return the same shape for every
        # call as long as it parses.
        return _trim_response_json(f"clip_{idx}_a")

    client, call_timestamps = _mock_client_with_latency(
        per_call_latency_s=0.1, text_factory=_factory
    )

    timing = TimingRecorder()
    usage_sink: list[UsageRecord] = []

    t0 = time.perf_counter()
    results = _run_trim(
        client,
        clips_by_source=clips_by_source,
        gene="TEST",
        usage_sink=usage_sink,
        trim_prompt_path=A1_TRIM_PROMPT_PATH,
        timing=timing,
        timing_phase="plan_trim_select_a1",
        timing_iteration=0,
    )
    elapsed = time.perf_counter() - t0

    # Every paper got a result entry (concurrency must not lose papers).
    assert set(results.keys()) == set(clips_by_source.keys())

    # Token accounting accumulated one record per call (no double-count,
    # no drop).
    assert len(usage_sink) == n_papers

    # Timing got one row per paper.
    trim_rows = [
        e for e in timing.entries if e.step_name.startswith("trim:iter0:PMID:")
    ]
    assert len(trim_rows) == n_papers
    # Each row carries the Haiku model attribution.
    assert all(e.model == "claude-haiku-4-5" for e in trim_rows)

    # Real concurrency: 20 × 0.1s = 2.0s sequential. With 10 workers
    # we expect ~0.2s + overhead. Allow generous slack so the test is
    # robust on a busy CI box.
    assert elapsed < 0.75, (
        f"expected concurrent trim to finish in <0.75s, took {elapsed:.3f}s "
        f"(sequential would be ~{n_papers * 0.1:.1f}s)"
    )

    # First-10 dispatch timestamps should all be within a small window
    # (they start concurrently), proving the pool fired them off in
    # parallel rather than one-at-a-time.
    early = sorted(call_timestamps)[:TRIM_CONCURRENCY]
    assert max(early) - min(early) < 0.1, (
        f"first {TRIM_CONCURRENCY} trim calls should start within ~0.1s of each "
        f"other; spread was {max(early) - min(early):.3f}s"
    )


def test_trim_handles_paper_with_no_clips() -> None:
    """An empty clip list is skipped (no model call, no result entry)."""
    clips_by_source: dict[str, list[EvidenceClaimDraft]] = {
        "PMID:42": [],
        "PMID:43": [_draft("PMID:43", "clip_43_a")],
    }
    client, _ = _mock_client_with_latency(
        per_call_latency_s=0.01,
        text_factory=lambda i: _trim_response_json("clip_43_a"),
    )
    usage_sink: list[UsageRecord] = []
    results = _run_trim(
        client,
        clips_by_source=clips_by_source,
        gene="X",
        usage_sink=usage_sink,
        trim_prompt_path=A1_TRIM_PROMPT_PATH,
    )
    # Only the non-empty paper produced a result.
    assert set(results.keys()) == {"PMID:43"}
    assert len(usage_sink) == 1


def test_trim_concurrency_recovers_from_one_paper_failing() -> None:
    """One paper's ``messages.create`` raising should not poison the
    other papers' results — surviving papers still produce
    TrimResponses."""

    clips_by_source: dict[str, list[EvidenceClaimDraft]] = {
        f"PMID:{1000+i}": [_draft(f"PMID:{1000+i}", f"clip_{i}_a")]
        for i in range(5)
    }

    call_idx = {"n": 0}
    lock = threading.Lock()

    def _create(**_kwargs: Any) -> Any:
        with lock:
            idx = call_idx["n"]
            call_idx["n"] += 1
        # Fail the first call deterministically.
        if idx == 0:
            raise RuntimeError("simulated API blip")
        block = MagicMock()
        block.text = _trim_response_json(f"clip_{idx}_a")
        usage = MagicMock()
        usage.input_tokens = 100
        usage.output_tokens = 50
        usage.cache_creation_input_tokens = 0
        usage.cache_read_input_tokens = 0
        resp = MagicMock()
        resp.content = [block]
        resp.usage = usage
        resp.stop_reason = "end_turn"
        return resp

    client = MagicMock()
    client.messages.create.side_effect = _create
    timing = TimingRecorder()
    usage_sink: list[UsageRecord] = []

    results = _run_trim(
        client,
        clips_by_source=clips_by_source,
        gene="X",
        usage_sink=usage_sink,
        trim_prompt_path=A1_TRIM_PROMPT_PATH,
        timing=timing,
    )

    # All 5 papers produced result entries (failed one is an empty
    # TrimResponse, not a missing key — keeps downstream selector code
    # from KeyError).
    assert set(results.keys()) == set(clips_by_source.keys())
    # The failed call did NOT contribute a UsageRecord (no resp returned).
    assert len(usage_sink) == 4
    # But it DID contribute a timing row (so the trace records the
    # attempt + elapsed wall-clock even on failure).
    assert (
        sum(1 for e in timing.entries if e.step_name.startswith("trim:iter0:")) == 5
    )


# Silence "unused import" — we use it in the assert above but ruff
# tracks this defensively.
_ = MethodObservation


# ---------------------------------------------------------------------------
# Per-focus prompt routing + deterministic kickoff
# ---------------------------------------------------------------------------


def test_resolve_focus_prompts_returns_triple() -> None:
    """``_resolve_focus_prompts`` returns (trim, select, evi_prefix) per
    focus. The LLM planner was retired in favor of a deterministic
    kickoff, so there is no longer a planner-prompt path in the tuple.
    The legacy unified-ledger (``None``) path was retired with the
    ``trim_system.md`` / ``select_system.md`` prompts."""
    from typing import Any, cast

    from accessible_surfaceome.agents.plan_trim_select.runner import (
        _resolve_focus_prompts,
    )

    trim_a1, select_a1, prefix_a1 = _resolve_focus_prompts("a1")
    assert prefix_a1 == "a1_evi_"
    assert trim_a1.exists() and select_a1.exists()

    trim_a2, select_a2, prefix_a2 = _resolve_focus_prompts("a2")
    assert prefix_a2 == "a2_evi_"
    assert trim_a2.exists() and select_a2.exists()

    # The per-focus trim + select prompts are distinct files.
    assert trim_a1 != trim_a2
    assert select_a1 != select_a2

    # ``None`` is no longer accepted — production runs a1+a2 via the
    # dual driver. Cast through ``Any`` so static typing doesn't
    # complain about the deliberately-wrong argument.
    with pytest.raises(ValueError, match="expected 'a1' or 'a2'"):
        _resolve_focus_prompts(cast(Any, None))


def test_a1_kickoff_emphasizes_methodology() -> None:
    """Tripwire: the deterministic A1 kickoff must request the method-
    centric evidence_retrieval categories A1's block builders need."""
    from accessible_surfaceome.agents.plan_trim_select.kickoff_templates import (
        build_a1_kickoff,
    )

    plan = build_a1_kickoff()
    categories = {s.category for s in plan.searches if s.tool == "evidence_retrieval"}
    for category in ("flow_cytometry", "surface_biotinylation", "mass_spec_surfaceome"):
        assert category in categories, f"A1 kickoff should request {category!r}"


def test_a2_kickoff_emphasizes_biology() -> None:
    """Tripwire mirror: the A2 kickoff leans on tissue / IHC categories."""
    from accessible_surfaceome.agents.plan_trim_select.kickoff_templates import (
        build_a2_kickoff,
    )

    plan = build_a2_kickoff()
    categories = {s.category for s in plan.searches if s.tool == "evidence_retrieval"}
    assert "ihc" in categories, "A2 kickoff should request the ihc category"
    # A2 skips A1-only method categories.
    assert "western_blot_paired" not in categories
    assert "structure_with_ecd" not in categories
