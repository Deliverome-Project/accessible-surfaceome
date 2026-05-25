"""Tests for the full-TriageRecord piping into v2's planner + synthesizer.

PR #23 design doc §1110-1116 calls for a "common preamble" that delivers
the full TriageRecord (verdict + verdict_reasoning + reason taxonomy +
key_uncertainty + confidence) to every downstream agent. v2 previously
only loaded the rolled-up `triage_signal` enum; these tests verify the
full-record path:

1. ``_summarize_triage_for_planner`` produces a JSON the planner can
   scan inline.
2. ``GeneContext`` carries ``triage_summary_json`` and ``_build_gene_context``
   tolerates the no-triage case (sets it to ``None``).
3. ``_run_planner`` and ``_run_selector`` user prompts include the
   ``"Triage prior"`` section when present and omit it when absent.
4. The A1 + A2 plan system prompts each contain a "Triage prior"
   section + the synthesizer prompt does too.
5. The synthesizer's ``_build_task`` includes the Triage-prior section
   when ``triage_summary_json`` is set.
"""

from __future__ import annotations

import json
from unittest.mock import MagicMock, patch

from accessible_surfaceome.agents.plan_trim_select.runner import (
    A1_PLAN_PROMPT_PATH,
    A2_PLAN_PROMPT_PATH,
    GeneContext,
    _summarize_triage_for_planner,
)
from accessible_surfaceome.agents.surfaceome_synthesizer.runner import (
    SYSTEM_PROMPT_PATH as SYNTH_SYSTEM_PROMPT_PATH,
    _build_task as _synth_build_task,
)
from accessible_surfaceome.tools._shared.models import (
    GeneIdentifier,
    IdentifierBundle,
    TriageRecord,
)


def _hspa5_triage_record() -> TriageRecord:
    """Canonical csGRP78 contextual-verdict triage fixture."""
    return TriageRecord(
        gene=GeneIdentifier(
            hgnc_symbol="HSPA5",
            hgnc_id="HGNC:5238",
            uniprot_acc="P11021",
        ),
        verdict="contextual",
        verdict_reasoning=(
            "HSPA5 / GRP78 is canonically an ER-lumenal chaperone with a "
            "C-terminal KDEL ER-retention motif, but the cancer "
            "literature has 20+ years of reports of cell-surface GRP78 "
            "(csGRP78) under ER stress, oncogenic transformation, and "
            "in tumor microenvironments. Surface presentation is "
            "state-dependent — not a steady-state surface marker."
        ),
        reason="cell_state_induced",
        confidence="medium",
        key_uncertainty=(
            "Mechanism of ER-to-PM translocation under stress is "
            "unresolved; multiple competing models exist."
        ),
    )


def _bundle() -> IdentifierBundle:
    return IdentifierBundle(
        hgnc_symbol="HSPA5",
        hgnc_id="HGNC:5238",
        uniprot_acc="P11021",
        previous_symbols=[],
        aliases=[],
    )


# ---------------------------------------------------------------------------
# Serializer
# ---------------------------------------------------------------------------


def test_summary_includes_all_five_fields():
    record = _hspa5_triage_record()
    out = json.loads(_summarize_triage_for_planner(record))
    assert out["verdict"] == "contextual"
    assert out["reason"] == "cell_state_induced"
    assert "ER-lumenal chaperone" in out["verdict_reasoning"]
    assert "unresolved" in out["key_uncertainty"]
    assert out["confidence"] == "medium"


def test_triage_record_rejects_legacy_model_path_field():
    """The legacy ``model_path`` closed-enum field was removed in favor
    of the ``provenance`` block. TriageRecord uses ``extra="forbid"``,
    so passing ``model_path`` as a kwarg should raise."""
    import pytest
    from pydantic import ValidationError

    with pytest.raises(ValidationError):
        TriageRecord(
            gene=GeneIdentifier(
                hgnc_symbol="HSPA5", hgnc_id="HGNC:5238", uniprot_acc="P11021"
            ),
            verdict="contextual",
            verdict_reasoning="...",
            reason="cell_state_induced",
            confidence="medium",
            model_path="haiku_only",  # ty:ignore[unknown-argument]
        )


def test_summary_omits_model_path_key():
    """The summarizer JSON injected into planners + synthesizer must
    not carry the removed model_path field."""
    out = json.loads(_summarize_triage_for_planner(_hspa5_triage_record()))
    assert "model_path" not in out


# ---------------------------------------------------------------------------
# Provenance threading (D1 loader → TriageRecord → summarizer → planner)
# ---------------------------------------------------------------------------


