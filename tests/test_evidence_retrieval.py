"""Tests for the ``evidence_retrieval`` tool.

Three groups of cases:

* **Snippet extractor**: per-category hallmark regex + section weighting
  on a fixture Paper with controlled section text.
* **HPA short-circuit**: no HTTP, reads from a fixture TSV; output
  body matches the orchestrator's body templater so substring
  validation works end-to-end.
* **Backfill-deeper**: when the gene-proximity filter empties the
  top-ranked papers, ``_pmc_retrieval`` keeps fetching deeper into the
  candidate pool — bounded by a fetch cap.

(The v0.5.1 ``SurfaceomeRecordDraft._check_wb_pairing`` validator was
retired in the v1.0.0 schema rewrite — the surface-evidence block now
models WB on whole-cell lysate via ``method_subclass=whole_cell_proteomics``
+ ``accessibility_relevance=expression_only`` rather than via a
draft-level cross-reference rule.)
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any, cast

import pytest

from accessible_surfaceome.tools._shared import retraction_watch as rw
from accessible_surfaceome.tools._shared.http import CachedHTTP

from accessible_surfaceome.tools import evidence_retrieval as er
from accessible_surfaceome.tools._shared.models import (
    IdentifierBundle,
    Paper,
    PaperSection,
)



# ---------------------------------------------------------------------------
# Snippet extractor — _extract_snippets on a fixture Paper
# ---------------------------------------------------------------------------


def _fixture_paper(*, sections: list[PaperSection]) -> Paper:
    return Paper(
        pmid=42,
        pmc_id="PMC42",
        title="A paper about surface biology",
        abstract="Surface staining was observed.",
        is_pmc_oa=True,
        retraction_checked_at=datetime.now(UTC),
        sections=sections,
    )


def test_ihc_extractor_prefers_figure_legend() -> None:
    paper = _fixture_paper(
        sections=[
            PaperSection(
                name="results",
                text=(
                    "Tumor cells were analyzed for ERBB2 expression. "
                    "We observed strong membranous staining of HER2 across all sections."
                ),
            ),
            PaperSection(
                name="figure_legends",
                text=(
                    "Figure 1. Representative immunohistochemistry showing "
                    "plasma membrane staining of HER2 on intact tumor cells, "
                    "scale bar 10 microns."
                ),
            ),
        ]
    )
    snippets = er._extract_snippets(
        paper=paper,
        spec=er._CATEGORY_SPECS["ihc"],
        max_snippets=3,
    )
    assert snippets, "expected at least one IHC snippet"
    top = snippets[0]
    assert top.section == "figure_legend"
    assert "membrane staining" in top.text.lower()
    # Every snippet must be a substring of one of the source sections,
    # otherwise the orchestrator's substring check would later reject it.
    full_text = "\n\n".join(s.text for s in paper.sections)
    for snippet in snippets:
        assert snippet.text in full_text


def test_mass_spec_extractor_picks_methods_phrase() -> None:
    paper = _fixture_paper(
        sections=[
            PaperSection(
                name="methods",
                text=(
                    "Cell-surface capture (CSC) was performed using "
                    "periodate-oxidized sialic acid biotinylation followed by "
                    "neutravidin enrichment and LC-MS/MS analysis."
                ),
            ),
            PaperSection(
                name="discussion",
                text="We discussed the surface proteome of these cells.",
            ),
        ]
    )
    snippets = er._extract_snippets(
        paper=paper,
        spec=er._CATEGORY_SPECS["mass_spec_surfaceome"],
        max_snippets=3,
    )
    assert snippets
    assert snippets[0].section == "methods"
    assert "lc-ms/ms" in snippets[0].text.lower() or "cell-surface capture" in snippets[0].text.lower()


def test_extractor_returns_empty_when_no_hallmark_match() -> None:
    paper = _fixture_paper(
        sections=[
            PaperSection(
                name="results",
                text="The cells were grown in serum-free media and harvested.",
            ),
        ]
    )
    snippets = er._extract_snippets(
        paper=paper,
        spec=er._CATEGORY_SPECS["flow_cytometry"],
        max_snippets=3,
    )
    assert snippets == []


def test_surface_expression_extractor_fires_on_context_tagged_sentences() -> None:
    # surface_expression must capture ASSAY-LESS, location-tagged surface
    # mentions that the method categories miss.
    paper = _fixture_paper(
        sections=[
            PaperSection(
                name="results",
                text=(
                    "CD19 is expressed on the surface of activated T cells. "
                    "In hepatocytes, cell surface levels of the receptor are "
                    "markedly elevated during regeneration."
                ),
            ),
        ]
    )
    snippets = er._extract_snippets(
        paper=paper,
        spec=er._CATEGORY_SPECS["surface_expression"],
        max_snippets=3,
    )
    assert snippets, "expected context-tagged surface-expression snippets"
    full_text = "\n\n".join(s.text for s in paper.sections)
    for snippet in snippets:
        assert snippet.text in full_text


def test_surface_expression_extractor_does_not_fire_on_bare_surface() -> None:
    # Precision guard: a bare "surface" mention with no context cue (no
    # tissue / cell-type / expression-level pairing) must NOT match.
    paper = _fixture_paper(
        sections=[
            PaperSection(
                name="results",
                text=(
                    "The protein has a smooth surface topology. "
                    "Cells were plated on a treated surface before imaging."
                ),
            ),
        ]
    )
    snippets = er._extract_snippets(
        paper=paper,
        spec=er._CATEGORY_SPECS["surface_expression"],
        max_snippets=3,
    )
    assert snippets == [], "bare 'surface' should not fire surface_expression"


def test_overexpression_extractor_fires_on_oe_surface_trafficking() -> None:
    # overexpression must capture OE-precedent surface trafficking regardless of
    # detection method.
    paper = _fixture_paper(
        sections=[
            PaperSection(
                name="results",
                text=(
                    "Ectopically expressed CLDN18 localized to the plasma "
                    "membrane of HEK293 cells. Surface expression of "
                    "transfected receptor was readily detectable."
                ),
            ),
        ]
    )
    snippets = er._extract_snippets(
        paper=paper,
        spec=er._CATEGORY_SPECS["overexpression"],
        max_snippets=3,
    )
    assert snippets, "expected OE-surface-trafficking snippets"
    full_text = "\n\n".join(s.text for s in paper.sections)
    for snippet in snippets:
        assert snippet.text in full_text


def test_overexpression_extractor_does_not_fire_without_surface_localization() -> None:
    # Precision guard: an OE term with no nearby surface/membrane-localization
    # phrase must NOT match (it's not surface-trafficking evidence).
    paper = _fixture_paper(
        sections=[
            PaperSection(
                name="results",
                text=(
                    "Cells overexpressing the construct showed increased "
                    "proliferation and elevated cytokine secretion."
                ),
            ),
        ]
    )
    snippets = er._extract_snippets(
        paper=paper,
        spec=er._CATEGORY_SPECS["overexpression"],
        max_snippets=3,
    )
    assert snippets == [], "OE without surface localization should not fire"


def test_target_mention_extractor_emits_for_high_throughput_categories() -> None:
    """For high-throughput categories, ``_extract_target_mentions`` emits a
    target-naming sentence even when it doesn't match a hallmark pattern.
    The agent uses these for paper-level gene attribution alongside the
    methodology snippet from the same paper.
    """
    paper = Paper(
        pmid=99,
        pmc_id="PMC99",
        title="surfaceome paper",
        is_pmc_oa=True,
        retraction_checked_at=datetime.now(UTC),
        sections=[
            PaperSection(
                name="results",
                text=(
                    "We identified 312 surface proteins by sulfo-NHS-SS-biotin "
                    "labeling. Among the top hits, CD81 ranked 47 in HEK293 "
                    "cells. CD81 expression was confirmed across all replicates."
                ),
            )
        ],
    )
    target = frozenset({"CD81"})
    mentions = er._extract_target_mentions(
        paper,
        spec=er._CATEGORY_SPECS["surface_biotinylation"],
        target_names=target,
    )
    assert mentions, "expected at least one target-mention snippet"
    assert all("CD81" in m.text for m in mentions)
    assert all(m.hallmark_phrase == er.TARGET_MENTION_HALLMARK for m in mentions)
    # Each mention must substring-match the source body for anchoring.
    full_text = "\n\n".join(s.text for s in paper.sections)
    for m in mentions:
        assert m.text in full_text


def test_target_mention_extractor_inert_for_strict_categories() -> None:
    """Strict-filter categories (e.g. flow_cytometry) keep the original
    hallmark + target-boost flow; ``_extract_target_mentions`` returns
    nothing for them so we don't double-emit target-named sentences that
    the hallmark path already covers.
    """
    paper = Paper(
        pmid=99,
        pmc_id="PMC99",
        title="paper",
        is_pmc_oa=True,
        retraction_checked_at=datetime.now(UTC),
        sections=[PaperSection(name="results", text="CD81 was detected on the surface.")],
    )
    mentions = er._extract_target_mentions(
        paper,
        spec=er._CATEGORY_SPECS["flow_cytometry"],
        target_names=frozenset({"CD81"}),
    )
    assert mentions == []


def test_adjacent_context_returns_window_when_neighbors_present() -> None:
    """Sentence with one before + one after yields a multi-sentence window."""
    section = (
        "Cells were biotinylated with sulfo-NHS-SS-biotin. "
        "Eluted material was analyzed by LC-MS/MS. "
        "CD81 was identified in the enriched fraction."
    )
    focal = "Eluted material was analyzed by LC-MS/MS."
    ctx = er._adjacent_context(section, focal)
    assert ctx is not None
    assert "Cells were biotinylated" in ctx
    assert "CD81 was identified" in ctx
    assert len(ctx) <= 500


def test_adjacent_context_returns_none_when_focal_stands_alone() -> None:
    """A section with a single sentence has no surrounding context to add."""
    section = "CD81 was detected on the surface."
    focal = "CD81 was detected on the surface."
    assert er._adjacent_context(section, focal) is None


def test_extractor_populates_context_excerpt() -> None:
    """Snippets emitted by ``_extract_snippets`` carry a ``context_excerpt``
    when the focal sentence has adjacent neighbors in the same section.
    """
    paper = _fixture_paper(
        sections=[
            PaperSection(
                name="methods",
                text=(
                    "Cells were lysed in RIPA buffer. "
                    "Cell-surface capture (CSC) was performed using "
                    "periodate-oxidized sialic acid biotinylation followed by "
                    "neutravidin enrichment and LC-MS/MS analysis. "
                    "Captured proteins were trypsinized for downstream analysis."
                ),
            ),
        ],
    )
    snippets = er._extract_snippets(
        paper=paper,
        spec=er._CATEGORY_SPECS["mass_spec_surfaceome"],
        max_snippets=3,
    )
    assert snippets
    ctx = snippets[0].context_excerpt
    assert ctx is not None
    assert len(ctx) <= 500
    # Context should mention the surrounding sentences, not just the focal one.
    assert ("Cells were lysed" in ctx) or ("Captured proteins" in ctx)


def test_pmc_retrieval_emits_evidence_claim_drafts(monkeypatch: pytest.MonkeyPatch) -> None:
    """``_pmc_retrieval`` packages every emitted snippet as an
    ``EvidenceClaimDraft`` with the snippet's quote/source_id/section
    locked together for downstream copy-paste-free claim authoring.
    """
    from accessible_surfaceome.tools._shared.models import CandidateSnippet

    snippet = CandidateSnippet(
        source_id="PMC:PMC42",
        section="methods",
        figure_or_table_id=None,
        text="Cell-surface capture (CSC) was performed using LC-MS/MS analysis.",
        score=4.0,
        hallmark_phrase="LC-MS/MS",
        context_excerpt="A longer surrounding context goes here.",
    )
    draft = er._snippet_to_draft(snippet, seq=3)
    assert draft.quote == snippet.text
    assert draft.source_id == snippet.source_id
    assert draft.section == snippet.section
    assert draft.figure_or_table_id == snippet.figure_or_table_id
    assert draft.context_excerpt == snippet.context_excerpt
    assert draft.hallmark_phrase == snippet.hallmark_phrase
    assert draft.score == snippet.score
    assert draft.suggested_evidence_id == "draft_PMC42_methods_03"


def test_target_mention_extractor_dedups_within_paper() -> None:
    """Repeated identical target-naming sentences in one paper collapse
    to a single emitted snippet — the dedup key matches what
    ``_extract_snippets`` uses, so cross-pollination between hallmark
    and target-mention snippets stays consistent.
    """
    paper = Paper(
        pmid=99,
        pmc_id="PMC99",
        title="paper",
        is_pmc_oa=True,
        retraction_checked_at=datetime.now(UTC),
        sections=[
            PaperSection(
                name="results",
                text=(
                    "CD81 was among the identified surface proteins. "
                    "CD81 was among the identified surface proteins."
                ),
            )
        ],
    )
    mentions = er._extract_target_mentions(
        paper,
        spec=er._CATEGORY_SPECS["mass_spec_surfaceome"],
        target_names=frozenset({"CD81"}),
    )
    assert len(mentions) == 1


def test_extractor_caps_to_quote_max() -> None:
    # Build a single sentence >600 chars so the trim path fires.
    long_sentence = (
        "The protein was detected on the surface of non-permeabilized intact cells "
        "by flow cytometry using a directly conjugated antibody against the "
        "extracellular domain, with consistent staining intensity across all "
        "biological replicates and across two independent donor preparations of "
        "primary cells obtained under standard sterile conditions in our facility, "
        "and the same panel was independently validated by an orthogonal "
        "immunofluorescence readout on intact cells from three additional donors "
        "with concordant single-cell distributions and no detectable shift in the "
        "negative-control population across all assay conditions and matched isotype "
        "controls in every replicate of the experiment from start to finish."
    )
    assert len(long_sentence) > er._QUOTE_MAX_CHARS
    paper = _fixture_paper(
        sections=[PaperSection(name="results", text=long_sentence)]
    )
    snippets = er._extract_snippets(
        paper=paper,
        spec=er._CATEGORY_SPECS["flow_cytometry"],
        max_snippets=3,
    )
    assert snippets
    for snippet in snippets:
        assert len(snippet.text) <= er._QUOTE_MAX_CHARS


def test_trim_snaps_to_clause_boundary_when_overlong() -> None:
    # Build a sentence with multiple clause boundaries (commas / semicolons)
    # that's >600 chars; verify the trimmed snippet doesn't start or end
    # mid-clause when it sits inside the sentence.
    long_sentence = (
        "First we describe a methodological observation about cell preparation; "
        "subsequently we performed surface biotinylation with sulfo-NHS-SS-biotin "
        "on intact non-permeabilized cells, captured biotinylated proteins on "
        "streptavidin-agarose, eluted in reducing buffer for LC-MS/MS analysis on "
        "an Orbitrap mass spectrometer with high-resolution scans, identified peptides "
        "with FragPipe at 1% FDR, and confirmed surface accessibility of the receptor "
        "in three independent biological replicates; further analyses summarized in "
        "later sections of this paper covered downstream targets and additional cell "
        "lines under separate experimental conditions across the full panel."
    )
    assert len(long_sentence) > er._QUOTE_MAX_CHARS
    paper = _fixture_paper(
        sections=[PaperSection(name="results", text=long_sentence)]
    )
    snippets = er._extract_snippets(
        paper=paper,
        spec=er._CATEGORY_SPECS["surface_biotinylation"],
        max_snippets=3,
    )
    assert snippets
    snip = snippets[0].text
    assert len(snip) <= er._QUOTE_MAX_CHARS
    # If the snippet starts inside the sentence (not at index 0), the first
    # character should be the beginning of a new clause — i.e. it should
    # start with a capital letter (sentence-end snap) or a "natural" word
    # following a clause boundary. We assert it does NOT start with a
    # lowercase letter that would indicate a mid-clause cut.
    if not long_sentence.startswith(snip):
        assert snip[0].isupper() or snip[0].isdigit() or snip[0] in "([\"'", (
            f"snippet starts mid-clause: {snip[:80]!r}"
        )
    # Similarly the snippet should end with a terminal-style character
    # (sentence punctuation or right after a clause boundary), not in the
    # middle of a word.
    if not long_sentence.endswith(snip):
        # Allow either terminal punctuation OR a clean word boundary
        # (the snap_right path may drop trailing punctuation).
        assert snip[-1] in ".!?\"')" or snip.endswith("  ") is False, (
            f"snippet ends mid-clause: ...{snip[-80:]!r}"
        )


# ---------------------------------------------------------------------------
# Backfill-deeper-when-filtered
# ---------------------------------------------------------------------------


def _candidate_paper(pmid: int, pmcid: str) -> Paper:
    """A discovery-pool paper: PMC-OA, no sections yet (pre-fetch)."""
    return Paper(
        pmid=pmid,
        pmc_id=pmcid,
        title=f"candidate {pmid}",
        is_pmc_oa=True,
        retraction_checked_at=datetime.now(UTC),
    )


def _fulltext_paper(pmcid: str, section_text: str) -> Paper:
    """A post-fetch paper with one figure-legends section."""
    pmid = int(pmcid.removeprefix("PMC"))
    return Paper(
        pmid=pmid,
        pmc_id=pmcid,
        title=f"fulltext {pmid}",
        is_pmc_oa=True,
        retraction_checked_at=datetime.now(UTC),
        sections=[PaperSection(name="figure_legends", text=section_text)],
    )


def _patch_pmc_retrieval(
    monkeypatch: pytest.MonkeyPatch,
    *,
    pool: list[Paper],
    bodies: dict[str, str],
    target_symbol: str = "GPRC5D",
    gazetteer: frozenset[str] = frozenset({"GPRC5D", "BCMA"}),
) -> list[str]:
    """Wire up _pmc_retrieval's collaborators with fakes; return a list
    that records every pmcid fetch_fulltext is called with."""
    bundle = IdentifierBundle(
        uniprot_acc="Q9NZD1", hgnc_id="HGNC:1", hgnc_symbol=target_symbol
    )
    monkeypatch.setattr(er, "_resolve", lambda acc, *, http: bundle)
    monkeypatch.setattr(er, "load_gazetteer", lambda: gazetteer)
    monkeypatch.setattr(er, "_pubtator_discovery", lambda **kw: [])
    monkeypatch.setattr(er, "_europepmc_discovery", lambda **kw: list(pool))

    fetch_calls: list[str] = []

    def _fake_fetch(*, http: Any, pmcid: str, retraction_index: Any) -> Paper:
        fetch_calls.append(pmcid)
        return _fulltext_paper(pmcid, bodies[pmcid])

    monkeypatch.setattr(er, "fetch_fulltext", _fake_fetch)
    return fetch_calls


def _patch_discovery_policy(
    monkeypatch: pytest.MonkeyPatch,
    *,
    epmc_pool: list[Paper],
    pubtator_pool: list[Paper],
    target_symbol: str = "GPRC5D",
) -> dict[str, int]:
    bundle = IdentifierBundle(
        uniprot_acc="Q9NZD1", hgnc_id="HGNC:1", hgnc_symbol=target_symbol
    )
    calls = {"epmc": 0, "pubtator": 0}
    monkeypatch.setattr(er, "_resolve", lambda acc, *, http: bundle)
    monkeypatch.setattr(er, "load_gazetteer", lambda: frozenset({target_symbol}))

    def _fake_epmc(**_kwargs: Any) -> list[Paper]:
        calls["epmc"] += 1
        return list(epmc_pool)

    def _fake_pubtator(**_kwargs: Any) -> list[Paper]:
        calls["pubtator"] += 1
        return list(pubtator_pool)

    monkeypatch.setattr(er, "_europepmc_discovery", _fake_epmc)
    monkeypatch.setattr(er, "_pubtator_discovery", _fake_pubtator)
    return calls


_COMPETING = "BCMA surface expression was confirmed by flow cytometry on intact cells."
_ON_SUBJECT = "GPRC5D surface expression was confirmed by flow cytometry on intact cells."


def test_high_specificity_category_skips_pubtator_when_epmc_has_oa_candidates(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls = _patch_discovery_policy(
        monkeypatch,
        epmc_pool=[
            _candidate_paper(1, "PMC1"),
            _candidate_paper(2, "PMC2"),
        ],
        pubtator_pool=[_candidate_paper(3, "PMC3")],
    )

    pack = er.evidence_retrieval(
        uniprot_acc="Q9NZD1",
        category="mass_spec_surfaceome",
        max_papers=2,
        http=cast(CachedHTTP, object()),
        retraction_index=rw.empty(),
        discover_only=True,
    )

    assert calls == {"epmc": 1, "pubtator": 0}
    assert [p.pmc_id for p in pack.papers] == ["PMC1", "PMC2"]


def test_high_specificity_category_falls_back_to_pubtator_when_epmc_is_thin(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls = _patch_discovery_policy(
        monkeypatch,
        epmc_pool=[_candidate_paper(1, "PMC1")],
        pubtator_pool=[_candidate_paper(2, "PMC2")],
    )

    pack = er.evidence_retrieval(
        uniprot_acc="Q9NZD1",
        category="surface_biotinylation",
        max_papers=2,
        http=cast(CachedHTTP, object()),
        retraction_index=rw.empty(),
        discover_only=True,
    )

    assert calls == {"epmc": 1, "pubtator": 1}
    assert [p.pmc_id for p in pack.papers] == ["PMC1", "PMC2"]


def test_noisy_category_keeps_pubtator_first_even_when_epmc_has_candidates(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls = _patch_discovery_policy(
        monkeypatch,
        epmc_pool=[
            _candidate_paper(1, "PMC1"),
            _candidate_paper(2, "PMC2"),
        ],
        pubtator_pool=[_candidate_paper(3, "PMC3")],
    )

    pack = er.evidence_retrieval(
        uniprot_acc="Q9NZD1",
        category="flow_cytometry",
        max_papers=2,
        http=cast(CachedHTTP, object()),
        retraction_index=rw.empty(),
        discover_only=True,
    )

    assert calls == {"epmc": 1, "pubtator": 1}
    assert [p.pmc_id for p in pack.papers] == ["PMC3", "PMC1", "PMC2"]


def test_europepmc_discovery_falls_back_to_ncbi_search(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    bundle = IdentifierBundle(
        uniprot_acc="Q9NZD1",
        hgnc_id="HGNC:1",
        hgnc_symbol="GPRC5D",
        aliases=["alias-a"],
    )
    fallback = [_candidate_paper(9, "PMC9")]
    seen: dict[str, object] = {}

    def _boom(**_kwargs: Any) -> object:
        raise RuntimeError("simulated Europe PMC outage")

    def _fake_ncbi(**kwargs: Any) -> list[Paper]:
        seen.update(kwargs)
        return fallback

    monkeypatch.setattr(er, "europepmc_search", _boom)
    monkeypatch.setattr(er, "ncbi_pubmed_search", _fake_ncbi)

    got = er._europepmc_discovery(
        bundle=bundle,
        spec=er._CATEGORY_SPECS["surface_biotinylation"],
        max_papers=2,
        http=cast(CachedHTTP, object()),
        retraction_index=rw.empty(),
    )

    assert got == fallback
    assert seen["page_size"] == 6
    assert '("GPRC5D" OR "alias-a")' in cast(str, seen["query"])
    assert "surface biotinylation" in cast(str, seen["query"])


def test_backfill_reaches_deeper_paper_when_top_filtered(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Papers 1-3 only have competing-gene (BCMA) sentences; paper 4 has
    the on-subject GPRC5D sentence. With max_papers=1 the loop must
    backfill past the three filtered papers to reach paper 4."""
    pool = [_candidate_paper(i, f"PMC{i}") for i in range(1, 5)]
    bodies = {
        "PMC1": _COMPETING,
        "PMC2": _COMPETING,
        "PMC3": _COMPETING,
        "PMC4": _ON_SUBJECT,
    }
    fetch_calls = _patch_pmc_retrieval(monkeypatch, pool=pool, bodies=bodies)

    pack = er.evidence_retrieval(
        uniprot_acc="Q9NZD1",
        category="flow_cytometry",
        max_papers=1,
        max_snippets_per_paper=3,
        http=cast(CachedHTTP, object()),
        retraction_index=rw.empty(),
    )

    # All four papers were fetched — the loop didn't stop at the filtered top.
    assert fetch_calls == ["PMC1", "PMC2", "PMC3", "PMC4"]
    # Only the on-subject paper is returned, and only its snippets.
    assert pack.n_papers_with_snippets == 1
    assert [p.pmc_id for p in pack.papers] == ["PMC4"]
    assert pack.snippets
    assert all("GPRC5D" in s.text for s in pack.snippets)
    assert pack.empty_reason is None


