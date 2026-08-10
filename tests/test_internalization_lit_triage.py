import json
from types import SimpleNamespace

from accessible_surfaceome.agents.internalization.literature_triage import (
    triage_internalization_abstracts,
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


def _paper(pmid, *, pmc_id=None, doi=None, abstract="cells internalized the antibody"):
    return SimpleNamespace(
        pmid=pmid, pmc_id=pmc_id, doi=doi, title="t", abstract=abstract
    )


def test_paper_id_uses_canonical_source_id():
    # No PMC -> PMID key; with PMC -> PMC key (paper_source_id preference).
    client = _FakeClient(
        [
            "```json\n"
            + json.dumps({"decision": "worth_fetching", "reason": "r"})
            + "\n```",
            "```json\n"
            + json.dumps({"decision": "discard", "reason": "r"})
            + "\n```",
        ]
    )
    out = triage_internalization_abstracts(
        client,
        papers=[_paper(1), _paper(2, pmc_id="PMC9")],
        gene="TFRC",
        system_prompt="SYS",
    )
    assert out[0].paper_id == "PMID:1"
    assert out[1].paper_id == "PMC:PMC9"


def test_triage_maps_decisions_per_paper():
    payloads = [
        json.dumps(
            {"paper_id": "PMID:1", "decision": "worth_fetching", "reason": "uptake kinetics"}
        ),
        json.dumps({"paper_id": "PMID:2", "decision": "discard", "reason": "unrelated"}),
    ]
    client = _FakeClient(["```json\n" + p + "\n```" for p in payloads])
    out = triage_internalization_abstracts(
        client, papers=[_paper(1), _paper(2)], gene="TFRC", system_prompt="SYS"
    )
    assert [o.response.decision for o in out] == ["worth_fetching", "discard"]
    assert out[0].paper_id == "PMID:1"
    assert out[0].error is None


def test_triage_captures_error_without_aborting_batch():
    good = json.dumps(
        {"paper_id": "PMID:2", "decision": "keep_abstract", "reason": "states result"}
    )
    client = _FakeClient(["not parseable", "```json\n" + good + "\n```"])
    out = triage_internalization_abstracts(
        client, papers=[_paper(1), _paper(2)], gene="TFRC", system_prompt="SYS"
    )
    assert out[0].response is None and out[0].error is not None
    assert out[1].response.decision == "keep_abstract"
