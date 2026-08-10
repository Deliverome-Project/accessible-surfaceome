"""Unit tests for the low-literature/SURFY badge predicate.

`is_low_literature_surfy` is NOT a tier preset — it flags a NON-canonical gene
whose below-canonical verdict may be evidence-limited (thin discovery corpus +
SURFY predicts surface). It takes the SURFY flag separately because SURFY is a
candidate-universe DB flag, not part of the deep-dive `filters`. Cutoff pinned
at LOW_LIT_PAPERS_MAX = 100 (empirical inflection; see PR #130).
"""
from accessible_surfaceome.release.catalog_presets import (
    LOW_LIT_PAPERS_MAX,
    is_low_literature_surfy,
)

# A minimal NON-canonical record (confidence='low' fails passes_canonical).
NON_CANON = {
    "evidence_grade": "weak",
    "confidence": "low",
    "surface_specificity": "mixed",
    "state_dependence": "unclear",
    "surface_accessibility": "low",
    "evidence_density": "low",
    "n_papers_found": 50,
}

# A CANONICAL record (clears every gate) — should never carry the badge.
CANON = {
    "evidence_grade": "direct_multi_method",
    "confidence": "high",
    "surface_specificity": "surface_dominant",
    "state_dependence": "low",
    "low_endogenous_expression": False,
    "surface_accessibility": "high",
    "evidence_density": "high",
    "n_papers_found": 20,  # thin lit, but canonical → still excluded
}


def test_cutoff_pinned_at_100():
    assert LOW_LIT_PAPERS_MAX == 100


def test_flagged_when_noncanonical_thin_and_surfy_positive():
    assert is_low_literature_surfy(NON_CANON, surfy_positive=True) is True


def test_not_flagged_when_surfy_negative():
    assert is_low_literature_surfy(NON_CANON, surfy_positive=False) is False


def test_not_flagged_above_cutoff():
    f = {**NON_CANON, "n_papers_found": LOW_LIT_PAPERS_MAX}  # 100 is NOT < 100
    assert is_low_literature_surfy(f, surfy_positive=True) is False
    f2 = {**NON_CANON, "n_papers_found": 150}
    assert is_low_literature_surfy(f2, surfy_positive=True) is False


def test_flagged_just_below_cutoff():
    f = {**NON_CANON, "n_papers_found": LOW_LIT_PAPERS_MAX - 1}  # 99
    assert is_low_literature_surfy(f, surfy_positive=True) is True


def test_canonical_never_flagged_even_if_thin_and_surfy():
    # Scope decision: canonical calls don't get the evidence-gap caveat.
    assert is_low_literature_surfy(CANON, surfy_positive=True) is False


def test_missing_paper_count_not_flagged():
    f = {k: v for k, v in NON_CANON.items() if k != "n_papers_found"}
    assert is_low_literature_surfy(f, surfy_positive=True) is False
