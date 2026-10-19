"""Disulfides the gate can actually see, and what it should conclude from them.

Two defects, found on two real proteins, with different causes:

* **MS4A1 N171** — UniProt annotates the 167-183 bond, the residue is 11.8 A
  from both cysteines, and it passes. It is four residues INSIDE a 16-residue
  closure. Distance is the wrong question; `hazard_residues` reduces a bond to
  two points and cannot express enclosure.
* **ACKR3 P35** — the model has a C34-C287 bond at 2.03 A that UniProt does not
  annotate at all. Residue 35 is 3.81 A from C287's SG, which the existing 10 A
  veto would have rejected outright. Nothing was wrong with the veto; it never
  saw the bond.

So the inputs come from BOTH sources, and a bond carries which source found it.
Selecting on annotations alone drops exactly the population most likely to sit
close to a bond, which is the population the veto exists for.

On what to do with enclosure: a published-corpus measurement (176 internal
sites, 133 proteins) found 27 sites strictly inside a disulfide span, 12 of them
functionally validated, with the enclosure rate HIGHER among function-validated
sites than among display-only ones. There is no span threshold separating
MS4A1's 16-residue closure from published successes at spans 9, 13 and 16. So
enclosure is REPORTED, never vetoed on its own, and the veto is on the insert
being longer than the loop it has to fit into — which is cargo-dependent and
therefore cannot be a static boolean on a site record.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from accessible_surfaceome.tag_sites import features as F

#: A minimal model: four cysteines, two of them bonded at ~2.03 A and two far
#: apart, plus a non-cysteine residue. Synthetic rather than a fetched AFDB
#: model so the test is offline and the distances are exact by construction.
PDB = """\
ATOM      1  N   CYS A  10      0.000   0.000   0.000  1.00 90.00           N
ATOM      2  CA  CYS A  10      1.500   0.000   0.000  1.00 90.00           C
ATOM      3  SG  CYS A  10      3.000   0.000   0.000  1.00 90.00           S
ATOM      4  N   ALA A  20     10.000   0.000   0.000  1.00 90.00           N
ATOM      5  CA  ALA A  20     11.000   0.000   0.000  1.00 90.00           C
ATOM      6  N   CYS A  30      4.000   0.000   0.000  1.00 90.00           N
ATOM      7  CA  CYS A  30      4.500   0.000   0.000  1.00 90.00           C
ATOM      8  SG  CYS A  30      5.030   0.000   0.000  1.00 90.00           S
ATOM      9  N   CYS A  40     40.000   0.000   0.000  1.00 90.00           N
ATOM     10  CA  CYS A  40     41.000   0.000   0.000  1.00 90.00           C
ATOM     11  SG  CYS A  40     42.000   0.000   0.000  1.00 90.00           S
ATOM     12  N   CYS A  50     80.000   0.000   0.000  1.00 90.00           N
ATOM     13  CA  CYS A  50     81.000   0.000   0.000  1.00 90.00           C
ATOM     14  SG  CYS A  50     82.000   0.000   0.000  1.00 90.00           S
END
"""


def uniprot_features(*bonds: tuple[int, int]) -> list[dict]:
    return [
        {
            "type": "Disulfide bond",
            "location": {"start": {"value": a}, "end": {"value": b}},
        }
        for a, b in bonds
    ]


@pytest.fixture
def model(tmp_path: Path) -> str:
    p = tmp_path / "model.pdb"
    p.write_text(PDB)
    return str(p)


# --------------------------------------------------------------------------
# reading the bonds
# --------------------------------------------------------------------------


def test_a_bond_in_the_model_is_found_without_any_annotation(model: str) -> None:
    """The ACKR3 case. C34-C287 is 2.03 A in the model and absent from UniProt,
    and our published P35 sits 3.81 A from it."""
    bonds = F.disulfide_bonds([], model)
    assert [(b.first, b.second) for b in bonds] == [(10, 30)]
    assert bonds[0].source == "model"


def test_an_annotated_bond_confirmed_by_the_model_is_marked_annotated(
    model: str,
) -> None:
    bonds = F.disulfide_bonds(uniprot_features((10, 30)), model)
    assert [(b.first, b.second) for b in bonds] == [(10, 30)]
    assert bonds[0].source == "annotated"


def test_cysteines_too_far_apart_are_not_a_bond(model: str) -> None:
    """C40 and C50 are 40 A apart. A free cysteine is not a closure, and
    treating one as a bond would veto a region for nothing."""
    pairs = {(b.first, b.second) for b in F.disulfide_bonds([], model)}
    assert (40, 50) not in pairs


def test_an_annotation_the_model_contradicts_is_still_reported(model: str) -> None:
    """A bond UniProt asserts between residues 40 A apart in the model. The
    annotation is experimental evidence and the model is a prediction, so the
    disagreement is surfaced rather than resolved by dropping either side."""
    bonds = {(b.first, b.second): b for b in F.disulfide_bonds(
        uniprot_features((40, 50)), model)}
    assert (40, 50) in bonds
    assert bonds[(40, 50)].source == "annotated_not_in_model"


def test_a_bond_with_no_model_available_still_comes_from_the_annotation() -> None:
    """No structure is a reason to fall back, not to claim there are no bonds."""
    bonds = F.disulfide_bonds(uniprot_features((10, 30)), None)
    assert [(b.first, b.second) for b in bonds] == [(10, 30)]


# --------------------------------------------------------------------------
# what the existing distance veto must now see
# --------------------------------------------------------------------------


def test_hazard_residues_include_a_model_only_bonds_cysteines(model: str) -> None:
    """The actual ACKR3 P35 fix. Once C34/C287 are hazard residues, the 10 A
    CA-CA veto rejects P35 on its own, with no new veto logic at all."""
    hazard = F.hazard_residues_with_model([], model)
    assert {10, 30} <= hazard


def test_the_annotation_only_path_is_unchanged(model: str) -> None:
    """`hazard_residues` keeps its old behaviour, so every existing caller and
    the 24,018 already-published sites remain interpretable against it."""
    assert F.hazard_residues(uniprot_features((10, 30))) == {10, 30}


# --------------------------------------------------------------------------
# enclosure: a column, not a veto
# --------------------------------------------------------------------------


def test_a_residue_between_the_cysteines_is_enclosed(model: str) -> None:
    bonds = F.disulfide_bonds([], model)
    assert [b.span for b in F.enclosing_bonds(bonds, 20)] == [20]


def test_the_cysteines_themselves_are_not_enclosed(model: str) -> None:
    """They are hazard POINTS, already handled by distance. Calling them
    enclosed would double-count and confuse the audit."""
    bonds = F.disulfide_bonds([], model)
    assert F.enclosing_bonds(bonds, 10) == []
    assert F.enclosing_bonds(bonds, 30) == []


def test_a_residue_outside_the_span_is_not_enclosed(model: str) -> None:
    bonds = F.disulfide_bonds([], model)
    assert F.enclosing_bonds(bonds, 35) == []


def test_the_span_is_reported_so_a_floor_can_be_calibrated_later(model: str) -> None:
    """27 published sites sit inside a span and 12 of them work, so the span
    goes in a column. A gate that dropped them would be rejecting precedent."""
    bonds = F.disulfide_bonds([], model)
    assert F.enclosing_bonds(bonds, 20)[0].span == 20


# --------------------------------------------------------------------------
# the veto that IS defensible, and it depends on the cargo
# --------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("insert", "span", "blocked"),
    [
        (51, 16, True),   # MS4A1 N171 with the SpyTag003+ALFA cassette
        (11, 16, False),  # an HA tag in the same loop: published precedent
        (8, 9, False),    # NPC1L1 986, span 9, functionally validated
        (51, 229, False), # a large ectodomain closure: the insert fits
        (16, 16, True),   # equal is already as long as the loop it goes in
    ],
)
def test_the_veto_is_insert_longer_than_the_loop_it_goes_into(
    insert: int, span: int, blocked: bool
) -> None:
    """Not span alone, at any value. The published corpus has working sites at
    spans 9, 13 and 16 — the same 16 as MS4A1 — so a span cutoff that catches
    our case also rejects functionally-validated precedent. What distinguishes
    them is the cargo: 51 residues into a 16-residue loop is three times its
    length, and nothing published supports it."""
    assert F.insert_exceeds_closure(insert_aa=insert, span=span) is blocked


def test_the_flag_cannot_be_static_on_a_record() -> None:
    """The same site is fatal for one cassette and fine for another, so the
    verdict is a function of the cargo and cannot be frozen into the site row."""
    assert F.insert_exceeds_closure(insert_aa=51, span=16) is True
    assert F.insert_exceeds_closure(insert_aa=11, span=16) is False
