"""Tests for the schema-enforcement leg of triage_runner's retry.

Background: the 2026-05-12 mainbench_canonical_v1 sweep wrote 15 rows to
``triage_run`` whose ``(predicted_verdict, predicted_reason)`` pair
violated the Pydantic ``_check_reason_matches_verdict`` validator
(verdict='yes' + reason='inner_leaflet_anchored', verdict='secreted_only',
etc). The validator was added 2026-05-10 — two days *before* this sweep —
but the runner bypassed it: ``_run_one_with_retry`` retries on a
schema-mismatch first attempt but then ``return second`` unconditionally,
even if the second sample is also schema-invalid.

These tests pin the fix:

* When the model emits an invalid (verdict, reason) combo on the FIRST
  attempt AND the retry, the runner must null out the predicted fields
  and stamp an explanatory ``error`` — never persist an invalid combo to
  D1.
* When the first attempt is invalid but the retry recovers, the retry's
  valid record is returned unchanged.
* When the first attempt is already valid, no retry fires and the record
  is returned unchanged.

The bypass at the lower D1RunSink layer is covered in a separate test —
this file is just the runner-side enforcement.
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
RUNNER_PATH = REPO_ROOT / "scripts" / "triage_runner.py"


@pytest.fixture(scope="module")
def runner():
    """Import the runner script as a module without executing main()."""
    spec = importlib.util.spec_from_file_location("triage_runner", RUNNER_PATH)
    assert spec is not None and spec.loader is not None
    mod = importlib.util.module_from_spec(spec)
    sys.modules["triage_runner"] = mod
    spec.loader.exec_module(mod)
    return mod


def _make_rec(runner, *, verdict, reason, error=None):
    """Build a minimal RunRecord with the given verdict/reason."""
    return runner.RunRecord(
        variant="ncbi",
        model="claude-haiku-4-5",
        gene_symbol="JAK3",
        replicate=1,
        truth_verdict="yes",
        truth_class="surface",
        predicted_verdict=verdict,
        predicted_reason=reason,
        verdict_reasoning="...",
        correct=False,
        prompt_tokens=0,
        completion_tokens=0,
        n_web_searches=0,
        cost_usd=0.0,
        latency_s=0.0,
        error=error,
    )


def test_persistent_schema_mismatch_nulls_fields(runner, monkeypatch):
    """If the model emits an invalid (verdict, reason) combo on BOTH the
    first attempt AND the retry, _run_one_with_retry must return a record
    with predicted_verdict=None and an explanatory error.

    Canonical case: verdict='yes' + reason='inner_leaflet_anchored'.
    inner_leaflet_anchored is in the NO-bucket per
    _REASONS_BY_VERDICT; pairing it with yes is the most common
    failure mode in the 2026-05-12 historical sweep."""
    calls = []

    def fake_run_one(**kw):
        calls.append(kw)
        return _make_rec(runner, verdict="yes", reason="inner_leaflet_anchored")

    monkeypatch.setattr(runner, "_run_one", fake_run_one)

    rec = runner._run_one_with_retry(
        variant="ncbi",
        model="claude-haiku-4-5",
        gene_symbol="JAK3",
        replicate=1,
        truth_verdict="yes",
        truth_class="surface",
        hgnc_id="HGNC:6193",
    )
    assert len(calls) == 2, f"expected one retry, got {len(calls)} calls"
    assert rec.predicted_verdict is None, (
        f"persistent schema mismatch must null verdict; got {rec.predicted_verdict!r}"
    )
    assert rec.predicted_reason is None, (
        f"persistent schema mismatch must null reason; got {rec.predicted_reason!r}"
    )
    assert rec.error and "schema" in rec.error.lower(), (
        f"error must explain schema mismatch; got {rec.error!r}"
    )


def test_invalid_verdict_enum_nulls_fields(runner, monkeypatch):
    """The most pathological 2026-05-12 row had verdict='secreted_only' —
    the model wrote a REASON into the VERDICT slot. The runner must
    detect this (verdict not in {yes, contextual, no}) and null on
    persistent invalidity."""
    def fake_run_one(**kw):
        return _make_rec(runner, verdict="secreted_only", reason="secreted_only")

    monkeypatch.setattr(runner, "_run_one", fake_run_one)

    rec = runner._run_one_with_retry(
        variant="ncbi",
        model="claude-haiku-4-5",
        gene_symbol="IGF1",
        replicate=1,
        truth_verdict="no",
        truth_class="secreted",
        hgnc_id="HGNC:5464",
    )
    assert rec.predicted_verdict is None
    assert rec.predicted_reason is None
    assert rec.error and "schema" in rec.error.lower()


def test_retry_recovery_returns_valid_record(runner, monkeypatch):
    """When the first attempt is schema-invalid but the retry recovers
    with a valid combo, the retry's record is returned unchanged. This
    is the happy-path retry — the runner shouldn't null fields just
    because the FIRST sample was bad."""
    state = {"call": 0}

    def fake_run_one(**kw):
        state["call"] += 1
        if state["call"] == 1:
            # First: schema-invalid
            return _make_rec(runner, verdict="yes", reason="inner_leaflet_anchored")
        # Retry: valid
        return _make_rec(runner, verdict="no", reason="inner_leaflet_anchored")

    monkeypatch.setattr(runner, "_run_one", fake_run_one)

    rec = runner._run_one_with_retry(
        variant="ncbi",
        model="claude-haiku-4-5",
        gene_symbol="SRC",
        replicate=1,
        truth_verdict="no",
        truth_class="cytoplasmic",
        hgnc_id="HGNC:11283",
    )
    assert state["call"] == 2
    assert rec.predicted_verdict == "no"
    assert rec.predicted_reason == "inner_leaflet_anchored"
    assert rec.error is None


def test_valid_first_attempt_no_retry(runner, monkeypatch):
    """No-op smoke check: when the first attempt is schema-valid the
    runner doesn't retry, doesn't null anything."""
    state = {"call": 0}

    def fake_run_one(**kw):
        state["call"] += 1
        return _make_rec(runner, verdict="yes", reason="classical_surface_receptor")

    monkeypatch.setattr(runner, "_run_one", fake_run_one)

    rec = runner._run_one_with_retry(
        variant="ncbi",
        model="claude-sonnet-4-6",
        gene_symbol="EGFR",
        replicate=1,
        truth_verdict="yes",
        truth_class="surface",
        hgnc_id="HGNC:3236",
    )
    assert state["call"] == 1, "valid first attempt should not retry"
    assert rec.predicted_verdict == "yes"
    assert rec.predicted_reason == "classical_surface_receptor"
    assert rec.error is None


# ---------------------------------------------------------------------------
# D1RunSink belt-and-suspenders: refuse to persist schema-invalid records
# ---------------------------------------------------------------------------


def test_d1_sink_schema_validator_rejects_invalid_combo():
    """``_is_record_schema_valid`` (the helper D1RunSink.insert uses)
    must reject verdict='yes' + reason='inner_leaflet_anchored'. This
    is the canonical case from the 2026-05-12 mainbench sweep — the
    runner-side null-out should have stopped these, but if a future
    runner forgets the check, the sink layer here catches it."""
    from accessible_surfaceome.cloud.triage_upload import _is_record_schema_valid

    assert not _is_record_schema_valid({
        "predicted_verdict": "yes",
        "predicted_reason": "inner_leaflet_anchored",
    })


def test_d1_sink_schema_validator_rejects_invalid_verdict_enum():
    """The 2026-05-12 IGF1 row had ``predicted_verdict='secreted_only'`` —
    the model wrote a REASON into the VERDICT slot. The sink's
    validator must reject this case (verdict not in the closed enum)."""
    from accessible_surfaceome.cloud.triage_upload import _is_record_schema_valid

    assert not _is_record_schema_valid({
        "predicted_verdict": "secreted_only",
        "predicted_reason": "secreted_only",
    })


def test_d1_sink_schema_validator_allows_valid_combos():
    """Sanity: the validator approves canonical valid combos."""
    from accessible_surfaceome.cloud.triage_upload import _is_record_schema_valid

    assert _is_record_schema_valid({
        "predicted_verdict": "yes",
        "predicted_reason": "classical_surface_receptor",
    })
    assert _is_record_schema_valid({
        "predicted_verdict": "no",
        "predicted_reason": "inner_leaflet_anchored",
    })
    assert _is_record_schema_valid({
        "predicted_verdict": "contextual",
        "predicted_reason": "lysosomal_exocytosis",
    })


def test_d1_sink_schema_validator_allows_null_verdict():
    """NULL verdict = errored cell. The runner writes these deliberately
    to record "tried this gene, got nothing"; the sink must allow them
    through (the failure mode we're guarding against is INVALID combos,
    not legitimate failure rows)."""
    from accessible_surfaceome.cloud.triage_upload import _is_record_schema_valid

    assert _is_record_schema_valid({
        "predicted_verdict": None,
        "predicted_reason": None,
        "error": "API timeout after 30s",
    })
