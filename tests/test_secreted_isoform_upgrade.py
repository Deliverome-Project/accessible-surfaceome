"""Unit tests for the deterministic secreted-form upgrade helper.

``_secreted_isoform_ids`` is the topology side of the v2 orchestrator's
secreted-form upgrade: a TM-less alternative isoform that still carries a
real ECD is a soluble/secreted species (e.g. EGFR's sEGFR isoforms), so the
orchestrator flips ``secreted_form.present=True`` for it.

Regression context: the original inline version referenced
``iso.is_canonical`` — a field ``IsoformTopology`` does NOT have — which
raised ``AttributeError`` on every v2 annotate run (it only surfaced once a
real run exercised it; the gene had previously been hand-patched, bypassing
the orchestrator). These tests pin the helper's behavior AND assert the
field it must not depend on.
"""

from __future__ import annotations

from datetime import UTC, datetime

from accessible_surfaceome.agents.surfaceome_v2.orchestrator import (
    _secreted_isoform_ids,
)
from accessible_surfaceome.tools._shared.models import IsoformTopology


def _iso(isoform_id: str, *, tm: int, ecd: int) -> IsoformTopology:
    return IsoformTopology(
        isoform_id=isoform_id,
        uniprot_acc=isoform_id.split("-")[0],
        tm_helix_count=tm,
        n_terminal_orientation="extracellular",
        c_terminal_orientation="cytoplasmic",
        signal_peptide_length=24,
        ecd_length_residues=ecd,
        icd_length_residues=50,
        per_residue_topology="",
        tool_version="stub",
        retrieved_at=datetime.now(UTC),
    )


def test_tm_less_isoform_with_ecd_is_flagged_soluble():
    """EGFR-style sEGFR isoforms (TM=0, real ECD) are returned."""
    isos = [_iso("P00533-2", tm=0, ecd=381), _iso("P00533-3", tm=0, ecd=681)]
    assert _secreted_isoform_ids(isos) == ["P00533-2", "P00533-3"]


def test_membrane_anchored_isoform_is_not_soluble():
    """A TM-bearing isoform is not a soluble form, regardless of ECD."""
    assert _secreted_isoform_ids([_iso("P00533-4", tm=1, ecd=620)]) == []


def test_tm_less_but_tiny_ecd_is_not_soluble():
    """TM=0 with a sub-30aa ECD is a fragment, not a soluble ectodomain."""
    assert _secreted_isoform_ids([_iso("X-2", tm=0, ecd=12)]) == []


def test_empty_isoform_list():
    assert _secreted_isoform_ids([]) == []


def test_isoform_topology_has_no_is_canonical_field():
    """Regression guard: the helper must NOT reference ``is_canonical`` —
    ``IsoformTopology`` has no such attribute (the canonical isoform lives in
    ``DeterministicFeatures.canonical_topology``, and isoform_topologies holds
    only the alternatives). Referencing it crashed every v2 run."""
    iso = _iso("P00533-2", tm=0, ecd=381)
    assert not hasattr(iso, "is_canonical")
    # And the helper runs clean on it (would have raised AttributeError before).
    assert _secreted_isoform_ids([iso]) == ["P00533-2"]
