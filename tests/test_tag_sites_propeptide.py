"""A cleaved C-terminus cannot carry a tag, and the terminal lane did not know.

A GPI-anchored protein's C-terminal propeptide is cleaved at the omega site and
replaced by the glycolipid anchor, so the precursor C-terminus is not a position
on the mature protein. The lane builds terminal proposals from the DeepTMHMM
string alone: it ends extracellular, so the rule proposes a C-terminal tag, and
nothing in it asks whether that terminus survives maturation.

The mechanism is NOT that the tag is carried off with the propeptide -- the GPI
signal has to BE the C-terminus to be recognised by the transamidase, so a tag
appended past it prevents anchoring instead and the protein ends up unanchored
rather than anchored-and-untagged. Same outcome, different reason; see
``terminal._c_terminus_cleaved``.

Measured cohort-wide against UniProt: **116 of the 981 deterministic
``terminal_c`` rows in ``tag_site_public`` sit inside a span maturation
removes**, and ``insert_after_residue`` equals the full precursor length in every
one, with the GPI omega site one residue before the propeptide start. ALPL 524
(propeptide 502-524), CD55 381 (354-381), PRNP 253 (231-253), THY1 161
(131-161), FOLR1 257 (235-257). An earlier version of this file said "20 of 21
across 19 well-known GPI proteins" -- that was a hand-picked probe set, not the
cohort, and it understated the population by an order of magnitude.

**This is a categorical refusal, not a ranking penalty**, and the distinction is
the one this repo spent a day learning. Thresholds on continuous signals should
rank: the 10 A clearance floor rejects 16.9% of published working sites, a DSSP
helix veto 31%. But a cleaved residue is not a risky site, it is *absent from
the mature chain* — the same category as a glycosylation sequon, which stays at
distance 0.0 and is refused outright. "If it was published and worked, why
reject it?" has no force here: nothing can be published at a residue the cell
removes before the protein arrives.

The lane already applies this exact reasoning at the OTHER end — it places an
N-terminal tag after the signal-peptide cleavage site "so the signal peptidase
can't take it with the signal". The C-terminus never got the same treatment.
"""

from __future__ import annotations

from typing import Any

from accessible_surfaceome.tag_sites import features as F
from accessible_surfaceome.tag_sites.terminal import terminal_candidates

#: ALPL's shape: 524 residues, extracellular C-terminus, propeptide 502-524.
ALPL_LEN = 524


def signals(
    length: int = ALPL_LEN,
    *,
    c_state: str = "O",
    n_state: str = "O",
    propeptide: tuple[int, int] | None = (502, 524),
) -> dict[str, Any]:
    topo = {i: "M" for i in range(1, length + 1)}
    topo[1] = n_state
    topo[length] = c_state
    out: dict[str, Any] = {
        "sequence": "A" * length,
        "topology": topo,
        "plddt": {i: 85.0 for i in range(1, length + 1)},
    }
    if propeptide is not None:
        out["propeptide"] = propeptide
    return out


def kinds(sig: dict[str, Any], **kw) -> set[str]:
    return {
        s["site_kind"]
        for s in terminal_candidates(sig, gene_symbol="ALPL", uniprot_acc="P05186", **kw)
    }


def test_a_cleaved_c_terminus_yields_no_c_terminal_tag() -> None:
    """The defect. ALPL 524 is inside propeptide 502-524, so the published site
    is the one position guaranteed absent from the mature protein."""
    assert "terminal_c" not in kinds(signals())


def test_without_a_propeptide_the_c_terminal_tag_is_unchanged() -> None:
    """Regression guard: most proteins have no C-terminal propeptide and must
    keep their C-terminal site exactly as before."""
    assert "terminal_c" in kinds(signals(propeptide=None))


def test_a_propeptide_elsewhere_does_not_block_the_c_terminus() -> None:
    """An N-terminal or internal propeptide says nothing about the C-terminus.
    Refusing on the mere presence of a Propeptide feature would be the
    over-broad version of this fix."""
    assert "terminal_c" in kinds(signals(propeptide=(20, 40)))


def test_the_c_terminal_snorkel_is_refused_too() -> None:
    """A snorkel presents a tag at the C-terminus through a TM-snorkeling
    linker — it needs a C-terminus to attach to. On a cleaved terminus there is
    nothing to snorkel, so suppressing the direct tag while emitting the snorkel
    would just relabel the same dead position."""
    sig = signals(n_state="I", c_state="I", propeptide=(502, 524))
    assert kinds(sig) == set(), f"expected no sites, got {kinds(sig)}"


def test_the_n_terminal_site_is_untouched() -> None:
    """The propeptide is at the far end. An N-terminal tag on a GPI protein is
    the correct design — it is why the one GPI member of the S4E9 plasmid batch
    is N-terminal by construction."""
    assert "terminal_n" in kinds(signals())


