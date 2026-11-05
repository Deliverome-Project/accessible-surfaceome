"""Pin the per-verdict rules of the tag-site literature audit correction."""

from __future__ import annotations

import json

import pytest

from accessible_surfaceome.cloud.tag_site_audit import (
    COLUMNS,
    REGION_LABELS,
    _frame,
    build_corrections,
    flanks,
    lowered_validation_level,
    read_audit,
    read_tsv,
    summarize,
)
from accessible_surfaceome.paths import REPO_ROOT

AUDIT_DIR = REPO_ROOT / "data" / "analysis" / "tag_site_corpus_audit"


def _kept(c) -> dict:
    """The surviving row of a non-delete correction (narrows Optional for ty)."""
    assert c.row is not None, c
    return c.row


SEQ = "M" + "ACDEFGHIKLMNPQRSTVWY" * 10  # 201 aa


def _row(site_id: str, residue: int | None, **over):
    base = {c: None for c in COLUMNS}
    base.update(
        gene_symbol="GENEX",
        uniprot_acc="P00001",
        site_id=site_id,
        provenance="literature_retrieved",
        site_kind="internal",
        insert_after_residue=residue,
        residue_before="A",
        residue_after="C",
        residue_label=f"A{residue}",
        extracellular=1,
        compartment="extracellular",
        validation_level="surface_and_function",
        position_evidence="validated",
        rationale="original rationale",
        sources_json="[]",
        tag_sites_version="2026-10-11",
        synced_at="2026-10-12T00:00:00+00:00",
    )
    base.update(over)
    return base


def _audit(
    site_id: str,
    verdict: str,
    residue: int | None = None,
    corrected: str = "",
    surface="yes",
    function="yes",
    basis="ortholog:mouse",
):
    return {
        "site_id": site_id,
        "insert_after_residue": "" if residue is None else str(residue),
        "verdict": verdict,
        "corrected_residue": corrected,
        "surface_shown": surface,
        "function_shown": function,
        "paper_numbering_basis": basis,
        "species_of_construct": "mouse",
        "pmid": "1",
        "paper_quote": "q",
        "notes": "n",
    }


def test_flanks_follow_the_served_convention():
    assert flanks("MACDE", 1) == ("M", "A", "M1")
    assert flanks("MACDE", 5) == ("E", None, "E5")
    with pytest.raises(ValueError):
        flanks("MACDE", 6)


@pytest.mark.parametrize(
    ("level", "surface", "function", "expected"),
    [
        ("surface_and_function", "yes", "yes", "surface_and_function"),
        ("surface_and_function", "yes", "no", "surface_only"),
        ("surface_and_function", "not_reported", "yes", "function_only"),
        ("surface_and_function", "no", "not_reported", "detected_only"),
        ("surface_only", "no", "yes", "function_only"),
        ("surface_only", "not_reported", "not_reported", "detected_only"),
        ("function_only", "no", "yes", "function_only"),
        ("function_only", "yes", "no", "surface_only"),
        ("function_perturbed", "not_reported", "not_reported", "detected_only"),
        ("detected_only", "yes", "yes", "detected_only"),  # never raised
        ("not_measured", "no", "no", "not_measured"),
        (None, "no", "no", None),
    ],
)
def test_validation_level_is_lowered_to_what_the_paper_shows(
    level, surface, function, expected
):
    assert (
        lowered_validation_level(level, surface=surface, function=function) == expected
    )


def test_confirmed_shifted_moves_the_residue_and_recomputes_flanks():
    before = [_row("GENEX-internal-10-lit", 10)]
    audit = [_audit("GENEX-internal-10-lit", "confirmed_shifted", 10, "14")]
    (c,) = build_corrections(before, audit, {"P00001": SEQ}, version="v", synced_at="t")
    assert c.action == "update" and c.shift == 4
    assert _kept(c)["insert_after_residue"] == 14
    assert (
        _kept(c)["residue_before"],
        _kept(c)["residue_after"],
        _kept(c)["residue_label"],
    ) == flanks(SEQ, 14)
    assert _kept(c)["site_id"] == "GENEX-internal-10-lit"  # key kept
    assert _kept(c)["position_frame"] == "ortholog:mouse"
    assert _kept(c)["tag_sites_version"] == "v"
    assert _kept(c)["rationale"].startswith("[Literature audit")
    assert _kept(c)["rationale"].endswith("original rationale")
    assert "10 -> 14" in _kept(c)["rationale"]


