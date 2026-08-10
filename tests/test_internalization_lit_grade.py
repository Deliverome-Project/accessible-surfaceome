import json
from types import SimpleNamespace

from accessible_surfaceome.agents.internalization.literature_grade import (
    grade_from_evidence,
)
from accessible_surfaceome.agents.internalization.models import (
    GradesByMode,
    InternalizationObservation,
    LiteratureLLMOut,
    ModeGrade,
)


class _FakeMessages:
    def __init__(self, texts):
        self._t = list(texts)
        self.calls = 0

    def create(self, **kw):
        self.calls += 1
        return SimpleNamespace(
            content=[SimpleNamespace(type="text", text=self._t.pop(0))],
            usage=SimpleNamespace(input_tokens=1, output_tokens=1),
            stop_reason="end_turn",
        )


class _FakeClient:
    def __init__(self, texts):
        self.messages = _FakeMessages(texts)


def _ev(eid, sid="PMID:1"):
    return SimpleNamespace(
        evidence_id=eid, claim="internalizes", source_id=sid,
        spans=[SimpleNamespace(quote="the receptor internalized")],
    )


def test_empty_evidence_returns_unknown_without_model_call():
    out = grade_from_evidence(object(), gene="TFRC", evidence=[], system_prompt="SYS")
    assert isinstance(out, LiteratureLLMOut)
    assert out.overall_grade == "unknown"


def test_grade_parses_and_scrubs_unknown_cites():
    payload = LiteratureLLMOut(
        grades_by_mode=GradesByMode(
            therapeutic=ModeGrade(
                grade="high",
                confidence="moderate",
                cited_source_ids=["int_evi_01", "int_evi_99"],  # 99 is not in the ledger
            )
        ),
        overall_grade="high",
        overall_confidence="moderate",
        observations=[
            InternalizationObservation(
                assay_type="antibody_uptake",
                internalization_mode="therapeutic",
                cited_source_ids=["int_evi_01", "int_evi_bogus"],
            )
        ],
    ).model_dump_json()
    client = _FakeClient(["```json\n" + payload + "\n```"])
    out = grade_from_evidence(
        client, gene="TFRC", evidence=[_ev("int_evi_01")], system_prompt="SYS"
    )
    assert out.grades_by_mode.therapeutic.grade == "high"
    # the invented cites are scrubbed, the real one kept
    assert out.grades_by_mode.therapeutic.cited_source_ids == ["int_evi_01"]
    assert out.observations[0].cited_source_ids == ["int_evi_01"]


def test_grade_repairs_on_invalid_assay_other_then_succeeds():
    bad = json.dumps(
        {"observations": [{"assay_type": "other"}]}  # 'other' without other_label -> invalid
    )
    good = LiteratureLLMOut(overall_grade="low", overall_confidence="low").model_dump_json()
    client = _FakeClient(["```json\n" + bad + "\n```", "```json\n" + good + "\n```"])
    out = grade_from_evidence(
        client, gene="TFRC", evidence=[_ev("int_evi_01")], system_prompt="SYS"
    )
    assert client.messages.calls == 2  # one repair round
    assert out.overall_grade == "low"
