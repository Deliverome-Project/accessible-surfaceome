"""SURFACE-Bind sites must say which side of the membrane they anchor on.

Reported from the API: the surface_bind block passed through per-site
geometry (area, seed counts, hydrophobicity) but nothing about topology,
so an intracellular patch looked exactly like an extracellular one.

That matters because SURFACE-Bind scores the whole solved structure, not
just the ectodomain. Cohort-wide, 1,091 of 4,749 sites (23%) anchor
somewhere other than the extracellular face — 803 intracellular, 122 in
the membrane, 166 inside a cleaved signal peptide. EGFR publishes eight
sites of which three (743, 764, 948) are in the kinase domain: a binder
designed against those is aimed at the inside of the cell.

The determination itself is one lookup into DeepTMHMM's per-residue
topology string; it already existed, but only offline in
scripts/tsv-export/export_sonnet_universe_det_features.py, where it was
immediately collapsed to a per-protein boolean for Supplementary Figure
S14 and never reached the record, D1, or the Worker.
"""
from __future__ import annotations

from accessible_surfaceome.tools._shared.models import SurfaceBindSite
from accessible_surfaceome.tools.surface_bind import anchor_topology


# index:              1234567890
_TOPO = "SSSOOOMMIIII"   # signal peptide, ectodomain, TM helix, cytoplasmic tail


def test_each_topology_class_is_reported() -> None:
    assert anchor_topology(_TOPO, 2) == "signal_peptide"
    assert anchor_topology(_TOPO, 5) == "extracellular"
    assert anchor_topology(_TOPO, 7) == "membrane"
    assert anchor_topology(_TOPO, 11) == "intracellular"


def test_beta_barrel_strand_counts_as_membrane() -> None:
    """'B' is a beta-barrel strand — still inside the bilayer, not exposed."""
    assert anchor_topology("OOBBOO", 3) == "membrane"


def test_unknown_is_none_not_a_guess() -> None:
    """Missing or out-of-range topology must read as unknown. Defaulting to
    'extracellular' would silently reintroduce the reported bug; defaulting
    to 'intracellular' would hide real targets."""
    assert anchor_topology(None, 5) is None
    assert anchor_topology("", 5) is None
    assert anchor_topology(_TOPO, 0) is None          # 1-indexed
    assert anchor_topology(_TOPO, len(_TOPO) + 1) is None  # isoform mismatch


def test_site_model_carries_the_field_and_defaults_to_unknown() -> None:
    site = SurfaceBindSite(
        site_id=0, anchor_residue=743, area_a2=1523.9,
        n_seeds_alpha=1, n_seeds_beta=878, hydrophobicity=6.7,
    )
    assert site.anchor_topology is None
    typed = site.model_copy(update={"anchor_topology": "intracellular"})
    assert typed.model_dump()["anchor_topology"] == "intracellular"


def test_field_is_an_enum_not_a_bool() -> None:
    """A bool would bury the 166 signal-peptide sites — genuinely ambiguous
    because the peptide is cleaved — among the truly intracellular ones."""
    import pydantic
    for bad in ("outside", "cytoplasm", True, "EXTRACELLULAR"):
        try:
            SurfaceBindSite(
                site_id=0, anchor_residue=1, area_a2=0.0, n_seeds_alpha=0,
                n_seeds_beta=0, hydrophobicity=0.0,
                anchor_topology=bad,  # ty: ignore[invalid-argument-type]
            )
        except pydantic.ValidationError:
            continue
        raise AssertionError(f"anchor_topology accepted {bad!r}")
