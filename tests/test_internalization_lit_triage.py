import json
import re
from types import SimpleNamespace

from accessible_surfaceome.agents.internalization.literature_triage import (
    triage_internalization_abstracts,
)


class _FakeMessages:
    """Keyed by the PMID embedded in the user prompt, so it's robust to the
    concurrent, out-of-order execution of the triage thread pool."""

    def __init__(self, by_pmid):
        self.by_pmid = by_pmid

    def create(self, **kw):
        content = kw["messages"][0]["content"]
        pmid = int(re.search(r"PMID: (\d+)", content).group(1))
        return SimpleNamespace(
            content=[SimpleNamespace(type="text", text=self.by_pmid[pmid])],
            usage=SimpleNamespace(input_tokens=1, output_tokens=1),
            stop_reason="end_turn",
        )


class _FakeClient:
    def __init__(self, by_pmid):
        self.messages = _FakeMessages(by_pmid)


def _paper(pmid, *, pmc_id=None, doi=None, abstract="cells internalized the antibody"):
    return SimpleNamespace(
        pmid=pmid, pmc_id=pmc_id, doi=doi, title="t", abstract=abstract
    )


def _fenced(d):
    return "```json\n" + json.dumps(d) + "\n```"


def test_paper_id_uses_canonical_source_id():
    client = _FakeClient(
        {
            1: _fenced({"decision": "worth_fetching", "reason": "r"}),
            2: _fenced({"decision": "discard", "reason": "r"}),
        }
    )
    out = triage_internalization_abstracts(
        client, papers=[_paper(1), _paper(2, pmc_id="PMC9")], gene="TFRC",
        system_prompt="SYS",
    )
    assert out[0].paper_id == "PMID:1"
    assert out[1].paper_id == "PMC:PMC9"  # PMC preferred over PMID


def test_triage_maps_decisions_per_paper():
    client = _FakeClient(
        {
            1: _fenced({"paper_id": "PMID:1", "decision": "worth_fetching", "reason": "uptake"}),
            2: _fenced({"paper_id": "PMID:2", "decision": "discard", "reason": "unrelated"}),
        }
    )
    out = triage_internalization_abstracts(
        client, papers=[_paper(1), _paper(2)], gene="TFRC", system_prompt="SYS"
    )
    assert all(o.response is not None for o in out)
    assert [o.response.decision for o in out if o.response] == ["worth_fetching", "discard"]
    assert out[0].error is None


def test_triage_captures_error_without_aborting_batch():
    client = _FakeClient(
        {
            1: "not parseable",
            2: _fenced({"paper_id": "PMID:2", "decision": "keep_abstract", "reason": "r"}),
        }
    )
    out = triage_internalization_abstracts(
        client, papers=[_paper(1), _paper(2)], gene="TFRC", system_prompt="SYS"
    )
    assert out[0].response is None and out[0].error is not None
    assert out[1].response is not None
    assert out[1].response.decision == "keep_abstract"


def test_triage_concurrent_preserves_order_and_processes_all():
    n = 6
    client = _FakeClient(
        {i: _fenced({"decision": "worth_fetching", "reason": "r"}) for i in range(1, n + 1)}
    )
    papers = [_paper(i) for i in range(1, n + 1)]
    out = triage_internalization_abstracts(
        client, papers=papers, gene="TFRC", system_prompt="SYS", concurrency=4
    )
    assert len(out) == n
    assert [o.paper_id for o in out] == [f"PMID:{i}" for i in range(1, n + 1)]
    assert all(o.response and o.response.decision == "worth_fetching" for o in out)


def test_triage_empty_papers_returns_empty():
    assert triage_internalization_abstracts(object(), papers=[], gene="X") == []
