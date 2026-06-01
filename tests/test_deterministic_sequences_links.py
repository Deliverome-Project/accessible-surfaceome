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
        "representative_experimental_structure",
    ):
        assert field in StructureFeatures.model_fields
        assert StructureFeatures.model_fields[field].default is None


def test_representative_structure_round_trips() -> None:
    rs = RepresentativeStructure(
        pdb_id="7syd",
        chain_id="A",
        unp_start=1,
        unp_end=1210,
        coverage=1.0,
        resolution_a=3.1,
        experimental_method="Electron Microscopy",
        n_experimental_structures=642,
    )
    again = RepresentativeStructure.model_validate(json.loads(rs.model_dump_json()))
    assert again == rs
    # A fragment structure (sub-span) is just as valid.
    frag = RepresentativeStructure(
        pdb_id="6mfa", chain_id="A", unp_start=903, unp_end=1268
    )
    assert frag.unp_end - frag.unp_start + 1 == 366


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
        st = df.get("structure") or {}
        rep = st.get("representative_experimental_structure")
        ct = df.get("canonical_topology") or {}
        canon_seq = ct.get("sequence")
        if not rep or not canon_seq:
            continue
        checked += 1
        assert 1 <= rep["unp_start"] <= rep["unp_end"] <= len(canon_seq), (
            f"{snap.stem}: rep structure span {rep['unp_start']}-{rep['unp_end']} "
            f"outside canonical (len {len(canon_seq)})"
        )
    # At least one snapshot should exercise this (EGFR ships in-tree).
    assert checked >= 1
