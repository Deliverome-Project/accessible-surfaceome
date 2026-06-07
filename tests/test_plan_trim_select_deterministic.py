"""Tests for the deterministic-feature wiring into plan_trim_select.

Verifies:

1. ``_summarize_deterministic_for_planner`` produces a compact JSON the
   selector can read, with the four signals it references
   (tm_helix_count, paralog top-N, mouse/cyno ortholog ECD identity).
2. ``GeneContext`` carries ``deterministic_summary_json`` and the
   ``_build_gene_context`` builder tolerates D1 unreachable (sets it
   to ``None`` so the selector prompt skips the block).
3. The ``_run_selector`` user prompt includes the ``"Deterministic
   inputs"`` header when the summary is present and omits it when absent.

(The LLM planner that previously also consumed this summary was retired
in favor of a deterministic kickoff template; the selector remains the
consumer of the deterministic block.)
"""

from __future__ import annotations

import json
from datetime import UTC, datetime
from unittest.mock import MagicMock, patch

from accessible_surfaceome.agents.plan_trim_select.runner import (
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


def test_paralog_entry_allows_null_ecd_identity():
    """ECD-less proteins (inner-leaflet kinases like SRC, secreted proteins)
    have NULL ECD identity for their paralogs — there's no ECD to compare.
    ParalogEntry.ecd_pct_identity must accept None so these paralogs land
    in the dump (lets the planner flag cross-reactivity from family
    membership even when an identity number isn't computable)."""
    from accessible_surfaceome.tools._shared.models import ParalogEntry

    entry = ParalogEntry(
        paralog_symbol="FYN",
        paralog_uniprot_acc="P06241",
        ecd_pct_identity=None,
        family_id="src_family_kinases",
        compara_version="r112",
    )
    assert entry.ecd_pct_identity is None
    assert entry.paralog_symbol == "FYN"


def test_summary_includes_paralogs_with_null_ecd_identity():
    """A SRC-like fixture: paralogs with NULL ECD identity should land
    in top_paralogs alongside the ones with numeric identity."""
    from accessible_surfaceome.tools._shared.models import ParalogEntry

    feats = _gpr75_features()
    src_family_no_ecd = [
        ParalogEntry(
            paralog_symbol=sym,
            paralog_uniprot_acc=acc,
            ecd_pct_identity=None,
            family_id="src_kinases",
            compara_version="r112",
        )
        for sym, acc in [
            ("YES1", "P07947"), ("FYN", "P06241"), ("FGR", "P09769"),
            ("HCK", "P08631"), ("BLK", "P51451"), ("LYN", "P07948"),
            ("LCK", "P06239"),
        ]
    ]
    feats = feats.model_copy(update={"paralogs": src_family_no_ecd})
    out = json.loads(_summarize_deterministic_for_planner(feats))
    assert out["paralog_count"] == 7
    assert len(out["top_paralogs"]) == 5  # capped at 5
    # NULL-identity entries land in top_paralogs with ecd_pct_identity=null
    for p in out["top_paralogs"]:
        assert p["symbol"] in {"YES1", "FYN", "FGR", "HCK", "BLK", "LYN", "LCK"}
        assert p["ecd_pct_identity"] is None


def test_summary_sorts_numeric_identity_first_when_mixed():
    """When the paralog list mixes numeric and NULL identity values,
    the numeric ones (highest first) come first in top_paralogs;
    NULL ones fall to the end."""
    from accessible_surfaceome.tools._shared.models import ParalogEntry

    feats = _gpr75_features()
    mixed = [
        ParalogEntry(paralog_symbol="HI", paralog_uniprot_acc="P00001",
                     ecd_pct_identity=85.0, family_id="f", compara_version="r112"),
        ParalogEntry(paralog_symbol="NULL_A", paralog_uniprot_acc="P00002",
                     ecd_pct_identity=None, family_id="f", compara_version="r112"),
        ParalogEntry(paralog_symbol="LO", paralog_uniprot_acc="P00003",
                     ecd_pct_identity=30.0, family_id="f", compara_version="r112"),
        ParalogEntry(paralog_symbol="NULL_B", paralog_uniprot_acc="P00004",
                     ecd_pct_identity=None, family_id="f", compara_version="r112"),
    ]
    feats = feats.model_copy(update={"paralogs": mixed})
    out = json.loads(_summarize_deterministic_for_planner(feats))
    assert out["top_paralogs"][0]["symbol"] == "HI"
    assert out["top_paralogs"][0]["ecd_pct_identity"] == 85.0
    assert out["top_paralogs"][1]["symbol"] == "LO"
    assert out["top_paralogs"][1]["ecd_pct_identity"] == 30.0
    # NULLs come after numeric values
    null_syms = {p["symbol"] for p in out["top_paralogs"][2:]}
    assert null_syms == {"NULL_A", "NULL_B"}


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


def _selector_kwargs(ctx: "GeneContext") -> dict:
    """Minimal kwargs to drive ``_run_selector`` for prompt-shape tests."""
    from accessible_surfaceome.agents.plan_trim_select.runner import (
        A1_SELECT_PROMPT_PATH,
    )

    return {
        "context": ctx,
        "menu_markdown": "(menu)",
        "n_kept": 0,
        "usage_sink": [],
        "select_prompt_path": A1_SELECT_PROMPT_PATH,
    }


def test_selector_user_prompt_includes_deterministic_block_when_present():
    """``_run_selector`` must include the Deterministic-inputs JSON in the
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
        runner._run_selector(client=MagicMock(), **_selector_kwargs(ctx))

    assert "Deterministic inputs" in captured["user_prompt"]
    assert '"tm_helix_count": 7' in captured["user_prompt"]
    assert '"paralog_count": 32' in captured["user_prompt"]


def test_selector_user_prompt_omits_deterministic_block_when_absent():
    """When ``deterministic_summary_json`` is None (D1 unreachable), the
    block must not appear — the selector should fall back to UniProt-only
    context, not see a confusing empty section."""
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
        runner._run_selector(client=MagicMock(), **_selector_kwargs(ctx))

    assert "Deterministic inputs" not in captured["user_prompt"]
