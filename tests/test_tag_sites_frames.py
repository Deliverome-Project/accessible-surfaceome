"""Proteoform-frame resolution for tag-site positions.

A paper states its insertion in whatever frame it used: the mature protein, an
isoform, an ortholog. ``residue_mentions`` reads one sequence, so a position in
any other frame fails to confirm and the site is downgraded to ``inferred`` —
its own docstring says so and defers the recovery to the synthesis REPL. These
tests pin the deterministic recovery, and the GUARDS that keep it from becoming
a coincidence generator.

Every "real" case below is a verbatim quote from a published record in
``tag_site_public`` whose ``position_evidence`` is ``inferred`` today, with the
verdict adjudicated by hand against the cited sentence. They are the reason the
guard is shaped the way it is:

* the GABA-A sentence NAMES its frame ("of the mature ... subunit"), so one
  evidence unit is enough;
* the alpha-2-delta sentence names no frame but spells TWO residues
  ("Asn-549 and Asp-550"), each confirmable against the isoform sequence, which
  is independent evidence that the paper is numbering in that frame;
* the KCC2b sentence names a frame we do not have ("of the rat"), so a frame
  that merely happens to fit must NOT validate it;
* the ATPase sentence gives bare positions with no letters at all, so there is
  nothing to confirm in any frame.
"""

from __future__ import annotations

import pytest

from accessible_surfaceome.agents.tag_site.frames import (
    Frame,
    letter_confirmed_positions,
    map_to_reference,
    named_frame_families,
    resolve,
)

# --------------------------------------------------------------------------
# frame keywords: what the sentence itself says about its numbering
# --------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("inserted between amino acids 4 and 5 of the mature subunit", {"mature"}),
        # "precursor" is the UNPROCESSED full-length form, i.e. what the UniProt
        # canonical sequence already is — the opposite of the mature frame. It
        # names the reference, so it licenses no alternate frame.
        ("numbering follows the precursor protein", {"reference"}),
        ("residues 383 and 384 of the rat KCC2b", {"ortholog"}),
        ("between Lys-595 and Arg-596 of the murine protein", {"ortholog"}),
        ("inserted in isoform 2 after residue 88", {"isoform"}),
        # No frame language at all -> nothing is named, so brute force is all
        # that is left and (per the guards below) it cannot validate.
        ("double tags at positions 119 and 318 were extracellular", set()),
        ("the human protein was tagged after residue 64", set()),
    ],
)
def test_named_frame_families(text: str, expected: set[str]) -> None:
    assert named_frame_families(text) == expected


def test_human_alone_is_not_a_named_alternate_frame() -> None:
    """"human" must not be read as naming an ortholog frame.

    Nearly every paper in the corpus says "human" somewhere. Treating it as a
    frame name would make the named-frame rule fire on almost everything and
    defeat the guard entirely."""
    assert "ortholog" not in named_frame_families("the human receptor was tagged")


# --------------------------------------------------------------------------
# letter-confirmed positions: the only form strong enough to validate a
# non-reference frame on its own
# --------------------------------------------------------------------------


def test_letter_confirmed_positions_requires_the_sequence_to_agree() -> None:
    seq = "MKTAYIAKQRQISFVKSHFSRQ"  # 1-based: M1 K2 T3 A4 Y5 I6 A7 K8 ...
    # A4 is an A in the sequence; A5 is not (Y5).
    assert letter_confirmed_positions("the A4 variant", seq) == {4}
    assert letter_confirmed_positions("the A5 variant", seq) == set()


def test_letter_confirmed_positions_reads_three_letter_and_full_names() -> None:
    seq = "MKTAYIAKQRQISFVKSHFSRQ"
    assert letter_confirmed_positions("between Thr-3 and Ala-4", seq) == {3, 4}
    assert letter_confirmed_positions("at threonine 3", seq) == {3}


def test_bare_positional_forms_are_not_letter_confirmed() -> None:
    """"positions 383 and 384" names no residue identity, so no sequence can
    confirm or deny it. It must not count toward the two-token guard — that is
    what keeps the rat-framed KCC2b citation from validating against a human
    isoform that happens to fit."""
    seq = "MKTAYIAKQRQISFVKSHFSRQ"
    assert letter_confirmed_positions("residues 3 and 4", seq) == set()
    assert letter_confirmed_positions("at position 3", seq) == set()
    assert letter_confirmed_positions("aa 3", seq) == set()