def test_mature_numbering_maps_to_the_workers_frame_vocabulary():
    before = [_row("GENEX-internal-10-lit", 10)]
    audit = [
        _audit(
            "GENEX-internal-10-lit",
            "confirmed_shifted",
            10,
            "12",
            basis="mature_protein",
        )
    ]
    (c,) = build_corrections(before, audit, {"P00001": SEQ}, version="v", synced_at="t")
    assert _kept(c)["position_frame"] == "mature"


def test_confirmed_exact_with_full_support_is_a_keep():
    before = [_row("GENEX-internal-10-lit", 10)]
    audit = [_audit("GENEX-internal-10-lit", "confirmed_exact", 10)]
    (c,) = build_corrections(before, audit, {"P00001": SEQ}, version="v", synced_at="t")
    assert c.action == "keep"
    assert _kept(c)["rationale"] == "original rationale"
    assert _kept(c)["insert_after_residue"] == 10


def test_confirmed_exact_with_missing_assay_lowers_validation_only():
    before = [_row("GENEX-internal-10-lit", 10)]
    audit = [
        _audit("GENEX-internal-10-lit", "confirmed_exact", 10, function="not_reported")
    ]
    (c,) = build_corrections(before, audit, {"P00001": SEQ}, version="v", synced_at="t")
    assert c.action == "update"
    assert _kept(c)["validation_level"] == "surface_only"
    assert _kept(c)["insert_after_residue"] == 10
    assert "surface_and_function -> surface_only" in _kept(c)["rationale"]


def test_region_only_takes_the_shape_of_the_existing_region_rows(monkeypatch):
    monkeypatch.setitem(
        REGION_LABELS, "GENEX-internal-10-lit", ("loop C at X10", (9, 10))
    )
    before = [_row("GENEX-internal-10-lit", 10)]
    audit = [
        _audit(
            "GENEX-internal-10-lit", "region_only", 10, basis="uniprot_canonical_human"
        )
    ]
    (c,) = build_corrections(before, audit, {"P00001": SEQ}, version="v", synced_at="t")
    r = _kept(c)
    assert r["insert_after_residue"] is None
    assert (r["residue_before"], r["residue_after"]) == ("", "")
    assert r["residue_label"] == "loop C at X10"
    assert r["residue_range"] == f"{SEQ[8]}9-{SEQ[9]}10"
    assert (r["extracellular"], r["compartment"], r["topology_state"]) == (
        0,
        "unknown",
        None,
    )
    assert r["cited_tag_residue"] == 10 and r["position_evidence"] == "inferred"
    assert r["position_frame"] is None


def test_region_row_that_the_paper_pins_gains_the_residue():
    before = [
        _row(
            "GENEX-internal-None-lit",
            None,
            residue_before="",
            residue_after="",
            residue_label="ECL2",
            extracellular=0,
            compartment="unknown",
            position_evidence="inferred",
        )
    ]
    audit = [
        _audit(
            "GENEX-internal-None-lit",
            "confirmed_exact",
            None,
            "12",
            basis="ortholog:rat",
        )
    ]
    topo = "I" * 5 + "M" * 5 + "O" * 191
    (c,) = build_corrections(
        before,
        audit,
        {"P00001": SEQ},
        version="v",
        synced_at="t",
        topologies={"P00001": topo},
    )
    r = _kept(c)
    assert c.action == "update" and c.residue_before_audit is None
    assert r["insert_after_residue"] == 12
    assert (r["residue_before"], r["residue_after"], r["residue_label"]) == flanks(
        SEQ, 12
    )
    assert (r["topology_state"], r["extracellular"], r["compartment"]) == (
        "O",
        1,
        "extracellular",
    )
    assert (
        r["position_evidence"] == "validated" and r["position_frame"] == "ortholog:rat"
    )
    assert r["site_id"] == "GENEX-internal-None-lit"
    assert "NULL -> 12" in r["rationale"]


def test_region_row_the_paper_cannot_pin_keeps_its_shape():
    before = [
        _row(
            "GENEX-internal-None-lit",
            None,
            residue_before="",
            residue_after="",
            residue_label="ECL2",
            extracellular=0,
            compartment="unknown",
        )
    ]
    audit = [_audit("GENEX-internal-None-lit", "region_only", None, "", function="no")]
    (c,) = build_corrections(before, audit, {"P00001": SEQ}, version="v", synced_at="t")
    r = _kept(c)
    assert r["insert_after_residue"] is None and r["residue_label"] == "ECL2"
    assert r["validation_level"] == "surface_only"
    assert "no junction recoverable" in r["rationale"]


