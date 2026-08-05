from types import SimpleNamespace

from accessible_surfaceome.agents.internalization import uniprot_isoforms as mod
from accessible_surfaceome.agents.internalization.uniprot_isoforms import (
    IsoformContext,
    fetch_isoform_context,
)
from accessible_surfaceome.tools._shared.models import IsoformRecord


def test_fetch_maps_each_isoform_to_a_sequence(monkeypatch):
    summary = SimpleNamespace(
        topology_features=[],
        isoforms=[
            IsoformRecord(isoform_id="P00533-1", is_canonical=True, length_aa=1210),
            IsoformRecord(isoform_id="P00533-2", is_canonical=False, length_aa=405),
        ],
    )
    monkeypatch.setattr(mod, "uniprot_summary", lambda acc, *, http: summary)
    monkeypatch.setattr(mod, "summarize_topology", lambda feats: "TOPO")

    seqs = {"P00533-1": "MRPSGTAG" * 10, "P00533-2": "MRPSGTAG" * 3}
    monkeypatch.setattr(
        mod,
        "fetch_uniprot_fasta",
        lambda acc, **kw: SimpleNamespace(header=">x", sequence=seqs[acc]),
    )

    out = fetch_isoform_context("P00533", http=object())
    assert [c.isoform_id for c in out] == ["P00533-1", "P00533-2"]
    assert out[0].is_canonical is True
    assert out[0].sequence == seqs["P00533-1"]
    assert out[0].topology_summary == "TOPO"
    assert all(isinstance(c, IsoformContext) for c in out)


def test_fetch_falls_back_to_acc_when_no_isoforms(monkeypatch):
    summary = SimpleNamespace(topology_features=[], isoforms=[])
    monkeypatch.setattr(mod, "uniprot_summary", lambda acc, *, http: summary)
    monkeypatch.setattr(mod, "summarize_topology", lambda feats: "TOPO")
    monkeypatch.setattr(
        mod,
        "fetch_uniprot_fasta",
        lambda acc, **kw: SimpleNamespace(header=">x", sequence="MSEQ" * 5),
    )

    out = fetch_isoform_context("Q9UBP8", http=object())
    assert len(out) == 1
    assert out[0].isoform_id == "Q9UBP8"
    assert out[0].is_canonical is True
    assert out[0].length_aa == len("MSEQ" * 5)
