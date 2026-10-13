"""Make residue-bearing clips survive the menu cap.

`select_clips` sorts the pool by `clip.score` and keeps the top 100. On the
richest genes that discards most of the evidence — TFRC 746 clips -> 100, LDLR
586 -> 100 — so a clip pinning a real site is never shown to the selector at
all. Reading residues (the previous commit) is useless if the clip carrying one
is cut before the model sees it.

This is a pre-pass on the tag-site pool only; the shared selector is untouched,
so the internalization track is unaffected.
"""
import types

from accessible_surfaceome.agents.tag_site.literature_discovery import boost_residue_clips

# TMEM123: SP 1-26 | extracellular 27-168 | TM 169-190 | cytoplasmic 191-208
SEQ = (
    "MGLGARGAWAALLLGTLQVLALLGAAHESAAMAASANIENSGLPHNSSANSTETLQHVPSDHTNETSNSTVKPPTSVAS"
    "DSSNTTVTTMKPTAASNTTTPGMVSTNMTSTTLKSTPKTTSVSQNTSQISTSTMTVTHNSSVTSAASSVTITTTMHSEA"
    "KKGSKFDTGSFVGGIVLTLGVLSILYIGCKMYYSRRGIRYRTIDEHDAII")
TOPO = "S" * 26 + "O" * 142 + "M" * 22 + "I" * 18

TABLE_ROW = ("CTGGAGGAAGAGCTGAGGCGCAGACTGAC GCGCCCTATTTGGTCATTCG CAGCCATGG /A33 "
             "CGAGCCCGGCAGCGGTAAGTGGCTGCGGGGGTCGTCAGC")


def _clip(quote, score, context=None):
    return types.SimpleNamespace(quote=quote, context_excerpt=context, score=score)


def _boost(pool):
    return boost_residue_clips(pool, sequence=SEQ, topology=TOPO)


def test_a_clip_naming_an_extracellular_residue_outranks_a_higher_scoring_one():
    pool = {"lo": _clip("an HA tag was inserted after H155 of the ectodomain", 0.1),
            "hi": _clip("background biology", 9.9)}
    assert len(_boost(pool)) == 1
    assert pool["lo"].score > pool["hi"].score


def test_a_bare_primer_table_row_is_no_longer_boosted():
    """The cost of requiring an insertion claim. Such a row carries the
    authoritative label but is a wall of nucleotides the model cannot quote a
    site out of; it still reaches the pool through draft ranking."""
    assert _boost({"t": _clip(TABLE_ROW, 0.1)}) == {}


def test_a_clip_naming_a_cytoplasmic_residue_is_not_boosted():
    """Residue 200 is in the cytoplasmic tail — not a tag site."""
    pool = {"c": _clip("the epitope was placed at residue 200", 0.1)}
    assert len(_boost(pool)) == 0
    assert pool["c"].score == 0.1


def test_a_clip_naming_a_transmembrane_residue_is_not_boosted():
    pool = {"c": _clip("insertion at position 175", 0.1)}
    assert len(_boost(pool)) == 0


def test_a_clip_with_no_residue_mention_is_untouched():
    pool = {"c": _clip("TMEM123 is a mucin-like protein", 5.0)}
    assert len(_boost(pool)) == 0
    assert pool["c"].score == 5.0


def test_the_surrounding_context_counts_not_just_the_quote():
    pool = {"c": _clip("see Fig. 4a", 0.1, context="the Alfa tag follows the signal peptide (Alanine 34)")}
    assert len(_boost(pool)) == 1


def test_relative_order_among_boosted_clips_is_preserved():
    pool = {
        "weak": _clip("tag inserted at residue 40", 0.2),
        "strong": _clip("tag inserted at residue 50", 0.8),
        "none": _clip("unrelated", 0.5),
    }
    assert len(_boost(pool)) == 2
    assert pool["strong"].score > pool["weak"].score > pool["none"].score


# --- say WHICH clips were lifted, not just how many ---------------------------
#
# A run logged "boosted 1/123" for a gene whose decisive paper had been
# retrieved, and there was no way to tell whether that one clip was the relevant
# one. The pool is not persisted, so a count alone makes the failure
# undiagnosable after the fact.

def test_the_boost_reports_which_clips_and_which_positions():
    pool = {
        "window": _clip("the tag was inserted into the HSEAKK region at H155", 0.1),
        "prose": _clip("the Alfa tag follows the signal peptide (Alanine 34)", 0.1),
        "noise": _clip("background biology", 9.9),
    }
    boosted = _boost(pool)
    assert set(boosted) == {"window", "prose"}
    assert 155 in boosted["window"]
    assert 34 in boosted["prose"]


def test_the_report_is_falsy_and_empty_when_nothing_qualifies():
    pool = {"c": _clip("TMEM123 is a mucin-like protein", 5.0)}
    boosted = _boost(pool)
    assert not boosted and len(boosted) == 0


# --- a residue alone is not enough: it must also describe an insertion ---------
#
# Sequence confirmation cannot catch these. They name a residue the target really
# has at that position; the text is simply about something else. From one ITGB1
# run, where residue 397 is Y and 280 is A:
#
#   "FAK Y397 phosphorylation notably increased"   <- another protein's phosphosite
#   "phosphorylation of FAK at tyrosine 397"       <- the same, spelled out
#   "assessed for purity via A260/A280 ratio"      <- a spectrophotometry reading
#   "an amino acid change at position 520"         <- a variant in another gene
#
# What separates them from the real clip is that none describes an insertion.

ITGB1_LIKE = "M" + "A" * 279 + "A" + "Q" * 115 + "Y" + "K" * 300   # A280, Y397


def _boost_itgb1(pool):
    return boost_residue_clips(pool, sequence=ITGB1_LIKE, topology="O" * len(ITGB1_LIKE))


def test_another_proteins_phosphosite_is_not_boosted():
    pool = {"c": _clip("FAK Y397 phosphorylation notably increased on collagen 1", 0.1)}
    assert _boost_itgb1(pool) == {}


def test_a_spelled_out_phosphosite_is_not_boosted_either():
    pool = {"c": _clip("integrins activate signaling via phosphorylation of FAK at tyrosine 397", 0.1)}
    assert _boost_itgb1(pool) == {}


def test_a_spectrophotometry_reading_is_not_boosted():
    pool = {"c": _clip("total RNA was assessed for purity via A260/A280 ratio (1.8-2.2)", 0.1)}
    assert _boost_itgb1(pool) == {}


def test_a_variant_in_another_gene_is_not_boosted():
    pool = {"c": _clip("The c.1559A>T substitution causes an amino acid change at position 280", 0.1)}
    assert _boost_itgb1(pool) == {}


def test_a_real_insertion_clip_is_still_boosted():
    pool = {"c": _clip("Each ecto-tag was inserted into the hybrid domain between residues A280 and A281", 0.1)}
    assert set(_boost_itgb1(pool)) == {"c"}