def test_d1_loader_populates_provenance_from_row():
    """_triage_record_from_d1_row must thread model + prompt_variant +
    run_id + replicate from the D1 row into a TriageProvenance block on
    the TriageRecord, so the synthesizer can see which model + variant
    actually ran the triage (rather than the default model_path enum).
    """
    from accessible_surfaceome.agents.surfaceome_v1.orchestrator import (
        _triage_record_from_d1_row,
    )

    row: dict[str, object] = {
        "predicted_verdict": "no",
        "predicted_reason": "inner_leaflet_anchored",
        "predicted_confidence": "high",
        "predicted_key_uncertainty": None,
        "verdict_reasoning": "SRC is myristoylated and tethered to the inner leaflet.",
        "uniprot_acc": "P12931",
        "model": "claude-sonnet-4-6",
        "prompt_variant": "ncbi",
        "run_id": "mainbench_canonical_v1",
        "replicate": 1,
    }

    record = _triage_record_from_d1_row("SRC", row)
    assert record is not None
    assert record.provenance is not None
    assert record.provenance.model == "claude-sonnet-4-6"
    assert record.provenance.prompt_variant == "ncbi"
    assert record.provenance.run_id == "mainbench_canonical_v1"
    assert record.provenance.replicate == 1


def test_summary_omits_provenance_even_when_set():
    """The summary JSON injected into planners + synthesizer carries ONLY
    verdict / reason / verdict_reasoning / key_uncertainty / confidence.
    Provenance is preserved on the TriageRecord for audit/logging but
    must NOT leak into the prompt — the LLM should weight the prior on
    confidence + reasoning prose, not on model identity."""
    from accessible_surfaceome.tools._shared.models import TriageProvenance

    record = _hspa5_triage_record().model_copy(
        update={
            "provenance": TriageProvenance(
                model="claude-sonnet-4-6",
                prompt_variant="ncbi",
                run_id="mainbench_canonical_v1",
                replicate=1,
            )
        }
    )
    out = json.loads(_summarize_triage_for_planner(record))
    assert "provenance" not in out
    # exactly the five fields the user enumerated
    assert set(out.keys()) == {
        "verdict",
        "reason",
        "verdict_reasoning",
        "key_uncertainty",
        "confidence",
    }


def test_synthesizer_prompt_does_not_reference_provenance():
    """The synthesizer prompt must not instruct the model to read a
    field it never receives — provenance is intentionally withheld
    from the prompt JSON."""
    body = SYNTH_SYSTEM_PROMPT_PATH.read_text().lower()
    assert "provenance" not in body


def test_d1_loader_fills_gene_identifier_when_row_provided():
    """When the D1 loader gets the gene_identifier_public row alongside
    the triage_run_public row, it populates the full GeneIdentifier
    (hgnc_id, ncbi_gene_id, ensembl_gene) instead of empty placeholders."""
    from accessible_surfaceome.agents.surfaceome_v1.orchestrator import (
        _triage_record_from_d1_row,
    )

    triage_row: dict[str, object] = {
        "predicted_verdict": "no",
        "predicted_reason": "inner_leaflet_anchored",
        "predicted_confidence": "high",
        "predicted_key_uncertainty": None,
        "verdict_reasoning": "SRC is myristoylated and tethered to the inner leaflet.",
        "uniprot_acc": "P12931",
        "model": "claude-sonnet-4-6",
        "prompt_variant": "ncbi",
        "run_id": "mainbench_canonical_v1",
        "replicate": 1,
    }
    identifier_row: dict[str, object] = {
        "hgnc_id": "HGNC:11283",
        "ncbi_gene_id": 6714,
        "ensembl_gene": "ENSG00000197122",
    }

    record = _triage_record_from_d1_row(
        "SRC", triage_row, identifier_row=identifier_row
    )
    assert record is not None
    assert record.gene.hgnc_symbol == "SRC"
    assert record.gene.hgnc_id == "HGNC:11283"
    assert record.gene.uniprot_acc == "P12931"
    assert record.gene.ncbi_gene_id == 6714
    assert record.gene.ensembl_gene == "ENSG00000197122"


def test_d1_loader_tolerates_missing_identifier_row():
    """When the identifier_row is absent (failed extra lookup), the
    loader falls back gracefully — verdict + reasoning still load,
    only the per-gene IDs are blank."""
    from accessible_surfaceome.agents.surfaceome_v1.orchestrator import (
        _triage_record_from_d1_row,
    )

    triage_row: dict[str, object] = {
        "predicted_verdict": "no",
        "predicted_reason": "inner_leaflet_anchored",
        "predicted_confidence": "high",
        "predicted_key_uncertainty": None,
        "verdict_reasoning": "SRC tethered to inner leaflet.",
        "uniprot_acc": "P12931",
        "model": "claude-sonnet-4-6",
        "prompt_variant": "ncbi",
        "run_id": "mainbench_canonical_v1",
        "replicate": 1,
    }
    record = _triage_record_from_d1_row("SRC", triage_row, identifier_row=None)
    assert record is not None
    assert record.gene.hgnc_symbol == "SRC"
    assert record.gene.uniprot_acc == "P12931"
    # Verdict + reasoning still populated
    assert record.verdict == "no"


