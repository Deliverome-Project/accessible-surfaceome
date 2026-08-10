from types import SimpleNamespace
from typing import Any, cast

from accessible_surfaceome.agents.internalization import uniprot_isoforms as mod
from accessible_surfaceome.agents.internalization.uniprot_isoforms import (
    IsoformContext,
    fetch_isoform_context,
)
from accessible_surfaceome.tools._shared.models import IsoformRecord


def _no_deeptmhmm(monkeypatch):
    monkeypatch.setattr(mod, "deeptmhmm_record", lambda iso, *, is_canonical: None)


def test_fetch_falls_back_to_uniprot_when_no_deeptmhmm(monkeypatch):
    summary = SimpleNamespace(
        topology_features=[],
        isoforms=[
            IsoformRecord(isoform_id="P00533-1", is_canonical=True, length_aa=1210),
            IsoformRecord(isoform_id="P00533-2", is_canonical=False, length_aa=405),
        ],
    )
    monkeypatch.setattr(mod, "uniprot_summary", lambda acc, *, http: summary)
    monkeypatch.setattr(mod, "summarize_topology", lambda feats: "UNIPROT_TOPO")
    _no_deeptmhmm(monkeypatch)

    seqs = {"P00533-1": "MRPSGTAG" * 10, "P00533-2": "MRPSGTAG" * 3}
    monkeypatch.setattr(
        mod,
        "fetch_uniprot_fasta",
        lambda acc, **kw: SimpleNamespace(header=">x", sequence=seqs[acc]),
    )

    out = fetch_isoform_context("P00533", http=cast(Any, object()))
    assert [c.isoform_id for c in out] == ["P00533-1", "P00533-2"]
    assert out[0].is_canonical is True
    assert out[0].sequence == seqs["P00533-1"]
    assert out[0].topology_summary == "UNIPROT_TOPO"
    assert out[0].topology_source == "uniprot"
    assert all(isinstance(c, IsoformContext) for c in out)


def test_fetch_prefers_deeptmhmm_sequence_and_topology(monkeypatch):
    summary = SimpleNamespace(
        topology_features=[],
        isoforms=[
            IsoformRecord(isoform_id="P00533-1", is_canonical=True, length_aa=1210)
        ],
    )
    monkeypatch.setattr(mod, "uniprot_summary", lambda acc, *, http: summary)
    monkeypatch.setattr(mod, "summarize_topology", lambda feats: "UNIPROT_TOPO")
    monkeypatch.setattr(mod, "deeptmhmm_record", lambda iso, *, is_canonical: {"sequence": "DEEPSEQ" * 5})
    monkeypatch.setattr(mod, "summarize_deeptmhmm_topology", lambda rec: "DT_TOPO")

    def _boom(*a, **k):
        raise AssertionError("fetch_uniprot_fasta must not run on the DeepTMHMM path")

    monkeypatch.setattr(mod, "fetch_uniprot_fasta", _boom)

    out = fetch_isoform_context("P00533", http=cast(Any, object()))
    assert len(out) == 1
    assert out[0].sequence == "DEEPSEQ" * 5
    assert out[0].topology_summary == "DT_TOPO"
    assert out[0].topology_source == "deeptmhmm"
    assert out[0].length_aa == 1210  # from IsoformRecord.length_aa


def test_fetch_falls_back_to_acc_when_no_isoforms(monkeypatch):
    summary = SimpleNamespace(topology_features=[], isoforms=[])
    monkeypatch.setattr(mod, "uniprot_summary", lambda acc, *, http: summary)
    monkeypatch.setattr(mod, "summarize_topology", lambda feats: "UNIPROT_TOPO")
    _no_deeptmhmm(monkeypatch)
    monkeypatch.setattr(
        mod,
        "fetch_uniprot_fasta",
        lambda acc, **kw: SimpleNamespace(header=">x", sequence="MSEQ" * 5),
    )

    out = fetch_isoform_context("Q9UBP8", http=cast(Any, object()))
    assert len(out) == 1
    assert out[0].isoform_id == "Q9UBP8"
    assert out[0].is_canonical is True
    assert out[0].length_aa == len("MSEQ" * 5)
    assert out[0].topology_source == "uniprot"