@pytest.mark.parametrize(
    "verdict", ["not_supported", "wrong_species_numbering", "terminal_misfiled"]
)
def test_unsupported_verdicts_are_deletes(verdict):
    before = [_row("GENEX-internal-10-lit", 10)]
    audit = [_audit("GENEX-internal-10-lit", verdict, 10)]
    (c,) = build_corrections(before, audit, {"P00001": SEQ}, version="v", synced_at="t")
    assert c.action == "delete" and c.row is None
    assert summarize([c])["deleted"] == ["GENEX-internal-10-lit"]


def test_audit_row_without_a_served_row_is_an_error():
    with pytest.raises(KeyError):
        build_corrections(
            [],
            [_audit("GENEX-internal-10-lit", "confirmed_exact", 10)],
            {"P00001": SEQ},
            version="v",
            synced_at="t",
        )


def test_unknown_verdict_is_an_error():
    with pytest.raises(ValueError):
        build_corrections(
            [_row("GENEX-internal-10-lit", 10)],
            [_audit("GENEX-internal-10-lit", "maybe", 10)],
            {"P00001": SEQ},
            version="v",
            synced_at="t",
        )


@pytest.mark.parametrize(
    ("basis", "expected"),
    [
        ("ortholog:mouse", "ortholog:mouse"),
        ("ortholog:mouse (KCC2b, NM_020333)", "ortholog:mouse"),
        ("ortholog:Xenopus laevis", "ortholog:Xenopus laevis"),
        ("isoform:NRG1 type III (700 aa)", "isoform:NRG1 type III"),
        ("mature_protein", "mature"),
        ("mature subunit numbering (after signal peptide cleavage)", "mature"),
        ("uniprot_canonical_human", None),
        ("flanking_residues_only", None),
        ("human TMEM123 (Q8N131) canonical numbering; endogenous knock-in", None),
        ("", None),
    ],
)
def test_position_frame_keeps_only_the_short_vocabulary(basis, expected):
    assert _frame(basis) == expected


def test_failed_construct_keeps_its_position_but_is_marked_perturbed():
    before = [_row("GENEX-internal-10-lit", 10, validation_level="surface_only")]
    audit = [_audit("GENEX-internal-10-lit", "confirmed_exact", 10)]
    (c,) = build_corrections(
        before,
        audit,
        {"P00001": SEQ},
        version="v",
        synced_at="t",
        failed={"GENEX-internal-10-lit": "construct failed to reach the surface"},
    )
    r = _kept(c)
    assert c.action == "update" and r["insert_after_residue"] == 10
    assert r["validation_level"] == "function_perturbed"
    assert r["rationale"].startswith("[Literature audit")
    assert "NOT TOLERATED: construct failed to reach the surface." in r["rationale"]
    assert summarize([c])["validation_level_changes"] == {
        "surface_only -> function_perturbed": 1
    }


def _added(site_id, gene, residue, tag, verdict="confirmed_shifted", **over):
    a = {
        "site_id": site_id,
        "gene": gene,
        "uniprot_acc": "P00001",
        "insert_after_residue": str(residue),
        "residue_before": SEQ[residue - 1],
        "residue_after": SEQ[residue],
        "tag_type": tag,
        "pmid": "7",
        "paper_quote": "between 4 and 5",
        "paper_numbering_basis": "mature subunit numbering",
        "species_of_construct": "human",
        "verdict": verdict,
        "surface_shown": "yes",
        "function_shown": "not_reported",
        "recovered_from": "OTHER-internal-1-lit",
        "notes": "n",
    }
    a.update(over)
    return a