def test_summary_handles_none_key_uncertainty():
    record = _hspa5_triage_record().model_copy(update={"key_uncertainty": None})
    out = json.loads(_summarize_triage_for_planner(record))
    assert out["key_uncertainty"] is None


# ---------------------------------------------------------------------------
# GeneContext
# ---------------------------------------------------------------------------


def test_gene_context_carries_triage_field():
    ctx = GeneContext(
        gene="HSPA5",
        bundle=_bundle(),
        uniprot_summary_json="{}",
        db_panel_json="{}",
        triage_summary_json='{"verdict": "contextual"}',
    )
    assert ctx.triage_summary_json == '{"verdict": "contextual"}'


def test_gene_context_triage_field_defaults_to_none():
    ctx = GeneContext(
        gene="HSPA5",
        bundle=_bundle(),
        uniprot_summary_json="{}",
        db_panel_json="{}",
    )
    assert ctx.triage_summary_json is None


# ---------------------------------------------------------------------------
# Planner / selector user-prompt injection
# ---------------------------------------------------------------------------


def test_planner_prompt_includes_triage_block_when_present():
    """``_run_planner`` must include the Triage-prior section when
    ``GeneContext.triage_summary_json`` is set."""
    from accessible_surfaceome.agents.plan_trim_select import runner

    ctx = GeneContext(
        gene="HSPA5",
        bundle=_bundle(),
        uniprot_summary_json="{}",
        db_panel_json="{}",
        triage_summary_json=(
            '{"verdict": "contextual", "reason": "cell_state_induced", '
            '"verdict_reasoning": "...ER stress..."}'
        ),
    )

    captured: dict[str, str] = {}

    def _fake_repair(client, *, system_prompt, user_prompt, **kw):
        captured["user_prompt"] = user_prompt
        return None, "", ""

    with patch.object(runner, "_call_with_repair", _fake_repair):
        runner._run_planner(
            client=MagicMock(),
            context=ctx,
            usage_sink=[],
            plan_prompt_path=runner.A1_PLAN_PROMPT_PATH,
        )

    assert "Triage prior" in captured["user_prompt"]
    assert "contextual" in captured["user_prompt"]
    assert "cell_state_induced" in captured["user_prompt"]


def test_planner_prompt_omits_triage_block_when_absent():
    from accessible_surfaceome.agents.plan_trim_select import runner

    ctx = GeneContext(
        gene="HSPA5",
        bundle=_bundle(),
        uniprot_summary_json="{}",
        db_panel_json="{}",
        triage_summary_json=None,
    )

    captured: dict[str, str] = {}

    def _fake_repair(client, *, system_prompt, user_prompt, **kw):
        captured["user_prompt"] = user_prompt
        return None, "", ""

    with patch.object(runner, "_call_with_repair", _fake_repair):
        runner._run_planner(
            client=MagicMock(),
            context=ctx,
            usage_sink=[],
            plan_prompt_path=runner.A2_PLAN_PROMPT_PATH,
        )

    assert "Triage prior" not in captured["user_prompt"]


# ---------------------------------------------------------------------------
# Prompt-content tripwires
# ---------------------------------------------------------------------------


def test_a1_plan_prompt_mentions_triage_prior():
    body = A1_PLAN_PROMPT_PATH.read_text().lower()
    assert "triage prior" in body
    assert "verdict_reasoning" in body
    assert "key_uncertainty" in body


def test_a2_plan_prompt_mentions_triage_prior():
    body = A2_PLAN_PROMPT_PATH.read_text().lower()
    assert "triage prior" in body
    assert "verdict_reasoning" in body
    assert "cell_state_induced" in body


def test_synthesizer_prompt_mentions_triage_prior():
    body = SYNTH_SYSTEM_PROMPT_PATH.read_text().lower()
    assert "triage prior" in body
    assert "verdict_reasoning" in body


# ---------------------------------------------------------------------------
# Synthesizer task-message injection
# ---------------------------------------------------------------------------


def test_synthesizer_task_includes_triage_block_when_present():
    triage_json = (
        '{"verdict": "contextual", "reason": "cell_state_induced", '
        '"verdict_reasoning": "...ER stress..."}'
    )
    task = _synth_build_task(
        "HSPA5",
        a1_draft={
            "evidence_grade": "weak",
            "grade_rationale": "",
            "methods": [],
            "evidence": [],
        },
        a2_draft=None,
        triage_summary_json=triage_json,
    )
    assert "Triage prior" in task
    assert "cell_state_induced" in task


def test_synthesizer_task_omits_triage_block_when_absent():
    task = _synth_build_task(
        "HSPA5",
        a1_draft={
            "evidence_grade": "weak",
            "grade_rationale": "",
            "methods": [],
            "evidence": [],
        },
        a2_draft=None,
        triage_summary_json=None,
    )
    assert "Triage prior" not in task
