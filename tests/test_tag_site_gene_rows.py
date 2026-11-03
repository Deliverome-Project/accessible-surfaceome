"""The per-gene row is what makes "we looked and found nothing" sayable.

`tag_site_public` holds one row per SITE, so a searched gene with no sites has
no rows and reads exactly like a gene nobody searched. 1,106 of the first
sweep's 1,824 genes are that case. These pin the distinction.
"""

from __future__ import annotations

import json

from accessible_surfaceome.cloud.tag_site_genes import row_for


def _row(record: dict, **kw) -> dict:
    """row_for() narrowed to a dict — these cases all expect a row to exist."""
    row = row_for(record, **kw)
    assert row is not None, "expected a row for a record the agent ran"
    return row


_RAN = {
    "gene_symbol": "SIGLEC9",
    "uniprot_acc": "Q9Y336",
    "prompt_sha": "abc123",
    "prompt_version": "1.4.0",
    "model": "claude-sonnet-4-6",
    "generated_at": "2026-10-11T14:22:21Z",
    "schema_version": "1.0.0",
    "sites": [],
}


def test_a_searched_gene_with_no_sites_still_gets_a_row() -> None:
    """The whole point: zero is a finding, and it has to be dateable."""
    row = row_for(_RAN, version="2026-10-11")
    assert row is not None
    assert row["n_sites"] == 0
    assert row["prompt_sha"] == "abc123"
    assert row["searched_at"] == "2026-10-11T14:22:21Z"


def test_a_gene_the_agent_never_ran_gets_no_row() -> None:
    """Absence of a row is the claim "unsearched", so a deterministic-only
    record must not create one — otherwise the distinction is worthless."""
    det_only = {
        "gene_symbol": "X",
        "uniprot_acc": "Q0",
        "sites": [{"site_id": "s", "provenance": "deterministic_computed"}],
    }
    assert row_for(det_only, version="v") is None


def test_only_literature_sites_are_counted() -> None:
    """n_sites answers "what did the LITERATURE agent find", so a gene with 20
    deterministic sites and no literature ones still reads as a zero."""
    rec = {
        **_RAN,
        "sites": [
            {"site_id": "a", "provenance": "deterministic_computed"},
            {"site_id": "b", "provenance": "deterministic_computed"},
            {"site_id": "c", "provenance": "literature_retrieved"},
        ],
    }
    assert _row(rec, version="v")["n_sites"] == 1


def test_other_positions_round_trip() -> None:
    rec = {
        **_RAN,
        "literature_other_positions": [
            {"residue": 271, "kind": "intracellular", "note": "faces cytoplasm"},
            {"residue": 127, "kind": "abrogates_function", "note": "abolished"},
        ],
    }
    row = _row(rec, version="v")
    assert row["n_other_positions"] == 2
    assert {o["kind"] for o in json.loads(row["other_positions_json"])} == {
        "intracellular",
        "abrogates_function",
    }


def test_no_other_positions_is_an_empty_list_not_null() -> None:
    """So a consumer can tell "none found" from "field absent"."""
    assert json.loads(_row(_RAN, version="v")["other_positions_json"]) == []
