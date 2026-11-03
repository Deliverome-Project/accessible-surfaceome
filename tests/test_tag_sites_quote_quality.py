"""A cited quote must actually describe a tag insertion.

`entailment_verified` only asks "is this string present in the ledger?" — never
"does this string support the site?". The GLUT4 run found the correct site
(Q64, exofacial loop 1) and the correct paper (PMID 7686158, the c-myc
exofacial-loop construct), then cited the abstract's opening sentence, which
mentions no tag at all. Right site, right paper, non-probative evidence.
"""
from accessible_surfaceome.agents.tag_site.literature_discovery import (
    best_supporting_quote,
    quote_is_probative,
)

# Verbatim from the SLC2A4 run.
GLUT4_BAD = (
    "Stimulation of glucose transport is the main physiological effect of insulin "
    "in target tissues. This effect is linked to"
)
GLUT4_GOOD = (
    "We inserted a c-myc epitope into the first exofacial loop of GLUT4 and "
    "detected the tag on the surface of non-permeabilized cells."
)


def test_a_quote_describing_a_tag_insertion_is_probative():
    assert quote_is_probative(GLUT4_GOOD) is True


def test_the_glut4_abstract_opener_is_not_probative():
    assert quote_is_probative(GLUT4_BAD) is False


def test_missing_or_empty_quotes_are_not_probative():
    assert quote_is_probative(None) is False
    assert quote_is_probative("") is False


def test_other_tagging_modalities_count_not_just_the_word_tag():
    for q in (
        "a GFP fusion was introduced into the second extracellular loop",
        "the HA epitope was knocked in at the mature N-terminus",
        "insertion of a bungarotoxin-binding site preserved surface display",
        "HiBiT was appended to the ectodomain",
    ):
        assert quote_is_probative(q) is True, q


def test_generic_biology_sentences_are_not_probative():
    for q in (
        "This receptor mediates glucose uptake in adipose tissue.",
        "Expression is restricted to the central nervous system.",
        "The structure was solved at 2.1 angstrom resolution.",
    ):
        assert quote_is_probative(q) is False, q


# --- upgrading a weak citation from the ledger --------------------------------

def _evi(*quotes):
    """Duck-typed Evidence: the helper only reads .spans[*].quote."""
    import types
    return [types.SimpleNamespace(
        spans=[types.SimpleNamespace(quote=q) for q in quotes])]


def test_upgrade_prefers_a_probative_quote_that_names_the_residue():
    ev = _evi(GLUT4_BAD,
              "an HA tag was inserted into the second loop",
              "a c-myc epitope was inserted after Q64 of the transporter")
    assert best_supporting_quote(residue=64, evidence=ev) == (
        "a c-myc epitope was inserted after Q64 of the transporter")


def test_upgrade_falls_back_to_any_probative_quote():
    ev = _evi(GLUT4_BAD, "an HA tag was inserted into the second loop")
    assert best_supporting_quote(residue=999, evidence=ev) == (
        "an HA tag was inserted into the second loop")


def test_upgrade_returns_none_when_the_ledger_has_nothing_probative():
    assert best_supporting_quote(residue=64, evidence=_evi(GLUT4_BAD)) is None
