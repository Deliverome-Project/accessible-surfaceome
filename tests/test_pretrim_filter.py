"""Tests for the pre-trim filter (Step 2 of the cost-reduction package).

Pins:
1. Volume gate: below HEAVY_THRESHOLD, filter is bypassed entirely.
2. Shadow mode: enable=False keeps everything but produces full audit.
3. Active mode: enable=True actually drops matching papers.
4. Review rule with quality-journal sparing.
5. Drug-review title regex (precision-focused — false positives are bad).
6. Atlas title regex.
7. Hard cap activates only at the configured ceiling.
8. Audit invariants: every input paper has exactly one decision; reasons
   tally to per-reason counts.
"""

from __future__ import annotations

import pytest

from accessible_surfaceome.agents.plan_trim_select.pretrim_filter import (
    HARD_CAP,
    HEAVY_THRESHOLD,
    THIN_THRESHOLD,
    pretrim_filter,
)
from accessible_surfaceome.tools._shared.models import Paper


def _paper(
    pmid: int,
    title: str = "Primary research paper",
    *,
    journal: str | None = "Cell",
    year: int = 2024,
    is_review: bool = False,
    publication_type: str = "other",
    is_pmc_oa: bool = True,
) -> Paper:
    return Paper(
        pmid=pmid,
        title=title,
        journal=journal,
        year=year,
        is_review=is_review,
        publication_type=publication_type,  # type: ignore[arg-type]
        is_pmc_oa=is_pmc_oa,
    )


def _bulk(n: int, title_prefix: str = "Primary research") -> list[Paper]:
    """Generate n distinct primary-research papers — used as baseline padding."""
    return [
        _paper(
            pmid=10_000 + i,
            title=f"{title_prefix} {i}: a specific mechanism study",
            journal="J Biol Chem",
            year=2024,
        )
        for i in range(n)
    ]


# -- Activation gate ----------------------------------------------------------


def test_below_thin_threshold_is_passthrough():
    """24 papers (below thin=25): filter doesn't activate at all."""
    papers = _bulk(24)
    # Add a review that the filter WOULD drop if activated.
    papers.append(_paper(99, "Targeted therapies in solid tumors", is_review=True))
    kept, audit = pretrim_filter(papers, enable=True)
    assert kept == papers
    assert audit.activated is False
    assert audit.n_kept == len(papers)


def test_between_thin_and_heavy_is_passthrough():
    """40 papers (mid: thin=25 <= n < heavy=50): filter doesn't activate.

    Precision is insufficient at this volume; filter would over-clip
    relative to the marginal cost savings. This is the calibrated
    activation threshold per the design doc.
    """
    papers = _bulk(40)
    kept, audit = pretrim_filter(papers, enable=True)
    assert audit.activated is False
    assert kept == papers


def test_above_heavy_threshold_activates():
    """60 papers (above heavy=50): filter activates."""
    papers = _bulk(60)
    kept, audit = pretrim_filter(papers, enable=True)
    assert audit.activated is True
    # All primary research; no rules fire; everything kept.
    assert audit.n_kept == 60
    assert audit.n_dropped_review == 0


# -- Shadow vs active mode ----------------------------------------------------


def test_shadow_mode_keeps_all_but_records_decisions():
    """enable=False: keep everything, but the audit records what WOULD drop."""
    papers = _bulk(55) + [
        _paper(
            500,
            "Antibody-drug conjugates in cancer therapy: a recent advance",
            is_review=True,
            journal="Theranostics",
        ),
        _paper(
            501,
            "Pan-Cancer analysis of the surfaceome landscape",
            journal="Nat Commun",
        ),
    ]
    kept, audit = pretrim_filter(papers, enable=False)
    # Shadow mode: everything kept.
    assert kept == papers
    assert audit.activated is True
    # But the would-have-dropped reasons are recorded.
    assert audit.n_dropped_review + audit.n_dropped_drug_review + audit.n_dropped_atlas >= 1
    # No actual hard-cap drops in shadow mode.
    assert audit.n_dropped_cap == 0


