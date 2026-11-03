"""Sequence adjacency is not spatial clearance, and the veto must not confuse them.

`feature_distances` minimises CA-CA over every hazard residue with no regard to
sequence separation. At separation 1 the Ca-Ca virtual bond fixes that distance
at 3.81-3.86 A **whatever the fold does**, so any residue sitting next to a
cysteine, a glycan or a binding-site residue reads ~3.8 A and is vetoed by
peptide geometry rather than by any clash.

That is not hypothetical and it is not rare:

* ACKR3 P35 was reported as a defect — and told to two other sessions — on a
  gate reading of 3.83 A. That is its distance to C34 at separation 1. Its
  nearest SPATIAL bonded cysteine is C287 at 7.63 A, and C117/C196 are 27 and
  22 A away. The dramatic number was geometry.
* A clearance calibration over 185 published internal sites found 9 of 130
  junctions within 2 residues of their cysteine, and the load-bearing row is
  **ADCYAP1R1 D24**: surface_and_function, position validated, one residue from
  bonded C25. So "adjacent to a bonded cysteine" is a configuration that
  demonstrably displays AND functions.

So the two are reported apart: `feature_dist` carries SPATIAL clearance over
hazards more than two residues away, and `hazard_sep` carries how close the
nearest hazard is in sequence. A floor fitted without that split has its
minimum set by bond geometry, and the whole study can be dismissed by anyone who
notices.
"""

from __future__ import annotations

import math
from pathlib import Path

import pytest

from accessible_surfaceome.tag_sites import features as F

#: Residue 10 is a hazard. Residue 11 is its sequence neighbour and is placed
#: 3.8 A away — the peptide geometry case. Residue 60 is a second hazard placed
#: 7.0 A from residue 11 in space while being 49 residues away in sequence: the
#: genuinely spatial neighbour. Residue 40 is far from both.
PDB = """\
ATOM      1  N   CYS A  10      0.000   0.000   0.000  1.00 90.00           N
ATOM      2  CA  CYS A  10      0.000   0.000   0.000  1.00 90.00           C
ATOM      3  SG  CYS A  10      1.000   0.000   0.000  1.00 90.00           S
ATOM      4  N   ALA A  11      3.800   0.000   0.000  1.00 90.00           N
ATOM      5  CA  ALA A  11      3.800   0.000   0.000  1.00 90.00           C
ATOM      6  N   ALA A  40     90.000   0.000   0.000  1.00 90.00           N
ATOM      7  CA  ALA A  40     90.000   0.000   0.000  1.00 90.00           C
ATOM      8  N   CYS A  60     10.800   0.000   0.000  1.00 90.00           N
ATOM      9  CA  CYS A  60     10.800   0.000   0.000  1.00 90.00           C
ATOM     10  SG  CYS A  60     11.800   0.000   0.000  1.00 90.00           S
END
"""


@pytest.fixture
def model(tmp_path: Path) -> str:
    p = tmp_path / "m.pdb"
    p.write_text(PDB)
    return str(p)


def test_an_adjacent_hazard_does_not_set_the_spatial_distance(model: str) -> None:
    """Residue 11 is 3.8 A from hazard 10 by peptide geometry and 7.0 A from
    hazard 60 in space. The spatial reading must be 7.0, not 3.8 — the ACKR3
    P35 case exactly."""
    d = F.feature_distances(model, {10, 60})
    assert d[11] == pytest.approx(7.0, abs=0.05)


def test_the_adjacency_is_still_reported_not_discarded(model: str) -> None:
    """Dropping it silently would be the opposite error. A junction one residue
    from a bonded cysteine is a fact worth ranking on, just not a veto."""
    sep = F.hazard_separations(model, {10, 60})
    assert sep[11] == 1


def test_a_residue_whose_only_hazard_is_adjacent_is_spatially_clear(model: str) -> None:
    """With hazard 10 alone, residue 11 has no spatial hazard at all. Reporting
    3.8 A here is what vetoes the ADCYAP1R1 D24 configuration — published,
    displaying AND functioning, one residue from a bonded cysteine."""
    d = F.feature_distances(model, {10})
    assert math.isinf(d[11]), f"expected no spatial hazard, got {d[11]}"
    assert F.hazard_separations(model, {10})[11] == 1


def test_a_sequence_distant_hazard_is_measured_as_before(model: str) -> None:
    """The change must not loosen the real case: residue 11 against hazard 60
    alone is 7.0 A, unchanged."""
    assert F.feature_distances(model, {60})[11] == pytest.approx(7.0, abs=0.05)


def test_a_residue_far_from_everything_stays_far(model: str) -> None:
    d = F.feature_distances(model, {10, 60})
    assert d[40] > 70


def test_no_hazards_means_fully_clear(model: str) -> None:
    d = F.feature_distances(model, set())
    assert math.isinf(d[11])
    assert F.hazard_separations(model, set())[11] is None


def test_the_hazard_residue_itself_reads_zero_separation(model: str) -> None:
    """A hazard residue is its own nearest hazard. The gate should not propose
    inserting AT a functional residue, and separation 0 says so plainly."""
    assert F.hazard_separations(model, {10, 60})[10] == 0


def test_the_separation_window_is_the_calibrated_one(model: str) -> None:
    """Two residues, from the calibration's own split: at separation 1-2 the
    distance is dominated by backbone geometry. Pinned so a later tweak is a
    deliberate recalibration rather than a drifted constant."""
    assert F.ADJACENCY_SEP == 2