def test_recovered_sites_are_minted_as_literature_rows_one_per_junction():
    added = [
        _added("GENEX-added-12-HA", "GENEX", 12, "HA"),
        _added("GENEX-added-12-FLAG", "GENEX", 12, "FLAG"),
        _added("GENEX-added-30-HA", "GENEX", 30, "HA", verdict="not_supported"),
    ]
    topo = "I" * 5 + "M" * 5 + "O" * 191
    (c,) = build_corrections(
        [],
        [],
        {"P00001": SEQ},
        version="v",
        synced_at="t",
        topologies={"P00001": topo},
        added=added,
    )
    r = _kept(c)
    assert c.action == "add" and r["site_id"] == "GENEX-internal-12-lit"
    assert r["provenance"] == "literature_retrieved" and r["site_kind"] == "internal"
    assert (r["residue_before"], r["residue_after"], r["residue_label"]) == flanks(
        SEQ, 12
    )
    assert r["tag_type"] == "HA / FLAG"
    assert (r["topology_state"], r["extracellular"], r["compartment"]) == (
        "O",
        1,
        "extracellular",
    )
    assert r["validation_level"] == "surface_only"  # surface yes, function not reported
    assert r["position_frame"] == "mature" and r["position_evidence"] == "validated"
    assert json.loads(r["sources_json"]) == [
        {"pmid": 7, "citation": "PMID 7", "claim": "between 4 and 5"}
    ]
    assert "OTHER-internal-1-lit" in r["rationale"]
    assert set(r) == set(COLUMNS)
    assert summarize([c])["added"] == ["GENEX-internal-12-lit"]


def test_recovered_site_whose_id_is_already_served_is_skipped():
    added = [_added("GENEX-added-12-HA", "GENEX", 12, "HA")]
    (c,) = build_corrections(
        [],
        [],
        {"P00001": SEQ},
        version="v",
        synced_at="t",
        added=added,
        existing_site_ids={"GENEX-internal-12-lit"},
    )
    assert c.action == "skip_existing" and c.row is None
    assert summarize([c])["added_skipped_existing"] == ["GENEX-internal-12-lit"]


def test_recovered_site_with_wrong_flanks_is_an_error():
    added = [_added("GENEX-added-12-HA", "GENEX", 12, "HA", residue_before="Z")]
    with pytest.raises(ValueError):
        build_corrections(
            [], [], {"P00001": SEQ}, version="v", synced_at="t", added=added
        )


# --- the committed artifacts ------------------------------------------------


def test_committed_audit_covers_every_region_label_and_vice_versa():
    audit = read_audit(AUDIT_DIR / "audit.tsv")
    region = {
        a["site_id"]
        for a in audit
        if a["verdict"] == "region_only" and a["insert_after_residue"] != ""
    }
    assert region == set(REGION_LABELS)


def test_committed_rows_after_are_what_the_snapshot_plus_audit_produce():
    """``rows_after.json`` is a generated artifact; it must match its inputs."""
    before = json.loads((AUDIT_DIR / "rows_before.json").read_text())
    seqs = json.loads((AUDIT_DIR / "canonical_sequences.json").read_text())
    summary = json.loads((AUDIT_DIR / "summary.json").read_text())
    audit = read_audit(AUDIT_DIR / "audit.tsv")
    topos = json.loads((AUDIT_DIR / "per_residue_topology.json").read_text())
    failed = {
        r["site_id"]: r["why_failed"] for r in read_tsv(AUDIT_DIR / "failed_sites.tsv")
    }
    added = read_tsv(AUDIT_DIR / "added_sites.tsv")
    live_ids = set(
        json.loads((AUDIT_DIR / "live_site_ids_added_genes.json").read_text())
    )
    corr = build_corrections(
        before,
        audit,
        seqs,
        version=summary["tag_sites_version"],
        synced_at="<set at execute time>",
        topologies=topos,
        failed=failed,
        added=added,
        existing_site_ids=live_ids,
    )
    expected = [c.row for c in corr if c.row is not None]
    committed = json.loads((AUDIT_DIR / "rows_after.json").read_text())
    assert committed == expected
    assert summarize(corr)["by_verdict"] == summary["by_verdict"]
    audited = {c.site_id for c in corr if c.action not in ("add", "skip_existing")}
    assert audited == {r["site_id"] for r in before}
    assert len(before) == 191
    assert set(failed) <= audited


def test_snapshot_flanks_agree_with_the_committed_sequences():
    """The convention ``flanks`` encodes is the one the served rows use."""
    before = json.loads((AUDIT_DIR / "rows_before.json").read_text())
    seqs = json.loads((AUDIT_DIR / "canonical_sequences.json").read_text())
    for r in before:
        if r["insert_after_residue"] is None:
            continue
        b, a, label = flanks(seqs[r["uniprot_acc"]], r["insert_after_residue"])
        assert (r["residue_before"], r["residue_after"], r["residue_label"]) == (
            b,
            a,
            label,
        ), r["site_id"]
