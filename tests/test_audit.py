"""Tests for the entailment audit + corpus round-trip audit walker.

The Sonnet entailment audit is exercised with stub callables (no live API
calls). The corpus audit walker runs against synthesized
``data/sources/`` payloads to confirm the deterministic re-verification
path.
"""

from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime
from pathlib import Path

from accessible_surfaceome.agents.surface_annotator import audit
from accessible_surfaceome.agents.surface_annotator.evidence_promotion import promote_claim
from typing import cast

from accessible_surfaceome.tools._shared.models import (
    AssayContext,
    Direction,
    Evidence,
    EvidenceClaim,
    SurfaceomeRecord,
)
from accessible_surfaceome.tools._shared.normalize import normalize_for_quote_matching
from accessible_surfaceome.tools._shared.source_text import SourceText, SourceTextStore


# ---------------------------------------------------------------------------
# Helpers (mirror the ones in test_evidence_promotion / test_source_corpus)
# ---------------------------------------------------------------------------


def _make_source(
    *,
    raw_text: str = "Short-term cultures of proximal tubule cells expressed KAAG1.",
    source_id: str = "PMID:10601354",
) -> SourceText:
    normalized = normalize_for_quote_matching(raw_text)
    return SourceText(
        source_id=source_id,
        source_type="pubmed",
        url="https://pubmed.ncbi.nlm.nih.gov/10601354/",
        title="Brandle et al.",
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
    direction: str = "supports",
    evidence_id: str = "evi_001",
    source_id: str = "PMID:10601354",
) -> EvidenceClaim:
    return EvidenceClaim(
        evidence_id=evidence_id,
        claim="KAAG1 is expressed on proximal tubule cells",
        claim_type="surface_expression",
        direction=cast(Direction, direction),
        evidence_type="immunohistochemistry",
        evidence_tier="primary",
        confidence="strong",
        assay_context=AssayContext(species="human"),
        source_id=source_id,
        quote=quote,
        section="results",
    )


# ---------------------------------------------------------------------------
# Entailment audit
# ---------------------------------------------------------------------------


def test_apply_entailment_audit_passes_for_supportive_quote() -> None:
    store = SourceTextStore()
    store.put(_make_source())
    evi = promote_claim(_make_claim(), store=store)
    assert evi.entailment_verified is True

    def stub_audit(*, claim: str, direction: str, quote: str) -> bool:
        # Pretend Sonnet said "yes, the quote supports the claim".
        return True

    audit.apply_entailment_audit([evi], audit=stub_audit)
    assert evi.entailment_audit_passed is True
    assert all("entailment audit" not in w for w in evi.validation_warnings)


def test_apply_entailment_audit_records_failure() -> None:
    """A False audit result flips the field and surfaces a warning."""

    store = SourceTextStore()
    store.put(_make_source())
    evi = promote_claim(_make_claim(direction="supports"), store=store)

    audit.apply_entailment_audit(
        [evi],
        audit=lambda **_: False,
    )
    assert evi.entailment_audit_passed is False
    assert any("entailment audit" in w for w in evi.validation_warnings)


def test_apply_entailment_audit_skips_unverified() -> None:
    """An Evidence that failed substring promotion has no quote to audit."""

    store = SourceTextStore()  # empty store → unverified
    evi = promote_claim(_make_claim(), store=store)
    assert evi.entailment_verified is False

    calls: list[tuple] = []

    def stub_audit(*, claim: str, direction: str, quote: str) -> bool:
        calls.append((claim, direction, quote))
        return True

    audit.apply_entailment_audit([evi], audit=stub_audit)
    assert calls == []  # never asked the auditor
    assert evi.entailment_audit_passed is None


def test_apply_entailment_audit_handles_none_result() -> None:
    """When the audit returns ``None`` (transient failure), surface a
    'not run' warning but leave the field as None."""

    store = SourceTextStore()
    store.put(_make_source())
    evi = promote_claim(_make_claim(), store=store)

    audit.apply_entailment_audit([evi], audit=lambda **_: None)
    assert evi.entailment_audit_passed is None
    assert any("not run" in w for w in evi.validation_warnings)


# ---------------------------------------------------------------------------
# Sonnet response parsing (unit-level)
# ---------------------------------------------------------------------------


def test_parse_entailment_response_clean_json() -> None:
    text = '{"entailed": true, "reasoning": "The quote supports the claim."}'
    assert audit._parse_entailment_response(text) is True


def test_parse_entailment_response_embedded_json() -> None:
    text = (
        "Here is my analysis:\n"
        '{"entailed": false, "reasoning": "Quote contradicts direction."}\n'
        "Hope this helps."
    )
    assert audit._parse_entailment_response(text) is False


def test_parse_entailment_response_missing_field() -> None:
    text = '{"reasoning": "no entailed key"}'
    assert audit._parse_entailment_response(text) is None


def test_parse_entailment_response_garbage() -> None:
    assert audit._parse_entailment_response("nothing here") is None


def test_make_sonnet_audit_handles_api_error() -> None:
    """A raised exception in the API call yields ``None``, not a crash."""

    class FailingClient:
        class messages:  # noqa: N801 — mimic SDK shape
            @staticmethod
            def create(**_kwargs):
                raise RuntimeError("simulated network error")

    auditor = audit.make_sonnet_entailment_audit(FailingClient())
    assert auditor(claim="x", direction="supports", quote="y") is None


# ---------------------------------------------------------------------------
# Corpus round-trip audit
# ---------------------------------------------------------------------------


