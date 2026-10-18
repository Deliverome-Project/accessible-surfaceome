"""Unit tests for the A1 evidence-recovery re-tag logic (no network / LLM).

Guards the permeabilization-aware, method-dependent rule and the A2->A1
re-tag mutation — the two pure-logic pieces the backfill + Modal run rely on.
"""
from __future__ import annotations

import json

from accessible_surfaceome.agents.surfaceome_v2.a1_recovery import (
    claim_is_direct_surface,
    retag_a2_direct_into_a1,
)


def _claim(**kw):
    base = {
        "evidence_id": kw.pop("evidence_id", "a2_evi_01"),
        "claim": "c",
        "claim_type": kw.pop("claim_type", "tissue_expression"),
        "direction": kw.pop("direction", "supports"),
        "evidence_type": kw.pop("evidence_type", "flow_cytometry"),
        "evidence_tier": kw.pop("evidence_tier", "primary"),
        "assay_context": {
            "permeabilized": kw.pop("permeabilized", False),
            "species": kw.pop("species", None),
        },
        "source_id": kw.pop("source_id", "PMID:1"),
        "quote": "q",
    }
    base.update(kw)
    return base


def test_nonperm_flow_is_direct():
    assert claim_is_direct_surface(_claim(evidence_type="flow_cytometry", permeabilized=False))


def test_permeabilized_flow_is_not_direct():
    # permeabilized flow measures TOTAL protein, not surface
    assert not claim_is_direct_surface(_claim(evidence_type="flow_cytometry", permeabilized=True))


def test_unknown_perm_if_is_credited():
    # grader-matching: perm=None IF/flow IS credited (only explicit True is excluded)
    assert claim_is_direct_surface(_claim(evidence_type="immunofluorescence", permeabilized=None))
    assert claim_is_direct_surface(_claim(evidence_type="flow_cytometry", permeabilized=None))


def test_surface_biotinylation_is_direct_regardless_of_perm_flag():
    # surface-by-method: permeabilized flag is not load-bearing
    assert claim_is_direct_surface(_claim(evidence_type="surface_biotinylation", permeabilized=None))
    assert claim_is_direct_surface(_claim(evidence_type="mass_spec_surfaceome", permeabilized=False))


def test_permeabilized_biotinylation_still_credited():
    # you cannot biotinylate an intracellular lysine on an intact cell anyway
    assert claim_is_direct_surface(_claim(evidence_type="surface_biotinylation", permeabilized=False))


def test_refutes_and_secondary_excluded():
    assert not claim_is_direct_surface(_claim(direction="refutes", permeabilized=False))
    assert not claim_is_direct_surface(_claim(evidence_tier="secondary", permeabilized=False))


def test_nonhuman_species_excluded():
    # CD79A-class: a non-human assay can't anchor a human direct_* grade
    assert not claim_is_direct_surface(_claim(evidence_type="flow_cytometry", permeabilized=False, species="other"))
    assert not claim_is_direct_surface(_claim(evidence_type="flow_cytometry", permeabilized=False, species="mouse"))


def test_human_and_unspecified_species_credited():
    assert claim_is_direct_surface(_claim(evidence_type="flow_cytometry", permeabilized=False, species="human"))
    assert claim_is_direct_surface(_claim(evidence_type="flow_cytometry", permeabilized=False, species=None))
    assert claim_is_direct_surface(_claim(evidence_type="flow_cytometry", permeabilized=False, species="unspecified"))


def test_non_surface_assays_excluded():
    # review / RNA / IHC are not surface-localization assays in the credited set
    assert not claim_is_direct_surface(_claim(evidence_type="review_assertion", permeabilized=False))
    assert not claim_is_direct_surface(_claim(evidence_type="single_cell_rna_seq", permeabilized=False))
    assert not claim_is_direct_surface(_claim(evidence_type="immunohistochemistry", permeabilized=False))


