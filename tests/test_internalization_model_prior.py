import json
from types import SimpleNamespace

import pytest

from accessible_surfaceome.agents.internalization.model_prior import (
    extract_json_object,
    grade_isoforms_with_model,
)
from accessible_surfaceome.agents.internalization.models import ModelPriorTrack
from accessible_surfaceome.agents.internalization.uniprot_isoforms import IsoformContext


def test_extract_json_object_prefers_fenced_block():
    text = "prose\n```json\n{\"a\": 1}\n```\ntail"
    assert extract_json_object(text) == {"a": 1}


def test_extract_json_object_bare_fallback():
    assert extract_json_object('  {"a": 2}  ') == {"a": 2}


def _llm_payload():
    return {
        "overall_grade": "high",
        "overall_confidence": "moderate",
        "model_reasoning": "Rapidly recycling receptor family.",
        "per_isoform": [
            {
                "isoform_id": "P02786-1",
                "is_canonical": True,
                "length_aa": 760,
                "topology_summary": "TOPO",
                "endocytic_motifs_noted": "YXXphi in cytoplasmic tail",
                "grade": "high",
                "confidence": "moderate",
                "rationale": "Cytoplasmic internalization motif present.",
            }
        ],
    }


class _FakeMessages:
    def __init__(self, texts):
        self._texts = list(texts)
        self.calls = 0

    def create(self, **kwargs):
        self.calls += 1
        text = self._texts.pop(0)
        return SimpleNamespace(
            content=[SimpleNamespace(type="text", text=text)],
            usage=SimpleNamespace(input_tokens=10, output_tokens=20),
            stop_reason="end_turn",
        )


class _FakeClient:
    def __init__(self, texts):
        self.messages = _FakeMessages(texts)


def _isoforms():
    return [
        IsoformContext(
            isoform_id="P02786-1",
            is_canonical=True,
            length_aa=760,
            sequence="MSEQ" * 20,
            topology_summary="TOPO",
        )
    ]


def test_grade_wraps_llm_output_and_stamps_model():
    client = _FakeClient(["```json\n" + json.dumps(_llm_payload()) + "\n```"])
    track = grade_isoforms_with_model(
        client,
        model="claude-opus-4-8",
        system_prompt="SYS",
        gene_symbol="TFRC",
        isoforms=_isoforms(),
    )
    assert isinstance(track, ModelPriorTrack)
    assert track.model == "claude-opus-4-8"
    assert track.scope == "intrinsic_propensity"
    assert track.overall_grade == "high"
    assert track.per_isoform[0].isoform_id == "P02786-1"


def test_grade_repairs_once_on_bad_json():
    good = "```json\n" + json.dumps(_llm_payload()) + "\n```"
    client = _FakeClient(["not json at all", good])
    track = grade_isoforms_with_model(
        client,
        model="claude-sonnet-4-6",
        system_prompt="SYS",
        gene_symbol="TFRC",
        isoforms=_isoforms(),
    )
    assert client.messages.calls == 2
    assert track.overall_grade == "high"


def test_grade_raises_after_exhausting_repairs():
    client = _FakeClient(["nope", "still nope"])
    with pytest.raises(ValueError):
        grade_isoforms_with_model(
            client,
            model="claude-sonnet-4-6",
            system_prompt="SYS",
            gene_symbol="TFRC",
            isoforms=_isoforms(),
        )