def test_active_mode_drops_matching_papers():
    """enable=True with a review + atlas + drug-review: all three drop."""
    primary = _bulk(50)
    review = _paper(
        500,
        "Some narrative review",
        is_review=True,
        journal="J Random Journal",
    )
    atlas = _paper(
        501,
        "Pan-Cancer analysis of the surfaceome landscape",
        journal="Cell Rep",
    )
    drug_review = _paper(
        502,
        "Antibody-drug conjugates in cancer therapy: recent advances",
        journal="Pharmaceutics",
    )
    papers = primary + [review, atlas, drug_review]
    kept, audit = pretrim_filter(papers, enable=True)
    assert audit.activated is True
    assert audit.n_kept == 50
    assert audit.n_dropped_review == 1
    assert audit.n_dropped_atlas == 1
    assert audit.n_dropped_drug_review == 1
    # Specific papers gone from the kept list.
    pmids_kept = {p.pmid for p in kept}
    assert 500 not in pmids_kept
    assert 501 not in pmids_kept
    assert 502 not in pmids_kept


# -- Review with journal-quality sparing -------------------------------------


def test_review_in_quality_journal_is_spared():
    """A Review in 'Cell' or 'Nat Rev' is kept (curatorial gating).

    Empirical reason: validates HMGB1's behaviour where 3 of 6 reviews were
    salvageable mechanism reviews from quality venues. Without this sparing
    the filter loses load-bearing secondary evidence.
    """
    primary = _bulk(50)
    quality_review = _paper(
        500,
        "The redox-sensitive protein HMGB1: intracellular and extracellular roles",
        is_review=True,
        journal="Exp Mol Med",
    )
    generic_review = _paper(
        501,
        "A potential new pathway for X-induced lung injury",
        is_review=True,
        journal="Front Cell Infect Microbiol",
    )
    papers = primary + [quality_review, generic_review]
    kept, audit = pretrim_filter(papers, enable=True)
    assert 500 in {p.pmid for p in kept}
    assert 501 not in {p.pmid for p in kept}
    assert audit.n_dropped_review == 1


@pytest.mark.parametrize(
    "journal",
    [
        "Cell",
        "Nature",
        "Annu Rev Biochem",
        "Annu Rev Cell Dev Biol",
        "Nat Rev Cancer",
        "Trends Cancer",
        "Curr Opin Cell Biol",
        "Cancer Cell",
        "Exp Mol Med",
    ],
)
def test_quality_journals_spare_reviews(journal: str):
    primary = _bulk(50)
    quality_review = _paper(500, "A review", is_review=True, journal=journal)
    kept, _ = pretrim_filter(primary + [quality_review], enable=True)
    assert 500 in {p.pmid for p in kept}, f"{journal!r} should spare reviews"


# -- Drug-review title patterns -----------------------------------------------


@pytest.mark.parametrize(
    "title",
    [
        "Antibody-drug conjugates in cancer therapy: recent advances",
        "Trop2-targeted therapies: emerging therapies and clinical outcomes",
        "Recent advances in ADC engineering for solid tumors",
        "Approved antibody review for breast cancer ADCs",
        "Advances and future directions in cancer immunotherapy",
    ],
)
def test_drug_review_titles_drop(title: str):
    """High-precision regex on the drug-discovery summary class. False
    positives here would drop primary research, so coverage is conservative.
    """
    primary = _bulk(50)
    drug_review = _paper(500, title, journal="Pharmaceutics")
    kept, audit = pretrim_filter(primary + [drug_review], enable=True)
    assert 500 not in {p.pmid for p in kept}, f"{title!r} should be dropped"
    assert audit.n_dropped_drug_review == 1


def test_primary_research_title_with_drug_terms_is_kept():
    """A primary study mentioning ADCs in its title shouldn't be falsely
    dropped. Regex is anchored to summary-paper phrasing.
    """
    primary = _bulk(50)
    # Primary research with "antibody-drug conjugate" in title but not as
    # the synthesis phrasing.
    p = _paper(
        500,
        "Structural characterization of a novel antibody-drug conjugate binder",
        journal="J Mol Biol",
    )
    kept, _ = pretrim_filter(primary + [p], enable=True)
    assert 500 in {p_.pmid for p_ in kept}


# -- Atlas title patterns -----------------------------------------------------


@pytest.mark.parametrize(
    "title",
    [
        "Pan-Cancer analysis of immune cell infiltrates",
        "Pan-cancer landscape of metabolic dysregulation",
        "Landscape of cell-surface proteome in cancer",
        "A compendium of cancer-associated mutations",
        "Broad and thematic remodeling of the surfaceome in glioma",
        "Surfaceome-wide CRISPR screen identifies new targets",
        "Terminomics reveals new substrates of MMP-9",
    ],
)
def test_atlas_titles_drop(title: str):
    primary = _bulk(50)
    atlas = _paper(500, title, journal="Cell Rep")
    kept, audit = pretrim_filter(primary + [atlas], enable=True)
    assert 500 not in {p.pmid for p in kept}, f"{title!r} should be dropped"
    assert audit.n_dropped_atlas == 1


