"""Tests for the evidence-promotion pipeline.

Covers normalization, substring matching, ``EvidenceClaim`` → ``Evidence``
promotion (happy + failure paths), and ``search_log`` construction from
synthetic ``events.jsonl``. The end-to-end test exercises ``_persist_annotation``
on a fully-synthesized draft to assert the canonical ``SurfaceomeRecord``
ships with the expected verified-evidence chain.
"""

from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime
from pathlib import Path

import pytest

from accessible_surfaceome.agents.surface_annotator.evidence_promotion import (
    build_search_log,
    promote_claim,
)
from accessible_surfaceome.agents.surface_annotator.orchestrator import _persist_annotation
from accessible_surfaceome.tools._shared.models import (
    AssayContext,
    EvidenceClaim,
    SourceType,
    SurfaceomeRecord,
)
from accessible_surfaceome.tools._shared.normalize import (
    find_quote_in_normalized,
    normalize_for_quote_matching,
)
from accessible_surfaceome.tools._shared.source_text import SourceText, SourceTextStore


# ---------------------------------------------------------------------------
# Normalization
# ---------------------------------------------------------------------------


def test_normalize_idempotent() -> None:
    text = "  α-helix  &amp;  GPI-anchor    ε-toxin "
    once = normalize_for_quote_matching(text)
    twice = normalize_for_quote_matching(once)
    assert once == twice
    assert "&" in once  # entity decoded
    assert once == once.lower()  # lowercased
    assert "  " not in once  # collapsed


def test_normalize_greek_glyphs_to_ascii() -> None:
    glyph = normalize_for_quote_matching("α-helix β-sheet")
    ascii_form = normalize_for_quote_matching("alpha-helix beta-sheet")
    assert glyph == ascii_form == "alpha-helix beta-sheet"


def test_normalize_ascii_greek_unchanged() -> None:
    # ASCII spellings like "alpha" already in the canonical form pass through.
    assert normalize_for_quote_matching("ALPHA") == "alpha"
    # And "alphabet" is *not* clobbered into "αbet".
    assert "alphabet" in normalize_for_quote_matching("Alphabet soup")


def test_normalize_html_entity_decode() -> None:
    out = normalize_for_quote_matching("CD25&nbsp;positive &amp; CD8&#x2014;negative")
    assert "&amp;" not in out
    assert "&nbsp;" not in out
    assert "&" in out  # decoded ampersand survives


def test_normalize_whitespace_collapse() -> None:
    out = normalize_for_quote_matching("hello\n\n  world\t\there")
    assert out == "hello world here"


def test_normalize_nfkc() -> None:
    # Full-width digits → ASCII digits via NFKC.
    out = normalize_for_quote_matching("CD１９ marker")
    assert "cd19" in out


def test_normalize_lowercase() -> None:
    assert normalize_for_quote_matching("PD-L1 KRAS") == "pd-l1 kras"


# ---------------------------------------------------------------------------
# Substring search
# ---------------------------------------------------------------------------


def test_find_quote_exact_match() -> None:
    src = "the quick brown fox jumps over the lazy dog"
    assert find_quote_in_normalized("brown fox", src) == 10


def test_find_quote_through_normalization() -> None:
    src = normalize_for_quote_matching("Surface biotinylation showed   α-tubulin   on the membrane.")
    quote = normalize_for_quote_matching("alpha-tubulin on the membrane")
    assert find_quote_in_normalized(quote, src) is not None


def test_find_quote_html_entities() -> None:
    src = normalize_for_quote_matching("CD25&nbsp;positive cells were enriched")
    quote = normalize_for_quote_matching("CD25 positive cells")
    assert find_quote_in_normalized(quote, src) is not None


def test_find_quote_no_match() -> None:
    src = normalize_for_quote_matching("KAAG1 was detected on proximal tubule cells")
    quote = normalize_for_quote_matching("CD20 was detected in B cells")
    assert find_quote_in_normalized(quote, src) is None


def test_find_quote_empty() -> None:
    assert find_quote_in_normalized("", "anything") is None