def test_the_refusal_is_recorded_not_silent() -> None:
    """A veto's false negatives are invisible: a refused site leaves no row, no
    pin and no artifact, which is how three bad gates survived in this repo
    until audits went looking. A reader must be able to tell "no C-terminal site
    because it is cleaved" from "no C-terminal site because the terminus is
    intracellular"."""
    sink: list[dict[str, Any]] = []
    terminal_candidates(
        signals(), gene_symbol="ALPL", uniprot_acc="P05186", rejected_sink=sink
    )
    assert len(sink) == 1
    assert sink[0]["site_kind"] == "terminal_c"
    assert sink[0]["gate"] == "propeptide_cleaved"
    assert "502-524" in sink[0]["reason"]


def test_nothing_is_recorded_when_nothing_is_refused() -> None:
    sink: list[dict[str, Any]] = []
    terminal_candidates(
        signals(propeptide=None), gene_symbol="ALPL", uniprot_acc="P05186",
        rejected_sink=sink,
    )
    assert sink == []


def test_the_boundary_is_inclusive_at_the_propeptide_start() -> None:
    """The omega site sits one residue BEFORE the propeptide, so the first
    propeptide residue is already removed. A site at exactly that residue is
    cleaved, not borderline."""
    assert "terminal_c" not in kinds(signals(length=524, propeptide=(524, 524)))


# --------------------------------------------------------------------------
# Either annotation establishes the cleavage, and the production path has to
# actually receive it.
#
# Measured over the 115 deterministic `terminal_c` rows whose gene is in the
# NetGPI anchored set (`deliverome-analysis` `gpi_set.tsv`, 157 genes):
#
#   UniProt Propeptide covers the C-terminus    110
#   no Propeptide, but UniProt GPI Lipidation     2   <- ACHE, MSLN
#   neither annotated in UniProt                  3   <- CLCA4, GML, GPC5
#
# So the Lipidation path is worth two genes at zero cost: the same features
# dict, already fetched for the hazard veto. The remaining three are why NetGPI
# is NOT wired as a source — GML has no omega site at all and GPC5 reports 27 on
# a 572-residue protein, a number in some alternative form's numbering rather
# than the canonical frame we publish against.
# --------------------------------------------------------------------------


def test_a_propeptide_feature_gives_the_span() -> None:
    feats = [{"type": "Propeptide",
              "location": {"start": {"value": 502}, "end": {"value": 524}}}]
    assert F.cleaved_c_terminus(feats, 524) == (502, 524)


def test_a_gpi_lipidation_alone_gives_the_span() -> None:
    """ACHE's shape: no C-terminal Propeptide, omega annotated at 588 of 614.
    The omega residue CARRIES the anchor and survives, so the cleaved span
    starts one residue after it."""
    feats = [{"type": "Lipidation", "description": "GPI-anchor amidated serine",
              "location": {"start": {"value": 588}}}]
    assert F.cleaved_c_terminus(feats, 614) == (589, 614)


def test_the_propeptide_wins_when_both_are_annotated() -> None:
    """The curated span is more specific than one derived from a point feature."""
    feats = [
        {"type": "Propeptide",
         "location": {"start": {"value": 231}, "end": {"value": 253}}},
        {"type": "Lipidation", "description": "GPI-anchor amidated glycine",
         "location": {"start": {"value": 230}}},
    ]
    assert F.cleaved_c_terminus(feats, 253) == (231, 253)


def test_a_non_gpi_lipidation_is_not_a_cleavage() -> None:
    """Palmitoylation, myristoylation and the rest attach without removing a
    propeptide. Only the GPI case cleaves."""
    feats = [{"type": "Lipidation", "description": "S-palmitoyl cysteine",
              "location": {"start": {"value": 588}}}]
    assert F.cleaved_c_terminus(feats, 614) is None


def test_an_omega_at_the_c_terminus_cleaves_nothing() -> None:
    """If the omega residue IS the last residue there is no tail to remove, so
    there is no span and no refusal — an empty range must not read as one."""
    feats = [{"type": "Lipidation", "description": "GPI-anchor amidated serine",
              "location": {"start": {"value": 614}}}]
    assert F.cleaved_c_terminus(feats, 614) is None


def test_no_annotation_means_no_span() -> None:
    assert F.cleaved_c_terminus([], 524) is None


def test_run_gene_threads_the_propeptide_into_the_signals() -> None:
    """The defect this closes: `run_gene` accepted no propeptide and so never
    put one in `signals`, leaving the refusal inert in the production path
    while every unit test of the lane passed. Structural, because `run_gene`
    needs an AF model and DSSP."""
    import inspect

    from accessible_surfaceome.tag_sites import run as R

    assert "propeptide" in inspect.signature(R.run_gene).parameters, (
        "run_gene takes no propeptide, so compute_signals cannot receive one"
    )
    src = inspect.getsource(R.run_gene)
    assert "propeptide=propeptide" in src, (
        "run_gene has the parameter but does not pass it to compute_signals"
    )
