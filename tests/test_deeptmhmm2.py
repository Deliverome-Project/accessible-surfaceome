"""Projection of DeepTMHMM2 output onto the topology_public schema."""

from __future__ import annotations

import importlib.util
import json
import re
from pathlib import Path

import pytest

from accessible_surfaceome.sources import deeptmhmm2 as d2

MIGRATION = (
    Path(__file__).resolve().parents[1]
    / "cloudflare/migrations/topology_public_dtm2.sql"
)


def _record(
    topology: str, display: str, types: list[str], probs: dict[str, float] | None = None
):
    vec = [0.0] * 21
    for name, p in (probs or {}).items():
        idx = next(i for i, n in d2.MEMBRANE_TYPE_NAMES.items() if n == name)
        vec[idx] = p
    return {
        "id": "TEST-1",
        "type": display,
        "membrane_types": types,
        "membrane_types_probabilities": vec,
        "topology_string": topology,
    }


PM = "Eukaryotic plasma membrane"
MOM = "Mitochondrial outer membrane"


# --------------------------------------------------------------------------- #
# the mirrored constants must not drift from upstream
# --------------------------------------------------------------------------- #


def _upstream_constants():
    """Load the predictor's constants.py by file path, without importing the package.

    ``import deeptmhmm2_predictor.constants`` runs the package __init__, which pulls in
    torch, lightning and fair-esm. Loading the one file directly — it imports nothing but
    ``typing`` — lets this drift guard run in ordinary CI instead of being skipped
    everywhere the GPU stack is absent, which is everywhere that matters.
    """
    from importlib.metadata import PackageNotFoundError, files

    try:
        paths = files("deeptmhmm2_predictor") or []
    except PackageNotFoundError:
        pytest.skip("deeptmhmm2_predictor not installed")
    for entry in paths:
        if entry.name == "constants.py" and entry.parent.name == "deeptmhmm2_predictor":
            spec = importlib.util.spec_from_file_location("_dtm2_up", entry.locate())
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)
            return module
    pytest.skip("constants.py not found in the installed predictor")


# Region names that mean "the cytosol-facing side" across the compartments modelled.
CYTOPLASM_FACING = frozenset(
    {
        "Cytoplasmic",
        "Mitochondrial matrix",
        "Stroma",
        "Nucleus matrix",
        "Extracellular",
        "Intravirion",
    }
)


def test_constants_match_upstream():
    up = _upstream_constants()
    assert d2.MEMBRANE_TYPE_NAMES == up.MEMBRANE_TYPE_NAMES
    assert d2.MEMBRANE_TOPOLOGY_MAP == up.MEMBRANE_TOPOLOGY_MAP


def test_cytoplasmic_side_agrees_with_upstream_region_names():
    """Which of 'a'/'b' faces the cytosol, checked against upstream's own naming.

    This is the guard that matters: indices 16 and 17 invert the sense every other
    compartment uses, so a mirror that drifted here would flip ECD and ICD for the
    mitochondrial and chloroplast outer membranes without any other test noticing.
    """
    up = _upstream_constants()
    inverted = set()
    for idx, sides in up.MEMBRANE_REGION_NAMES.items():
        cyto = d2.CYTOPLASMIC_SIDE[idx]
        other = "b" if cyto == "a" else "a"
        assert sides[cyto] in CYTOPLASM_FACING, (
            f"idx {idx}: {sides[cyto]!r} is not cytosolic"
        )
        assert sides[cyto] != sides[other]
        if cyto == "b":
            inverted.add(idx)
    assert inverted == {16, 17}, "the set of inverted-sense membranes changed upstream"


def test_display_mapping_is_injective_over_reachable_codes():
    upstream = pytest.importorskip(
        "deeptmhmm2_predictor.constants", reason="not installed"
    )
    infer = pytest.importorskip(
        "deeptmhmm2_predictor.utils.postprocessing"
    ).infer_structural_type
    # Every code infer_structural_type can actually return, exercised through it.
    reachable = {infer(t) for t in ["IBI", "IMI", "SIMI", ">IMI", "SII", ">II", "III"]}
    assert reachable == set(d2.DISPLAY_TO_TYPE_CODE.values())
    displays = [upstream.DISPLAY_PROT_TYPE_MAPPING[c] for c in reachable]
    assert len(set(displays)) == len(displays), (
        "display strings collide over reachable codes"
    )