# ---------------------------------------------------------------------------
# Promote claim
# ---------------------------------------------------------------------------


def _make_source(
    *,
    source_id: str = "PMID:10601354",
    raw_text: str = "Short-term cultures of proximal tubule cells expressed KAAG1.",
    title: str = "Brandle et al.",
    source_type: SourceType = "pubmed",
    url: str = "https://pubmed.ncbi.nlm.nih.gov/10601354/",
) -> SourceText:
    normalized = normalize_for_quote_matching(raw_text)
    return SourceText(
        source_id=source_id,
        source_type=source_type,
        url=url,
        title=title,
        raw_text=raw_text,
        normalized_text=normalized,
        content_sha256=hashlib.sha256(raw_text.encode("utf-8")).hexdigest(),
        normalized_source_sha256=hashlib.sha256(normalized.encode("utf-8")).hexdigest(),
        retrieved_at=datetime.now(UTC),
        publication_type="primary_research",
        is_retracted=False,
        retraction_checked_at=datetime.now(UTC),
    )


def _make_claim(
    *,
    quote: str = "proximal tubule cells",
    source_id: str = "PMID:10601354",
    evidence_id: str = "evi_001",
) -> EvidenceClaim:
    return EvidenceClaim(
        evidence_id=evidence_id,
        claim="KAAG1 is expressed on proximal tubule cells",
        claim_type="surface_expression",
        direction="supports",
        evidence_type="immunohistochemistry",
        evidence_tier="primary",
        confidence="strong",
        assay_context=AssayContext(species="human"),
        source_id=source_id,
        quote=quote,
        section="results",
    )


def test_promote_claim_happy_path() -> None:
    store = SourceTextStore()
    store.put(_make_source())
    evi = promote_claim(_make_claim(), store=store)
    assert evi.entailment_verified is True
    assert evi.validation_warnings == []
    assert len(evi.spans) == 1
    span = evi.spans[0]
    assert span.quote == "proximal tubule cells"
    assert span.char_offset >= 0
    assert span.source.source_id == "PMID:10601354"
    assert span.quote_sha256 == hashlib.sha256(b"proximal tubule cells").hexdigest()


def test_promote_claim_missing_source() -> None:
    store = SourceTextStore()  # empty
    evi = promote_claim(_make_claim(), store=store)
    assert evi.entailment_verified is False
    assert evi.spans == []
    assert any("not in session source store" in w for w in evi.validation_warnings)


def test_promote_claim_quote_not_in_source() -> None:
    store = SourceTextStore()
    store.put(_make_source())
    evi = promote_claim(_make_claim(quote="distal convoluted tubule"), store=store)
    assert evi.entailment_verified is False
    assert evi.spans == []
    assert any("substring not found" in w for w in evi.validation_warnings)


def test_promote_claim_greek_normalization() -> None:
    # Source uses ASCII "alpha"; agent's quote uses the glyph. They match
    # after normalization.
    store = SourceTextStore()
    store.put(_make_source(raw_text="The alpha-helix transmembrane domain is exposed."))
    evi = promote_claim(_make_claim(quote="α-helix transmembrane domain"), store=store)
    assert evi.entailment_verified is True


# ---------------------------------------------------------------------------
# search_log construction
# ---------------------------------------------------------------------------


def _write_events(path: Path, events: list[dict]) -> None:
    with path.open("w") as fh:
        for ev in events:
            fh.write(json.dumps(ev) + "\n")