def test_primary_research_with_atlas_word_in_body_kept():
    """A primary mechanistic study that just mentions 'pan-cancer' or
    'atlas' shouldn't drop — regex needs the synthesis phrasing."""
    primary = _bulk(50)
    p = _paper(
        500,
        "TROP2 forms a stable dimer on the surface of carcinoma cells",
        journal="Int J Mol Sci",
    )
    kept, _ = pretrim_filter(primary + [p], enable=True)
    assert 500 in {p_.pmid for p_ in kept}


# -- Hard cap -----------------------------------------------------------------


def test_hard_cap_at_default_ceiling():
    """151 primary papers → cap drops the oldest one."""
    papers = []
    for i in range(151):
        papers.append(
            _paper(
                pmid=10_000 + i,
                title=f"Primary {i}",
                year=2024 - (i % 10),  # mix years
                is_pmc_oa=(i % 3 == 0),
            )
        )
    kept, audit = pretrim_filter(papers, enable=True, cap=HARD_CAP)
    assert audit.activated is True
    assert audit.n_dropped_cap == 1
    assert len(kept) == HARD_CAP


def test_cap_sorts_newest_first_then_pmc_oa():
    """When the cap bites, prefer newer + PMC-OA papers."""
    papers = [
        _paper(pmid=1, title="Old", year=2015, is_pmc_oa=True),
        _paper(pmid=2, title="New non-OA", year=2024, is_pmc_oa=False),
        _paper(pmid=3, title="New OA", year=2024, is_pmc_oa=True),
    ]
    # Pad to activate filter, then add the three above.
    padding = _bulk(50)
    kept, _ = pretrim_filter(padding + papers, enable=True, cap=51)
    pmids_kept = {p.pmid for p in kept}
    # Of the three above, the new OA wins; old loses first.
    assert 3 in pmids_kept


def test_cap_does_not_fire_when_under_ceiling():
    """100 primary papers → cap is irrelevant."""
    papers = _bulk(100)
    _, audit = pretrim_filter(papers, enable=True, cap=HARD_CAP)
    assert audit.n_dropped_cap == 0


# -- Audit invariants ---------------------------------------------------------


def test_audit_has_one_decision_per_input_paper():
    papers = _bulk(60)
    papers.append(_paper(500, "Pan-Cancer analysis", journal="Cell"))
    _, audit = pretrim_filter(papers, enable=True)
    decision_pmids = {d.paper_pmid for d in audit.decisions}
    input_pmids = {p.pmid for p in papers}
    assert decision_pmids == input_pmids
    assert len(audit.decisions) == len(papers)


def test_audit_drop_counts_match_decisions():
    """Per-reason counts in the audit reconcile with the decisions list."""
    primary = _bulk(50)
    extras = [
        _paper(500, "A narrative review of X", is_review=True, journal="J X"),
        _paper(501, "Pan-Cancer analysis", journal="Cell Rep"),
        _paper(
            502,
            "Antibody-drug conjugates in cancer therapy: recent advances",
            journal="Pharmaceutics",
        ),
    ]
    _, audit = pretrim_filter(primary + extras, enable=True)
    n_review_decisions = sum(
        1 for d in audit.decisions if d.drop_reason == "review"
    )
    n_atlas_decisions = sum(
        1 for d in audit.decisions if d.drop_reason == "atlas"
    )
    n_drug_decisions = sum(
        1 for d in audit.decisions if d.drop_reason == "drug_review"
    )
    assert n_review_decisions == audit.n_dropped_review
    assert n_atlas_decisions == audit.n_dropped_atlas
    assert n_drug_decisions == audit.n_dropped_drug_review


def test_thresholds_match_published_defaults():
    """Sentinel: if a future refactor changes thresholds, this catches it.

    Cost projection depends on these — bumping them without re-running the
    cohort projection will silently break the $6,010 estimate.
    """
    assert THIN_THRESHOLD == 25
    assert HEAVY_THRESHOLD == 50
    assert HARD_CAP == 150