# --------------------------------------------------------------------------- #
# side decoding
# --------------------------------------------------------------------------- #


def test_plasma_membrane_sides_decode():
    # idx 3: 'a'->'E' cytoplasmic, 'b'->'e' extracellular.
    pred = d2.parse_record(_record("eeeMMMEEE", "Alpha TM", [PM], {PM: 0.9}))
    assert pred.main_membrane_type_idx == 3
    assert pred.sides == "OOOMMMIII"
    assert pred.n_terminal_orientation == "extracellular"
    assert pred.c_terminal_orientation == "cytoplasmic"


def test_outer_membrane_sense_is_inverted():
    """Index 17 maps 'b'->'Y' and 'b' is the cytosolic side — case is not the rule.

    Decoding by letter case would flip inside and outside for every VDAC, TOMM40 and
    SAMM50 in the human set.
    """
    pred = d2.parse_record(_record("YYYBBByyy", "Beta Barrel", [MOM], {MOM: 0.8}))
    assert pred.main_membrane_type_idx == 17
    assert pred.sides == "IIIBBBOOO"
    assert pred.icd_length_residues == 3
    assert pred.ecd_length_residues == 3


def test_the_topology_string_decides_the_membrane_not_the_probabilities():
    """The string wins over the reported probabilities. This is the H3BTG2 case.

    predictions.json stores membrane_types_probabilities already rounded to 2dp, so ties
    are common and the predictor's own argmax is not recoverable from them. H3BTG2 has ER
    and nuclear inner membrane both at 0.39; the predictor translated with nuclear, and
    re-deriving from the rounded values picks ER, after which every side character in the
    string is unreadable and the whole row is wrong.
    """
    rec = _record(
        "nnnMMMNNN",
        "Alpha TM",
        ["Endoplasmic reticulum membrane", "Nuclear inner membrane"],
        {"Endoplasmic reticulum membrane": 0.39, "Nuclear inner membrane": 0.39},
    )
    pred = d2.parse_record(rec)
    assert pred.main_membrane_type == "Nuclear inner membrane"  # 'n'/'N' are index 9
    assert pred.main_membrane_type_idx == 9
    assert pred.membrane_types[0] == "Nuclear inner membrane"
    assert pred.sides == "OOOMMMIII"


def test_side_characters_from_two_membranes_are_refused():
    """A string cannot be written in two compartments at once; that is corrupt input."""
    rec = _record("EEEMMMlll", "Alpha TM", [PM, "Golgi membrane"], {PM: 0.9})
    with pytest.raises(d2.Deeptmhmm2Error, match="mixes side characters"):
        d2.parse_record(rec)


def test_unknown_character_is_refused_not_guessed():
    pred = d2.parse_record(_record("eeeMMMEEE", "Alpha TM", [PM], {PM: 0.9}))
    bad = d2.Prediction(**{**pred.__dict__, "topology_string": "eeeMMM???"})
    with pytest.raises(d2.Deeptmhmm2Error, match="neither a state nor a side"):
        _ = bad.sides


# --------------------------------------------------------------------------- #
# the v1 projection
# --------------------------------------------------------------------------- #


def test_v1_projection_is_exact_when_no_v2_only_states():
    pred = d2.parse_record(_record("SSSSSeeeMMMEEE", "Alpha TM + SP", [PM], {PM: 0.9}))
    assert pred.v1_alphabet == "SSSSSOOOMMMIII"
    assert pred.v1_alphabet_lossy is False
    assert set(pred.v1_alphabet) <= set("SOMIB")
    assert pred.signal_peptide_length == 5
    assert pred.v1_label == "SP+TM"


@pytest.mark.parametrize("state", ["R", "F", ">"])
def test_v2_only_states_flag_the_projection_lossy(state):
    pred = d2.parse_record(
        _record(f"EEE{state}{state}EEEMMMeee", "Alpha TM", [PM], {PM: 0.9})
    )
    assert pred.v1_alphabet_lossy is True
    assert set(pred.v1_alphabet) <= set("SOMIB")


def test_counts_come_from_the_v2_string_not_the_projection():
    """R and F project to M; if the counts read the projection they would inflate."""
    pred = d2.parse_record(_record("EEERREEEMMMeee", "Alpha TM", [PM], {PM: 0.9}))
    assert pred.v1_alphabet == "IIIMMIIIMMMOOO"  # two M runs in the projection
    assert pred.tm_helix_count == 1  # but only one real helix
    assert pred.reentrant_count == 1
    assert pred.interfacial_count == 0


