"""Tests for orchestrator injection of deterministic family tags.

The synthesizer emits ``llm_family`` (its high-level functional call).
The orchestrator separately attaches the deterministic, curator-assigned
family tags from the resolved ``IdentifierBundle`` — ``hgnc_gene_groups``
and ``uniprot_family`` — onto the ExecutiveSummary so the reader can
cross-check the model's call against registry/curator ground truth.
These tests pin that the injection helper is a pure model_copy that
overwrites only the deterministic fields and preserves everything else.
"""
from __future__ import annotations

from accessible_surfaceome.agents.surfaceome_v1.orchestrator import (
    _attach_deterministic_families,
)
from accessible_surfaceome.tools._shared.models import (
    ExecutiveSummary,
    IdentifierBundle,
)


def _exec() -> ExecutiveSummary:
    return ExecutiveSummary(
        one_paragraph="—",
        surface_accessibility="high",
        evidence_grade_summary="direct_multi_method",
        confidence="high",
        state_dependence="low",
        subcategory="GPCR",
        llm_family="receptor",
        surface_call_reason="classical_surface_receptor",
        headline_risks=[],
        cited_evidence_ids=[],
    )


def _bundle(**overrides) -> IdentifierBundle:
    # Build with explicit kwargs so each field carries its own type (a
    # `**dict` splat collapses the values to `str | list[str]`, which ty
    # then rejects against every typed field); apply test-case overrides
    # via model_copy, whose `update` accepts an untyped mapping.
    bundle = IdentifierBundle(
        hgnc_symbol="GPR75",
        hgnc_id="HGNC:4526",
        uniprot_acc="O95800",
        hgnc_gene_groups=["G protein-coupled receptors, Class A orphans"],
        uniprot_family="G-protein coupled receptor 1 family",
    )
    return bundle.model_copy(update=overrides) if overrides else bundle


def test_injects_both_deterministic_fields_from_bundle():
    out = _attach_deterministic_families(_exec(), _bundle())
    assert out.hgnc_gene_groups == ["G protein-coupled receptors, Class A orphans"]
    assert out.uniprot_family == "G-protein coupled receptor 1 family"


def test_preserves_llm_family_and_other_fields():
    src = _exec()
    out = _attach_deterministic_families(src, _bundle())
    assert out.llm_family == "receptor"
    assert out.subcategory == "GPCR"
    assert out.surface_call_reason == "classical_surface_receptor"
    assert out.one_paragraph == "—"


def test_overwrites_any_preexisting_values_deterministically():
    # Even if the draft somehow carried stale family tags, the bundle wins.
    stale = _exec().model_copy(
        update={"hgnc_gene_groups": ["WRONG"], "uniprot_family": "wrong family"}
    )
    out = _attach_deterministic_families(
        stale, _bundle(hgnc_gene_groups=[], uniprot_family=None)
    )
    assert out.hgnc_gene_groups == []
    assert out.uniprot_family is None


def test_returns_new_instance_does_not_mutate_input():
    src = _exec()
    _attach_deterministic_families(src, _bundle())
    # Source is untouched (defaults preserved).
    assert src.hgnc_gene_groups == []
    assert src.uniprot_family is None
