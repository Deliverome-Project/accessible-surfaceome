"""Unit tests for the v2 block-builders.

Each builder is exercised with a MagicMock Anthropic client that yields a
prepared text body so the call() goes through ``_call_with_repair`` without
touching the network. Coverage per builder:

* Happy path: valid claims → valid block.
* Empty input: no qualifying claims → empty / sane fallback.
* Citation roundtrip: cited evidence_ids that aren't in the input ledger
  get scrubbed by the builder.

A schema-validation test at the bottom assembles a full SurfaceomeRecord
from synthetic A1 + A2 fixtures + a mocked synthesizer/draft and confirms
the assembled record validates.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, get_args
from unittest.mock import MagicMock

import pytest
from pydantic import BaseModel, ConfigDict

from accessible_surfaceome.agents._support.pricing import UsageRecord
from accessible_surfaceome.agents.surfaceome_v2.builders import (
    EvidenceGradeBlock,
    build_accessibility_modulation,
    build_anatomical_accessibility,
    build_contradictions,
    build_evidence_grade,
    build_expression,
    build_methods,
    build_subcellular_localization,
)
from accessible_surfaceome.agents.surfaceome_v2.orchestrator import (
    _synthetic_source_store,
)
from accessible_surfaceome.tools._shared.models import (
    AccessibilityModulationObservation,
    AnatomicalAccessibilityObservation,
    AssayContext,
    BiologicalContext,
    BiologicalContextDraft,
    Contradiction,
    EvidenceClaim,
    ExpressionRow,
    MethodFamily,
    MethodObservation,
    SubcellularLocalization,
    SurfaceEvidence,
    SurfaceEvidenceDraft,
)


def test_method_family_includes_functional_surface_assay():
    """``functional_surface_assay`` distinguishes evidence where binding /
    engagement implies surface access (antibody-mediated tumor killing,
    surface-targeted ADC efficacy, photo-tag labeling, FRET-on-surface)
    from the catch-all ``other``. SRC's a1_evi_02 — anti-Src antibody
    therapy in xenografts — is the canonical case that didn't fit any
    methodology bucket before."""
    assert "functional_surface_assay" in get_args(MethodFamily)


def test_methods_prompt_documents_functional_surface_assay():
    """The methods_builder prompt must mention the new method_family
    value so the LLM knows when to pick it."""
    prompt_path = (
        Path(__file__).parent.parent
        / "src/accessible_surfaceome/agents/surfaceome_v2/prompts/methods_builder_system.md"
    )
    body = prompt_path.read_text()
    assert "functional_surface_assay" in body


# ---------------------------------------------------------------------------
# Test helpers
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
    """Build a MagicMock Anthropic client whose ``messages.create`` yields
    the given text bodies in order (one per call).

    Each response has a TextBlock-like ``text`` attribute the builder
    code reads and a ``usage`` block the pricing code reads. Stop
    reason is always ``end_turn`` — use :func:`_mock_client_with_stops`
    when you need to simulate ``max_tokens`` truncation.
    """
    return _mock_client_with_stops([(t, "end_turn") for t in text_responses])


def _mock_client_with_stops(
    text_and_stop: list[tuple[str, str]],
) -> Any:
    """Like ``_mock_client`` but lets each response carry a distinct
    ``stop_reason`` — ``"end_turn"`` for clean completion,
    ``"max_tokens"`` for truncation, etc."""
    client = MagicMock()
    iterator = iter(text_and_stop)

    def _create(**_kwargs: Any) -> Any:
        text, stop_reason = next(iterator)
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
        resp.stop_reason = stop_reason
        return resp

    client.messages.create.side_effect = _create
    return client


@pytest.fixture(autouse=True)
def _patch_text_block(monkeypatch: pytest.MonkeyPatch) -> None:
    """Patch ``isinstance(b, TextBlock)`` checks in the builder common
    module + therapeutic-engagement builder so MagicMock content blocks
    pass through."""

    class _FakeTextBlock:  # noqa: D401 — marker class
        """Marker for MagicMock content blocks."""

    # Patch the TextBlock symbol in each module that uses it via
    # ``isinstance(b, TextBlock)``.
    from accessible_surfaceome.agents.surfaceome_v2.builders import (
        _common as common_mod,
    )

    # Replace TextBlock with a tuple of (real TextBlock, MagicMock) so
    # both real responses and mocked ones pass the isinstance check.
    monkeypatch.setattr(
        common_mod, "TextBlock", (common_mod.TextBlock, MagicMock), raising=True
    )


def _fenced(body: str) -> str:
    return f"```json\n{body}\n```"


# ---------------------------------------------------------------------------
# methods_builder
# ---------------------------------------------------------------------------


def test_build_methods_happy_path() -> None:
    claims = [
        _claim("01", evidence_type="flow_cytometry", quote="Live cells stained with anti-X."),
        _claim("02", evidence_type="surface_biotinylation", quote="Biotinylated surface proteins."),
    ]
    output = [
        {
            "method_family": "flow_cytometry",
            "method_subclass": "live_cell_flow",
            "permeabilization": "nonpermeabilized",
            "expression_system": "endogenous",
            "antibodies": [
                {
                    "name": "anti-X",
                    "monoclonal_or_polyclonal": "monoclonal",
                    "antibody_epitope_region": "extracellular",
                    "validation_strategy": "unknown",
                    "validation_strength": "unknown",
                }
            ],
            "accessibility_relevance": "direct_surface_accessibility",
            "surface_claim_type": "surface_accessible",
            "expression_observations": [],
            "cited_evidence_ids": ["a1_evi_01"],
        }
    ]
    client = _mock_client([_fenced(json.dumps(output))])
    sink: list[UsageRecord] = []
    rows = build_methods(
        claims, client=client, usage_sink=sink, context={"gene": "GPR75"}
    )
    assert len(rows) == 1
    assert isinstance(rows[0], MethodObservation)
    assert rows[0].cited_evidence_ids == ["a1_evi_01"]
    assert len(sink) == 1


def test_build_methods_empty_input() -> None:
    claims = [_claim("01", claim_type="tissue_expression", evidence_type="rna_seq")]
    client = _mock_client([])
    sink: list[UsageRecord] = []
    rows = build_methods(claims, client=client, usage_sink=sink, context={"gene": "X"})
    assert rows == []
    assert sink == []
    # No model call — the builder filtered before dispatching.
    client.messages.create.assert_not_called()


def test_build_methods_scrubs_unknown_citations() -> None:
    claims = [_claim("01", evidence_type="flow_cytometry")]
    output = [
        {
            "method_family": "flow_cytometry",
            "method_subclass": "live_cell_flow",
            "permeabilization": "nonpermeabilized",
            "expression_system": "endogenous",
            "antibodies": [],
            "accessibility_relevance": "direct_surface_accessibility",
            "surface_claim_type": "surface_accessible",
            "expression_observations": [],
            # 99 isn't in input; should be scrubbed
            "cited_evidence_ids": ["a1_evi_01", "a1_evi_99"],
        }
    ]
    client = _mock_client([_fenced(json.dumps(output))])
    sink: list[UsageRecord] = []
    rows = build_methods(claims, client=client, usage_sink=sink, context={"gene": "X"})
    assert rows[0].cited_evidence_ids == ["a1_evi_01"]


def test_build_methods_overexpression_with_native_sp() -> None:
    """A native-SP overexpression panel populates the overexpression block
    with `signal_peptide_source="native"`."""
    claims = [
        _claim(
            "01",
            evidence_type="flow_cytometry",
            quote="HEK293 cells transfected with untagged full-length [GENE] cDNA.",
        )
    ]
    output = [
        {
            "method_family": "flow_cytometry",
            "method_subclass": "live_cell_flow",
            "permeabilization": "nonpermeabilized",
            "expression_system": "overexpression",
            "overexpression": {
                "signal_peptide_source": "native",
                "signal_peptide_detail": "native signal peptide",
                "construct_tag": None,
                "cell_line": "HEK293",
                "cited_evidence_ids": ["a1_evi_01"],
            },
            "antibodies": [],
            "accessibility_relevance": "direct_surface_accessibility",
            "surface_claim_type": "surface_accessible",
            "expression_observations": [],
            "cited_evidence_ids": ["a1_evi_01"],
        }
    ]
    client = _mock_client([_fenced(json.dumps(output))])
    sink: list[UsageRecord] = []
    rows = build_methods(claims, client=client, usage_sink=sink, context={"gene": "X"})
    assert len(rows) == 1
    assert rows[0].expression_system == "overexpression"
    assert rows[0].overexpression is not None
    assert rows[0].overexpression.signal_peptide_source == "native"
    assert rows[0].overexpression.cell_line == "HEK293"


def test_build_methods_overexpression_with_exogenous_sp() -> None:
    """An exogenous-SP construct should be flagged so downstream tier
    rules can demote it (csGRP78 / cell-surface-vimentin failure mode)."""
    claims = [
        _claim(
            "01",
            evidence_type="flow_cytometry",
            quote="HEK293 cells transfected with IgG kappa leader-[GENE] fusion.",
        )
    ]
    output = [
        {
            "method_family": "flow_cytometry",
            "method_subclass": "live_cell_flow",
            "permeabilization": "nonpermeabilized",
            "expression_system": "overexpression",
            "overexpression": {
                "signal_peptide_source": "exogenous",
                "signal_peptide_detail": "IgG kappa leader",
                "construct_tag": "C-terminal FLAG",
                "cell_line": "HEK293",
                "cited_evidence_ids": ["a1_evi_01"],
            },
            "antibodies": [],
            "accessibility_relevance": "direct_surface_accessibility",
            "surface_claim_type": "surface_accessible",
            "expression_observations": [],
            "cited_evidence_ids": ["a1_evi_01"],
        }
    ]
    client = _mock_client([_fenced(json.dumps(output))])
    sink: list[UsageRecord] = []
    rows = build_methods(claims, client=client, usage_sink=sink, context={"gene": "X"})
    assert rows[0].overexpression is not None
    assert rows[0].overexpression.signal_peptide_source == "exogenous"
    assert rows[0].overexpression.signal_peptide_detail == "IgG kappa leader"


def test_build_methods_endogenous_panel_has_no_overexpression_block() -> None:
    """Endogenous-evidence panels leave the overexpression block as None."""
    claims = [_claim("01", evidence_type="flow_cytometry")]
    output = [
        {
            "method_family": "flow_cytometry",
            "method_subclass": "live_cell_flow",
            "permeabilization": "nonpermeabilized",
            "expression_system": "endogenous",
            "antibodies": [],
            "accessibility_relevance": "direct_surface_accessibility",
            "surface_claim_type": "surface_accessible",
            "expression_observations": [],
            "cited_evidence_ids": ["a1_evi_01"],
        }
    ]
    client = _mock_client([_fenced(json.dumps(output))])
    sink: list[UsageRecord] = []
    rows = build_methods(claims, client=client, usage_sink=sink, context={"gene": "X"})
    assert rows[0].expression_system == "endogenous"
    assert rows[0].overexpression is None


def test_build_methods_extracts_clone_vendor_rrid_from_claim_quote() -> None:
    """When the claim quote names an antibody clone + vendor + RRID, the
    builder must split them into the structured fields, not collapse into
    `name`. Verifies the new "Antibody-identifier extraction discipline"
    section of the methods builder prompt."""
    claims = [
        _claim(
            "01",
            evidence_type="flow_cytometry",
            quote=(
                "Surface CD81 was detected by flow cytometry with anti-CD81 "
                "clone 5A6 (BD Biosciences, RRID:AB_396171) on live HEK293T "
                "cells; CD81-KO cells were negative."
            ),
        )
    ]
    output = [
        {
            "method_family": "flow_cytometry",
            "method_subclass": "live_cell_flow",
            "permeabilization": "nonpermeabilized",
            "expression_system": "endogenous",
            "antibodies": [
                {
                    "name": "anti-CD81",
                    "clone": "5A6",
                    "vendor": "BD Biosciences",
                    "rrid": "AB_396171",
                    "monoclonal_or_polyclonal": "monoclonal",
                    "antibody_epitope_region": "extracellular",
                    "validation_strategy": "genetic_KO",
                    "validation_strength": "strong",
                }
            ],
            "accessibility_relevance": "direct_surface_accessibility",
            "surface_claim_type": "surface_accessible",
            "expression_observations": [],
            "cited_evidence_ids": ["a1_evi_01"],
        }
    ]
    client = _mock_client([_fenced(json.dumps(output))])
    sink: list[UsageRecord] = []
    rows = build_methods(claims, client=client, usage_sink=sink, context={"gene": "CD81"})
    assert len(rows) == 1
    ab = rows[0].antibodies[0]
    assert ab.name == "anti-CD81"
    assert ab.clone == "5A6"
    assert ab.vendor == "BD Biosciences"
    assert ab.rrid == "AB_396171"
    assert ab.validation_strategy == "genetic_KO"
    assert ab.validation_strength == "strong"


def test_build_methods_generic_antibody_lands_vendor_claim_only() -> None:
    """When the claim quote uses generic language ('a commercial anti-X
    antibody'), the builder should set clone=null AND
    validation_strategy=vendor_claim_only AND validation_strength=weak.
    Verifies the prompt's "honest about gaps" rule."""
    claims = [
        _claim(
            "01",
            evidence_type="flow_cytometry",
            quote=(
                "Live cells were stained with a commercial anti-CD81 "
                "antibody and analyzed by flow cytometry."
            ),
        )
    ]
    output = [
        {
            "method_family": "flow_cytometry",
            "method_subclass": "live_cell_flow",
            "permeabilization": "nonpermeabilized",
            "expression_system": "endogenous",
            "antibodies": [
                {
                    "name": "anti-CD81",
                    "clone": None,
                    "vendor": None,
                    "monoclonal_or_polyclonal": "unknown",
                    "antibody_epitope_region": "unknown",
                    "validation_strategy": "vendor_claim_only",
                    "validation_strength": "weak",
                }
            ],
            "accessibility_relevance": "direct_surface_accessibility",
            "surface_claim_type": "surface_accessible",
            "expression_observations": [],
            "cited_evidence_ids": ["a1_evi_01"],
        }
    ]
    client = _mock_client([_fenced(json.dumps(output))])
    sink: list[UsageRecord] = []
    rows = build_methods(claims, client=client, usage_sink=sink, context={"gene": "CD81"})
    ab = rows[0].antibodies[0]
    assert ab.clone is None
    assert ab.validation_strategy == "vendor_claim_only"
    assert ab.validation_strength == "weak"


def test_methods_builder_prompt_mentions_clone_extraction_discipline() -> None:
    """Tripwire: the methods builder prompt must carry the antibody-
    identifier extraction discipline section that strengthens clone /
    vendor / RRID extraction (PR #38 follow-up after audit found 0 of
    ~50 antibody rows had a clone extracted)."""
    from accessible_surfaceome.agents.surfaceome_v2.builders._common import load_prompt
    body = load_prompt("methods_builder_system").lower()
    assert "antibody-identifier extraction discipline" in body
    assert "do not bury identifiers" in body or "not bury the identifier" in body or "burying" in body or "bury" in body
    assert "vendor_claim_only" in body
    assert "ab_" in body or "rrid" in body  # RRID guidance


def test_methods_builder_prompt_mentions_validation_strategy_table() -> None:
    """Tripwire: the prompt must explicitly map literature language to
    validation_strategy enum values so the builder doesn't default to
    `none`."""
    from accessible_surfaceome.agents.surfaceome_v2.builders._common import load_prompt
    body = load_prompt("methods_builder_system").lower()
    assert "validation-strategy assignment" in body
    assert "siRNA knockdown abolishes".lower() in body
    assert "ip_ms_pulldown" in body


def test_build_methods_caps_input_claims_at_max(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """When _select_input_claims returns >MAX_CLAIMS_TO_LLM qualifying
    claims, the methods builder must pre-truncate to the top MAX_CLAIMS_TO_LLM
    BEFORE invoking the LLM. Caps cost on heaviest-gene cases (TACSTD2's
    methods builder hit $0.36/call at 87k input tokens; tail genes much
    higher).

    Verifies:
      1. The ledger embedded in the user prompt contains exactly
         MAX_CLAIMS_TO_LLM claims, not the full input.
      2. The top-ranked evidence types (live_cell_flow / biotinylation /
         nonperm IF) survive over the bottom ones (rt_qpcr /
         tissue_expression).
      3. A log line records the truncation so an operator can see it.
    """
    from accessible_surfaceome.agents.surfaceome_v2.builders.methods import (
        MAX_CLAIMS_TO_LLM,
    )
    import logging

    # 30 claims: 10 high-rank surface (flow_cytometry, surface_biotinylation,
    # immunofluorescence with permeabilized=False), 10 mid-rank (IHC, WB),
    # 10 low-rank (rt_qpcr methodological).
    high_rank = [
        _claim(f"h{i:02d}", evidence_type="surface_biotinylation",
               quote=f"Surface biotin probe {i}.")
        for i in range(5)
    ] + [
        _claim(f"f{i:02d}", evidence_type="flow_cytometry",
               quote=f"Live flow {i}.")
        for i in range(5)
    ]
    mid_rank = [
        _claim(f"ih{i:02d}", evidence_type="immunohistochemistry",
               quote=f"IHC {i}.")
        for i in range(5)
    ] + [
        _claim(f"wb{i:02d}", evidence_type="western_blot",
               quote=f"WB {i}.")
        for i in range(5)
    ]
    low_rank = [
        _claim(
            f"q{i:02d}",
            claim_type="methodological",
            evidence_type="rt_qpcr",
            quote=f"qPCR {i}.",
        )
        for i in range(10)
    ]

    # Make some low-rank claims have non-human species so they sort lower:
    # easier than that, we just trust the evidence_type weight to push
    # rt_qpcr below the surface assays.
    claims = high_rank + mid_rank + low_rank
    assert len(claims) == 30  # confirm setup

    # Model returns an empty array so the test focuses on what got
    # sent to the model, not what came back.
    client = _mock_client([_fenced("[]")])
    sink: list[UsageRecord] = []
    with caplog.at_level(logging.INFO):
        rows = build_methods(
            claims, client=client, usage_sink=sink, context={"gene": "TACSTD2"}
        )
    assert rows == []
    # Exactly one model call (no repair loop).
    assert client.messages.create.call_count == 1
    # The user prompt sent to the model must contain only 25 claims.
    sent_kwargs = client.messages.create.call_args.kwargs
    user_msg_content = sent_kwargs["messages"][0]["content"]
    # Ledger header looks like "## A1 surface-method claims (N claims)"
    import re
    m = re.search(r"A1 surface-method claims \((\d+) claims\)", user_msg_content)
    assert m is not None, f"ledger header missing in prompt: {user_msg_content[:500]}"
    assert int(m.group(1)) == MAX_CLAIMS_TO_LLM, (
        f"expected {MAX_CLAIMS_TO_LLM} claims in user-prompt ledger, got {m.group(1)}"
    )
    # The top-ranked surface assays (h*/f* evidence_ids) must all survive;
    # the low-rank rt_qpcr ones (q*) must have been dropped first.
    assert "a1_evi_h00" in user_msg_content
    assert "a1_evi_f00" in user_msg_content
    # Confirm at least some rt_qpcr claims were dropped.
    qpcr_present_count = sum(
        1 for i in range(10) if f"a1_evi_q{i:02d}" in user_msg_content
    )
    assert qpcr_present_count < 10, (
        "all 10 rt_qpcr claims survived truncation; "
        "expected the cap to drop low-rank ones first"
    )
    # Truncation log emitted.
    truncation_msgs = [
        r.getMessage() for r in caplog.records
        if "truncated" in r.getMessage().lower()
    ]
    assert truncation_msgs, (
        "expected a log mentioning truncated; got: "
        f"{[r.getMessage() for r in caplog.records]}"
    )
    expected_kept = str(MAX_CLAIMS_TO_LLM)
    assert any("30" in m and expected_kept in m for m in truncation_msgs), (
        f"expected the truncation log to show 30 -> {expected_kept}; got: "
        f"{truncation_msgs}"
    )


def test_build_methods_no_truncation_when_under_cap() -> None:
    """When _select_input_claims returns <=25 claims, no truncation
    happens and all claims are sent to the LLM unchanged."""
    claims = [
        _claim(f"{i:02d}", evidence_type="flow_cytometry")
        for i in range(10)
    ]
    client = _mock_client([_fenced("[]")])
    sink: list[UsageRecord] = []
    rows = build_methods(
        claims, client=client, usage_sink=sink, context={"gene": "X"}
    )
    assert rows == []
    sent = client.messages.create.call_args.kwargs["messages"][0]["content"]
    import re
    m = re.search(r"A1 surface-method claims \((\d+) claims\)", sent)
    assert m is not None
    assert int(m.group(1)) == 10  # unchanged


# ---------------------------------------------------------------------------
# contradiction_builder
# ---------------------------------------------------------------------------


def test_build_contradictions_happy() -> None:
    claims = [
        _claim(
            "07",
            claim_type="contradictory",
            direction="refutes",
            evidence_type="immunofluorescence",
            quote="Permeabilized IF shows X is intracellular.",
        )
    ]
    output = [
        {
            "claim": "Permeabilized IF shows X is dominantly intracellular.",
            "contradiction_type": "intracellular_pool",
            "severity_for_surface_accessibility": "moderate",
            "likely_explanation": "Permeabilization reveals an ER pool.",
            "cited_evidence_ids": ["a1_evi_07"],
        }
    ]
    client = _mock_client([_fenced(json.dumps(output))])
    sink: list[UsageRecord] = []
    rows = build_contradictions(
        claims, client=client, usage_sink=sink, context={"gene": "X"}
    )
    assert len(rows) == 1
    assert isinstance(rows[0], Contradiction)


def test_build_contradictions_empty_input() -> None:
    claims = [_claim("01", claim_type="surface_expression", direction="supports")]
    client = _mock_client([])
    sink: list[UsageRecord] = []
    rows = build_contradictions(
        claims, client=client, usage_sink=sink, context={"gene": "X"}
    )
    assert rows == []
    client.messages.create.assert_not_called()


# ---------------------------------------------------------------------------
# evidence_grade_builder
# ---------------------------------------------------------------------------


def test_build_evidence_grade_happy() -> None:
    claims = [
        _claim("01", evidence_type="flow_cytometry"),
        _claim("02", evidence_type="rt_qpcr", claim_type="tissue_expression"),
    ]
    output = {
        "evidence_grade": "direct_single_method",
        "grade_rationale": "One direct flow cytometry observation.",
        "non_surface_expression": [
            {
                "context": "HEK293 cells",
                "sample_type": "established_cell_line",
                "measurement_type": "RNA",
                "level": "moderate",
                "cited_evidence_ids": ["a1_evi_02"],
            }
        ],
    }
    client = _mock_client([_fenced(json.dumps(output))])
    sink: list[UsageRecord] = []
    block = build_evidence_grade(
        claims, client=client, usage_sink=sink, context={"gene": "X"}
    )
    assert isinstance(block, EvidenceGradeBlock)
    assert block.evidence_grade == "direct_single_method"
    assert len(block.non_surface_expression) == 1
    assert block.non_surface_expression[0].cited_evidence_ids == ["a1_evi_02"]


def test_build_evidence_grade_empty_input_returns_default() -> None:
    client = _mock_client([])
    sink: list[UsageRecord] = []
    block = build_evidence_grade(
        [], client=client, usage_sink=sink, context={"gene": "X"}
    )
    assert block.evidence_grade == "weak"
    assert block.non_surface_expression == []


# ---------------------------------------------------------------------------
# expression_builder
# ---------------------------------------------------------------------------


def test_build_expression_happy() -> None:
    claims = [
        _claim(
            "01",
            prefix="a2",
            claim_type="tissue_expression",
            evidence_type="immunohistochemistry",
            source_id="PMID:222",
        ),
        _claim(
            "02",
            prefix="a2",
            claim_type="tissue_expression",
            evidence_type="rna_seq",
            source_id="PMID:333",
        ),
    ]
    output = [
        {
            "tissue": "cerebellum",
            "cell_type": "Purkinje neurons",
            "present": "high",
            "disease_context": "normal",
            "disease_label": None,
            "cell_states": [],
            "cited_evidence_ids": ["a2_evi_01", "a2_evi_02"],
        }
    ]
    client = _mock_client([_fenced(json.dumps(output))])
    sink: list[UsageRecord] = []
    rows = build_expression(
        claims, client=client, usage_sink=sink, context={"gene": "X"}
    )
    assert len(rows) == 1
    assert isinstance(rows[0], ExpressionRow)
    assert rows[0].tissue == "cerebellum"
    assert rows[0].cell_type == "Purkinje neurons"


def test_build_expression_empty_input() -> None:
    # No tissue_expression OR surface_expression claims → builder
    # short-circuits without a call. (As of the dual-dimension safety net,
    # surface_expression claims also qualify — they may carry a tissue
    # dimension under the load-bearing-point rule — so the empty-input
    # probe uses a claim_type that genuinely doesn't qualify.)
    claims = [_claim("01", prefix="a2", claim_type="topology")]
    client = _mock_client([])
    sink: list[UsageRecord] = []
    rows = build_expression(
        claims, client=client, usage_sink=sink, context={"gene": "X"}
    )
    assert rows == []
    client.messages.create.assert_not_called()


def test_build_expression_surface_expression_dual_dimension() -> None:
    # Safety net: a surface_expression claim is now also a candidate input —
    # the prompt decides whether its prose names a tissue / cell-type /
    # disease context that warrants an ExpressionRow.
    claims = [
        _claim(
            "01",
            prefix="a2",
            claim_type="surface_expression",
            evidence_type="immunofluorescence",
            source_id="PMID:444",
        ),
    ]
    output = [
        {
            "tissue": "liver",
            "cell_type": "Kupffer cell",
            "present": "low",
            "disease_context": "tumor",
            "disease_label": "hepatocellular carcinoma",
            "cell_states": [],
            "cited_evidence_ids": ["a2_evi_01"],
        }
    ]
    client = _mock_client([_fenced(json.dumps(output))])
    sink: list[UsageRecord] = []
    rows = build_expression(
        claims, client=client, usage_sink=sink, context={"gene": "X"}
    )
    assert len(rows) == 1
    assert rows[0].disease_context == "tumor"
    assert rows[0].cited_evidence_ids == ["a2_evi_01"]


# ---------------------------------------------------------------------------
# (former cell_states_builder tests retired in schema 2.5.0 — single-context
# state observations now emit as AccessibilityModulationObservation rows with
# baseline_context=None + modulating_state=None; see
# test_build_accessibility_modulation_* below for coverage.)
# ---------------------------------------------------------------------------


# ---------------------------------------------------------------------------
# subcellular_localization_builder
# ---------------------------------------------------------------------------


def test_build_subcellular_localization_happy() -> None:
    claims = [_claim("01", prefix="a2")]
    output = {
        "primary_compartment": "plasma_membrane",
        "dual_localization": [
            {
                "compartment": "endosome",
                "fraction_estimate": 0.2,
                "condition": "after agonist stim",
                "cited_evidence_ids": ["a2_evi_01"],
            }
        ],
        "membrane_subdomains": [
            {"subdomain": "lipid raft", "cited_evidence_ids": ["a2_evi_01"]}
        ],
    }
    client = _mock_client([_fenced(json.dumps(output))])
    sink: list[UsageRecord] = []
    block = build_subcellular_localization(
        claims, client=client, usage_sink=sink, context={"gene": "X"}
    )
    assert isinstance(block, SubcellularLocalization)
    assert block.primary_compartment == "plasma_membrane"
    assert len(block.dual_localization) == 1
    assert len(block.membrane_subdomains) == 1


def test_build_subcellular_localization_empty_input_returns_pm_default() -> None:
    client = _mock_client([])
    sink: list[UsageRecord] = []
    block = build_subcellular_localization(
        [], client=client, usage_sink=sink, context={"gene": "X"}
    )
    assert block.primary_compartment == "plasma_membrane"


# ---------------------------------------------------------------------------
# anatomical_accessibility_builder
# ---------------------------------------------------------------------------


def test_build_anatomical_accessibility_happy() -> None:
    claims = [_claim("01", prefix="a2")]
    output = [
        {
            "context": "intestinal epithelium",
            "orientation": "apical",
            "accessibility_implication": "restricted",
            "rationale": "Apical surface is tight-junction protected from systemic delivery.",
            "cited_evidence_ids": ["a2_evi_01"],
        }
    ]
    client = _mock_client([_fenced(json.dumps(output))])
    sink: list[UsageRecord] = []
    rows = build_anatomical_accessibility(
        claims, client=client, usage_sink=sink, context={"gene": "X"}
    )
    assert len(rows) == 1
    assert isinstance(rows[0], AnatomicalAccessibilityObservation)


def test_build_anatomical_accessibility_empty_returns_empty() -> None:
    client = _mock_client([])
    sink: list[UsageRecord] = []
    rows = build_anatomical_accessibility(
        [], client=client, usage_sink=sink, context={"gene": "X"}
    )
    assert rows == []


# ---------------------------------------------------------------------------
# accessibility_modulation_builder
# ---------------------------------------------------------------------------


def test_build_accessibility_modulation_happy() -> None:
    claims = [_claim("01", prefix="a2", quote="Activated T cells upregulate X.")]
    output = [
        {
            "category": "activation_induced",
            "category_other_label": None,
            "cell_state_trigger": "antigen_stimulation",
            "restricted_lineage": None,
            "dual_loc_partner_compartment": None,
            "baseline_context": "resting CD4 T cells",
            "modulating_state": "TCR-stimulated CD4 T cells",
            "change": "Surface X increases 5-fold within 24h of stimulation.",
            "accessibility_implication": "Activation-restricted surface availability favors specificity for activated cells.",
            "cited_evidence_ids": ["a2_evi_01"],
        }
    ]
    client = _mock_client([_fenced(json.dumps(output))])
    sink: list[UsageRecord] = []
    rows = build_accessibility_modulation(
        claims, client=client, usage_sink=sink, context={"gene": "X"}
    )
    assert len(rows) == 1
    assert isinstance(rows[0], AccessibilityModulationObservation)
    assert rows[0].category == "activation_induced"
    assert rows[0].cell_state_trigger == "antigen_stimulation"


def test_build_accessibility_modulation_drops_mispaired() -> None:
    """A row whose category-conditional pairing is invalid causes the whole
    array's Pydantic validation to fail (call_builder repair loop). After
    the repair budget is exhausted the builder returns []. Confirms the
    pairing rules are enforced and no invalid row leaks through."""
    claims = [_claim("01", prefix="a2")]
    bad_output = [
        # tissue_restricted_surface + cell_state_trigger → invalid pairing
        {
            "category": "tissue_restricted_surface",
            "category_other_label": None,
            "cell_state_trigger": "antigen_stimulation",
            "restricted_lineage": "hematopoietic",
            "dual_loc_partner_compartment": None,
            "baseline_context": "non-hematopoietic",
            "modulating_state": "hematopoietic lineage",
            "change": "X is restricted to hematopoietic lineage.",
            "accessibility_implication": "Restricted to hematopoietic surface.",
            "cited_evidence_ids": ["a2_evi_01"],
        },
    ]
    # Three responses to cover the MAX_REPAIRS=2 retries (initial + 2 repairs).
    client = _mock_client(
        [_fenced(json.dumps(bad_output))] * 3
    )
    sink: list[UsageRecord] = []
    rows = build_accessibility_modulation(
        claims, client=client, usage_sink=sink, context={"gene": "X"}
    )
    # All rows that survive must have valid category-conditional pairing.
    for r in rows:
        if r.category == "tissue_restricted_surface":
            assert r.cell_state_trigger is None
    # In this case no rows survive (all attempts were invalid).
    assert rows == []


def test_build_accessibility_modulation_empty() -> None:
    client = _mock_client([])
    sink: list[UsageRecord] = []
    rows = build_accessibility_modulation(
        [], client=client, usage_sink=sink, context={"gene": "X"}
    )
    assert rows == []


def test_build_accessibility_modulation_injects_tumor_pair_candidates() -> None:
    """When the A2 ledger has same-tissue normal-vs-tumor expression
    claims, the builder must inject a structured "candidate modulation
    rows derived from expression-level deltas" block into the user prompt
    so the LLM doesn't have to reconstruct the pair from prose.

    Verifies the deterministic detector that addresses the TACSTD2 amod
    regression (18→0 from v2.8.0 to v2.35.0): the v2.8.0 builder lifted
    6× ``disease_state_induced × oncogenic_transformation`` rows from
    normal-vs-cancer expression pairs that the model is no longer
    reliably reconstructing under temperature=1.0."""
    claims = [
        _claim(
            "01",
            prefix="a2",
            claim_type="tissue_expression",
            evidence_type="immunohistochemistry",
            source_id="PMID:111",
            quote=(
                "TROP2 is undetectable by IHC in normal colonic epithelium."
            ),
        ),
        _claim(
            "02",
            prefix="a2",
            claim_type="tissue_expression",
            evidence_type="immunohistochemistry",
            source_id="PMID:222",
            quote=(
                "TROP2 expression is high in colorectal tumor tissue compared "
                "to normal colon, with heterogeneous membranous staining."
            ),
        ),
        # An unrelated claim that should NOT pair (no tumor signal).
        _claim(
            "03",
            prefix="a2",
            quote="TROP2 is expressed on the surface of HEK293 cells.",
        ),
    ]
    # The model returns []; we only care what got SENT in the user prompt.
    client = _mock_client([_fenced("[]")])
    sink: list[UsageRecord] = []
    rows = build_accessibility_modulation(
        claims, client=client, usage_sink=sink, context={"gene": "TACSTD2"}
    )
    assert rows == []
    assert client.messages.create.call_count == 1
    sent_user_msg = client.messages.create.call_args.kwargs["messages"][0][
        "content"
    ]
    assert "candidate modulation rows" in sent_user_msg.lower(), (
        "expected the prompt to inject a tumor-pair candidate block; "
        f"got: {sent_user_msg[:500]}"
    )
    # Both paired evidence_ids must appear in the candidates section so
    # the LLM can cite them.
    assert "a2_evi_01" in sent_user_msg
    assert "a2_evi_02" in sent_user_msg


# ---------------------------------------------------------------------------
# Synthetic source store + draft assembly
# ---------------------------------------------------------------------------


def test_synthetic_source_store_supports_promote() -> None:
    """Round-trip a claim through the synthetic store + promote_claim."""
    from accessible_surfaceome.agents._support.evidence_promotion import promote_claim

    claims = [
        _claim("01", quote="X is expressed on the surface of HEK293 cells."),
        _claim("02", quote="A second verbatim sentence from the same source.",
               source_id="PMID:11111"),
    ]
    store = _synthetic_source_store(claims)
    for c in claims:
        ev = promote_claim(c, store=store)
        assert ev.entailment_verified is True
        assert len(ev.spans) == 1
        assert ev.spans[0].quote == c.quote


# ---------------------------------------------------------------------------
# End-to-end schema validation — assemble a full SurfaceomeRecord
# ---------------------------------------------------------------------------


def test_surface_evidence_draft_validates_with_block_builder_outputs() -> None:
    """If the block-builders return valid blocks for the input ledger,
    the SurfaceEvidenceDraft wrapper should validate."""
    a1_claims = [
        _claim("01", evidence_type="flow_cytometry"),
        _claim("02", evidence_type="surface_biotinylation"),
    ]
    se = SurfaceEvidence(
        evidence_grade="direct_multi_method",
        grade_rationale="Flow + biotinylation.",
        methods=[
            MethodObservation(
                method_family="flow_cytometry",
                method_subclass="live_cell_flow",
                permeabilization="nonpermeabilized",
                expression_system="endogenous",
                antibodies=[],
                accessibility_relevance="direct_surface_accessibility",
                surface_claim_type="surface_accessible",
                expression_observations=[],
                cited_evidence_ids=["a1_evi_01"],
            ),
            # direct_multi_method requires ≥2 direct methods from ≥2 distinct
            # sources — pair the flow row with a surface-biotinylation row
            # citing the SECOND evidence_id so the cross-block validator
            # (_check_evidence_grade_methods_cardinality) accepts the grade.
            MethodObservation(
                method_family="biotinylation",
                method_subclass="surface_biotinylation",
                permeabilization="live_cell",
                expression_system="endogenous",
                antibodies=[],
                accessibility_relevance="direct_surface_accessibility",
                surface_claim_type="surface_accessible",
                expression_observations=[],
                cited_evidence_ids=["a1_evi_02"],
            ),
        ],
        non_surface_expression=[],
        contradicting_evidence=[],
    )
    draft = SurfaceEvidenceDraft(surface_evidence=se, evidence_claims=a1_claims)
    assert len(draft.surface_evidence.methods) == 2


def test_biological_context_draft_validates_with_block_builder_outputs() -> None:
    a2_claims = [
        _claim("01", prefix="a2", claim_type="tissue_expression"),
        _claim("02", prefix="a2"),
    ]
    bc = BiologicalContext(
        expression=[
            ExpressionRow(
                tissue="cerebellum",
                cell_type="Purkinje neurons",
                present="high",
                disease_context="normal",
                cited_evidence_ids=["a2_evi_01"],
            )
        ],
        subcellular_localization=SubcellularLocalization(
            primary_compartment="plasma_membrane",
            dual_localization=[],
            membrane_subdomains=[],
        ),
        anatomical_accessibility=[],
        accessibility_modulation=[],
    )
    draft = BiologicalContextDraft(
        biological_context=bc, evidence_claims=a2_claims
    )
    assert len(draft.biological_context.expression) == 1


def test_block_counts_helper() -> None:
    from accessible_surfaceome.agents.surfaceome_v2.orchestrator import _count_blocks

    se = SurfaceEvidence(
        evidence_grade="weak",
        grade_rationale="rationale",
        methods=[],
        non_surface_expression=[],
        contradicting_evidence=[],
    )
    bc = BiologicalContext(
        expression=[],
        subcellular_localization=SubcellularLocalization(
            primary_compartment="plasma_membrane",
            dual_localization=[],
            membrane_subdomains=[],
        ),
        anatomical_accessibility=[],
        accessibility_modulation=[],
    )
    counts = _count_blocks(se, bc)
    assert counts["methods"] == 0
    assert counts["expression"] == 0


# ---------------------------------------------------------------------------
# max_tokens cutoff detection in call_builder repair loop
# ---------------------------------------------------------------------------


def test_call_builder_logs_max_tokens_truncation(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """When the first response is truncated by ``stop_reason="max_tokens"``,
    the repair-loop log must say "output truncated at max_tokens" — not
    the generic "no fenced JSON block" — so an operator immediately knows
    to bump the per-builder token cap rather than chasing prompt issues.

    Second response is a clean valid JSON object so the repair loop
    recovers and ``call_builder`` returns the parsed model.
    """
    import logging

    from accessible_surfaceome.agents.surfaceome_v2.builders._common import (
        call_builder,
    )
    from accessible_surfaceome.tools._shared.models import EvidenceGrade

    # Minimal Pydantic shape for the test — just need ANY validating model.
    class _Block(BaseModel):
        model_config = ConfigDict(extra="forbid")
        evidence_grade: EvidenceGrade
        grade_rationale: str

    # First response: looks like the start of a fenced JSON block but
    # was cut off before the closing fence — the realistic
    # max_tokens-truncation shape.
    truncated_text = (
        '```json\n{\n  "evidence_grade": "direct_multi_method",\n'
        '  "grade_rationale": "Strong evidence from multiple direct surface '
    )
    # Second response: clean valid JSON object.
    clean_text = _fenced(
        '{"evidence_grade": "direct_multi_method",'
        ' "grade_rationale": "Strong evidence from multiple direct surface assays."}'
    )
    client = _mock_client_with_stops(
        [
            (truncated_text, "max_tokens"),
            (clean_text, "end_turn"),
        ]
    )

    with caplog.at_level(logging.WARNING):
        parsed = call_builder(
            client,
            system_prompt="(test system prompt)",
            user_prompt="(test user prompt)",
            schema=_Block,
            usage_sink=[],
            label="test_builder",
            max_tokens=512,
        )

    # call_builder recovered on retry.
    assert isinstance(parsed, _Block)
    assert parsed.evidence_grade == "direct_multi_method"

    # The max_tokens-truncation log fired (this is the key contract:
    # an operator reading the log sees "bump max_tokens", not
    # "no fenced JSON block").
    max_tokens_logs = [
        rec.getMessage() for rec in caplog.records
        if "max_tokens" in rec.getMessage().lower()
    ]
    assert max_tokens_logs, (
        "expected a log mentioning max_tokens; got: "
        f"{[r.getMessage() for r in caplog.records]}"
    )
    assert any("test_builder" in m for m in max_tokens_logs)


def test_call_builder_no_false_max_tokens_warning_on_clean_completion() -> None:
    """The max_tokens log path must NOT fire when stop_reason is
    ``end_turn`` (the normal case). Verifies the if-guard."""
    import logging

    from accessible_surfaceome.agents.surfaceome_v2.builders._common import (
        call_builder,
    )
    from accessible_surfaceome.tools._shared.models import EvidenceGrade

    class _Block(BaseModel):
        model_config = ConfigDict(extra="forbid")
        evidence_grade: EvidenceGrade
        grade_rationale: str

    clean_text = _fenced(
        '{"evidence_grade": "weak", "grade_rationale": "test rationale"}'
    )
    client = _mock_client([clean_text])

    import io
    log_stream = io.StringIO()
    handler = logging.StreamHandler(log_stream)
    handler.setLevel(logging.INFO)
    logger = logging.getLogger(
        "accessible_surfaceome.agents.surfaceome_v2.builders._common"
    )
    logger.addHandler(handler)
    try:
        parsed = call_builder(
            client,
            system_prompt="x",
            user_prompt="x",
            schema=_Block,
            usage_sink=[],
            label="quiet_builder",
            max_tokens=1024,
        )
    finally:
        logger.removeHandler(handler)

    assert isinstance(parsed, _Block)
    assert "max_tokens" not in log_stream.getvalue().lower()


# Used only to silence ruff's unused-import warning for AssayContext (kept
# for fixture clarity).
_ = AssayContext
_ = datetime  # used by mock helper future expansion
_ = UTC
