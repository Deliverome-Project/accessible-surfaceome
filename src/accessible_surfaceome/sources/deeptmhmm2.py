"""DeepTMHMM2 output → ``topology_public`` row values.

DeepTMHMM2 writes four files per run; this module reads ``predictions.json``, which
carries everything the other three do. Each record is::

    {"id": ..., "type": "Alpha TM", "membrane_types": [...],
     "membrane_types_probabilities": [...], "topology_string": ...,
     "segments": [[name, start, end], ...]}

The job here is the projection from that onto the v1 column contract, which is where all
the subtlety lives. See ``cloudflare/migrations/topology_public_dtm2.sql`` for the schema
this fills and why it is shaped that way.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from itertools import groupby
from pathlib import Path
from typing import Any

# Mirrors of deeptmhmm2_predictor.constants. Duplicated rather than imported because the
# predictor pulls in torch, lightning and fair-esm; nothing that reads published rows
# should need a GPU stack to interpret them. test_deeptmhmm2.py asserts these stay equal
# to upstream whenever the predictor happens to be installed.
MEMBRANE_TYPE_NAMES: dict[int, str] = {
    0: "Archaebacterial membrane",
    1: "Bacterial Gram-negative inner membrane",
    2: "Bacterial Gram-negative outer membrane",
    3: "Eukaryotic plasma membrane",
    4: "Mitochondrial inner membrane",
    5: "Endoplasmic reticulum membrane",
    6: "Thylakoid membrane",
    7: "Bacterial Gram-positive plasma membrane",
    8: "Golgi membrane",
    9: "Nuclear inner membrane",
    11: "Endosome membrane",
    12: "Vacuole membrane",
    13: "Vesicle membrane",
    14: "Viral membrane",
    16: "Chloroplast outer membrane",
    17: "Mitochondrial outer membrane",
    18: "Lysosome membrane",
}

PLASMA_MEMBRANE_IDX = 3
PLASMA_MEMBRANE_NAME = MEMBRANE_TYPE_NAMES[PLASMA_MEMBRANE_IDX]

# side-character -> membrane index, built from MEMBRANE_TOPOLOGY_MAP. The 'a'/'b' keys are
# the model's own two sides; which of them is cytoplasmic is *not* a function of letter
# case. Indices 16 and 17 (chloroplast / mitochondrial outer membrane) invert the sense
# that every other index uses, so decoding by case silently flips inside and outside for
# every VDAC, TOMM40 and SAMM50 in the set.
MEMBRANE_TOPOLOGY_MAP: dict[int, dict[str, str]] = {
    0: {"a": "A", "b": "a"},
    1: {"a": "C", "b": "c"},
    2: {"b": "D", "a": "d"},
    3: {"a": "E", "b": "e"},
    4: {"a": "G", "b": "g"},
    5: {"a": "H", "b": "h"},
    6: {"a": "J", "b": "j"},
    7: {"a": "K", "b": "k"},
    8: {"a": "L", "b": "l"},
    9: {"a": "N", "b": "n"},
    10: {"a": "Z", "b": "z"},
    11: {"a": "P", "b": "p"},
    12: {"a": "Q", "b": "q"},
    13: {"a": "T", "b": "t"},
    14: {"a": "V", "b": "v"},
    15: {"a": "W", "b": "w"},
    16: {"b": "X", "a": "x"},
    17: {"b": "Y", "a": "y"},
    18: {"a": "3", "b": "4"},
    19: {"a": "5", "b": "6"},
    20: {"a": "7", "b": "8"},
}

# Which of the two sides is the cytoplasm-facing one, per membrane index.
CYTOPLASMIC_SIDE: dict[int, str] = {
    0: "a",
    1: "a",
    2: "a",
    3: "a",
    4: "a",
    5: "a",
    6: "a",
    7: "a",
    8: "a",
    9: "a",
    10: "a",
    11: "a",
    12: "a",
    13: "a",
    14: "a",
    15: "a",
    16: "b",
    17: "b",  # outer membranes: 'b' faces the cytosol
    18: "a",
    19: "a",
    20: "a",
}

DISPLAY_TO_TYPE_CODE: dict[str, str] = {
    "Alpha TM": "M",
    "Alpha TM + SP": "M+S",
    "Globular + SP": "S",
    "Globular": "I",
    "Beta Barrel": "B",
    "Alpha TM + TP": "M+T",
    "Globular + TP": "T",
}

# v1's five-value vocabulary. Lossy by construction — dtm2_structural_type keeps the
# finer call. M+R / M+F / M+R+F are absent because infer_structural_type() cannot return
# them; they are CRF training labels only. Reentrant and interfacial segments are recorded
# by their own count columns, which is the sole place that signal survives.
TYPE_CODE_TO_V1_LABEL: dict[str, str] = {
    "M": "TM",
    "M+S": "SP+TM",
    "M+T": "TM",
    "S": "SP",
    "I": "GLOB",
    "T": "GLOB",  # a transit peptide is not a secretory signal peptide
    "B": "BETA",
}

NON_MEMBRANE_TYPE_CODES = frozenset({"I", "S", "T"})

# Projection onto v1's {S,O,M,I,B} alphabet. Side characters resolve per row; these are
# the state characters:
#
#   S  signal peptide       -> S   exact
#   M  alpha TM helix       -> M   exact
#   B  beta strand          -> B   exact
#   R  reentrant loop       -> M   LOSSY: membrane-embedded but not spanning; v1 has no
#                                   such state and would have emitted M or a side
#   F  interfacial helix    -> M   LOSSY: same
#   >  transit peptide      -> I   LOSSY: cleaved, cytosolically synthesised; mapping it
#                                   to S would corrupt signal_peptide_length
#
# Every summary count (tm_helix_count, signal_peptide_length, ecd/icd lengths) is computed
# from the v2 string, never from this projection, so R/F->M cannot inflate a helix count.
V1_STATE_PROJECTION: dict[str, str] = {
    "S": "S",
    "M": "M",
    "B": "B",
    "R": "M",
    "F": "M",
    ">": "I",
}
LOSSY_STATES = frozenset({"R", "F", ">"})


class Deeptmhmm2Error(ValueError):
    """Raised when a prediction record cannot be projected onto the schema."""


@dataclass(frozen=True)
class Prediction:
    """One protein's v2 prediction, decoded into schema-ready values."""

    accession: str
    type_code: str
    structural_type: str
    topology_string: str
    main_membrane_type: str | None
    main_membrane_type_idx: int | None
    membrane_types: list[str]
    membrane_type_probs: dict[str, float]

    # ---- v2-native summaries, all from topology_string ---------------------- #

    @property
    def sides(self) -> str:
        """``topology_string`` with side characters normalised to I/O, states kept.

        The one decode that everything else goes through. Non-membrane proteins already
        carry plain I/O, and everything else resolves through this row's membrane index.
        """
        if self.main_membrane_type_idx is None:
            unknown = set(self.topology_string) - set("IO") - set(V1_STATE_PROJECTION)
            if unknown:
                raise Deeptmhmm2Error(
                    f"{self.accession}: no membrane type, but topology carries "
                    f"membrane-specific characters {sorted(unknown)}"
                )
            return self.topology_string
        mapping = MEMBRANE_TOPOLOGY_MAP[self.main_membrane_type_idx]
        cyto = CYTOPLASMIC_SIDE[self.main_membrane_type_idx]
        other = "b" if cyto == "a" else "a"
        decode = {mapping[cyto]: "I", mapping[other]: "O"}
        out = []
        for char in self.topology_string:
            if char in decode:
                out.append(decode[char])
            elif char in V1_STATE_PROJECTION:
                out.append(char)
            else:
                raise Deeptmhmm2Error(
                    f"{self.accession}: character {char!r} is neither a state nor a side "
                    f"of membrane type {self.main_membrane_type_idx}"
                )
        return "".join(out)

    def _segment_count(self, state: str) -> int:
        return sum(1 for char, _ in groupby(self.topology_string) if char == state)

    @property
    def tm_helix_count(self) -> int:
        return self._segment_count("M")

    @property
    def beta_strand_count(self) -> int:
        return self._segment_count("B")

    @property
    def reentrant_count(self) -> int:
        return self._segment_count("R")

    @property
    def interfacial_count(self) -> int:
        return self._segment_count("F")

    @property
    def signal_peptide_length(self) -> int:
        return self.topology_string.count("S")

    @property
    def transit_peptide_length(self) -> int:
        return self.topology_string.count(">")

    @property
    def v1_alphabet(self) -> str:
        """The {S,O,M,I,B} projection written to ``per_residue_topology``."""
        return "".join(V1_STATE_PROJECTION.get(c, c) for c in self.sides)

    @property
    def v1_alphabet_lossy(self) -> bool:
        return bool(LOSSY_STATES & set(self.topology_string))

    @property
    def ecd_length_residues(self) -> int:
        return self.v1_alphabet.count("O")

    @property
    def icd_length_residues(self) -> int:
        return self.v1_alphabet.count("I")

    def _terminus(self, end: str) -> str:
        """First/last side after skipping cleaved N-terminal peptides — the v1 rule."""
        mature = self.sides.lstrip("S>").rstrip("S>")
        if not mature:
            return "indeterminate"
        char = mature[0] if end == "n" else mature[-1]
        # v1 treats a beta-strand terminus as extracellular; keep that.
        return {"O": "extracellular", "B": "extracellular", "I": "cytoplasmic"}.get(
            char, "indeterminate"
        )

    @property
    def n_terminal_orientation(self) -> str:
        return self._terminus("n")

    @property
    def c_terminal_orientation(self) -> str:
        return self._terminus("c")

    @property
    def v1_label(self) -> str:
        return TYPE_CODE_TO_V1_LABEL[self.type_code]

    @property
    def plasma_membrane(self) -> bool:
        return PLASMA_MEMBRANE_NAME in self.membrane_types

    @property
    def plasma_membrane_prob(self) -> float:
        return self.membrane_type_probs.get(PLASMA_MEMBRANE_NAME, 0.0)

    def segments(self) -> list[tuple[str, int, int]]:
        """Reconstruct the run-length segment list that is deliberately not stored."""
        names = {
            "S": "signal",
            "M": "TMhelix",
            "B": "Beta sheet",
            "R": "reentrant",
            "F": "interfacial",
            ">": "transit_peptide",
            "I": "inside",
            "O": "outside",
        }
        out: list[tuple[str, int, int]] = []
        pos = 1
        for char, group in groupby(self.sides):
            length = len(list(group))
            out.append((names[char], pos, pos + length - 1))
            pos += length
        return out

    # ---- schema ------------------------------------------------------------- #

    def columns(self) -> dict[str, Any]:
        """Every ``topology_public`` column this prediction determines.

        Identity columns (accession, cohort, hgnc_id, sequence, ...) are carried over from
        the v1 row by the uploader — the input was the v1 row's own stored sequence, so
        re-deriving them here would be a second chance to get them wrong.
        """
        return {
            # v1 columns, filled under the v1 contract
            "deeptmhmm_label": self.v1_label,
            "tm_helix_count": self.tm_helix_count,
            "beta_strand_count": self.beta_strand_count,
            "n_terminal_orientation": self.n_terminal_orientation,
            "c_terminal_orientation": self.c_terminal_orientation,
            "signal_peptide_length": self.signal_peptide_length,
            "ecd_length_residues": self.ecd_length_residues,
            "icd_length_residues": self.icd_length_residues,
            "per_residue_topology": self.v1_alphabet,
            "predicted_surface_membrane": int(self.v1_label in {"TM", "SP+TM"}),
            "predicted_secreted": int(self.v1_label == "SP"),
            # v2-only
            "dtm2_structural_type": self.structural_type,
            "dtm2_topology_string": self.topology_string,
            "dtm2_v1_alphabet_lossy": int(self.v1_alphabet_lossy),
            "dtm2_main_membrane_type": self.main_membrane_type,
            "dtm2_main_membrane_type_idx": self.main_membrane_type_idx,
            "dtm2_membrane_types": json.dumps(self.membrane_types),
            "dtm2_membrane_type_probs": json.dumps(self.membrane_type_probs),
            "dtm2_plasma_membrane": int(self.plasma_membrane),
            "dtm2_plasma_membrane_prob": self.plasma_membrane_prob,
            "dtm2_reentrant_count": self.reentrant_count,
            "dtm2_interfacial_count": self.interfacial_count,
            "dtm2_transit_peptide_length": self.transit_peptide_length,
        }


