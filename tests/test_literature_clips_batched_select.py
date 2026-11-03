"""Showing the selector the whole pool in batches instead of truncating it.

The selector saw the top ``_MAX_CLIP_MENU`` clips by score and nothing else.
Measured across 559 archived tag-site runs, the median pool was 315 clips and
419 of those runs had a pool larger than the menu — so two thirds of the
evidence never reached the model, and the clip pinning a real insertion could
be cut before it was ever seen. The faceted discovery that would triple the
pool was disabled for precisely this reason, with the note "revisit together
with the menu cap, not before".

Batching is that revisit. ``max_batches=1`` is the old behaviour exactly, so
the internalization track that shares this selector is untouched.
"""

from __future__ import annotations

import pytest

from accessible_surfaceome.agents._support import literature_clips as lc
from accessible_surfaceome.agents.plan_trim_select.schemas import (
    SelectionResponse,
)
from accessible_surfaceome.tools._shared.models import EvidenceClaimDraft


def draft(i: int, score: float) -> EvidenceClaimDraft:
    return EvidenceClaimDraft(
        suggested_evidence_id=f"clip_{i:04d}",
        quote=f"sentence number {i}",
        source_id="PMC:PMC1",
        section="methods",
        hallmark_phrase="x",
        score=score,
    )


def pool_of(n: int) -> dict[str, EvidenceClaimDraft]:
    # Descending score, so clip_0000 is the highest and ordering is predictable.
    return {f"clip_{i:04d}": draft(i, float(n - i)) for i in range(n)}


class Recorder:
    """Stands in for ``call_model_structured``: records each menu it was shown
    and picks the first clip of each."""

    def __init__(self) -> None:
        self.menus: list[list[str]] = []

    def __call__(self, client, **kw):  # noqa: ANN001, ANN003
        prompt = kw["user_prompt"]
        shown = [
            line.split("]")[0].lstrip("[")
            for line in prompt.splitlines()
            if line.startswith("[clip_")
        ]
        self.menus.append(shown)
        first = shown[0] if shown else None
        sels = (
            [
                {
                    "clip_id": first,
                    "claim": "c",
                    "claim_type": "methodological",
                    "evidence_type": "functional_assay",
                    "evidence_tier": "primary",
                    "direction": "supports",
                    "confidence": "moderate",
                    "assay_context": {"species": "human"},
                }
            ]
            if first
            else []
        )
        return SelectionResponse.model_validate({"selections": sels, "notes": ""})


@pytest.fixture
def recorder(monkeypatch: pytest.MonkeyPatch) -> Recorder:
    rec = Recorder()
    monkeypatch.setattr(lc, "call_model_structured", rec)
    return rec


def _select(pool, recorder, **kw):
    return lc.select_clips(
        object(), pool=pool, gene="GENEX", system_prompt="sys", **kw
    )


def test_one_batch_is_the_old_behaviour(recorder: Recorder) -> None:
    """Default must not change for the internalization track."""
    got = _select(pool_of(250), recorder)
    assert len(recorder.menus) == 1
    assert len(recorder.menus[0]) == lc._MAX_CLIP_MENU
    assert len(got.selections) == 1


def test_batches_cover_successive_slices_and_union_the_picks(
    recorder: Recorder,
) -> None:
    """Four batches of 100 show 400 of a 350-clip pool — i.e. all of it — and
    each slice is a complete menu in its own right, so a clip competes only
    against its ~100 neighbours rather than against the whole pool for one cut.
    """
    got = _select(pool_of(350), recorder, max_batches=4)
    assert len(recorder.menus) == 4
    assert [len(m) for m in recorder.menus] == [100, 100, 100, 50]
    # Every clip was shown exactly once — a partition, not a repeated top-N.
    shown = [c for m in recorder.menus for c in m]
    assert len(shown) == 350
    assert len(set(shown)) == 350
    # One pick per batch, unioned.
    assert len(got.selections) == 4
    assert {s.clip_id for s in got.selections} == {
        "clip_0000", "clip_0100", "clip_0200", "clip_0300",
    }


def test_the_batch_cap_bounds_the_work(recorder: Recorder) -> None:
    """A 1,167-clip pool is the observed maximum; the cap stops it becoming 12
    selector calls."""
    _select(pool_of(1167), recorder, max_batches=4)
    assert len(recorder.menus) == 4
    assert sum(len(m) for m in recorder.menus) == 400


def test_a_pool_within_one_menu_is_not_batched(recorder: Recorder) -> None:
    """No extra model call when there is nothing to split."""
    _select(pool_of(40), recorder, max_batches=4)
    assert len(recorder.menus) == 1
    assert len(recorder.menus[0]) == 40


def test_batches_are_score_ordered(recorder: Recorder) -> None:
    """The highest-scoring clips are still seen first, so a run that dies
    partway through has lost the least."""
    _select(pool_of(250), recorder, max_batches=3)
    assert recorder.menus[0][0] == "clip_0000"
    assert recorder.menus[1][0] == "clip_0100"


def test_a_failing_batch_does_not_lose_the_others(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A partial union is strictly better than the single truncated menu this
    replaces, so one slice erroring must not take the run with it."""
    calls = {"n": 0}

    def flaky(client, **kw):  # noqa: ANN001, ANN003
        calls["n"] += 1
        if calls["n"] == 2:
            raise ValueError("schema repair exhausted")
        return SelectionResponse.model_validate(
            {
                "selections": [
                    {
                        "clip_id": f"clip_{(calls['n'] - 1) * 100:04d}",
                        "claim": "c",
                        "claim_type": "methodological",
                        "evidence_type": "functional_assay",
                        "evidence_tier": "primary",
                        "direction": "supports",
                        "confidence": "moderate",
                        "assay_context": {"species": "human"},
                    }
                ],
                "notes": "",
            }
        )

    monkeypatch.setattr(lc, "call_model_structured", flaky)
    got = lc.select_clips(
        object(), pool=pool_of(350), gene="GENEX", system_prompt="sys", max_batches=4
    )
    assert calls["n"] == 4
    assert len(got.selections) == 3
    assert "batch2: failed" in got.notes


def test_an_empty_pool_short_circuits(recorder: Recorder) -> None:
    got = _select({}, recorder, max_batches=4)
    assert recorder.menus == []
    assert got.selections == []
