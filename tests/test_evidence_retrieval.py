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
from pathlib import Path
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


def test_extractor_caps_to_200_chars() -> None:
    long_sentence = (
        "The protein was detected on the surface of non-permeabilized intact cells "
        "by flow cytometry using a directly conjugated antibody against the "
        "extracellular domain, with consistent staining intensity across all "
        "biological replicates and across two independent donor preparations of "
        "primary cells obtained under standard sterile conditions in our facility."
    )
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
        assert len(snippet.text) <= 200


# ---------------------------------------------------------------------------
# HPA short-circuit
# ---------------------------------------------------------------------------


def _hpa_fixture_row(tmp_path: Path, symbol: str = "ERBB2") -> Path:
    """Write a minimal HPA snapshot TSV with one matching row."""
    snapshot = tmp_path / "hpa_human_snapshot.tsv"
    header = "\t".join([
        "uniprot_accession", "ensembl_gene_id", "hpa_gene_symbol",
        "hpa_reliability", "hpa_surface_flag", "hpa_pm_accessible",
        "hpa_junctional", "hpa_pm_in_enhanced", "hpa_pm_in_supported",
        "hpa_pm_in_approved", "hpa_pm_in_uncertain", "hpa_locations",
    ])
    row = "\t".join([
        "P04626", "ENSG00000141736", symbol,
        "Enhanced", "1", "1",
        "0", "1", "0",
        "0", "0", "Plasma membrane;Vesicles",
    ])
    snapshot.write_text(f"{header}\n{row}\n")
    return snapshot


def test_hpa_ihc_reads_snapshot_no_http(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Pipe DATA_DIR at /processed/hpa to a tmp fixture; assert no HTTP."""
    hpa_dir = tmp_path / "processed" / "hpa"
    hpa_dir.mkdir(parents=True)
    _hpa_fixture_row(hpa_dir, symbol="ERBB2")
    # Move the snapshot to the canonical filename location.
    (hpa_dir / "hpa_human_snapshot.tsv").rename(hpa_dir / "hpa_human_snapshot.tsv")

    # Patch DATA_DIR so _hpa_ihc reads our fixture.
    monkeypatch.setattr("accessible_surfaceome.paths.DATA_DIR", tmp_path)

    class _NoHTTP:
        def __getattr__(self, name: str) -> Any:
            raise AssertionError(
                f"hpa_ihc should not touch HTTP; called {name!r}"
            )

    # _hpa_ihc calls gene_lookup.resolve which uses http. We stub resolve
    # to skip the HTTP path entirely.
    from accessible_surfaceome.tools._shared.models import IdentifierBundle

    def _fake_resolve(_acc: str, *, http: Any) -> IdentifierBundle:
        return IdentifierBundle(
            uniprot_acc="P04626",
            hgnc_id="HGNC:3430",
            hgnc_symbol="ERBB2",
            approved_name="erb-b2 receptor tyrosine kinase 2",
            aliases=["HER2"],
            ncbi_gene_id=2064,
            ensembl_gene="ENSG00000141736",
        )

    monkeypatch.setattr(er, "_resolve", _fake_resolve)

    pack = er.evidence_retrieval(
        uniprot_acc="P04626",
        category="hpa_ihc",
        http=cast(CachedHTTP, _NoHTTP()),
    )
    assert pack.category == "hpa_ihc"
    assert pack.snippets, f"expected HPA snippets; got empty pack: {pack!r}"
    # Every snippet's text must be a line of the synthetic body so the
    # orchestrator's substring check passes against the registered body.
    assert pack.synthetic_sources
    body = pack.synthetic_sources[0].raw_text
    for snippet in pack.snippets:
        assert snippet.text in body
    # Source ID convention.
    for snippet in pack.snippets:
        assert snippet.source_id == "HPA:ERBB2"


def test_hpa_body_template_is_deterministic() -> None:
    """format_hpa_body must produce the same bytes for the same row —
    the orchestrator depends on this to register a body the snippet
    substring check can find."""
    row = {
        "hpa_gene_symbol": "ERBB2",
        "hpa_reliability": "Enhanced",
        "hpa_locations": "Plasma membrane",
        "hpa_pm_accessible": "1",
        "hpa_pm_in_enhanced": "1",
    }
    body_a = er.format_hpa_body(row)
    body_b = er.format_hpa_body(dict(row))
    assert body_a == body_b
    assert "HPA reliability for IHC: Enhanced" in body_a
    assert "Plasma membrane" in body_a


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


_COMPETING = "BCMA surface expression was confirmed by flow cytometry on intact cells."
_ON_SUBJECT = "GPRC5D surface expression was confirmed by flow cytometry on intact cells."


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
