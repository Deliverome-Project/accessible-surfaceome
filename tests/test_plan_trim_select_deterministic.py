"""Tests for the deterministic-feature wiring into plan_trim_select.

Verifies:

1. ``_summarize_deterministic_for_planner`` produces a compact JSON the
   planner can read, with the four signals A1/A2 prompts reference
   (tm_helix_count, paralog top-N, mouse/cyno ortholog ECD identity).
2. ``GeneContext`` carries ``deterministic_summary_json`` and the
   ``_build_gene_context`` builder tolerates D1 unreachable (sets it
   to ``None`` so the planner prompts skip the block).
3. ``_run_planner`` and ``_run_selector`` user prompts include the
   ``"Deterministic inputs"`` header when the summary is present and
   omit it when absent.
4. The A1 and A2 plan system prompts each contain a "Deterministic
   inputs" section so the planner knows the JSON block exists and how
   to weight it.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime
from unittest.mock import MagicMock, patch

from accessible_surfaceome.agents.plan_trim_select.runner import (
    A1_PLAN_PROMPT_PATH,
    A2_PLAN_PROMPT_PATH,
    GeneContext,
    _summarize_deterministic_for_planner,
)
from accessible_surfaceome.tools._shared.models import (
    DeterministicFeatures,
    IdentifierBundle,
    IsoformTopology,
    OrthologEntry,
    Orthologs,
    ParalogEntry,
    StructureFeatures,
)


def _gpr75_features() -> DeterministicFeatures:
    canon = IsoformTopology(
        isoform_id="O95800-1",
        uniprot_acc="O95800",
        tm_helix_count=7,
        n_terminal_orientation="extracellular",
        c_terminal_orientation="cytoplasmic",
        signal_peptide_length=0,
        ecd_length_residues=89,
        icd_length_residues=123,
        per_residue_topology="o" * 89 + "M" * 21 * 7 + "i" * 123,
        tool_version="deeptmhmm-1.0.24",
        retrieved_at=datetime.now(UTC),
    )
    mouse_canon = OrthologEntry(
        is_canonical=True,
        isoform_id="Q6X632-1",
        ensembl_id="ENSMUSG00000074882",
        ortholog_uniprot_acc="Q6X632",
        ortholog_symbol="GPR75_MOUSE",
        type="one2one",
        ecd_pct_identity_to_human_canonical=74.2,
        ecd_pct_similarity_to_human_canonical=82.0,
        ecd_length_residues=89,
        tm_helix_count=7,
        compara_version="r112",
        retrieved_at=datetime.now(UTC),
    )
    cyno_canon = OrthologEntry(
        is_canonical=True,
        isoform_id="A0A7N9DAV0-1",
        ensembl_id="ENSMFAG00000023456",
        ortholog_uniprot_acc="A0A7N9DAV0",
        ortholog_symbol="A0A7N9DAV0_MACFA",
        type="one2one",
        ecd_pct_identity_to_human_canonical=98.9,
        ecd_pct_similarity_to_human_canonical=99.5,
        ecd_length_residues=89,
        tm_helix_count=7,
        compara_version="r112",
        retrieved_at=datetime.now(UTC),
    )
    return DeterministicFeatures(
        canonical_topology=canon,
        isoform_topologies=[canon],
        paralogs=[
            ParalogEntry(
                paralog_symbol="OR9G1",
                paralog_uniprot_acc="Q8NH87",
                ecd_pct_identity=35.7,
                family_id="OR_family",
                compara_version="r112",
            ),
            ParalogEntry(
                paralog_symbol="GPR19",
                paralog_uniprot_acc="Q15760",
                ecd_pct_identity=28.7,
                family_id="GPR_family",
                compara_version="r112",
            ),
        ],
        orthologs=Orthologs(mouse=[mouse_canon], cynomolgus=[cyno_canon]),
        structure=StructureFeatures(
            afdb_id="AF-O95800-F1-model_v4",
            afdb_version="v4",
            ecd_mean_plddt=0.0,
            ecd_disordered_fraction=0.0,
            source="stub",
            license="CC BY 4.0",
            attribution="© DeepMind / EMBL-EBI",
        ),
    )


def test_summary_includes_tm_paralog_ortholog():
    out = json.loads(_summarize_deterministic_for_planner(_gpr75_features()))
    assert out["tm_helix_count"] == 7
    assert out["ecd_length_residues"] == 89
    assert out["signal_peptide_length"] == 0
    assert out["paralog_count"] == 2
    assert out["top_paralogs"][0]["symbol"] == "OR9G1"
    assert out["top_paralogs"][0]["ecd_pct_identity"] == 35.7
    assert out["mouse_ortholog_ecd_pct_identity"] == 74.2
    assert out["cyno_ortholog_ecd_pct_identity"] == 98.9
    assert out["mouse_ortholog_symbol"] == "GPR75_MOUSE"
    assert out["cyno_ortholog_symbol"] == "A0A7N9DAV0_MACFA"
    assert out["mouse_ortholog_count"] == 1
    assert out["cyno_ortholog_count"] == 1


def test_summary_omits_tool_version():
    """``tool_version`` is audit metadata for the DeterministicFeatures
    record itself — not signal the planner LLM needs. Withheld from the
    injected summary to keep the prompt focused on decision-driving
    fields (topology, paralog/ortholog cutoffs)."""
    out = json.loads(_summarize_deterministic_for_planner(_gpr75_features()))
    assert "tool_version" not in out


def test_summary_counts_all_orthologs_not_just_canonical():
    """mouse_ortholog_count / cyno_ortholog_count are aggregate counts
    of every ortholog entry returned by Compara — not just the canonical
    one. Lets the planner spot one-to-many cross-species mappings (where
    cross-reactivity warnings matter) without losing the canonical
    ECD-identity signal."""
    feats = _gpr75_features()
    extra_mouse_iso = OrthologEntry(
        is_canonical=False,
        isoform_id="Q6X632-2",
        ensembl_id="ENSMUSG00000074882",
        ortholog_uniprot_acc="Q6X632-2",
        ortholog_symbol="GPR75_MOUSE_iso2",
        type="one2one",
        ecd_pct_identity_to_human_canonical=50.0,
        ecd_pct_similarity_to_human_canonical=60.0,
        ecd_length_residues=89,
        tm_helix_count=7,
        compara_version="r112",
        retrieved_at=datetime.now(UTC),
    )
    feats = feats.model_copy(
        update={
            "orthologs": Orthologs(
                mouse=list(feats.orthologs.mouse) + [extra_mouse_iso],
                cynomolgus=list(feats.orthologs.cynomolgus),
            )
        }
    )
    out = json.loads(_summarize_deterministic_for_planner(feats))
    assert out["mouse_ortholog_count"] == 2
    assert out["cyno_ortholog_count"] == 1
    # Canonical identity signal preserved
    assert out["mouse_ortholog_ecd_pct_identity"] == 74.2


def test_summary_zero_ortholog_counts_when_empty():
    feats = _gpr75_features().model_copy(update={"orthologs": Orthologs()})
    out = json.loads(_summarize_deterministic_for_planner(feats))
    assert out["mouse_ortholog_count"] == 0
    assert out["cyno_ortholog_count"] == 0


def test_summary_handles_no_orthologs():
    feats = _gpr75_features().model_copy(update={"orthologs": Orthologs()})
    out = json.loads(_summarize_deterministic_for_planner(feats))
    assert out["mouse_ortholog_ecd_pct_identity"] is None
    assert out["cyno_ortholog_ecd_pct_identity"] is None
    assert out["mouse_ortholog_symbol"] is None
    assert out["cyno_ortholog_symbol"] is None


def test_summary_caps_paralogs_at_5():
    feats = _gpr75_features()
    feats = feats.model_copy(
        update={
            "paralogs": [
                ParalogEntry(
                    paralog_symbol=f"P{i}",
                    paralog_uniprot_acc=f"Q{i:05d}",
                    ecd_pct_identity=50.0 - i,
                    family_id="fam",
                    compara_version="r112",
                )
                for i in range(20)
            ]
        }
    )
    out = json.loads(_summarize_deterministic_for_planner(feats))
    assert len(out["top_paralogs"]) == 5
    assert out["top_paralogs"][0]["ecd_pct_identity"] == 50.0
    assert out["top_paralogs"][4]["ecd_pct_identity"] == 46.0
    assert out["paralog_count"] == 20


def test_summary_picks_canonical_ortholog_when_multiple():
    feats = _gpr75_features()
    non_canon_mouse = OrthologEntry(
        is_canonical=False,
        isoform_id="Q6X632-2",
        ensembl_id="ENSMUSG00000074882",
        ortholog_uniprot_acc="Q6X632-2",
        ortholog_symbol="GPR75_MOUSE_iso2",
        type="one2one",
        ecd_pct_identity_to_human_canonical=50.0,
        ecd_pct_similarity_to_human_canonical=60.0,
        ecd_length_residues=89,
        tm_helix_count=7,
        compara_version="r112",
        retrieved_at=datetime.now(UTC),
    )
    feats = feats.model_copy(
        update={
            "orthologs": Orthologs(
                mouse=[non_canon_mouse] + list(feats.orthologs.mouse),
                cynomolgus=list(feats.orthologs.cynomolgus),
            )
        }
    )
    out = json.loads(_summarize_deterministic_for_planner(feats))
    assert out["mouse_ortholog_ecd_pct_identity"] == 74.2


def test_gene_context_has_deterministic_field():
    ctx = GeneContext(
        gene="GPR75",
        bundle=IdentifierBundle(
            hgnc_id="HGNC:4526",
            hgnc_symbol="GPR75",
            uniprot_acc="O95800",
            previous_symbols=[],
            aliases=[],
        ),
        uniprot_summary_json="{}",
        db_panel_json="{}",
        deterministic_summary_json='{"tm_helix_count": 7}',
    )
    assert ctx.deterministic_summary_json == '{"tm_helix_count": 7}'


def test_gene_context_deterministic_field_can_be_none():
    ctx = GeneContext(
        gene="GPR75",
        bundle=IdentifierBundle(
            hgnc_id="HGNC:4526",
            hgnc_symbol="GPR75",
            uniprot_acc="O95800",
            previous_symbols=[],
            aliases=[],
        ),
        uniprot_summary_json="{}",
        db_panel_json="{}",
        deterministic_summary_json=None,
    )
    assert ctx.deterministic_summary_json is None


def test_planner_user_prompt_includes_deterministic_block_when_present():
    """``_run_planner`` must include the Deterministic-inputs JSON in the
    user prompt when ``GeneContext.deterministic_summary_json`` is set."""
    from accessible_surfaceome.agents.plan_trim_select import runner

    ctx = GeneContext(
        gene="GPR75",
        bundle=IdentifierBundle(
            hgnc_id="HGNC:4526",
            hgnc_symbol="GPR75",
            uniprot_acc="O95800",
            previous_symbols=[],
            aliases=[],
        ),
        uniprot_summary_json="{}",
        db_panel_json="{}",
        deterministic_summary_json='{"tm_helix_count": 7, "paralog_count": 32}',
    )

    captured: dict[str, str] = {}

    def _fake_repair(client, *, system_prompt, user_prompt, **kw):
        captured["system_prompt"] = system_prompt
        captured["user_prompt"] = user_prompt
        return None, "", ""

    with patch.object(runner, "_call_with_repair", _fake_repair):
        runner._run_planner(
            client=MagicMock(),
            context=ctx,
            usage_sink=[],
            plan_prompt_path=runner.A1_PLAN_PROMPT_PATH,
        )

    assert "Deterministic inputs" in captured["user_prompt"]
    assert '"tm_helix_count": 7' in captured["user_prompt"]
    assert '"paralog_count": 32' in captured["user_prompt"]


def test_planner_user_prompt_omits_deterministic_block_when_absent():
    """When ``deterministic_summary_json`` is None (D1 unreachable), the
    block must not appear — planners should fall back to UniProt-only
    planning, not see a confusing empty section."""
    from accessible_surfaceome.agents.plan_trim_select import runner

    ctx = GeneContext(
        gene="GPR75",
        bundle=IdentifierBundle(
            hgnc_id="HGNC:4526",
            hgnc_symbol="GPR75",
            uniprot_acc="O95800",
            previous_symbols=[],
            aliases=[],
        ),
        uniprot_summary_json="{}",
        db_panel_json="{}",
        deterministic_summary_json=None,
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

    assert "Deterministic inputs" not in captured["user_prompt"]


def test_a1_plan_prompt_mentions_deterministic_inputs():
    body = A1_PLAN_PROMPT_PATH.read_text().lower()
    assert "deterministic inputs" in body
    # Should reference the four signals the planner can act on.
    assert "tm_helix_count" in body
    assert "paralog" in body
    assert "ortholog" in body


def test_a2_plan_prompt_mentions_deterministic_inputs():
    body = A2_PLAN_PROMPT_PATH.read_text().lower()
    assert "deterministic inputs" in body
    assert "tm_helix_count" in body
    assert "paralog" in body
    assert "ortholog" in body
