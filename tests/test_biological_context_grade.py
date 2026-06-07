"""Unit tests for the A2 ``biological_context_grade`` rollup builder.

The A2 analog of the A1 ``evidence_grade`` builder coverage in
``test_surfaceome_v2_builders.py``. Each builder call goes through a
MagicMock Anthropic client (no network):

* Happy path: A2 claims → a valid ``BiologicalContextGradeBlock``.
* Empty input: no claims → ``"absent"`` / empty fallback (no model call).
* Citation roundtrip: cited evidence_ids absent from the input ledger are
  scrubbed.
* Enum + prompt tripwires: the four grade values exist and the prompt
  documents them + names the five A2 axes it rolls up.
"""

from __future__ import annotations

import json
from typing import Any
from unittest.mock import MagicMock

import pytest

from accessible_surfaceome.agents._support.pricing import UsageRecord
from accessible_surfaceome.agents.surfaceome_v2.builders import (
    BiologicalContextGradeBlock,
    build_biological_context_grade,
)
from accessible_surfaceome.agents.surfaceome_v2.builders.biological_context_grade import (
    BiologicalContextGrade,
)
from accessible_surfaceome.tools._shared.models import EvidenceClaim


# ---------------------------------------------------------------------------
# Helpers (mirror test_surfaceome_v2_builders.py)
# ---------------------------------------------------------------------------


def _claim(
    evi_id: str,
    *,
    prefix: str = "a2",
    claim_type: str = "tissue_expression",
    evidence_type: str = "immunohistochemistry",
    direction: str = "supports",
    quote: str = "Example verbatim quote.",
    source_id: str = "PMID:11111",
    section: str = "results",
) -> EvidenceClaim:
    return EvidenceClaim.model_validate(
        {
            "evidence_id": f"{prefix}_evi_{evi_id}",
            "claim": f"Synthetic claim {evi_id}",
            "claim_type": claim_type,
            "direction": direction,
            "evidence_type": evidence_type,
            "evidence_tier": "primary",
            "confidence": "moderate",
            "assay_context": {
                "species": "human",
                "cell_type_or_line": "HEK293",
                "permeabilized": False,
            },
            "source_id": source_id,
            "quote": quote,
            "section": section,
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
        usage.input_tokens = 100
        usage.output_tokens = 50
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
    """Let MagicMock content blocks pass the builder's
    ``isinstance(b, TextBlock)`` check."""
    from accessible_surfaceome.agents.surfaceome_v2.builders import (
        _common as common_mod,
    )

    monkeypatch.setattr(
        common_mod, "TextBlock", (common_mod.TextBlock, MagicMock), raising=True
    )


def _fenced(body: str) -> str:
    return f"```json\n{body}\n```"


# ---------------------------------------------------------------------------
# enum + prompt tripwires
# ---------------------------------------------------------------------------


def test_biological_context_grade_enum_values() -> None:
    """The closed enum carries exactly the four proposed values, high → low."""
    from typing import get_args

    assert get_args(BiologicalContextGrade) == (
        "rich",
        "moderate",
        "sparse",
        "absent",
    )


def test_prompt_documents_grade_values_and_axes() -> None:
    """The builder prompt must document every grade value AND name the five
    A2 axes it rolls up, so the LLM knows what it's grading over."""
    from accessible_surfaceome.agents.surfaceome_v2.builders._common import (
        load_prompt,
    )

    body = load_prompt("biological_context_grade_builder_system").lower()
    for value in ("rich", "moderate", "sparse", "absent"):
        assert value in body
    for axis in (
        "expression",
        "cell_states",
        "subcellular_localization",
        "anatomical_accessibility",
        "accessibility_modulation",
    ):
        assert axis in body


# ---------------------------------------------------------------------------
# build_biological_context_grade
# ---------------------------------------------------------------------------


def test_build_biological_context_grade_happy() -> None:
    claims = [
        _claim("01", evidence_type="immunohistochemistry"),
        _claim("02", evidence_type="rna_seq", source_id="PMID:22222"),
    ]
    output = {
        "biological_context_grade": "moderate",
        "grade_rationale": (
            "Expression mapped across 2 tissues + PM localization confirmed; "
            "no state/anatomical data."
        ),
        "cited_evidence_ids": ["a2_evi_01", "a2_evi_02"],
    }
    client = _mock_client([_fenced(json.dumps(output))])
    sink: list[UsageRecord] = []
    block = build_biological_context_grade(
        claims, client=client, usage_sink=sink, context={"gene": "X"}
    )
    assert isinstance(block, BiologicalContextGradeBlock)
    assert block.biological_context_grade == "moderate"
    assert block.cited_evidence_ids == ["a2_evi_01", "a2_evi_02"]
    assert len(sink) == 1


def test_build_biological_context_grade_empty_input_returns_default() -> None:
    """No A2 claims → absent / empty fallback, no model call."""
    client = _mock_client([])
    sink: list[UsageRecord] = []
    block = build_biological_context_grade(
        [], client=client, usage_sink=sink, context={"gene": "X"}
    )
    assert block.biological_context_grade == "absent"
    assert block.cited_evidence_ids == []
    assert sink == []
    client.messages.create.assert_not_called()


def test_build_biological_context_grade_scrubs_unknown_citations() -> None:
    """cited_evidence_ids the input ledger doesn't carry are dropped."""
    claims = [_claim("01")]
    output = {
        "biological_context_grade": "sparse",
        "grade_rationale": "Single tissue mention only.",
        # a2_evi_99 isn't in the input ledger → scrubbed.
        "cited_evidence_ids": ["a2_evi_01", "a2_evi_99"],
    }
    client = _mock_client([_fenced(json.dumps(output))])
    sink: list[UsageRecord] = []
    block = build_biological_context_grade(
        claims, client=client, usage_sink=sink, context={"gene": "X"}
    )
    assert block.cited_evidence_ids == ["a2_evi_01"]


def test_build_biological_context_grade_repair_failure_falls_back() -> None:
    """When the model never yields valid JSON (MAX_REPAIRS exhausted), the
    builder returns the absent/empty default rather than raising."""
    claims = [_claim("01")]
    # Three non-JSON responses cover the initial call + 2 repairs.
    client = _mock_client(["not json at all"] * 3)
    sink: list[UsageRecord] = []
    block = build_biological_context_grade(
        claims, client=client, usage_sink=sink, context={"gene": "X"}
    )
    assert block.biological_context_grade == "absent"
    assert block.cited_evidence_ids == []
