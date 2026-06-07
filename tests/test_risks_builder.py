"""Unit tests for the cross-focus accessibility-risks block-builder.

``build_risks`` consumes the MERGED A1+A2 ``EvidenceClaim`` ledger (+ the
deterministic-features summary) and emits ONE ``AccessibilityRisks``
object — the six risk sub-blocks the catalog filters on. These tests use
a MagicMock Anthropic client (no network) and assert:

* Happy path: a merged-ledger fixture → a valid ``AccessibilityRisks``
  whose risk chips cite real evidence ids from the input ledger.
* Citation roundtrip: cited evidence_ids absent from the merged ledger
  are scrubbed.
* Repair-loop exhaustion → ``None`` (the orchestrator owns the fallback).
* The deterministic-features summary, when supplied, surfaces in the
  user prompt (so the model can emit ``ecd_size_assessment`` per the
  bands and corroborate homo-oligomerization).
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock

import pytest
from pydantic import ValidationError

from accessible_surfaceome.agents._support.pricing import UsageRecord
from accessible_surfaceome.agents.surfaceome_v1.orchestrator import (
    _stub_deterministic_features,
)
from accessible_surfaceome.agents.surfaceome_v2.builders import build_risks
from accessible_surfaceome.tools._shared.models import (
    AccessibilityRisks,
    DeterministicFeatures,
    EvidenceClaim,
    HomoOligomerizationFeatures,
)


# ---------------------------------------------------------------------------
# Test helpers (mirror tests/test_surfaceome_v2_builders.py)
# ---------------------------------------------------------------------------


def _claim(
    evi_id: str,
    *,
    prefix: str = "a1",
    claim_type: str = "surface_expression",
    evidence_type: str = "flow_cytometry",
    direction: str = "supports",
    quote: str = "Example verbatim quote.",
    source_id: str = "PMID:11111",
    section: str = "results",
) -> EvidenceClaim:
    return EvidenceClaim.model_validate(
        {
            "evidence_id": f"{prefix}_evi_{evi_id}",
            "claim": f"Synthetic claim {evi_id}",
            "claim_type": claim_type,
            "direction": direction,
            "evidence_type": evidence_type,
            "evidence_tier": "primary",
            "confidence": "moderate",
            "assay_context": {
                "species": "human",
                "cell_type_or_line": "HEK293",
                "permeabilized": False,
            },
            "source_id": source_id,
            "quote": quote,
            "section": section,
        }
    )


def _mock_client(text_responses: list[str]) -> Any:
    client = MagicMock()
    iterator = iter(text_responses)

    def _create(**_kwargs: Any) -> Any:
        text = next(iterator)
        block = MagicMock()
        block.text = text
        usage = MagicMock()
        usage.input_tokens = 100
        usage.output_tokens = 50
        usage.cache_creation_input_tokens = 0
        usage.cache_read_input_tokens = 0
        resp = MagicMock()
        resp.content = [block]
        resp.usage = usage
        resp.stop_reason = "end_turn"
        return resp

    client.messages.create.side_effect = _create
    return client


@pytest.fixture(autouse=True)
def _patch_text_block(monkeypatch: pytest.MonkeyPatch) -> None:
    """Let MagicMock content blocks pass the ``isinstance(b, TextBlock)``
    check inside ``_common``."""
    from accessible_surfaceome.agents.surfaceome_v2.builders import (
        _common as common_mod,
    )

    monkeypatch.setattr(
        common_mod, "TextBlock", (common_mod.TextBlock, MagicMock), raising=True
    )


def _fenced(body: str) -> str:
    return f"```json\n{body}\n```"


def _merged_ledger() -> list[EvidenceClaim]:
    """A small merged A1+A2 ledger covering the risk-relevant evidence
    classes (surface methodology + soluble-form + subdomain + partner)."""
    return [
        _claim("01", prefix="a1", evidence_type="flow_cytometry",
               quote="Live-cell flow cytometry detects X on the surface."),
        _claim("02", prefix="a1", evidence_type="surface_biotinylation",
               quote="Surface biotinylation labels X across the membrane."),
        _claim("03", prefix="a2", claim_type="tissue_expression",
               evidence_type="immunohistochemistry", source_id="PMID:222",
               quote="A soluble ectodomain of X is measured in patient serum."),
        _claim("04", prefix="a2", claim_type="surface_expression",
               source_id="PMID:333",
               quote="X requires partner Y for ER exit and surface delivery."),
    ]


def _valid_risks_payload() -> dict[str, Any]:
    """A schema-valid ``AccessibilityRisks`` object citing real ids."""
    return {
        "co_receptor_requirements": {
            "surface_expression_dependency": "required",
            "partners": ["Y"],
            "evidence_basis": "trafficking",
            "rationale": "X needs partner Y for ER exit and surface delivery (a2_evi_04).",
            "cited_evidence_ids": ["a2_evi_04"],
        },
        "shed_form": {
            "present": False,
            "severity": "low",
            "evidence_strength": "weak",
            "mechanism": None,
            "sheddase_if_known": None,
            "cited_evidence_ids": [],
        },
        "secreted_form": {
            "present": True,
            "severity": "moderate",
            "evidence_strength": "moderate",
            "ratio_to_membrane": None,
            "source": "proteolytic",
            "cited_evidence_ids": ["a2_evi_03"],
        },
        "restricted_subdomain": {
            "present": False,
            "domain": "unknown",
            "severity": "low",
            "evidence_strength": "weak",
            "rationale": (
                "Surface biotinylation labels X membrane-wide (a1_evi_02); "
                "no subdomain restriction."
            ),
            "cited_evidence_ids": ["a1_evi_02"],
        },
        "ecd_size_assessment": {
            "ecd_accessibility_class": "large",
            "rationale": "ECD ~310 residues -> large.",
            "cited_evidence_ids": [],
        },
        "epitope_masking": {
            "mechanism": ["none"],
            "severity": "none",
            "evidence_strength": "weak",
            "rationale": "No masking documented in the ledger.",
            "cited_evidence_ids": [],
        },
    }


def _det_features() -> DeterministicFeatures:
    """A schema-valid DeterministicFeatures with a large ECD + a Schweke
    homo-oligomer positive — built off the stub so we don't hand-supply
    every required IsoformTopology / StructureFeatures field."""
    stub = _stub_deterministic_features("P00533")
    canon = stub.canonical_topology.model_copy(
        update={"tm_helix_count": 1, "ecd_length_residues": 310}
    )
    return stub.model_copy(
        update={
            "canonical_topology": canon,
            "homo_oligomerization": HomoOligomerizationFeatures(
                is_homo_oligomer=True, stoichiometry=2
            ),
        }
    )


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


def test_build_risks_happy_path_emits_valid_block_and_cites_evidence() -> None:
    claims = _merged_ledger()
    client = _mock_client([_fenced(json.dumps(_valid_risks_payload()))])
    sink: list[UsageRecord] = []
    risks = build_risks(
        claims, client=client, usage_sink=sink, context={"gene": "GENEX"}
    )
    assert isinstance(risks, AccessibilityRisks)
    # The literature-driven risks cite real ids from the merged ledger.
    assert risks.co_receptor_requirements.cited_evidence_ids == ["a2_evi_04"]
    assert risks.secreted_form.present is True
    assert risks.secreted_form.cited_evidence_ids == ["a2_evi_03"]
    assert risks.restricted_subdomain.cited_evidence_ids == ["a1_evi_02"]
    # Every cited id resolves to an input-ledger claim — no fabrication.
    known = {c.evidence_id for c in claims}
    for block in (
        risks.co_receptor_requirements,
        risks.shed_form,
        risks.secreted_form,
        risks.restricted_subdomain,
        risks.ecd_size_assessment,
        risks.epitope_masking,
    ):
        assert set(block.cited_evidence_ids) <= known
    assert len(sink) == 1


def test_build_risks_scrubs_unknown_citations() -> None:
    claims = _merged_ledger()
    payload = _valid_risks_payload()
    # Inject a fabricated id alongside a real one — it must be scrubbed.
    payload["co_receptor_requirements"]["cited_evidence_ids"] = [
        "a2_evi_04",
        "a2_evi_99",
    ]
    client = _mock_client([_fenced(json.dumps(payload))])
    sink: list[UsageRecord] = []
    risks = build_risks(
        claims, client=client, usage_sink=sink, context={"gene": "GENEX"}
    )
    assert isinstance(risks, AccessibilityRisks)
    assert risks.co_receptor_requirements.cited_evidence_ids == ["a2_evi_04"]


def test_build_risks_returns_none_after_repair_exhaustion() -> None:
    claims = _merged_ledger()
    # Three non-JSON responses (initial + MAX_REPAIRS=2) → repair loop fails.
    client = _mock_client(["not json at all"] * 3)
    sink: list[UsageRecord] = []
    risks = build_risks(
        claims, client=client, usage_sink=sink, context={"gene": "GENEX"}
    )
    assert risks is None


def test_build_risks_includes_deterministic_summary_in_prompt() -> None:
    claims = _merged_ledger()
    client = _mock_client([_fenced(json.dumps(_valid_risks_payload()))])
    sink: list[UsageRecord] = []
    build_risks(
        claims,
        client=client,
        usage_sink=sink,
        context={"gene": "GENEX", "deterministic_features": _det_features()},
    )
    # Inspect the user prompt the builder sent.
    _, kwargs = client.messages.create.call_args
    user_msg = kwargs["messages"][0]["content"]
    assert "Deterministic features" in user_msg
    assert "ecd_length_residues" in user_msg
    assert "310" in user_msg
    assert "homo_oligomerization" in user_msg


def test_build_risks_runs_without_deterministic_features() -> None:
    """The ECD / homo-oligomer post-passes run in the orchestrator, so the
    builder must still produce a valid block when no deterministic summary
    is supplied (CLI / stub paths)."""
    claims = _merged_ledger()
    client = _mock_client([_fenced(json.dumps(_valid_risks_payload()))])
    sink: list[UsageRecord] = []
    risks = build_risks(
        claims, client=client, usage_sink=sink, context={"gene": "GENEX"}
    )
    assert isinstance(risks, AccessibilityRisks)
    _, kwargs = client.messages.create.call_args
    user_msg = kwargs["messages"][0]["content"]
    assert "Deterministic features" not in user_msg


def test_risks_builder_prompt_documents_each_risk_and_cite_discipline() -> None:
    """Tripwire: the risks builder prompt must carry the six risk
    sub-blocks, the homo/hetero masking-axis split, the cite-a-real-id
    discipline, and the deterministic-ECD / corroboration-only-oligomer
    rules that the orchestrator's post-passes depend on."""
    prompt_path = (
        Path(__file__).parent.parent
        / "src/accessible_surfaceome/agents/surfaceome_v2/prompts/risks_builder_system.md"
    )
    body = prompt_path.read_text()
    lower = body.lower()
    for block in (
        "co_receptor_requirements",
        "shed_form",
        "secreted_form",
        "restricted_subdomain",
        "ecd_size_assessment",
        "epitope_masking",
    ):
        assert block in body
    # masking-axis enum values + homo/hetero split
    assert "oligomerization" in body
    assert "partner" in body
    assert "homo" in lower and "hetero" in lower
    # cite-a-real-id discipline
    assert "cited_evidence_ids" in body
    assert "a1_evi" in lower and "a2_evi" in lower
    # deterministic ECD overwrite + corroboration-only oligomer
    assert "deterministically" in lower or "deterministic" in lower
    assert "corroborat" in lower
    # orchestrator-only prediction chip is excluded
    assert "homo_oligomerization_prediction" in body


def test_valid_risks_payload_is_schema_valid() -> None:
    """Guard the fixture itself: the happy-path payload must validate as a
    real AccessibilityRisks (so a schema change to the risk sub-models
    surfaces here, not as a confusing mock-call failure)."""
    try:
        AccessibilityRisks.model_validate(_valid_risks_payload())
    except ValidationError as exc:  # pragma: no cover - fixture guard
        pytest.fail(f"fixture payload no longer matches AccessibilityRisks: {exc}")
