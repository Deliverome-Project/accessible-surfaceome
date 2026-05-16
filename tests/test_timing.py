"""Unit tests for the ``TimingRecorder`` + per-step instrumentation.

Covers:

* ``TimingRecorder.step`` records elapsed_s and merges the usage records
  the body attached via ``handle.set_usage``.
* The plan-trim-select runner threads a recorder through planner / trim
  / selector calls, producing one row per LLM call.
* ``build_methods`` (representative block-builder) records a row when
  the orchestrator wraps it in ``timing.step``.
* The HTML viewer renders Section 0.5 when ``record["timing"]`` is
  populated and skips it when absent.
"""

from __future__ import annotations

import json
import time
from typing import Any
from unittest.mock import MagicMock

import pytest

from accessible_surfaceome.agents._support.pricing import UsageRecord
from accessible_surfaceome.agents._support.timing import (
    TimingRecorder,
    summarize_usage_for_step,
)
from accessible_surfaceome.agents.surfaceome_v2.builders import build_methods
from accessible_surfaceome.agents.surfaceome_v2.render_html import (
    _render_timing_section,
    render_html,
)
from accessible_surfaceome.tools._shared.models import EvidenceClaim


# ---------------------------------------------------------------------------
# Helpers (mirrors the pattern in tests/test_surfaceome_v2_builders.py)
# ---------------------------------------------------------------------------


def _claim(
    evi_id: str,
    *,
    evidence_type: str = "flow_cytometry",
    quote: str = "Example verbatim quote.",
) -> EvidenceClaim:
    return EvidenceClaim.model_validate(
        {
            "evidence_id": f"a1_evi_{evi_id}",
            "claim": f"Synthetic claim {evi_id}",
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
            "quote": quote,
            "section": "results",
        }
    )


def _mock_client(text_responses: list[str]) -> Any:
    client = MagicMock()
    iterator = iter(text_responses)

    def _create(**_kwargs: Any) -> Any:
        text = next(iterator)
        block = MagicMock()
        block.text = text
        usage = MagicMock()
        usage.input_tokens = 200
        usage.output_tokens = 120
        usage.cache_creation_input_tokens = 0
        usage.cache_read_input_tokens = 0
        resp = MagicMock()
        resp.content = [block]
        resp.usage = usage
        resp.stop_reason = "end_turn"
        return resp

    client.messages.create.side_effect = _create
    return client


@pytest.fixture(autouse=True)
def _patch_text_block(monkeypatch: pytest.MonkeyPatch) -> None:
    from accessible_surfaceome.agents.surfaceome_v2.builders import (
        _common as common_mod,
    )

    monkeypatch.setattr(
        common_mod, "TextBlock", (common_mod.TextBlock, MagicMock), raising=True
    )


def _fenced(body: str) -> str:
    return f"```json\n{body}\n```"


# ---------------------------------------------------------------------------
# TimingRecorder unit tests
# ---------------------------------------------------------------------------


def test_recorder_records_elapsed_and_n_items() -> None:
    rec = TimingRecorder()
    with rec.step("demo", phase="post", n_items=5):
        time.sleep(0.01)
    assert len(rec.entries) == 1
    entry = rec.entries[0]
    assert entry.step_name == "demo"
    assert entry.phase == "post"
    assert entry.n_items == 5
    assert entry.elapsed_s >= 0.005
    # JSON-serializable representation drops the None-valued fields.
    j = entry.as_dict()
    assert "elapsed_s" in j and "input_tokens" not in j


def test_recorder_set_usage_rolls_token_counts() -> None:
    rec = TimingRecorder()
    with rec.step("planner", phase="plan_trim_select_a1") as h:
        h.set_usage(
            [
                UsageRecord(
                    input_tokens=1000,
                    output_tokens=200,
                    cache_creation_input_tokens=500,
                    cache_read_input_tokens=0,
                    cost_usd=0.0123,
                ),
                UsageRecord(
                    input_tokens=300,
                    output_tokens=50,
                    cache_creation_input_tokens=0,
                    cache_read_input_tokens=900,
                    cost_usd=0.0012,
                ),
            ],
            model="claude-sonnet-4-6",
        )
    entry = rec.entries[0]
    assert entry.input_tokens == 1300
    assert entry.output_tokens == 250
    assert entry.cache_creation_input_tokens == 500
    assert entry.cache_read_input_tokens == 900
    assert entry.cost_usd == pytest.approx(0.0135, abs=1e-6)
    assert entry.model == "claude-sonnet-4-6"


def test_summarize_usage_for_step_handles_empty() -> None:
    assert summarize_usage_for_step([], None) == {}


def test_recorder_to_jsonable_returns_list_of_dicts() -> None:
    rec = TimingRecorder()
    with rec.step("a", phase="post"):
        pass
    with rec.step("b", phase="post", n_items=2):
        pass
    payload = rec.to_jsonable()
    assert isinstance(payload, list)
    assert len(payload) == 2
    # Round-trip through JSON to confirm it's serializable.
    json.dumps(payload)


