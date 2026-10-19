import json
from types import SimpleNamespace
from typing import Any, cast

from accessible_surfaceome.agents.internalization import runner as mod
from accessible_surfaceome.agents.internalization.models import (
    InternalizationRecord,
    ModelPriorTrack,
)
from accessible_surfaceome.agents.internalization.uniprot_isoforms import IsoformContext


def _prior(model):
    return ModelPriorTrack(
        model=model,
        overall_grade="high",
        overall_confidence="moderate",
        model_reasoning="r",
        per_isoform=[],
    )


def test_annotate_assembles_record_and_persists(tmp_path, monkeypatch):
    monkeypatch.setattr(mod, "resolve_hgnc_id", lambda g, **kw: "HGNC:11763")
    monkeypatch.setattr(
        mod,
        "resolve_by_hgnc_id",
        lambda hid, *, http: SimpleNamespace(
            hgnc_symbol="TFRC", hgnc_id=hid, uniprot_acc="P02786"
        ),
    )
    monkeypatch.setattr(
        mod,
        "fetch_isoform_context",
        lambda acc, *, http, canonical_only=True: [
            IsoformContext(
                isoform_id="P02786-1",
                is_canonical=True,
                length_aa=760,
                sequence="MSEQ" * 10,
                topology_summary="TOPO",
            )
        ],
    )
    monkeypatch.setattr(mod, "load_prompt", lambda: "SYS")

    seen = []
    monkeypatch.setattr(
        mod,
        "grade_isoforms_with_model",
        lambda client, *, model, **kw: seen.append(model) or _prior(model),
    )

    rec = mod.annotate_model_prior(
        "TFRC",
        client=object(),
        http=cast(Any, object()),
        models=("claude-opus-4-8", "claude-sonnet-4-6"),
        annotations_dir=tmp_path,
    )
    assert isinstance(rec, InternalizationRecord)
    assert rec.gene_symbol == "TFRC"
    assert rec.uniprot_acc == "P02786"
    assert [t.model for t in rec.model_priors] == [
        "claude-opus-4-8",
        "claude-sonnet-4-6",
    ]
    assert seen == ["claude-opus-4-8", "claude-sonnet-4-6"]

    written = json.loads((tmp_path / "TFRC.json").read_text())
    assert written["schema_version"] == rec.schema_version
    assert len(written["model_priors"]) == 2


def test_annotate_can_skip_persist(tmp_path, monkeypatch):
    monkeypatch.setattr(mod, "resolve_hgnc_id", lambda g, **kw: "HGNC:11763")
    monkeypatch.setattr(
        mod,
        "resolve_by_hgnc_id",
        lambda hid, *, http: SimpleNamespace(
            hgnc_symbol="TFRC", hgnc_id=hid, uniprot_acc="P02786"
        ),
    )
    monkeypatch.setattr(
        mod, "fetch_isoform_context", lambda acc, *, http, canonical_only=True: []
    )
    monkeypatch.setattr(mod, "load_prompt", lambda: "SYS")
    monkeypatch.setattr(
        mod, "grade_isoforms_with_model", lambda client, *, model, **kw: _prior(model)
    )

    mod.annotate_model_prior(
        "TFRC",
        client=object(),
        http=cast(Any, object()),
        persist=False,
        annotations_dir=tmp_path,
    )
    assert list(tmp_path.iterdir()) == []