def test_retag_moves_only_qualifying_and_renumbers():
    blob = {
        "plan_trim_select": {
            "a1": {"claims": []},
            "a2": {
                "claims": [
                    _claim(evidence_id="a2_evi_01", evidence_type="flow_cytometry", permeabilized=False),
                    _claim(evidence_id="a2_evi_02", evidence_type="immunofluorescence", permeabilized=True),  # perm -> stays
                    _claim(evidence_id="a2_evi_03", evidence_type="mass_spec_surfaceome", permeabilized=None),
                    _claim(evidence_id="a2_evi_04", evidence_type="review_assertion", permeabilized=None),      # not method -> stays
                ]
            },
        }
    }
    out = retag_a2_direct_into_a1(blob)
    assert out["n_moved"] == 2
    assert out["method_types"] == {"flow_cytometry": 1, "mass_spec_surfaceome": 1}
    a1 = blob["plan_trim_select"]["a1"]["claims"]
    a2 = blob["plan_trim_select"]["a2"]["claims"]
    assert len(a1) == 2 and len(a2) == 2
    # moved claims re-id'd into the a1_evi_ namespace + re-tagged surface_expression
    assert [c["evidence_id"] for c in a1] == ["a1_evi_01", "a1_evi_02"]
    assert all(c["claim_type"] == "surface_expression" for c in a1)
    # the permeabilized IF and the review assertion remain in A2
    assert {c["evidence_type"] for c in a2} == {"immunofluorescence", "review_assertion"}


def test_retag_empty_when_nothing_qualifies():
    blob = {"plan_trim_select": {"a1": {"claims": []}, "a2": {"claims": [
        _claim(evidence_type="review_assertion"), _claim(evidence_type="flow_cytometry", permeabilized=True),
    ]}}}
    out = retag_a2_direct_into_a1(blob)
    assert out["n_moved"] == 0
    assert blob["plan_trim_select"]["a1"]["claims"] == []


def test_reconstruct_dual_preserves_n_papers_discovered():
    """The replay rebuild must carry each side's discovery-corpus size.

    ``Filters.n_papers_found`` is ``max(a1, a2).n_papers_discovered``, and the
    orchestrator treats 0 as "unknown". Dropping the field here defaulted it to
    0, so every builders replay published ``n_papers_found = None`` — 19
    records on 2026-09-21, after a backfill had just repaired ~485 others.
    """
    from accessible_surfaceome.agents.surfaceome_v2.a1_recovery import (
        reconstruct_dual_from_blob,
    )

    blob = {
        "gene": "GENEX",
        "bundle": {"hgnc_symbol": "GENEX", "hgnc_id": "HGNC:1", "uniprot_acc": "P00001"},
        "plan_trim_select": {
            "a1": {"claims": [], "n_papers_discovered": 237},
            "a2": {"claims": [], "n_papers_discovered": 210},
        },
    }
    dual = reconstruct_dual_from_blob(blob)
    assert dual.a1.n_papers_discovered == 237
    assert dual.a2.n_papers_discovered == 210


_LOG_ROW = {
    "tool": "gene_literature",
    "params": {"mode": "topic_search", "anchors": ["epitope_masking"]},
    "intent": "standing: epitope-masking evidence",
    "n_drafts": 3,
    "n_papers": 25,
    "elapsed_s": 1.5,
    "error": None,
}


def _blob(**side_extra: object) -> dict:
    return {
        "gene": "GENEX",
        "bundle": {"hgnc_symbol": "GENEX", "hgnc_id": "HGNC:1", "uniprot_acc": "P00001"},
        "plan_trim_select": {
            "a1": {"claims": [], **side_extra},
            "a2": {"claims": [], **side_extra},
        },
    }