def test_recorder_exception_in_body_still_emits_row() -> None:
    rec = TimingRecorder()
    with pytest.raises(RuntimeError):
        with rec.step("crashy", phase="post"):
            raise RuntimeError("boom")
    assert len(rec.entries) == 1
    assert rec.entries[0].step_name == "crashy"


# ---------------------------------------------------------------------------
# Builder integration — orchestrator-style wrapping
# ---------------------------------------------------------------------------


def test_build_methods_inside_timing_step_captures_usage() -> None:
    """Mirror the orchestrator's pattern: wrap build_methods in
    ``timing.step``, hand it a fresh usage_sink, then ``set_usage`` after.
    """
    claims = [_claim("01", evidence_type="flow_cytometry")]
    output = [
        {
            "method_family": "flow_cytometry",
            "method_subclass": "live_cell_flow",
            "permeabilization": "nonpermeabilized",
            "expression_system": "endogenous",
            "antibodies": [],
            "accessibility_relevance": "direct_surface_accessibility",
            "surface_claim_type": "surface_accessible",
            "expression_observations": [],
            "cited_evidence_ids": ["a1_evi_01"],
        }
    ]
    client = _mock_client([_fenced(json.dumps(output))])
    sink: list[UsageRecord] = []
    rec = TimingRecorder()
    with rec.step(
        "builder:methods",
        phase="builders_a1",
        n_items=len(claims),
        model="claude-sonnet-4-6",
    ) as h:
        rows = build_methods(
            claims, client=client, usage_sink=sink, context={"gene": "GPR75"}
        )
        h.set_usage(sink, model="claude-sonnet-4-6")
    assert len(rows) == 1
    assert len(rec.entries) == 1
    entry = rec.entries[0]
    assert entry.step_name == "builder:methods"
    assert entry.phase == "builders_a1"
    assert entry.n_items == 1
    assert entry.model == "claude-sonnet-4-6"
    assert entry.input_tokens == 200
    assert entry.output_tokens == 120


# ---------------------------------------------------------------------------
# HTML viewer — Section 0.5
# ---------------------------------------------------------------------------


def _stub_record(*, with_timing: bool) -> dict[str, Any]:
    record: dict[str, Any] = {
        "schema_version": "1.0.0",
        "gene": {"hgnc_symbol": "X", "uniprot_acc": "Q1", "hgnc_id": "HGNC:1"},
        "executive_summary": None,
        "confidence": "moderate",
        "confidence_reasoning": "—",
        "surface_evidence": None,
        "biological_context": None,
        "deterministic_features": None,
        "accessibility_risks": None,
        "filters": None,
        "evidence": [],
        "evidence_count": 0,
        "primary_evidence_count": 0,
        "secondary_evidence_count": 0,
        "model_path": "claude-sonnet-4-6",
        "record_generated_at": "2026-05-16T00:00:00Z",
    }
    if with_timing:
        record["timing"] = [
            {
                "step_name": "planner",
                "phase": "plan_trim_select_a1",
                "started_at": "2026-05-16T00:00:00Z",
                "elapsed_s": 12.5,
                "model": "claude-sonnet-4-6",
                "input_tokens": 8000,
                "output_tokens": 1500,
                "cost_usd": 0.0465,
            },
            {
                "step_name": "selector:iter0",
                "phase": "plan_trim_select_a2",
                "started_at": "2026-05-16T00:00:20Z",
                "elapsed_s": 47.1,
                "n_items": 32,
                "model": "claude-sonnet-4-6",
                "input_tokens": 12000,
                "output_tokens": 3000,
                "cost_usd": 0.081,
            },
            {
                "step_name": "builder:methods",
                "phase": "builders_a1",
                "started_at": "2026-05-16T00:01:10Z",
                "elapsed_s": 22.0,
                "n_items": 12,
            },
        ]
        record["total_elapsed_s"] = 81.6
    return record


def test_render_timing_section_present_when_timing_set() -> None:
    html_out = _render_timing_section(_stub_record(with_timing=True))
    assert "Step timeline" in html_out
    # Slowest step floats to the top of the detail table.
    head_pos = html_out.find("selector:iter0")
    plan_pos = html_out.find("planner")
    assert 0 <= head_pos < plan_pos
    # Stacked bar segments are present.
    assert "bar-seg" in html_out


def test_render_timing_section_empty_when_no_timing() -> None:
    html_out = _render_timing_section(_stub_record(with_timing=False))
    assert html_out == ""


def test_full_render_html_includes_section_when_timing_present() -> None:
    html_out = render_html(_stub_record(with_timing=True))
    assert "Step timeline" in html_out


def test_full_render_html_skips_section_when_no_timing() -> None:
    html_out = render_html(_stub_record(with_timing=False))
    assert "Step timeline" not in html_out