def test_backfill_respects_fetch_cap(monkeypatch: pytest.MonkeyPatch) -> None:
    """When every candidate is competing-gene-only, the loop stops at the
    fetch cap rather than walking the whole pool, and reports an honest
    empty result. With max_papers=2 the cap is the floor (8), not the
    multiplier product (6)."""
    pool = [_candidate_paper(i, f"PMC{i}") for i in range(1, 13)]  # 12 papers
    bodies = {f"PMC{i}": _COMPETING for i in range(1, 13)}
    fetch_calls = _patch_pmc_retrieval(monkeypatch, pool=pool, bodies=bodies)

    pack = er.evidence_retrieval(
        uniprot_acc="Q9NZD1",
        category="flow_cytometry",
        max_papers=2,
        max_snippets_per_paper=3,
        http=cast(CachedHTTP, object()),
        retraction_index=rw.empty(),
    )

    # cap = max(2 * _BACKFILL_FETCH_MULTIPLIER, _BACKFILL_MIN_FETCHES) = 8.
    cap = max(2 * er._BACKFILL_FETCH_MULTIPLIER, er._BACKFILL_MIN_FETCHES)
    assert cap == 8
    assert len(fetch_calls) == cap
    assert pack.snippets == []
    assert pack.n_papers_with_snippets == 0
    assert pack.papers == []
    assert pack.empty_reason is not None
    assert f"fetched {cap} of 12" in pack.empty_reason


def test_backfill_happy_path_does_not_overfetch(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """When the top papers all yield, the loop stops at max_papers — it
    does not keep fetching just because the pool is deeper."""
    pool = [_candidate_paper(i, f"PMC{i}") for i in range(1, 9)]  # 8 papers
    bodies = {f"PMC{i}": _ON_SUBJECT for i in range(1, 9)}
    fetch_calls = _patch_pmc_retrieval(monkeypatch, pool=pool, bodies=bodies)

    pack = er.evidence_retrieval(
        uniprot_acc="Q9NZD1",
        category="flow_cytometry",
        max_papers=3,
        max_snippets_per_paper=3,
        http=cast(CachedHTTP, object()),
        retraction_index=rw.empty(),
    )

    # Stopped at 3 yielding papers; did not fetch papers 4-8.
    assert fetch_calls == ["PMC1", "PMC2", "PMC3"]
    assert pack.n_papers_with_snippets == 3
    assert len(pack.papers) == 3
