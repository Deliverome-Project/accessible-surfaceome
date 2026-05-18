"""Tests for the AlphaFold DB pLDDT fetcher.

Covers the four pillars of the fetcher's contract:

1. Cache hit: metadata + CIF on disk → returns ``StructureFeatures``
   without an HTTP call.
2. ECD restriction: when a DeepTMHMM ``per_residue_topology`` is
   provided, mean pLDDT and disordered-fraction are computed only on
   residues with the ``O`` (outside / extracellular) character. This
   is what the schema field ``ecd_mean_plddt`` semantically requires.
3. Whole-protein fallback: when topology is missing or contains no
   ``O`` chars (e.g. cytosolic / nuclear proteins, tm=0 no signal
   peptide), the fetcher falls back to ``globalMetricValue`` from the
   metadata JSON so the caller still gets a measured number rather
   than a zero stub.
4. 404 from AlphaFold DB: returns a labeled-stub
   ``StructureFeatures`` and logs a warning — never crashes the v1/v2
   orchestrator, since some isoforms aren't in AFDB.
"""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from accessible_surfaceome.tools.afdb_plddt import fetch_afdb_plddt


REPO_ROOT = Path(__file__).resolve().parent.parent


def test_cache_hit_uses_local_metadata_and_cif(tmp_path: Path, monkeypatch):
    """When both the metadata JSON and CIF are on disk, the fetcher
    must not make any HTTP calls."""
    cache = tmp_path / "afdb_prediction"
    cache.mkdir()
    # Mirror the AFDB API JSON shape; only the fields the fetcher
    # actually reads are populated.
    (cache / "TEST1.json").write_text(
        json.dumps(
            [
                {
                    "entryId": "AF-TEST1-F1",
                    "uniprotAccession": "TEST1",
                    "globalMetricValue": 80.0,
                    "fractionPlddtVeryHigh": 0.5,
                    "fractionPlddtConfident": 0.3,
                    "fractionPlddtLow": 0.15,
                    "fractionPlddtVeryLow": 0.05,
                    "cifUrl": "https://alphafold.ebi.ac.uk/files/AF-TEST1-F1-model_v6.cif",
                }
            ]
        )
    )
    # Tiny 10-residue CIF with B-factor (pLDDT) per atom. Only the CA
    # rows feed the parser.
    (cache / "TEST1.cif").write_text(_make_synthetic_cif(plddts=[
        95.0, 90.0, 85.0, 80.0, 75.0, 70.0, 65.0, 60.0, 55.0, 50.0
    ]))
    monkeypatch.setattr(
        "accessible_surfaceome.tools.afdb_plddt.AFDB_CACHE_DIR", cache
    )

    # Topology: first 5 residues inside, residues 6-10 outside (the ECD).
    sf = fetch_afdb_plddt("TEST1", per_residue_topology="IIIIIOOOOO")
    # ECD = residues 6-10 → pLDDTs [70, 65, 60, 55, 50] → mean 60.0.
    # Disorder threshold is strict (< 70), so the 70.0 isn't counted; 4 of 5 → 0.8.
    assert sf.ecd_mean_plddt == pytest.approx(60.0)
    assert sf.ecd_disordered_fraction == pytest.approx(0.8)
    assert sf.afdb_id.startswith("AF-TEST1-F1")
    assert "ECD-restricted" in sf.source


def test_falls_back_to_global_when_no_ecd_residues(tmp_path: Path, monkeypatch):
    """``tm=0`` cytosolic proteins have no 'O' chars in the topology
    string — we still want a measured number, so use globalMetricValue
    from the JSON. The source label must say so."""
    cache = tmp_path / "afdb_prediction"
    cache.mkdir()
    (cache / "TEST2.json").write_text(
        json.dumps(
            [
                {
                    "entryId": "AF-TEST2-F1",
                    "uniprotAccession": "TEST2",
                    "globalMetricValue": 88.5,
                    "fractionPlddtVeryHigh": 0.7,
                    "fractionPlddtConfident": 0.2,
                    "fractionPlddtLow": 0.07,
                    "fractionPlddtVeryLow": 0.03,
                    "cifUrl": "https://alphafold.ebi.ac.uk/files/AF-TEST2-F1-model_v6.cif",
                }
            ]
        )
    )
    monkeypatch.setattr(
        "accessible_surfaceome.tools.afdb_plddt.AFDB_CACHE_DIR", cache
    )

    sf = fetch_afdb_plddt("TEST2", per_residue_topology="IIIIIIIIII")
    assert sf.ecd_mean_plddt == pytest.approx(88.5)
    # fractionPlddtLow + fractionPlddtVeryLow = 0.07 + 0.03 = 0.10
    assert sf.ecd_disordered_fraction == pytest.approx(0.10)
    assert "whole-protein" in sf.source.lower()