def _persist_record(
    record: SurfaceomeRecord, tmp_path: Path
) -> tuple[Path, Path]:
    """Write the record + its sources to ``tmp_path``."""

    annotations_dir = tmp_path / "annotations"
    annotations_dir.mkdir()
    annotation_path = annotations_dir / "KAAG1.json"
    annotation_path.write_text(record.model_dump_json(indent=2) + "\n")
    sources_dir = tmp_path / "sources"
    sources_dir.mkdir()
    return annotation_path, sources_dir


def _build_record_from(evi: Evidence) -> SurfaceomeRecord:
    """Synthesize a minimal SurfaceomeRecord that carries one Evidence."""

    return SurfaceomeRecord.model_validate(
        {
            "schema_version": "v0.3.3",
            "gene": {
                "hgnc_symbol": "KAAG1",
                "hgnc_id": "HGNC:21031",
                "uniprot_acc": "Q9UBP8",
            },
            "canonical_isoform": "Q9UBP8",
            "isoform_flattened": True,
            "targetability": {
                "tier": "edge_case",
                "recommended_modalities": [],
                "tldr": "tldr",
                "cited_evidence_ids": [evi.evidence_id],
            },
            "surface_biology": {
                "surface_status": "rare_surface",
                "topology": "not_pm_associated",
                "anchor_type": "mhc_presented_peptide",
                "db_comparison": {"n_sources_voting_surface": 0},
                "cited_evidence_ids": [evi.evidence_id],
            },
            "expression": {
                "tumor_indications": [],
                "tumor_specificity": "indication_restricted",
                "normal_tissue_top": [],
                "normal_tissue_concerns": [],
                "summary": None,
                "cited_evidence_ids": [evi.evidence_id],
            },
            "adc_properties": {},
            "therapeutic_landscape": {},
            "risk_flags": [],
            "evidence": [evi.model_dump()],
            "primary_evidence_count": 1,
            "secondary_evidence_count": 0,
            "evidence_count": 1,
            "search_log": [],
            "confidence": "medium",
            "confidence_reasoning": "test",
            "contradiction_flag": False,
            "rationale": "test",
            "model_path": "opus_light",
        }
    )


def test_audit_record_passes_when_corpus_matches(tmp_path: Path) -> None:
    """Happy path: persist record + sources with consistent hashes; audit
    should report every span as verified."""

    store = SourceTextStore()
    store.put(_make_source())
    evi = promote_claim(_make_claim(), store=store)
    record = _build_record_from(evi)
    annotation_path, sources_dir = _persist_record(record, tmp_path)
    store.persist_to_disk(sources_dir)

    report = audit.audit_record_path(annotation_path, sources_dir=sources_dir)
    assert report.n_spans == 1
    assert report.all_passed is True
    assert report.span_results[0].mismatches == ()


def test_audit_record_detects_missing_source(tmp_path: Path) -> None:
    """Source body absent from the corpus → span flagged with mismatch."""

    store = SourceTextStore()
    store.put(_make_source())
    evi = promote_claim(_make_claim(), store=store)
    record = _build_record_from(evi)
    annotation_path, sources_dir = _persist_record(record, tmp_path)
    # Don't persist sources — directory exists but is empty.

    report = audit.audit_record_path(annotation_path, sources_dir=sources_dir)
    assert report.all_passed is False
    assert report.span_results[0].found_in_store is False
    assert any("missing" in m for m in report.span_results[0].mismatches)


def test_audit_record_detects_tampered_body(tmp_path: Path) -> None:
    """Source body present but with different bytes → content_sha256
    mismatch surfaces."""

    store = SourceTextStore()
    store.put(_make_source())
    evi = promote_claim(_make_claim(), store=store)
    record = _build_record_from(evi)
    annotation_path, sources_dir = _persist_record(record, tmp_path)
    store.persist_to_disk(sources_dir)

    # Tamper with the persisted source body.
    source_path = sources_dir / "PMID_10601354.json"
    payload = json.loads(source_path.read_text())
    payload["raw_text"] = "Tampered: " + payload["raw_text"]
    source_path.write_text(json.dumps(payload))

    report = audit.audit_record_path(annotation_path, sources_dir=sources_dir)
    assert report.all_passed is False
    result = report.span_results[0]
    assert result.found_in_store is True
    assert result.content_sha256_match is False
    assert any("content_sha256 mismatch" in m for m in result.mismatches)


def test_format_report_renders_pass_and_fail(tmp_path: Path) -> None:
    store = SourceTextStore()
    store.put(_make_source())
    evi = promote_claim(_make_claim(), store=store)
    record = _build_record_from(evi)
    annotation_path, sources_dir = _persist_record(record, tmp_path)
    store.persist_to_disk(sources_dir)

    report = audit.audit_record_path(annotation_path, sources_dir=sources_dir)
    rendered = audit.format_report(report)
    assert "audit:" in rendered
    assert "passed: 1" in rendered
    assert "failed: 0" in rendered
    assert "✓" in rendered


def test_audit_record_record_with_no_spans(tmp_path: Path) -> None:
    """An unverified Evidence (empty spans) is silently skipped — no spans
    to audit. The report is empty rather than failed."""

    store = SourceTextStore()  # empty → promotion produces unverified evidence
    evi = promote_claim(_make_claim(), store=store)
    assert evi.spans == []
    record = _build_record_from(evi)
    annotation_path, sources_dir = _persist_record(record, tmp_path)

    report = audit.audit_record_path(annotation_path, sources_dir=sources_dir)
    assert report.n_spans == 0
    assert report.all_passed is True  # no failures because nothing to check