# --------------------------------------------------------------------------
# mapping a frame position back to the reference coordinate
# --------------------------------------------------------------------------


def test_map_to_reference_uses_the_offset_when_the_frame_has_one() -> None:
    """A mature frame is the reference minus the signal peptide, so the mapping
    is pure arithmetic and needs no alignment."""
    reference = "SSSSSMKTAYIAKQRQISFVKSHFSRQ"
    mature = Frame(label="mature", sequence=reference[5:], offset=5)
    assert map_to_reference(mature, 1, reference=reference) == 6


def test_map_to_reference_finds_a_unique_window_when_there_is_no_offset() -> None:
    """An isoform differs by an indel, so the offset is not constant and the
    coordinate is recovered by locating the residue's own neighbourhood."""
    reference = "MKTAYIAKQRQISFVKSHFSRQWEDLYKNVAC"
    isoform = Frame(label="isoform:X-2", sequence="MKTAY" + reference[5:], offset=None)
    # Identical here, so position 12 maps to 12.
    assert map_to_reference(isoform, 12, reference=reference) == 12


def test_map_to_reference_refuses_an_ambiguous_window() -> None:
    """A repeated neighbourhood cannot identify one coordinate, and guessing is
    how a cassette lands 100 residues off. Refuse instead."""
    repeat = "MKTAYIAKQR"
    reference = repeat * 4
    frame = Frame(label="isoform:X-2", sequence=reference, offset=None)
    assert map_to_reference(frame, 5, reference=reference) is None


def test_map_to_reference_refuses_a_position_outside_the_frame() -> None:
    reference = "MKTAYIAKQRQISFVKSHFSRQ"
    frame = Frame(label="isoform:X-2", sequence=reference, offset=None)
    assert map_to_reference(frame, 9_999, reference=reference) is None


# --------------------------------------------------------------------------
# the guards, against the four real sentences
# --------------------------------------------------------------------------

#: GABRA4 (P31644), junction 39. Signal peptide is 35, so the paper's mature
#: residue 4 IS canonical 39 — the agent had the junction right and only lacked
#: a way to prove it from the sentence.
GABA_QUOTE = (
    "FLAG (DYKDDDDK) or HA (YPYDVPDYA) epitopes were inserted between amino "
    "acids 4 and 5 of the mature GABA A receptor subunit subtypes as needed, so "
    "that subunit total and cell surface expression could be determined by flow "
    "cytometry."
)

#: CACNA2D1 (P54289), junction 568. The sentence names no frame but spells both
#: flanking residues, and they confirm in isoform-2 coordinates (549 -> 568).
A2D1_QUOTE = (
    "alpha 2 delta-1-HA (HA-tag sequence YPYDVPDYA inserted between Asn-549 and "
    "Asp-550) were used in all imaging experiments."
)

#: SLC12A5 (Q9H2X9), junction 406. Names a RAT frame, which we do not hold.
KCC2B_QUOTE = (
    "The extracellular FLAG-tag was inserted into the low-conserved region of "
    "the 3rd extracellular loop between amino acid positions 383 and 384 of the "
    "rat KCC2b."
)

#: ATP1A3 (P13637), junction 109. Bare positions, no residue identities.
ATPASE_QUOTE = (
    "Immunofluorescence analysis of permeabilized and intact cells using a "
    "monoclonal antibody specific for the HA epitope showed that double tags at "
    "positions 119 and 318 were located extracellularly."
)


def _mature_case() -> tuple[str, list[Frame], int]:
    """A reference with a 35-residue signal peptide; mature 4 == reference 39."""
    reference = "S" * 35 + "MKTAYIAKQRQISFVKSHFSRQWEDLYKNVACGH"
    frames = [
        Frame(label="member", sequence=reference, offset=0),
        Frame(label="mature", sequence=reference[35:], offset=35),
    ]
    return reference, frames, 39


