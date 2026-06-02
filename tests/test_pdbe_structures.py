"""Tests for the PDBe representative-structure picker + the self-describing
topology schema additions (Chunk 7 of the PR #47 redesign)."""

from __future__ import annotations

from unittest.mock import MagicMock

from accessible_surfaceome.tools._shared.models import (
    CLOSE_PARALOG_THRESHOLD,
    ParalogEntry,
    RepresentativeStructure,
)
from accessible_surfaceome.tools.pdbe_structures import (
    _pick_best,
    fetch_representative_structure,
)


def test_pick_best_prefers_higher_coverage():
    entries = [
        {"pdb_id": "1low", "coverage": 0.4, "resolution": 1.5},
        {"pdb_id": "2high", "coverage": 0.95, "resolution": 2.5},
    ]
    best = _pick_best(entries)
    assert best is not None and best["pdb_id"] == "2high"


def test_pick_best_breaks_coverage_tie_on_resolution():
    entries = [
        {"pdb_id": "1coarse", "coverage": 0.9, "resolution": 3.0},
        {"pdb_id": "2fine", "coverage": 0.9, "resolution": 1.8},
    ]
    best = _pick_best(entries)
    assert best is not None and best["pdb_id"] == "2fine"


def test_pick_best_handles_missing_resolution():
    # An EM entry with no resolution sorts after a same-coverage X-ray.
    entries = [
        {"pdb_id": "1em", "coverage": 0.9, "resolution": None},
        {"pdb_id": "2xray", "coverage": 0.9, "resolution": 2.0},
    ]
    best = _pick_best(entries)
    assert best is not None and best["pdb_id"] == "2xray"


def test_pick_best_empty_is_none():
    assert _pick_best([]) is None


def test_fetch_maps_pdbe_entry_to_model():
    http = MagicMock()
    http.get_json.return_value = {
        "P00533": [
            {
                "pdb_id": "1ivo",
                "chain_id": "A",
                "coverage": 0.62,
                "resolution": 3.3,
                "experimental_method": "X-ray diffraction",
                "unp_start": 1,
                "unp_end": 501,
            }
        ]
    }
    rep = fetch_representative_structure("P00533", http=http)
    assert isinstance(rep, RepresentativeStructure)
    assert rep.pdb_id == "1ivo"
    assert rep.chain == "A"
    assert rep.coverage_fraction == 0.62
    assert rep.residue_end == 501


def test_fetch_returns_none_on_no_structures():
    http = MagicMock()
    http.get_json.return_value = {"Q99999": []}
    assert fetch_representative_structure("Q99999", http=http) is None


def test_fetch_swallows_network_error():
    http = MagicMock()
    http.get_json.side_effect = RuntimeError("PDBe down")
    assert fetch_representative_structure("P00533", http=http) is None


def test_close_paralog_threshold_value():
    assert CLOSE_PARALOG_THRESHOLD == 80.0


def test_paralog_topology_fields_default_none():
    # Far/ECD-less paralogs (and pre-population records) carry None.
    p = ParalogEntry(
        paralog_symbol="FYN",
        paralog_uniprot_acc="P06241",
        family_id="src_family",
        compara_version="r112",
    )
    assert p.per_residue_topology is None
    assert p.tm_helix_count is None
    assert p.sequence is None