def test_replay_reconstruction_carries_search_log() -> None:
    """Both rebuild paths must keep each side's search_log.

    The record's search_log is built from them. Rebuilding with
    ``search_log=[]`` published 839 records with no search log
    (found 2026-10-17).
    """
    from accessible_surfaceome.agents.surfaceome_v2.a1_recovery import (
        reconstruct_dual_from_blob,
    )
    from accessible_surfaceome.agents.surfaceome_v2.orchestrator import (
        _build_search_log,
        _dual_from_serialized,
    )

    blob = _blob(search_log=[_LOG_ROW, {**_LOG_ROW, "unknown_future_key": 1}])
    for dual in (
        reconstruct_dual_from_blob(blob),
        _dual_from_serialized("GENEX", blob["plan_trim_select"] | {"bundle": blob["bundle"]}),
    ):
        assert len(dual.a1.search_log) == 2 and len(dual.a2.search_log) == 2
        entries = _build_search_log(dual)
        assert len(entries) == 4
        assert entries[0].query["agent_focus"] == "a1"
        assert entries[0].mode == "topic_search" and entries[0].n_results == 25


def test_hydrate_search_logs_restores_slim_blob_from_r2(monkeypatch) -> None:
    from accessible_surfaceome.cloud import intermediates, r2_client

    full = _blob(search_log=[_LOG_ROW])
    slim = intermediates._slim_intermediates_for_d1(full)
    slim["_r2_full_audit_key"] = "agent_run_intermediates/GENEX/x.json"
    slim["_r2_full_audit_bucket"] = "audit-bucket"
    assert "search_log" not in slim["plan_trim_select"]["a1"]

    seen = {}
    monkeypatch.setattr(
        r2_client.R2Config, "from_env", classmethod(lambda cls, bucket="b": cls("acct", "tok", bucket))
    )

    def fake_get(*, key, cfg):
        seen["key"], seen["bucket"] = key, cfg.bucket
        return json.dumps(full).encode()

    monkeypatch.setattr(r2_client, "get_object", fake_get)
    assert intermediates.hydrate_search_logs(slim) is True
    assert seen == {"key": "agent_run_intermediates/GENEX/x.json", "bucket": "audit-bucket"}
    assert slim["plan_trim_select"]["a1"]["search_log"] == [_LOG_ROW]
    assert slim["plan_trim_select"]["a2"]["search_log"] == [_LOG_ROW]


def test_hydrate_search_logs_reports_an_unrecoverable_blob() -> None:
    from accessible_surfaceome.cloud import intermediates

    slim = intermediates._slim_intermediates_for_d1(_blob(search_log=[_LOG_ROW]))
    assert intermediates.hydrate_search_logs(slim) is False  # no R2 pointer
    assert intermediates.hydrate_search_logs(_blob(search_log=[])) is True  # nothing missing


def test_recover_one_refuses_to_publish_without_a_search_log(monkeypatch) -> None:
    from types import SimpleNamespace

    from accessible_surfaceome.agents.surfaceome_v2 import a1_recovery, orchestrator
    from accessible_surfaceome.cloud import surface_annotation

    claim = {
        "evidence_id": "a2_evi_01",
        "claim_type": "tissue_expression",
        "evidence_type": "flow_cytometry",
        "direction": "supports",
        "evidence_tier": "primary",
        "assay_context": {"permeabilized": False, "species": "human"},
    }
    blob = _blob()
    blob["plan_trim_select"]["a2"]["claims"] = [claim]
    monkeypatch.setattr(a1_recovery, "load_latest_intermediates", lambda gene, at=None: blob)
    monkeypatch.setattr(a1_recovery, "reconstruct_dual_from_blob", lambda b: object())
    monkeypatch.setattr(
        orchestrator,
        "annotate",
        lambda gene, cached_dual, persist: SimpleNamespace(
            record=SimpleNamespace(search_log=[]), error=None, total_cost_usd=0.0
        ),
    )
    published = []
    monkeypatch.setattr(surface_annotation, "publish_record", lambda *a, **k: published.append(1))

    out = a1_recovery.recover_one("GENEX", publish=True)
    assert out["status"] == "failed" and "search_log" in out["error"]
    assert not published
