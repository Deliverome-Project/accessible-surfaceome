import json
from types import SimpleNamespace
from typing import Any, cast

from accessible_surfaceome.agents.internalization import literature_runner as mod
from accessible_surfaceome.agents.internalization.models import (
    GradesByMode,
    InternalizationObservation,
    InternalizationRecord,
    LiteratureLLMOut,
    ModeGrade,
    ModelPriorTrack,
    ModulatorObservation,
)


def _evidence(eid: str):
    from datetime import UTC, datetime

    from accessible_surfaceome.tools._shared.models import (
        AssayContext,
        Evidence,
        EvidenceSpan,
        SourceRef,
    )

    now = datetime(2026, 1, 1, tzinfo=UTC)
    src = SourceRef(
        source_type="pubmed",
        source_id=f"PMID:{eid}",
        url="https://pubmed.ncbi.nlm.nih.gov/1/",
        title="t",
        retrieved_at=now,
        content_sha256="a" * 64,
        publication_type="primary_research",
        is_retracted=False,
        retraction_checked_at=now,
    )
    span = EvidenceSpan(
        source=src,
        section="results",
        quote="q",
        quote_sha256="a" * 64,
        char_offset=0,
        normalized_source_sha256="b" * 64,
    )
    return Evidence(
        evidence_id=eid,
        claim="c",
        claim_type="methodological",
        direction="supports",
        evidence_type="functional_assay",
        evidence_tier="primary",
        confidence="moderate",
        assay_context=AssayContext(species="human"),
        spans=[span],
        entailment_verified=True,
    )


def _wire(monkeypatch, *, discovered, llm, evidence=None):
    monkeypatch.setattr(mod, "resolve_hgnc_id", lambda g, **kw: "HGNC:11763")
    monkeypatch.setattr(
        mod,
        "resolve_by_hgnc_id",
        lambda hid, *, http: SimpleNamespace(
            hgnc_symbol="TFRC", hgnc_id=hid, uniprot_acc="P02786",
            approved_name="transferrin receptor", aliases=[], previous_symbols=[],
        ),
    )
    monkeypatch.setattr(
        mod, "discover_internalization_papers", lambda b, *, http, retraction_index: discovered
    )
    monkeypatch.setattr(mod, "paper_source_id", lambda p: f"PMID:{p.pmid}")
    monkeypatch.setattr(
        mod,
        "triage_internalization_abstracts",
        lambda c, *, papers, gene, synonyms: [],
    )
    monkeypatch.setattr(
        mod, "build_pool", lambda outcomes, pbi, *, http, retraction_index: ({}, [])
    )
    monkeypatch.setattr(
        mod,
        "build_source_store",
        lambda pool, *, papers_by_source_id, http, retraction_index: object(),
    )
    monkeypatch.setattr(
        mod, "select_clips", lambda c, *, pool, gene, synonyms: SimpleNamespace()
    )
    monkeypatch.setattr(
        mod, "promote", lambda sel, *, pool, store: list(evidence or [])
    )
    monkeypatch.setattr(
        mod, "grade_from_evidence", lambda c, *, gene, evidence, synonyms: llm
    )


def test_annotate_literature_assembles_record(tmp_path, monkeypatch):
    discovered = {1: SimpleNamespace(pmid=1), 2: SimpleNamespace(pmid=2)}
    llm = LiteratureLLMOut(
        grades_by_mode=GradesByMode(
            therapeutic=ModeGrade(grade="high", confidence="moderate")
        ),
        overall_grade="high",
        overall_confidence="moderate",
        observations=[InternalizationObservation(assay_type="antibody_uptake")],
    )
    _wire(monkeypatch, discovered=discovered, llm=llm)

    rec = mod.annotate_literature(
        "TFRC", client=object(), http=cast(Any, object()), annotations_dir=tmp_path,
        model_priors=[
            ModelPriorTrack(
                model="claude-opus-4-8", overall_grade="high",
                overall_confidence="high", model_reasoning="r", per_isoform=[],
            )
        ],
    )
    assert isinstance(rec, InternalizationRecord)
    assert rec.schema_version == "0.2.4"
    assert rec.literature is not None
    assert rec.literature.overall_grade == "high"
    assert rec.literature.grades_by_mode.therapeutic.grade == "high"
    assert rec.literature.n_papers_discovered == 2
    assert rec.literature.n_observations == 1
    # the sole observation defaults cell_context='unknown' → derived flag False
    assert rec.literature.has_primary_or_invivo_evidence is False
    # model_priors folded in (the --track both path)
    assert [t.model for t in rec.model_priors] == ["claude-opus-4-8"]

    written = json.loads((tmp_path / "TFRC.json").read_text())
    assert written["literature"]["overall_grade"] == "high"


def test_annotate_literature_derives_primary_or_invivo_flag(tmp_path, monkeypatch):
    discovered = {1: SimpleNamespace(pmid=1)}
    llm = LiteratureLLMOut(
        overall_grade="moderate",
        overall_confidence="moderate",
        trafficking_summary="recycles to the surface",
        observations=[
            InternalizationObservation(
                assay_type="ligand_uptake", cell_context="primary"
            )
        ],
    )
    _wire(monkeypatch, discovered=discovered, llm=llm)
    rec = mod.annotate_literature(
        "TFRC", client=object(), http=cast(Any, object()), annotations_dir=tmp_path
    )
    assert rec.literature is not None
    # a primary-tissue observation flips the code-derived flag on
    assert rec.literature.has_primary_or_invivo_evidence is True
    assert rec.literature.trafficking_summary == "recycles to the surface"


