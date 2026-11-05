"""Pin the per-verdict rules of the tag-site literature audit correction."""

from __future__ import annotations

import json

import pytest

from accessible_surfaceome.cloud.tag_site_audit import (
    COLUMNS,
    REGION_LABELS,
    build_corrections,
    flanks,
    lowered_validation_level,
    read_audit,
    summarize,
)
from accessible_surfaceome.paths import REPO_ROOT

AUDIT_DIR = REPO_ROOT / "data" / "analysis" / "tag_site_corpus_audit"

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
    assert c.row["insert_after_residue"] == 14
    assert (
        c.row["residue_before"],
        c.row["residue_after"],
        c.row["residue_label"],
    ) == flanks(SEQ, 14)
    assert c.row["site_id"] == "GENEX-internal-10-lit"  # key kept
    assert c.row["position_frame"] == "ortholog:mouse"
    assert c.row["tag_sites_version"] == "v"
    assert c.row["rationale"].startswith("[Literature audit")
    assert c.row["rationale"].endswith("original rationale")
    assert "10 -> 14" in c.row["rationale"]


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
    assert c.row["position_frame"] == "mature"


def test_confirmed_exact_with_full_support_is_a_keep():
    before = [_row("GENEX-internal-10-lit", 10)]
    audit = [_audit("GENEX-internal-10-lit", "confirmed_exact", 10)]
    (c,) = build_corrections(before, audit, {"P00001": SEQ}, version="v", synced_at="t")
    assert c.action == "keep"
    assert c.row["rationale"] == "original rationale"
    assert c.row["insert_after_residue"] == 10


def test_confirmed_exact_with_missing_assay_lowers_validation_only():
    before = [_row("GENEX-internal-10-lit", 10)]
    audit = [
        _audit("GENEX-internal-10-lit", "confirmed_exact", 10, function="not_reported")
    ]
    (c,) = build_corrections(before, audit, {"P00001": SEQ}, version="v", synced_at="t")
    assert c.action == "update"
    assert c.row["validation_level"] == "surface_only"
    assert c.row["insert_after_residue"] == 10
    assert "surface_and_function -> surface_only" in c.row["rationale"]


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
    r = c.row
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


# --- the committed artifacts ------------------------------------------------


def test_committed_audit_covers_every_region_label_and_vice_versa():
    audit = read_audit(AUDIT_DIR / "audit.tsv")
    region = {a["site_id"] for a in audit if a["verdict"] == "region_only"}
    assert region == set(REGION_LABELS)


def test_committed_rows_after_are_what_the_snapshot_plus_audit_produce():
    """``rows_after.json`` is a generated artifact; it must match its inputs."""
    before = json.loads((AUDIT_DIR / "rows_before.json").read_text())
    seqs = json.loads((AUDIT_DIR / "canonical_sequences.json").read_text())
    summary = json.loads((AUDIT_DIR / "summary.json").read_text())
    audit = read_audit(AUDIT_DIR / "audit.tsv")
    corr = build_corrections(
        before,
        audit,
        seqs,
        version=summary["tag_sites_version"],
        synced_at="<set at execute time>",
    )
    expected = [c.row for c in corr if c.row is not None]
    committed = json.loads((AUDIT_DIR / "rows_after.json").read_text())
    assert committed == expected
    assert summarize(corr)["by_verdict"] == summary["by_verdict"]
    assert {c.site_id for c in corr} == {r["site_id"] for r in before}
    assert len(before) == 176


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
