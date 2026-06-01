"""Regression: the v2 orchestrator must inject the deterministic family tags.

v2 used to build the final SurfaceomeRecord straight from
``synth_draft.executive_summary``, never calling
``_attach_deterministic_families`` the way v1 does — so every v2 record
shipped with ``executive_summary.uniprot_family = None`` and
``hgnc_gene_groups = []`` even for genes that clearly have them (EGFR).
The viewer's deterministic "Family & gene group" bucket then rendered
nothing. These tests guard the wiring so it can't silently regress.

Offline: inspects the orchestrator source + exercises the injection
helper directly. No network, no LLM.
"""

from __future__ import annotations

import inspect

from accessible_surfaceome.agents.surfaceome_v1.orchestrator import (
    _attach_deterministic_families,
)
from accessible_surfaceome.agents.surfaceome_v2 import orchestrator as v2
from accessible_surfaceome.tools._shared.models import (
    ExecutiveSummary,
    IdentifierBundle,
)


def test_v2_annotate_wires_deterministic_family_injection() -> None:
    """``_annotate`` must route the executive_summary through
    ``_attach_deterministic_families`` before it reaches the record."""
    src = inspect.getsource(v2._annotate)
    assert "_attach_deterministic_families(" in src, (
        "v2 _annotate must call _attach_deterministic_families(...) so the "
        "record's executive_summary carries uniprot_family / "
        "hgnc_gene_groups from the resolved bundle"
    )


def test_injection_populates_family_from_bundle() -> None:
    """Behavioral proof: the helper v2 now calls turns an empty-family
    ExecutiveSummary (the synthesizer's default) into one carrying the
    bundle's curator-assigned family tags. No network, no LLM."""
    es = ExecutiveSummary(
        one_paragraph="EGFR is a single-pass RTK with a large ECD.",
        surface_accessibility="high",
        evidence_grade_summary="direct_multi_method",
        confidence="high",
        state_dependence="low",
        subcategory="single_pass_T1",
        surface_call_reason="classical_surface_receptor",
    )
    # Synthesizer default — the bug state.
    assert es.uniprot_family is None
    assert es.hgnc_gene_groups == []

    bundle = IdentifierBundle(
        hgnc_symbol="EGFR",
        hgnc_id="HGNC:3236",
        uniprot_acc="P00533",
        uniprot_family=(
            "protein kinase superfamily. Tyr protein kinase family. "
            "EGF receptor subfamily"
        ),
        hgnc_gene_groups=["Erb-b2 receptor tyrosine kinases"],
    )
    out = _attach_deterministic_families(es, bundle)
    assert out.uniprot_family == bundle.uniprot_family
    assert out.hgnc_gene_groups == bundle.hgnc_gene_groups
    # Input untouched (model_copy returns a new instance).
    assert es.uniprot_family is None