def test_named_frame_validates_on_one_evidence_unit() -> None:
    """The GABA-A case. The sentence says "of the mature ... subunit", so the
    frame is named and a single span of positions is enough."""
    reference, frames, target = _mature_case()
    res = resolve(
        GABA_QUOTE, frames=frames, reference_label="member", target=target
    )
    assert res.validating_hit is not None
    assert res.validating_hit.frame_label == "mature"
    assert res.validating_hit.frame_position == 4
    assert res.validating_hit.reference_position == 39
    assert res.validating_hit.frame_named is True


def test_two_letter_confirmed_tokens_validate_an_unnamed_frame() -> None:
    """The alpha-2-delta-1 case. No frame is named, but "Asn-549 and Asp-550"
    are two residue identities that both confirm in the same frame."""
    # Reference carries N/D at 568/569; the isoform reaches the same residues at
    # 549/550 via a 19-residue deletion upstream.
    reference = "M" * 567 + "ND" + "GH"
    isoform_seq = "M" * 548 + "ND" + "GH"
    frames = [
        Frame(label="member", sequence=reference, offset=0),
        Frame(label="isoform:P54289-2", sequence=isoform_seq, offset=19),
    ]
    res = resolve(A2D1_QUOTE, frames=frames, reference_label="member", target=568)
    assert res.validating_hit is not None
    assert res.validating_hit.frame_label == "isoform:P54289-2"
    assert res.validating_hit.frame_named is False
    assert res.validating_hit.letter_confirmed_tokens >= 2


def test_receptor_nomenclature_does_not_license_a_frame() -> None:
    """Two code-form tokens are NOT independent evidence of a frame.

    Measured, not hypothesized: scoring a 495-clip ADCY2 pool, every clip that
    only a non-reference frame "confirmed" was a dopamine-receptor sentence —
    "D1-like ... D2 ... D3 ... D4" read as aspartate at positions 2/3/4, which
    an isoform happens to carry. That is three letter-confirmed tokens in one
    frame, so a bare >=2 rule licenses it.

    ``residue_mentions`` already documents that the bare CODE form is the noisy
    one ("A549 is a cell line, H3K79 a histone mark"), and the sequence check
    is near-useless at low positions where any letter has a ~1/20 chance. So
    the two-token rule additionally requires at least one SPELLED residue —
    "Asn-549", "threonine 436" — which nomenclature does not produce.
    """
    frame_seq = "MDDDAYIAKQRQISFVKSHFSRQ"  # D at 2, 3 and 4
    reference = "MKTAYIAKQRQISFVKSHFSRQ"
    frames = [
        Frame(label="member", sequence=reference, offset=0),
        Frame(label="isoform:X-2", sequence=frame_seq, offset=0),
    ]
    res = resolve(
        "D1-like receptors are distinguished from the D2, D3 and D4 subtypes",
        frames=frames,
        reference_label="member",
        target=3,
    )
    assert res.validating_hit is None


def test_a_spelled_residue_plus_a_code_still_licenses_a_frame() -> None:
    """The alpha-2-delta-1 case must keep working: "Asn-549 and Asp-550" are
    spelled, so the frame is licensed. The refinement must not cost us the
    rescue it was built for."""
    reference = "M" * 567 + "ND" + "GH"
    isoform_seq = "M" * 548 + "ND" + "GH"
    frames = [
        Frame(label="member", sequence=reference, offset=0),
        Frame(label="isoform:P54289-2", sequence=isoform_seq, offset=19),
    ]
    res = resolve(A2D1_QUOTE, frames=frames, reference_label="member", target=568)
    assert res.validating_hit is not None
    assert res.validating_hit.frame_label == "isoform:P54289-2"
    assert res.validating_hit.spelled_tokens >= 1


