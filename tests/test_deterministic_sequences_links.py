"""Guard the deterministic_features sequence + AFDB/PDB-link additions.

These fields make the per-gene API/record self-contained — the sequence
each ``per_residue_topology`` indexes, the AFDB model download URLs, and a
pointer to the representative experimental (PDB) structure. The invariants
that must hold:

  * Every topology entity that carries a ``sequence`` has it length-aligned
    1:1 with its ``per_residue_topology`` (so residue *i* of the topology
    string refers to residue *i* of the sequence).
  * ``RepresentativeStructure`` round-trips through the schema.
  * The new fields are present + optional on the models (back-compat: a
    record without them still validates).

Validates the ``deterministic_features`` sub-block only (not the whole
``SurfaceomeRecord``) so unrelated schema drift elsewhere in a snapshot
can't mask a regression here.
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from accessible_surfaceome.tools._shared.models import (
    DeterministicFeatures,
    IsoformTopology,
    OrthologEntry,
    ParalogEntry,
    RepresentativeStructure,
    StructureFeatures,
    SurfaceBindFeatures,
)

_ROOT = Path(__file__).resolve().parents[1]
_SNAPSHOT_DIR = _ROOT / "viewer" / "public" / "data" / "surfaceome"


def _topology_entities(df: dict) -> list[tuple[str, dict]]:
    """(label, entity-dict) for every topology-bearing entity in a record."""
    out: list[tuple[str, dict]] = []
    ct = df.get("canonical_topology")
    if ct:
        out.append(("canonical", ct))
    for i, iso in enumerate(df.get("isoform_topologies") or []):
        out.append((f"isoform[{i}]", iso))
    orth = df.get("orthologs") or {}
    for sp in ("mouse", "cynomolgus"):
        for i, o in enumerate(orth.get(sp) or []):
            out.append((f"ortholog.{sp}[{i}]", o))
    for i, p in enumerate(df.get("paralogs") or []):
        out.append((f"paralog[{i}]", p))
    return out


def test_new_fields_present_and_optional() -> None:
    """The sequence + link fields exist on the models AND default to None
    (so a pre-backfill record still validates)."""
    for model in (IsoformTopology, OrthologEntry, ParalogEntry):
        assert "sequence" in model.model_fields
        assert model.model_fields["sequence"].default is None
    for field in (
        "model_cif_url",
        "model_pdb_url",
        "model_pae_url",
    ):
        assert field in StructureFeatures.model_fields
        assert StructureFeatures.model_fields[field].default is None
    # PR #54 moved the experimental-structure pointer from StructureFeatures
    # to SurfaceBindFeatures.representative_structure (A1.10), so the
    # presence assertion lives on that side now.
    assert "representative_structure" in SurfaceBindFeatures.model_fields
    assert SurfaceBindFeatures.model_fields["representative_structure"].default is None


def test_representative_structure_round_trips() -> None:
    rs = RepresentativeStructure(
        pdb_id="7syd",
        chain="A",
        residue_start=1,
        residue_end=1210,
        coverage_fraction=1.0,
        resolution_angstrom=3.1,
        method="Electron Microscopy",
    )
    again = RepresentativeStructure.model_validate(json.loads(rs.model_dump_json()))
    assert again == rs
    # A fragment structure (sub-span) is just as valid.
    frag = RepresentativeStructure(
        pdb_id="6mfa", chain="A", residue_start=903, residue_end=1268
    )
    assert frag.residue_end is not None and frag.residue_start is not None
    assert frag.residue_end - frag.residue_start + 1 == 366


def _snapshots() -> list[Path]:
    return sorted(_SNAPSHOT_DIR.glob("*.json"))


@pytest.mark.skipif(not _SNAPSHOT_DIR.exists(), reason="no snapshot dir")
@pytest.mark.parametrize("snap", _snapshots(), ids=lambda p: p.stem)
def test_snapshot_sequences_align_with_topology(snap: Path) -> None:
    """Every stored sequence is length-aligned with its topology, and the
    deterministic_features block validates against the schema."""
    rec = json.loads(snap.read_text())
    df = rec.get("deterministic_features")
    if not df:
        pytest.skip(f"{snap.stem}: no deterministic_features")
    # Block-level validation — immune to unrelated drift elsewhere.
    DeterministicFeatures.model_validate(df)
    for label, ent in _topology_entities(df):
        seq = ent.get("sequence")
        topo = ent.get("per_residue_topology")
        if seq is None:
            continue
        assert topo, f"{snap.stem} {label}: sequence present but topology empty"
        assert len(seq) == len(topo), (
            f"{snap.stem} {label}: sequence ({len(seq)}) != topology ({len(topo)})"
        )


@pytest.mark.skipif(not _SNAPSHOT_DIR.exists(), reason="no snapshot dir")
def test_representative_structure_span_within_canonical() -> None:
    """Where a snapshot carries a representative structure AND a canonical
    sequence, the structure's UniProt span fits inside the canonical."""
    checked = 0
    for snap in _snapshots():
        df = (json.loads(snap.read_text()) or {}).get("deterministic_features") or {}
        # PR #54: the pointer is on surface_bind, not structure.
        sb = df.get("surface_bind") or {}
        rep = sb.get("representative_structure")
        ct = df.get("canonical_topology") or {}
        canon_seq = ct.get("sequence")
        if not rep or not canon_seq:
            continue
        checked += 1
        assert 1 <= rep["residue_start"] <= rep["residue_end"] <= len(canon_seq), (
            f"{snap.stem}: rep structure span {rep['residue_start']}-{rep['residue_end']} "
            f"outside canonical (len {len(canon_seq)})"
        )
    # In-tree snapshots predate PR #54's move and were stripped of the
    # pre-move ``structure.representative_experimental_structure`` block;
    # the new ``surface_bind.representative_structure`` will populate
    # once a v2 deep-dive re-annotates the cohort.
    if checked == 0:
        pytest.skip("no snapshot yet carries surface_bind.representative_structure")
