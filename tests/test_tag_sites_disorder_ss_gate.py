"""The disorder lane must ask the model whether a residue is in a helix.

`surface_loop_candidates` requires `ss in LOOP_SS` from pydssp on the AlphaFold
model. `disorder_candidates` asked for neither: it gated on (a) membership in a
flexible extracellular run and (b) 3D clearance, then RANKED by a disorder
consensus that weights netsurfp-3.0 at 2.0 — a SEQUENCE predictor that never
sees the structure.

Those two facts compound. A sequence predictor's errors on this task are
asymmetric: a parallel session measured its SS3 against DSSP across five panel
proteins and found 18% disagreement overall (36% on one), with 13 cases calling
coil where the model is structured. Coil-where-structured is precisely the
direction that puts a 51-aa cassette into a helix, and it is the direction a
predictor biased toward disorder will err in.

The lane's premise — very low pLDDT implies unstructured — mostly holds, which
is why this survived: our two published ACKR3 disorder-path sites (S9, S18) are
genuinely coil at pLDDT 29-40. It fails only where pLDDT is low AND the model
still forms an element, which our own notes put at roughly 12% of the lane's
sites. 1,551 of the 3,865 published sites inside a disulfide span came from
this lane.

The fix costs nothing: `signals["ss"]` is already computed for both lanes from
the same model, so the gate is a lookup the lane simply never did.
"""

from __future__ import annotations

from typing import Any

from accessible_surfaceome.tag_sites.disorder import disorder_candidates
from accessible_surfaceome.tag_sites.surface_loop import LOOP_SS

#: A 12-residue extracellular run that every other gate waves through: flexible,
#: exposed, clear of hazards. Secondary structure is the only axis in play.
RUN = range(20, 32)


def signals(ss: dict[int, str]) -> dict[str, Any]:
    res = list(RUN)
    return {
        "sequence": "A" * 40,
        "topology": {r: "O" for r in range(1, 41)},
        "plddt": {r: 45.0 for r in range(1, 41)},
        "disorder": {r: (90.0 if r in RUN else 10.0) for r in range(1, 41)},
        "rsa": {r: 0.7 for r in range(1, 41)},
        "ss": ss,
        "feature_dist": {r: 25.0 for r in range(1, 41)},
        "conservation": {r: 0.0 for r in range(1, 41)},
        "gap_freq": {r: 0.0 for r in range(1, 41)},
        "_res": res,
    }


def picks(ss: dict[int, str]) -> set[int]:
    return {
        s["insert_after_residue"]
        for s in disorder_candidates(
            signals(ss), gene_symbol="GENEX", uniprot_acc="P00000"
        )
    }


def test_a_helical_residue_in_a_flexible_run_is_not_a_candidate() -> None:
    """The defect. Low pLDDT plus a helix is the 12% the lane's premise misses,
    and a 51-aa cassette into a helix is the failure this gate exists to stop."""
    ss = {r: ("H" if 24 <= r <= 28 else "C") for r in range(1, 41)}
    assert picks(ss).isdisjoint({24, 25, 26, 27, 28})


def test_the_coil_residues_of_the_same_run_still_pass() -> None:
    """The gate must not empty the lane — it is the only path that reaches a
    long disordered ectodomain, where the surface-loop gate's loop-length floor
    has nothing to measure."""
    ss = {r: ("H" if 24 <= r <= 28 else "C") for r in range(1, 41)}
    assert {20, 21, 22, 23} <= picks(ss)


def test_a_fully_coil_run_is_untouched() -> None:
    """ACKR3's S9/S18 are genuinely coil at pLDDT 29-40, so the common case has
    to be unaffected or the fix costs real sites."""
    assert picks({r: "C" for r in range(1, 41)}) == set(RUN)


def test_a_strand_is_structure_too() -> None:
    """DSSP E is not in LOOP_SS. A beta strand inside a flexible run is as bad
    a host as a helix, and 143-149 on one panel protein was mostly E."""
    ss = {r: ("E" if 24 <= r <= 28 else "C") for r in range(1, 41)}
    assert picks(ss).isdisjoint({24, 25, 26, 27, 28})


def test_the_lane_accepts_every_member_of_LOOP_SS() -> None:
    """Coil, turn, bend and 3-10 all host an insert; only H and E are excluded.
    Pinned against LOOP_SS itself so the two lanes cannot drift apart."""
    for code in sorted(LOOP_SS):
        ss = {r: code for r in range(1, 41)}
        assert picks(ss) == set(RUN), f"{code} should be insertable"


def test_a_missing_ss_call_does_not_silently_drop_a_residue() -> None:
    """No DSSP for a residue is unknown, not structured. Treating absence as a
    helix would quietly empty the lane for any protein whose model failed to
    parse — a failure that looks identical to 'this protein has no sites'."""
    assert picks({}) == set(RUN)
