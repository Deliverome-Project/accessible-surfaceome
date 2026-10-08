"""Draft extraction must be able to rank on relevance, not only position.

`extract_paper_drafts` scores every sentence by where it sits in its section
(`position_score = 1.0 + (n - pos) / n`) and keeps 8 per section. For a paper of
any length that means the model is handed the section PREAMBLE and nothing else.

Measured on the EndoNB preprint (the source for 5 of the curated controls): 30
drafts from 38k chars, all section openings, and the sentence that states the
tag position -- "...so we added the Alfa tag to the N-terminal region following
the signal peptide (Alanine 34)" -- is not among them. The agent then cited the
one tag-related sentence it did get, a general-method line, and invented a
residue 64 positions away.

The default stays position-only so every existing caller is byte-identical; a
caller that knows what it is looking for can supply a relevance term.
"""
import warnings

import pytest

from accessible_surfaceome.tools.evidence_retrieval import extract_paper_drafts

warnings.filterwarnings("ignore")

PDF = ("data/external/blob_cache/unpaywall_pdf/"
       "7a5a643d5a6b2d18ab0bae43843b384a113373ec0f4e58da698b627137e20996.bin")
SITE_SENTENCE_MARK = "Alanine 34"


def _endonb_sections():
    from pathlib import Path

    from accessible_surfaceome.agents.plan_trim_select.pdf_parse import parse_pdf_to_sections
    if not Path(PDF).exists():
        pytest.skip("EndoNB PDF not in the local blob cache")
    return parse_pdf_to_sections(Path(PDF).read_bytes())


def test_position_only_scoring_drops_the_sentence_that_states_the_site():
    """Pins the defect this change exists to fix."""
    drafts = extract_paper_drafts(source_id="DOI:x", abstract=None,
                                  sections=_endonb_sections())
    assert not any(SITE_SENTENCE_MARK in d.quote for d in drafts)


def test_a_relevance_term_promotes_the_sentence_that_states_the_site():
    def relevance(text: str) -> float:
        return 10.0 if "Alfa tag" in text and "signal peptide" in text else 0.0

    drafts = extract_paper_drafts(source_id="DOI:x", abstract=None,
                                  sections=_endonb_sections(), relevance=relevance)
    assert any(SITE_SENTENCE_MARK in d.quote for d in drafts)


def test_relevance_does_not_change_how_many_drafts_are_emitted():
    """It re-ranks within the caps; it must not inflate any pool."""
    sections = _endonb_sections()
    base = extract_paper_drafts(source_id="DOI:x", abstract=None, sections=sections)
    ranked = extract_paper_drafts(source_id="DOI:x", abstract=None, sections=sections,
                                  relevance=lambda t: 10.0 if "Alfa tag" in t else 0.0)
    assert len(ranked) == len(base)


def test_the_default_is_unchanged_for_every_existing_caller():
    sections = _endonb_sections()
    a = extract_paper_drafts(source_id="DOI:x", abstract=None, sections=sections)
    b = extract_paper_drafts(source_id="DOI:x", abstract=None, sections=sections,
                             relevance=None)
    assert [d.quote for d in a] == [d.quote for d in b]


# --- the tag-site scorer, against the real paper ------------------------------

def test_the_tag_site_scorer_rescues_the_site_sentence():
    """End to end on the EndoNB preprint: with the tag-site relevance term the
    sentence stating the insertion position survives the per-section cap."""
    from accessible_surfaceome.agents.tag_site.runner import tag_site_relevance
    TMEM123 = (
        "MGLGARGAWAALLLGTLQVLALLGAAHESAAMAASANIENSGLPHNSSANSTETLQHVPSDHTNETSNSTVKPPTSVAS"
        "DSSNTTVTTMKPTAASNTTTPGMVSTNMTSTTLKSTPKTTSVSQNTSQISTSTMTVTHNSSVTSAASSVTITTTMHSEA"
        "KKGSKFDTGSFVGGIVLTLGVLSILYIGCKMYYSRRGIRYRTIDEHDAII")
    drafts = extract_paper_drafts(
        source_id="DOI:x", abstract=None, sections=_endonb_sections(),
        relevance=tag_site_relevance(TMEM123))
    assert any(SITE_SENTENCE_MARK in d.quote for d in drafts)


def test_the_scorer_ranks_a_positional_tagging_claim_above_background_prose():
    from accessible_surfaceome.agents.tag_site.runner import tag_site_relevance
    seq = "M" + "A" * 99 + "K" + "G" + "A" * 150        # K101
    score = tag_site_relevance(seq)
    site = score("an HA epitope was inserted after K101 of the ectodomain")
    partial = score("the protein was tagged in a previous study")
    background = score("TMEM123 is a highly glycosylated, mucin-like protein")
    assert site > partial > background
    assert background == 0.0
