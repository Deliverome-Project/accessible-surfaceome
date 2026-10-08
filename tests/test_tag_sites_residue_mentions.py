"""Recognise residue positions however a paper spells them.

EndoNB — which supplies 5 of the 16 positive controls — states its insertion
sites in prose, not residue codes: "(Alanine 34)" for TMEM123, "at the codon for
glycine 101" for ITGB1. The machine-readable copies live inside primer tables
surrounded by raw DNA, and TFRC's I290 never appears as a code at all. A parser
that only matches ``[A-Z]\\d+`` cannot see any of it.
"""
from accessible_surfaceome.agents.tag_site.literature_discovery import residue_mentions

# Verbatim from the EndoNB preprint (DOI 10.1101/2025.06.08.658482).
TMEM123 = ("The extracellular region of TMEM123 is predicted to be unstructured, so we "
           "added the Alfa tag to the N-terminal region following the signal peptide "
           "(Alanine 34) (Fig. 4a).")
ITGB1 = ("We endogenously Alfa-tagged this gene (ITGB1) at the codon for glycine 101, "
         "located in a flexible loop")


def test_reads_a_spelled_out_residue_in_parentheses():
    assert 34 in residue_mentions(TMEM123)


def test_reads_a_spelled_out_residue_in_running_prose():
    assert 101 in residue_mentions(ITGB1)


def test_still_reads_the_plain_code_form():
    assert residue_mentions("an ALFA tag was inserted after I290") == {290}


def test_reads_three_letter_and_spaced_forms():
    assert 436 in residue_mentions("BBS inserted after Thr436")
    assert 102 in residue_mentions("the tag sits at Ala 102 of the hybrid domain")


def test_reads_bare_positional_phrases():
    assert 64 in residue_mentions("the epitope was placed at residue 64")
    assert 155 in residue_mentions("insertion at position 155 of the ectodomain")


def test_does_not_mistake_citations_or_years_for_residues():
    """Reference markers and years are the obvious false positives."""
    assert residue_mentions("colorectal cancers 37,38 . In a screen 39 .") == set()
    assert residue_mentions("as reported in 2017 and 2023") == set()


def test_ignores_a_residue_code_buried_in_a_dna_block():
    """The only literal 'A33' in the EndoNB PDF sits inside a primer table."""
    assert residue_mentions("CAGCCATGG /A33 CGAGCCCGGCAGCGGTAAGTGGCTGCGG") == set()
