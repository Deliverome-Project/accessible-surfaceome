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
    pool = {"lo": _clip(TABLE_ROW, 0.1), "hi": _clip("background biology", 9.9)}
    assert len(_boost(pool)) == 1
    assert pool["lo"].score > pool["hi"].score


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
        "table": _clip(TABLE_ROW, 0.1),
        "prose": _clip("the Alfa tag follows the signal peptide (Alanine 34)", 0.1),
        "noise": _clip("background biology", 9.9),
    }
    boosted = _boost(pool)
    assert set(boosted) == {"table", "prose"}
    assert 33 in boosted["table"]
    assert 34 in boosted["prose"]


def test_the_report_is_falsy_and_empty_when_nothing_qualifies():
    pool = {"c": _clip("TMEM123 is a mucin-like protein", 5.0)}
    boosted = _boost(pool)
    assert not boosted and len(boosted) == 0