def test_build_search_log_pairs_use_with_result(tmp_path: Path) -> None:
    events_path = tmp_path / "events.jsonl"
    _write_events(
        events_path,
        [
            {
                "type": "agent.custom_tool_use",
                "id": "tu_1",
                "name": "gene_lookup",
                "input": {"mode": "resolve", "symbol_or_acc": "KAAG1"},
            },
            {
                "type": "user.custom_tool_result",
                "custom_tool_use_id": "tu_1",
                "content": [{"type": "text", "text": json.dumps({"uniprot_acc": "Q9UBP8"})}],
            },
            {
                "type": "agent.custom_tool_use",
                "id": "tu_2",
                "name": "gene_literature",
                "input": {"mode": "gene2pubmed", "uniprot_acc": "Q9UBP8"},
            },
            {
                "type": "user.custom_tool_result",
                "custom_tool_use_id": "tu_2",
                "content": [
                    {
                        "type": "text",
                        "text": json.dumps(
                            {
                                "papers": [{"pmid": 10601354}, {"pmid": 14574404}],
                                "n_total": 2,
                            }
                        ),
                    }
                ],
            },
            {
                "type": "agent.custom_tool_use",
                "id": "tu_3",
                "name": "patent_lookup",
                "input": {"wo_number": "WO2024036333A2"},
            },
            {
                "type": "user.custom_tool_result",
                "custom_tool_use_id": "tu_3",
                "content": [{"type": "text", "text": json.dumps({"wo_number": "WO2024036333A2"})}],
            },
        ],
    )

    contributed = {"PMID:10601354": ["evi_001"]}
    log = build_search_log(events_path, contributed_by=contributed)

    assert len(log) == 3

    resolve_entry = log[0]
    assert resolve_entry.tool == "gene_lookup"
    assert resolve_entry.mode == "resolve"
    assert resolve_entry.sources_seen == ["UniProt:Q9UBP8"]
    assert resolve_entry.n_results == 1

    lit_entry = log[1]
    assert lit_entry.tool == "gene_literature"
    assert lit_entry.mode == "gene2pubmed"
    assert lit_entry.sources_seen == ["PMID:10601354", "PMID:14574404"]
    assert lit_entry.n_results == 2
    assert lit_entry.contributed_evidence_ids == ["evi_001"]

    patent_entry = log[2]
    assert patent_entry.tool == "patent_lookup"
    assert patent_entry.sources_seen == ["WO:WO2024036333A2"]


def test_build_search_log_missing_events(tmp_path: Path) -> None:
    assert build_search_log(tmp_path / "absent.jsonl") == []


# ---------------------------------------------------------------------------
# End-to-end via _persist_annotation
# ---------------------------------------------------------------------------


def _draft_dict(*, evidence_claims: list[dict]) -> dict:
    """Synthesize a minimal SurfaceomeRecordDraft JSON dict.

    Defaults populate just enough required fields to validate; tests override
    ``evidence_claims`` to exercise the promotion path.
    """

    return {
        "schema_version": "v0.3.3",
        "gene": {
            "hgnc_symbol": "KAAG1",
            "hgnc_id": "HGNC:18225",
            "uniprot_acc": "Q9UBP8",
        },
        "canonical_isoform": "Q9UBP8",
        "isoform_flattened": True,
        "targetability": {
            "tier": "edge_case",
            "recommended_modalities": [],
            "tldr": "MHC-presented peptide; targetable via TCR-mimic mAb.",
            "cited_evidence_ids": ["evi_001"],
        },
        "surface_biology": {
            "surface_status": "rare_surface",
            "topology": "not_pm_associated",
            "anchor_type": "mhc_presented_peptide",
            "db_comparison": {
                "n_sources_voting_surface": 0,
            },
            "cited_evidence_ids": ["evi_001"],
        },
        "expression": {
            "tumor_indications": ["renal cell carcinoma"],
            "tumor_specificity": "indication_restricted",
            "normal_tissue_top": ["kidney proximal tubule"],
            "normal_tissue_concerns": [],
            "summary": "Restricted to kidney; presented as a peptide-MHC complex on tumor cells.",
            "cited_evidence_ids": ["evi_001"],
        },
        "adc_properties": {
            "internalization": "unknown",
            "expression_homogeneity": "unknown",
        },
        "therapeutic_landscape": {
            "approved_drugs": [],
            "clinical_trials": [],
            "patent_disclosures": [],
            "preclinical_evidence": [],
        },
        "risk_flags": [],
        "evidence_claims": evidence_claims,
        "confidence": "medium",
        "confidence_reasoning": "Founding paper anchors the proximal-tubule expression call.",
        "contradiction_flag": False,
        "rationale": "KAAG1 was first described as a kidney-restricted antigen presented as pMHC.",
        "model_path": "opus_light",
    }


