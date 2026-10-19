import json
from types import SimpleNamespace

import pytest

from accessible_surfaceome.agents.internalization.model_prior import (
    _build_user_prompt,
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


def test_grade_stamps_prompt_provenance():
    """The track records the model string, the prompt content-sha, and the
    bumpable prompt version — so a stale record is detectable. The sha tracks the
    exact system-prompt text (a prompt edit changes it)."""
    from accessible_surfaceome.agents.internalization.model_prior import prompt_sha
    from accessible_surfaceome.agents.internalization.models import (
        MODEL_PRIOR_PROMPT_VERSION,
    )

    payload = "```json\n" + json.dumps(_llm_payload()) + "\n```"
    track = grade_isoforms_with_model(
        _FakeClient([payload]),
        model="claude-opus-4-8",
        system_prompt="SYS-A",
        gene_symbol="TFRC",
        isoforms=_isoforms(),
    )
    assert track.model == "claude-opus-4-8"
    assert track.prompt_version == MODEL_PRIOR_PROMPT_VERSION
    assert track.prompt_sha == prompt_sha("SYS-A")

    # A different prompt yields a different sha (staleness is detectable).
    track_b = grade_isoforms_with_model(
        _FakeClient([payload]),
        model="claude-opus-4-8",
        system_prompt="SYS-B",
        gene_symbol="TFRC",
        isoforms=_isoforms(),
    )
    assert track_b.prompt_sha != track.prompt_sha


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


def test_build_user_prompt_is_blind_to_identity():
    """The prompt must not leak the gene symbol or the raw isoform accession —
    isoforms are labeled generically so the grade is identity-blind."""
    isoforms = [
        IsoformContext(
            isoform_id="Q99999-1",
            is_canonical=True,
            length_aa=500,
            sequence="MSEQ" * 10,
            topology_summary="TOPO-A",
        ),
        IsoformContext(
            isoform_id="Q99999-2",
            is_canonical=False,
            length_aa=420,
            sequence="MSEQ" * 8,
            topology_summary="TOPO-B",
        ),
    ]
    prompt = _build_user_prompt("SECRETGENE", isoforms)
    assert "SECRETGENE" not in prompt
    assert "Q99999-1" not in prompt
    assert "Q99999-2" not in prompt
    assert "Isoform 1 (canonical)" in prompt
    assert "Isoform 2" in prompt
    # Non-identifying context is still present.
    assert "TOPO-A" in prompt
    assert "TOPO-B" in prompt


def test_grade_remaps_isoform_id_from_input_by_index():
    """The model sees generic labels, so its per_isoform ids are placeholders;
    grade_isoforms_with_model must overwrite isoform_id / is_canonical /
    length_aa from the INPUT isoforms by position."""
    payload = {
        "overall_grade": "moderate",
        "overall_confidence": "low",
        "model_reasoning": "Reasoned from sequence + topology only.",
        "per_isoform": [
            {
                "isoform_id": "Isoform 1",  # placeholder generic label
                "is_canonical": False,  # wrong on purpose — code must override
                "length_aa": 1,  # wrong on purpose — code must override
                "topology_summary": "TOPO-A",
                "endocytic_motifs_noted": "YXXphi",
                "grade": "high",
                "confidence": "moderate",
                "rationale": "Cytoplasmic motif present.",
            },
            {
                "isoform_id": "Isoform 2",  # placeholder generic label
                "is_canonical": True,  # wrong on purpose
                "length_aa": 9,  # wrong on purpose
                "topology_summary": "TOPO-B",
                "endocytic_motifs_noted": None,
                "grade": "unknown",
                "confidence": "low",
                "rationale": "No decisive sequence signal.",
            },
        ],
    }
    isoforms = [
        IsoformContext(
            isoform_id="Q99999-1",
            is_canonical=True,
            length_aa=500,
            sequence="MSEQ" * 10,
            topology_summary="TOPO-A",
        ),
        IsoformContext(
            isoform_id="Q99999-2",
            is_canonical=False,
            length_aa=420,
            sequence="MSEQ" * 8,
            topology_summary="TOPO-B",
        ),
    ]
    client = _FakeClient(["```json\n" + json.dumps(payload) + "\n```"])
    track = grade_isoforms_with_model(
        client,
        model="claude-opus-4-8",
        system_prompt="SYS",
        gene_symbol="SECRETGENE",
        isoforms=isoforms,
    )
    assert [p.isoform_id for p in track.per_isoform] == ["Q99999-1", "Q99999-2"]
    assert [p.is_canonical for p in track.per_isoform] == [True, False]
    assert [p.length_aa for p in track.per_isoform] == [500, 420]
    # The grade payload (the model's actual judgement) is preserved.
    assert [p.grade for p in track.per_isoform] == ["high", "unknown"]


def test_per_residue_topology_appears_in_prompt_and_is_restamped():
    """The DeepTMHMM per-residue string is (a) handed to the model in the prompt
    and (b) re-stamped onto the persisted output from the trusted input context —
    the model is never asked to echo the long string back, so whatever it emits
    for that field is overwritten."""
    tpr = "I" * 65 + "M" * 21 + "O" * 674  # residue-aligned to a 760aa sequence
    isoforms = [
        IsoformContext(
            isoform_id="P02786-1",
            is_canonical=True,
            length_aa=760,
            sequence="M" * 760,
            topology_summary="TOPO",
            topology_source="deeptmhmm",
            topology_per_residue=tpr,
        )
    ]
    # The prompt carries the aligned per-residue block + the S/I/O/M/B legend.
    prompt = _build_user_prompt("SECRETGENE", isoforms)
    assert "Per-residue topology (S/I/O/M/B" in prompt
    assert tpr in prompt

    # Even if the model emits a bogus topology_per_residue, the code re-stamps it.
    payload = _llm_payload()
    payload["per_isoform"][0]["topology_per_residue"] = "GARBAGE"
    client = _FakeClient(["```json\n" + json.dumps(payload) + "\n```"])
    track = grade_isoforms_with_model(
        client,
        model="claude-opus-4-8",
        system_prompt="SYS",
        gene_symbol="SECRETGENE",
        isoforms=isoforms,
    )
    assert track.per_isoform[0].topology_per_residue == tpr


def test_grade_drops_extra_isoforms_on_count_mismatch():
    """If the model returns more graded isoforms than were given, the extras are
    dropped (zip-by-index) rather than crashing."""
    payload = _llm_payload()
    payload["per_isoform"].append(
        {
            "isoform_id": "Isoform 2",
            "is_canonical": False,
            "length_aa": 999,
            "topology_summary": "EXTRA",
            "endocytic_motifs_noted": None,
            "grade": "unknown",
            "confidence": "low",
            "rationale": "Hallucinated extra isoform.",
        }
    )
    client = _FakeClient(["```json\n" + json.dumps(payload) + "\n```"])
    track = grade_isoforms_with_model(
        client,
        model="claude-opus-4-8",
        system_prompt="SYS",
        gene_symbol="TFRC",
        isoforms=_isoforms(),  # exactly one input isoform
    )
    assert len(track.per_isoform) == 1
    assert track.per_isoform[0].isoform_id == "P02786-1"