def test_annotate_literature_prunes_orphan_sources(tmp_path, monkeypatch):
    # A modulator/off-target clip that SELECT let into the ledger but GRADE built
    # no observation from (and no per-mode grade cites) must be pruned from the
    # shipped sources — it backs no claim in the record.
    discovered = {1: SimpleNamespace(pmid=1)}
    llm = LiteratureLLMOut(
        overall_grade="moderate",
        overall_confidence="moderate",
        observations=[
            InternalizationObservation(
                assay_type="antibody_uptake", cited_source_ids=["int_evi_01"]
            )
        ],
        grades_by_mode=GradesByMode(
            therapeutic=ModeGrade(grade="moderate", cited_source_ids=["int_evi_02"])
        ),
    )
    _wire(
        monkeypatch,
        discovered=discovered,
        llm=llm,
        evidence=[_evidence("int_evi_01"), _evidence("int_evi_02"), _evidence("int_evi_03")],
    )
    rec = mod.annotate_literature(
        "TFRC", client=object(), http=cast(Any, object()), annotations_dir=tmp_path
    )
    assert rec.literature is not None
    kept = {e.evidence_id for e in rec.literature.sources}
    # int_evi_03 is attributed nowhere → pruned; 01 (observation) + 02 (mode) kept
    assert kept == {"int_evi_01", "int_evi_02"}


def test_annotate_literature_keeps_modulator_cited_source(tmp_path, monkeypatch):
    # A source cited only by a modulator_observation (the separate cross-gene
    # table) must survive the prune — modulator clips are kept, not dropped.
    discovered = {1: SimpleNamespace(pmid=1)}
    llm = LiteratureLLMOut(
        overall_grade="moderate",
        overall_confidence="moderate",
        observations=[
            InternalizationObservation(
                assay_type="antibody_uptake", cited_source_ids=["int_evi_01"]
            )
        ],
        modulator_observations=[
            ModulatorObservation(
                modulator="GENEX",
                perturbation="knockdown",
                effect_on_target="increases",
                cited_source_ids=["int_evi_02"],
            )
        ],
    )
    _wire(
        monkeypatch,
        discovered=discovered,
        llm=llm,
        evidence=[_evidence("int_evi_01"), _evidence("int_evi_02"), _evidence("int_evi_03")],
    )
    rec = mod.annotate_literature(
        "TFRC", client=object(), http=cast(Any, object()), annotations_dir=tmp_path
    )
    assert rec.literature is not None
    kept = {e.evidence_id for e in rec.literature.sources}
    # int_evi_02 kept via the modulator table; int_evi_03 (cited nowhere) pruned
    assert kept == {"int_evi_01", "int_evi_02"}
    assert rec.literature.n_modulator_observations == 1
    assert rec.literature.modulator_observations[0].modulator == "GENEX"


def test_annotate_literature_drops_target_self_modulators(tmp_path, monkeypatch):
    # The modulator table is directional (modulator -> target). Any modulator
    # entry that NAMES THE TARGET itself — a target-self perturbation, or the
    # reverse "target modulates another gene" — must be dropped by the code
    # backstop even if the grader emits it. Third-party modulators are kept.
    discovered = {1: SimpleNamespace(pmid=1)}
    llm = LiteratureLLMOut(
        overall_grade="moderate",
        overall_confidence="moderate",
        modulator_observations=[
            ModulatorObservation(modulator="EGFR", effect_on_target="increases"),
            ModulatorObservation(  # target-self knockdown → must drop
                modulator="TFRC (knockdown in some disease context)",
                perturbation="knockdown",
                effect_on_target="decreases",
            ),
            ModulatorObservation(  # reverse arrow: target named as modulator → drop
                modulator="transferrin receptor effect on another gene",
                effect_on_target="increases",
            ),
        ],
    )
    _wire(monkeypatch, discovered=discovered, llm=llm)
    rec = mod.annotate_literature(
        "TFRC", client=object(), http=cast(Any, object()), annotations_dir=tmp_path
    )
    assert rec.literature is not None
    mods = [m.modulator for m in rec.literature.modulator_observations]
    assert mods == ["EGFR"]  # both target-naming entries dropped
    assert rec.literature.n_modulator_observations == 1


def test_annotate_literature_keeps_all_sources_when_grader_cites_nothing(
    tmp_path, monkeypatch
):
    # Guard: if the grader emitted no citations at all, keep the full span-verified
    # ledger rather than risk stripping genuine evidence on a sloppy grade.
    discovered = {1: SimpleNamespace(pmid=1)}
    llm = LiteratureLLMOut(overall_grade="low", overall_confidence="low")
    _wire(
        monkeypatch,
        discovered=discovered,
        llm=llm,
        evidence=[_evidence("int_evi_01"), _evidence("int_evi_02")],
    )
    rec = mod.annotate_literature(
        "TFRC", client=object(), http=cast(Any, object()), annotations_dir=tmp_path
    )
    assert rec.literature is not None
    assert {e.evidence_id for e in rec.literature.sources} == {
        "int_evi_01",
        "int_evi_02",
    }


def test_annotate_literature_can_skip_persist(tmp_path, monkeypatch):
    _wire(monkeypatch, discovered={}, llm=LiteratureLLMOut())
    mod.annotate_literature(
        "TFRC", client=object(), http=cast(Any, object()), persist=False, annotations_dir=tmp_path
    )
    assert list(tmp_path.iterdir()) == []