def test_topology_none_uses_global_metric(tmp_path: Path, monkeypatch):
    """No topology hint → fetcher uses whole-protein stats from the
    JSON. Same fallback as the no-ECD case but flagged differently."""
    cache = tmp_path / "afdb_prediction"
    cache.mkdir()
    (cache / "TEST3.json").write_text(
        json.dumps(
            [
                {
                    "entryId": "AF-TEST3-F1",
                    "uniprotAccession": "TEST3",
                    "globalMetricValue": 75.0,
                    "fractionPlddtVeryHigh": 0.4,
                    "fractionPlddtConfident": 0.3,
                    "fractionPlddtLow": 0.2,
                    "fractionPlddtVeryLow": 0.1,
                    "cifUrl": "https://alphafold.ebi.ac.uk/files/AF-TEST3-F1-model_v6.cif",
                }
            ]
        )
    )
    monkeypatch.setattr(
        "accessible_surfaceome.tools.afdb_plddt.AFDB_CACHE_DIR", cache
    )

    sf = fetch_afdb_plddt("TEST3", per_residue_topology=None)
    assert sf.ecd_mean_plddt == pytest.approx(75.0)
    assert sf.ecd_disordered_fraction == pytest.approx(0.30)


def test_404_returns_labeled_stub_without_crashing(tmp_path: Path, monkeypatch):
    """Some isoforms / accs aren't in AFDB. Return a placeholder so
    the orchestrator can still assemble a SurfaceomeRecord."""
    cache = tmp_path / "afdb_prediction"
    cache.mkdir()
    monkeypatch.setattr(
        "accessible_surfaceome.tools.afdb_plddt.AFDB_CACHE_DIR", cache
    )

    fake_client = MagicMock()
    fake_resp = MagicMock()
    fake_resp.status_code = 404
    fake_resp.raise_for_status.side_effect = Exception("404 Not Found")
    fake_client.get.return_value = fake_resp

    with patch("httpx.Client", return_value=fake_client):
        sf = fetch_afdb_plddt("MISSING1", per_residue_topology="OOOO")

    assert sf.ecd_mean_plddt == 0.0
    assert sf.ecd_disordered_fraction == 0.0
    assert "placeholder" in sf.source.lower() or "fetch failed" in sf.source.lower()


def _make_synthetic_cif(plddts: list[float]) -> str:
    """Render a minimal CIF with one CA atom per residue and the
    B-factor (which AFDB overloads as pLDDT) set per residue.

    The fetcher only reads B-factor + residue index from the
    ``_atom_site`` loop; everything else can be skipped.
    """
    rows = []
    for i, plddt in enumerate(plddts, start=1):
        rows.append(
            f"ATOM   {i:5d} C  CA  . ALA A 1 {i:4d} ?  "
            f"{i:.3f}  0.000  0.000  1.00 {plddt:.2f}  ? {i} ALA A CA  1"
        )
    body = "\n".join(rows)
    return (
        "data_TEST\n"
        "loop_\n"
        "_atom_site.group_PDB\n"
        "_atom_site.id\n"
        "_atom_site.type_symbol\n"
        "_atom_site.label_atom_id\n"
        "_atom_site.label_alt_id\n"
        "_atom_site.label_comp_id\n"
        "_atom_site.label_asym_id\n"
        "_atom_site.label_entity_id\n"
        "_atom_site.label_seq_id\n"
        "_atom_site.pdbx_PDB_ins_code\n"
        "_atom_site.Cartn_x\n"
        "_atom_site.Cartn_y\n"
        "_atom_site.Cartn_z\n"
        "_atom_site.occupancy\n"
        "_atom_site.B_iso_or_equiv\n"
        "_atom_site.pdbx_formal_charge\n"
        "_atom_site.auth_seq_id\n"
        "_atom_site.auth_comp_id\n"
        "_atom_site.auth_asym_id\n"
        "_atom_site.auth_atom_id\n"
        "_atom_site.pdbx_PDB_model_num\n"
        f"{body}\n"
    )