def _type_code(display: str) -> str:
    """The model's structural code for a display string.

    A plain inversion, not an inference. ``infer_structural_type`` reaches exactly seven
    codes and ``DISPLAY_PROT_TYPE_MAPPING`` is injective over those seven, so the display
    string determines the code. (The mapping is non-injective over the full ten-label CRF
    vocabulary, but M+R / M+F / M+R+F are training labels the predictor never emits.)
    """
    try:
        return DISPLAY_TO_TYPE_CODE[display]
    except KeyError:
        raise Deeptmhmm2Error(f"unknown structural type {display!r}") from None


def parse_record(record: dict[str, Any]) -> Prediction:
    """Decode one ``predictions.json`` entry."""
    accession = record["id"]
    topology = record["topology_string"]
    display = record["type"]
    type_code = _type_code(display)

    names = list(record["membrane_types"])
    raw_probs = record["membrane_types_probabilities"]
    probs = {
        name: round(float(raw_probs[idx]), 2)
        for idx, name in MEMBRANE_TYPE_NAMES.items()
        if idx < len(raw_probs)
    }

    if type_code in NON_MEMBRANE_TYPE_CODES:
        # The predictor zeroes membrane types for globular / SP-only / TP-only proteins.
        # Keep that: a probability vector of zeros is not evidence of a compartment.
        return Prediction(
            accession=accession,
            type_code=type_code,
            structural_type=display,
            topology_string=topology,
            main_membrane_type=None,
            main_membrane_type_idx=None,
            membrane_types=[],
            membrane_type_probs={},
        )

    if not names:
        raise Deeptmhmm2Error(f"{accession}: membrane protein ({display}) with no type")
    by_name = {name: idx for idx, name in MEMBRANE_TYPE_NAMES.items()}
    unknown = [n for n in names if n not in by_name]
    if unknown:
        raise Deeptmhmm2Error(f"{accession}: unrecognised membrane type(s) {unknown}")
    ordered = sorted(names, key=lambda n: probs.get(n, 0.0), reverse=True)
    return Prediction(
        accession=accession,
        type_code=type_code,
        structural_type=display,
        topology_string=topology,
        main_membrane_type=ordered[0],
        main_membrane_type_idx=by_name[ordered[0]],
        membrane_types=ordered,
        membrane_type_probs=probs,
    )


def parse_predictions(path: Path) -> list[Prediction]:
    """Read a shard's ``predictions.json``, skipping its trailing metadata entry."""
    payload = json.loads(Path(path).read_text())
    return [parse_record(r) for r in payload if "metadata" not in r]