def test_a_named_but_unavailable_frame_blocks_every_other_frame() -> None:
    """The KCC2b case, and the whole point of the guard.

    The sentence says "of the rat". We hold no rat sequence. A human isoform
    that happens to carry a residue at the cited number is a coincidence, and
    accepting it would publish a human coordinate derived from a rat position
    with nothing but arithmetic behind it."""
    reference = "M" * 405 + "TP" + "GH"
    isoform_seq = "M" * 383 + "TP" + "GH"
    frames = [
        Frame(label="member", sequence=reference, offset=0),
        Frame(label="isoform:Q9H2X9-2", sequence=isoform_seq, offset=22),
    ]
    res = resolve(KCC2B_QUOTE, frames=frames, reference_label="member", target=406)
    assert res.named_families == {"ortholog"}
    assert res.blocked_by_unavailable_frame is True
    assert res.validating_hit is None


def test_an_unavailable_named_frame_does_not_suppress_the_protein_s_own_frame() -> None:
    """Guard 2 stops an alternate frame being promoted — never the reference.

    The frame-name patterns read ordinary methods prose, and "of the rat
    anti-HA antibody" names a reagent, not a numbering frame. If a false
    positive there could block the reference frame, this module would silently
    DOWNGRADE correctly-cited sites — a regression dressed as a safeguard.
    """
    reference = "MKTAYIAKQRQISFVKSHFSRQ"
    frames = [Frame(label="member", sequence=reference, offset=0)]
    res = resolve(
        "detected with a mouse monoclonal antibody of the rat anti-HA clone; "
        "the tag was inserted after Thr-3",
        frames=frames,
        reference_label="member",
        target=3,
    )
    assert res.blocked_by_unavailable_frame is True
    assert res.validating_hit is not None
    assert res.validating_hit.frame_label == "member"


def test_bare_positions_never_validate_an_alternate_frame() -> None:
    """The ATPase case. "positions 119 and 318" names no residue identity, so
    no sequence confirms it; and no frame is named, so there is nothing to
    license the frame that happens to fit."""
    reference = "M" * 107 + "AG" + "H" * 400
    isoform_seq = "M" * 117 + "AG" + "H" * 400
    frames = [
        Frame(label="member", sequence=reference, offset=0),
        Frame(label="isoform:P13637-2", sequence=isoform_seq, offset=-10),
    ]
    res = resolve(ATPASE_QUOTE, frames=frames, reference_label="member", target=109)
    assert res.validating_hit is None


def test_reference_frame_hit_validates_without_a_named_frame() -> None:
    """Unchanged behaviour for the ordinary case: when the quote names the
    residue in the protein's OWN frame, that is a validated position and no
    frame language is required."""
    reference = "MKTAYIAKQRQISFVKSHFSRQ"
    frames = [Frame(label="member", sequence=reference, offset=0)]
    res = resolve(
        "the tag was inserted after Thr-3", frames=frames,
        reference_label="member", target=3,
    )
    assert res.validating_hit is not None
    assert res.validating_hit.frame_label == "member"


def test_a_hit_off_target_does_not_validate() -> None:
    """A frame that confirms SOME residue is not evidence for THIS junction."""
    reference, frames, _ = _mature_case()
    res = resolve(GABA_QUOTE, frames=frames, reference_label="member", target=200)
    assert res.validating_hit is None


def test_neighbouring_positions_are_within_tolerance() -> None:
    """Papers differ on whether the label is the residue before or after the
    junction, which ``residue_mentions`` documents, so n-1 and n+1 count."""
    reference, frames, target = _mature_case()
    for t in (target - 1, target, target + 1):
        res = resolve(GABA_QUOTE, frames=frames, reference_label="member", target=t)
        assert res.validating_hit is not None, t
    res = resolve(GABA_QUOTE, frames=frames, reference_label="member", target=target + 3)
    assert res.validating_hit is None


def test_resolution_records_every_hit_even_when_none_validates() -> None:
    """A blocked or unlicensed hit is still worth recording: it is what lets a
    record say "the citation numbers this in a rat frame at 383" instead of
    silently claiming nothing."""
    reference = "M" * 405 + "TP" + "GH"
    isoform_seq = "M" * 383 + "TP" + "GH"
    frames = [
        Frame(label="member", sequence=reference, offset=0),
        Frame(label="isoform:Q9H2X9-2", sequence=isoform_seq, offset=22),
    ]
    res = resolve(KCC2B_QUOTE, frames=frames, reference_label="member", target=406)
    assert res.validating_hit is None
    assert res.cited_positions == {383, 384}
