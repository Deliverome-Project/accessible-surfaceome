"""Tests for the ``evidence_retrieval`` tool + WB pairing validator.

Three groups of cases:

* **WB pairing validator** on :class:`SurfaceomeRecordDraft`: a record
  emitting a `western_blot` + `surface_expression` EvidenceClaim must
  co-cite a `surface_biotinylation` or `mass_spec_surfaceome` claim
  sharing the same `source_id` — otherwise Pydantic rejects.
* **Snippet extractor**: per-category hallmark regex + section weighting
  on a fixture Paper with controlled section text.
* **HPA short-circuit**: no HTTP, reads from a fixture TSV; output
  body matches the orchestrator's body templater so substring
  validation works end-to-end.
"""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from typing import Any, cast

import pytest
from pydantic import ValidationError

from accessible_surfaceome.tools._shared.http import CachedHTTP

from accessible_surfaceome.tools import evidence_retrieval as er
from accessible_surfaceome.tools._shared.models import (
    Paper,
    PaperSection,
    SurfaceomeRecordDraft,
)


# ---------------------------------------------------------------------------
# Helpers — minimal valid SurfaceomeRecordDraft scaffolding
# ---------------------------------------------------------------------------


def _draft_payload(evidence_claims: list[dict[str, Any]]) -> dict[str, Any]:
    """Minimal payload that satisfies SurfaceomeRecordDraft + buckets."""
    return {
        "schema_version": "v0.5.1",
        "gene": {
            "hgnc_symbol": "TEST1",
            "hgnc_id": "HGNC:1",
            "uniprot_acc": "P00001",
        },
        "canonical_isoform": "P00001-1",
        "isoform_flattened": False,
        "in_candidate_universe": True,
        "targetability": {
            "tier": "novel_candidate",
            "tldr": "test",
            "cited_evidence_ids": [],
        },
        "surface_biology": {
            "surface_status": "moderate_surface",
            "topology": "transmembrane_single_pass",
            "anchor_type": "transmembrane_single",
            "exposure_class": "exposed_ecd",
            "extracellular_domain": {
                "accessibility": "unknown",
            },
            "surface_localization_assays": [
                {
                    "assay_type": "flow_cytometry",
                    "species": "human",
                    "cell_type_or_line": "test cell",
                    "direction": "supports_surface",
                    "strength": "moderate",
                    "cited_evidence_ids": ["evi_dummy"],
                    "antibody": {},
                }
            ],
            "db_comparison": {"n_sources_voting_surface": 0},
            "cited_evidence_ids": ["evi_dummy"],
        },
        "isoform_accessibility": [],
        "coreceptor_requirements": [],
        "orthology": [],
        "paralogs": [],
        "evidence_claims": evidence_claims,
        "contradictions": [],
        "confidence": "medium",
        "confidence_reasoning": "test",
        "contradiction_flag": False,
        "rationale": "test",
        "model_path": "sonnet_only",
        "triage_signal": "likely_accessible",
    }


def _claim(
    *,
    evidence_id: str,
    evidence_type: str,
    claim_type: str = "surface_expression",
    source_id: str = "PMID:1",
    quote: str = "the protein localizes to the plasma membrane",
) -> dict[str, Any]:
    return {
        "evidence_id": evidence_id,
        "claim": "test claim",
        "claim_type": claim_type,
        "direction": "supports",
        "evidence_type": evidence_type,
        "evidence_tier": "primary",
        "confidence": "moderate",
        "assay_context": {
            "species": "human",
            "cell_type_or_line": "HEK293",
            "fixation": "live",
        },
        "source_id": source_id,
        "quote": quote,
        "section": "results",
    }


# ---------------------------------------------------------------------------
# WB pairing validator
# ---------------------------------------------------------------------------


def test_wb_surface_claim_without_pair_rejects() -> None:
    """A western_blot + surface_expression claim alone fails validation."""
    payload = _draft_payload(
        evidence_claims=[
            _claim(
                evidence_id="evi_dummy",
                evidence_type="flow_cytometry",
                source_id="PMID:1",
            ),
            _claim(
                evidence_id="evi_wb",
                evidence_type="western_blot",
                source_id="PMID:2",
            ),
        ]
    )
    with pytest.raises(ValidationError) as exc_info:
        SurfaceomeRecordDraft.model_validate(payload)
    errors = exc_info.value.errors()
    assert any(
        "western_blot evidence for surface_expression requires a paired" in str(e["msg"])
        for e in errors
    )


def test_wb_paired_with_biotinylation_same_source_validates() -> None:
    """WB + biotinylation on the same source_id — pairing satisfied."""
    payload = _draft_payload(
        evidence_claims=[
            _claim(
                evidence_id="evi_dummy",
                evidence_type="flow_cytometry",
                source_id="PMID:1",
            ),
            _claim(
                evidence_id="evi_biot",
                evidence_type="surface_biotinylation",
                source_id="PMID:42",
            ),
            _claim(
                evidence_id="evi_wb",
                evidence_type="western_blot",
                source_id="PMID:42",
            ),
        ]
    )
    draft = SurfaceomeRecordDraft.model_validate(payload)
    assert any(c.evidence_type == "western_blot" for c in draft.evidence_claims)


def test_wb_paired_with_ms_same_source_validates() -> None:
    """WB + MS on the same source_id — pairing satisfied via the MS route."""
    payload = _draft_payload(
        evidence_claims=[
            _claim(
                evidence_id="evi_dummy",
                evidence_type="flow_cytometry",
                source_id="PMID:1",
            ),
            _claim(
                evidence_id="evi_ms",
                evidence_type="mass_spec_surfaceome",
                source_id="PMC:PMC42",
            ),
            _claim(
                evidence_id="evi_wb",
                evidence_type="western_blot",
                source_id="PMC:PMC42",
            ),
        ]
    )
    draft = SurfaceomeRecordDraft.model_validate(payload)
    assert sum(c.evidence_type == "western_blot" for c in draft.evidence_claims) == 1


def test_wb_pair_must_share_source_id() -> None:
    """A biotinylation claim on a *different* source doesn't pair."""
    payload = _draft_payload(
        evidence_claims=[
            _claim(
                evidence_id="evi_dummy",
                evidence_type="flow_cytometry",
                source_id="PMID:1",
            ),
            _claim(
                evidence_id="evi_biot",
                evidence_type="surface_biotinylation",
                source_id="PMID:42",
            ),
            _claim(
                evidence_id="evi_wb",
                evidence_type="western_blot",
                source_id="PMID:99",  # different paper
            ),
        ]
    )
    with pytest.raises(ValidationError):
        SurfaceomeRecordDraft.model_validate(payload)


def test_wb_topology_claim_does_not_require_pair() -> None:
    """The pairing rule fires only for claim_type=surface_expression. A
    WB claim about something else (e.g. topology) doesn't need a pair."""
    payload = _draft_payload(
        evidence_claims=[
            _claim(
                evidence_id="evi_dummy",
                evidence_type="flow_cytometry",
                source_id="PMID:1",
            ),
            _claim(
                evidence_id="evi_wb_topo",
                evidence_type="western_blot",
                claim_type="topology",
                source_id="PMID:99",
            ),
        ]
    )
    SurfaceomeRecordDraft.model_validate(payload)  # no raise


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