def test_transit_peptide_is_not_counted_as_signal_peptide():
    pred = d2.parse_record(_record(">>>>EEEMMMeee", "Alpha TM + TP", [PM], {PM: 0.9}))
    assert pred.transit_peptide_length == 4
    assert pred.signal_peptide_length == 0
    assert pred.v1_label == "TM"
    # cleaved N-terminal peptides are skipped for the terminus call, as in v1
    assert pred.n_terminal_orientation == "cytoplasmic"


# --------------------------------------------------------------------------- #
# membrane type
# --------------------------------------------------------------------------- #


def test_multi_label_types_reported_with_the_strings_membrane_first():
    """All types over threshold are kept; the one the string is written in leads."""
    rec = _record(
        "LLLMMMlll",
        "Alpha TM",
        [PM, "Golgi membrane"],
        {PM: 0.40, "Golgi membrane": 0.85},
    )
    pred = d2.parse_record(rec)
    assert pred.main_membrane_type == "Golgi membrane"
    assert pred.membrane_types == ["Golgi membrane", PM]
    assert pred.plasma_membrane is True  # still a member of the set
    assert pred.plasma_membrane_prob == 0.40


def test_probability_is_kept_even_when_the_call_is_negative():
    """The PM threshold is 0.172; a near-miss must stay re-thresholdable."""
    rec = _record(
        "LLLMMMlll", "Alpha TM", ["Golgi membrane"], {PM: 0.17, "Golgi membrane": 0.85}
    )
    pred = d2.parse_record(rec)
    assert pred.plasma_membrane is False
    assert pred.plasma_membrane_prob == 0.17
    assert json.loads(pred.columns()["dtm2_membrane_type_probs"])[PM] == 0.17


def test_non_membrane_proteins_carry_no_compartment():
    pred = d2.parse_record(_record("IIIIOOOO", "Globular", [], {}))
    assert pred.main_membrane_type is None
    assert pred.membrane_types == []
    assert pred.columns()["dtm2_membrane_types"] == "[]"
    assert pred.plasma_membrane is False
    assert pred.v1_label == "GLOB"


def test_membrane_protein_without_a_type_is_refused():
    with pytest.raises(d2.Deeptmhmm2Error, match="no type"):
        d2.parse_record(_record("EEEMMMeee", "Alpha TM", [], {}))


# --------------------------------------------------------------------------- #
# schema agreement — the module and the migration must not drift apart
# --------------------------------------------------------------------------- #


def test_columns_match_the_migration_exactly():
    declared = set(
        re.findall(
            r"^ALTER TABLE topology_public ADD COLUMN (\w+)",
            MIGRATION.read_text(),
            re.M,
        )
    )
    assert declared, "no ADD COLUMN statements parsed from the migration"
    pred = d2.parse_record(_record("SSSeeeMMMEEE", "Alpha TM + SP", [PM], {PM: 0.9}))
    produced = {k for k in pred.columns() if k.startswith("dtm2_")}
    assert produced == declared


def test_v1_columns_produced_all_exist_in_the_v1_schema():
    schema = (MIGRATION.parent.parent / "d1_public_schema.sql").read_text()
    body = schema[schema.index("CREATE TABLE IF NOT EXISTS topology_public") :]
    body = body[: body.index(");")]
    v1_cols = set(re.findall(r"^\s{4}(\w+)\s", body, re.M))
    pred = d2.parse_record(_record("SSSeeeMMMEEE", "Alpha TM + SP", [PM], {PM: 0.9}))
    produced = {k for k in pred.columns() if not k.startswith("dtm2_")}
    assert produced <= v1_cols, f"not real v1 columns: {sorted(produced - v1_cols)}"


def test_segments_round_trip_the_topology_string():
    pred = d2.parse_record(_record("SSSeeeMMMEEE", "Alpha TM + SP", [PM], {PM: 0.9}))
    segs = pred.segments()
    assert segs == [
        ("signal", 1, 3),
        ("outside", 4, 6),
        ("TMhelix", 7, 9),
        ("inside", 10, 12),
    ]
    assert segs[-1][2] == len(pred.topology_string)
