"""Which contacts veto a tag site, and which must not.

The contact table mixes endogenous biology with therapeutic antibodies, research
tools, viral proteins and crystallisation additives. Vetoing on all of them
would delete candidates for reasons that have nothing to do with the protein's
own function — a tag overlapping a *drug's* epitope is a different concern from
one blocking a co-receptor. These pin that boundary.
"""
from __future__ import annotations

from accessible_surfaceome.tag_sites.ligand_contacts import (
    blocked,
    is_endogenous,
    veto_residues,
)

HUMAN = {"P61769", "P05106", "Q9NZQ7"}  # b2-microglobulin, integrin b3, PD-L1


def _obs(**kw):
    base = {"category": "unclassified", "partner": "P61769", "positions": [10, 11]}
    return {**base, **kw}


def test_an_explicit_co_receptor_counts() -> None:
    assert is_endogenous(_obs(category="receptor_partner"), human_accessions=HUMAN)


def test_an_endogenous_large_ligand_counts() -> None:
    assert is_endogenous(_obs(category="endogenous_large"), human_accessions=HUMAN)


def test_a_human_protein_partner_counts_even_when_unclassified() -> None:
    """10,538 of the extracellular observations are exactly this shape — a human
    accession the upstream classifier left as 'unclassified'. Dropping them
    would discard almost the entire co-receptor signal."""
    assert is_endogenous(_obs(partner="P05106"), human_accessions=HUMAN)


def test_a_therapeutic_antibody_does_not_count() -> None:
    """Overlapping a drug's epitope is not the same concern as blocking
    function, and the user asked for endogenous partners only."""
    assert not is_endogenous(
        _obs(category="therapeutic", partner="10E5 Fab"), human_accessions=HUMAN
    )


def test_a_research_tool_does_not_count() -> None:
    assert not is_endogenous(_obs(category="tool", partner="C4 VHH"), human_accessions=HUMAN)


def test_a_viral_partner_does_not_count() -> None:
    """SARS-CoV-2 spike on ACE2 is a real interface but not an endogenous one,
    and it is 564 observations — enough to matter if it leaked in."""
    assert not is_endogenous(_obs(partner="P0DTC2"), human_accessions=HUMAN)


def test_a_bare_small_molecule_code_does_not_count() -> None:
    """Indistinguishable from a buffer or cryoprotectant without curation."""
    assert not is_endogenous(_obs(partner="EGC"), human_accessions=HUMAN)


def test_cytoplasmic_contacts_are_ignored() -> None:
    """A tag on the surface face cannot block a cytoplasmic contact, so vetoing
    on one would discard a candidate for no reason."""
    rows = [{"uniprot_acc": "Q9NZQ7", "context": "non_extracellular:cytoplasmic",
             "observation_json": _obs()}]
    assert veto_residues(rows, human_accessions=HUMAN) == {}


def test_extracellular_contacts_produce_veto_residues() -> None:
    rows = [{"uniprot_acc": "Q9NZQ7", "context": "extracellular",
             "observation_json": _obs(positions=[41, 42, 43])}]
    assert veto_residues(rows, human_accessions=HUMAN) == {"Q9NZQ7": {41, 42, 43}}


def test_a_malformed_payload_does_not_fail_the_run() -> None:
    rows = [{"uniprot_acc": "Q9NZQ7", "context": "extracellular",
             "observation_json": "{not json"}]
    assert veto_residues(rows, human_accessions=HUMAN) == {}


def test_tolerance_zero_blocks_only_the_residue_itself() -> None:
    """The calibrated default. +/-3 would collide with 2.2% of published,
    working sites instead of 0.4%."""
    assert blocked(41, veto={41}, tolerance=0)
    assert not blocked(42, veto={41}, tolerance=0)


def test_a_wider_tolerance_blocks_the_neighbourhood() -> None:
    assert blocked(44, veto={41}, tolerance=3)
    assert not blocked(45, veto={41}, tolerance=3)


def test_no_veto_set_blocks_nothing() -> None:
    assert not blocked(41, veto=None)
    assert not blocked(41, veto=set())