def test_persist_annotation_end_to_end(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Synthesize a draft + populated SourceTextStore, run the persist pipeline,
    assert the persisted JSON validates as the current SurfaceomeRecord
    schema with the promoted evidence chain.
    """

    annotations_dir = tmp_path / "data" / "annotations"
    monkeypatch.setattr(
        "accessible_surfaceome.agents.surface_annotator.orchestrator.DATA_DIR",
        tmp_path / "data",
    )
    run_dir = tmp_path / "run"
    run_dir.mkdir()
    # Empty events file is fine — search_log will be empty, which is allowed.
    (run_dir / "events.jsonl").write_text("")

    store = SourceTextStore()
    store.put(_make_source())  # Seeds PMID:10601354 with the proximal-tubule sentence.

    draft = _draft_dict(
        evidence_claims=[
            {
                "evidence_id": "evi_001",
                "claim": "KAAG1 is expressed on kidney proximal tubule cells",
                "claim_type": "surface_expression",
                "direction": "supports",
                "evidence_type": "immunohistochemistry",
                "evidence_tier": "primary",
                "confidence": "strong",
                "assay_context": {"species": "human"},
                "source_id": "PMID:10601354",
                "quote": "proximal tubule cells",
                "section": "results",
            }
        ]
    )

    annotation_path, invalid_path, status, errors = _persist_annotation(
        gene="KAAG1",
        annotation_json=draft,
        run_dir=run_dir,
        source_store=store,
    )

    assert status == "valid", f"errors={errors}"
    assert invalid_path is None
    assert annotation_path is not None
    assert annotation_path == annotations_dir / "KAAG1.json"

    persisted = json.loads(annotation_path.read_text())
    record = SurfaceomeRecord.model_validate(persisted)
    assert record.schema_version == "v0.3.3"
    assert record.evidence_count == 1
    assert record.primary_evidence_count == 1
    assert record.secondary_evidence_count == 0
    assert len(record.evidence) == 1
    evi = record.evidence[0]
    assert evi.entailment_verified is True
    assert evi.evidence_id == "evi_001"
    assert len(evi.spans) == 1
    assert evi.spans[0].source.source_id == "PMID:10601354"


def test_persist_annotation_unverified_claim_persists(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A claim citing a source the agent never fetched still persists, with
    ``entailment_verified=False`` and a warning. The record validates under
    the current schema because empty ``spans`` is now legal for unverified
    evidence."""

    monkeypatch.setattr(
        "accessible_surfaceome.agents.surface_annotator.orchestrator.DATA_DIR",
        tmp_path / "data",
    )
    run_dir = tmp_path / "run"
    run_dir.mkdir()
    (run_dir / "events.jsonl").write_text("")

    store = SourceTextStore()  # empty — agent cited a source it didn't fetch
    draft = _draft_dict(
        evidence_claims=[
            {
                "evidence_id": "evi_001",
                "claim": "claim referencing untouched source",
                "claim_type": "surface_expression",
                "direction": "supports",
                "evidence_type": "immunohistochemistry",
                "evidence_tier": "primary",
                "confidence": "weak",
                "assay_context": {"species": "human"},
                "source_id": "PMID:99999",
                "quote": "irrelevant",
                "section": "results",
            }
        ]
    )

    annotation_path, _invalid, status, _errors = _persist_annotation(
        gene="KAAG1",
        annotation_json=draft,
        run_dir=run_dir,
        source_store=store,
    )
    assert status == "valid"
    assert annotation_path is not None
    record = SurfaceomeRecord.model_validate_json(annotation_path.read_text())
    evi = record.evidence[0]
    assert evi.entailment_verified is False
    assert evi.spans == []
    assert evi.validation_warnings
