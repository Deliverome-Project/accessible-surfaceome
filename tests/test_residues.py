"""Residue sanitisation, and the drift guard against the Modal app's copy."""

from __future__ import annotations

import ast
import re
from pathlib import Path

import pytest

from accessible_surfaceome.sources.residues import SUBSTITUTIONS, sanitise

APP = Path(__file__).resolve().parents[1] / "modal/disorder_app.py"


def test_standard_sequence_is_returned_untouched():
    assert sanitise("MKVLAA") == ("MKVLAA", False)


@pytest.mark.parametrize(
    "raw,expected",
    [
        ("MKUVLAA", "MKCVLAA"),  # selenocysteine -> cysteine
        ("MKOVLAA", "MKKVLAA"),  # pyrrolysine -> lysine
        ("MKBVLAA", "MKNVLAA"),
        ("MKZVLAA", "MKQVLAA"),
        ("MKJVLAA", "MKLVLAA"),
        ("MKXVLAA", "MKAVLAA"),  # unknown -> alanine
    ],
)
def test_each_non_standard_letter_maps_as_documented(raw, expected):
    out, changed = sanitise(raw)
    assert (out, changed) == (expected, True)
    assert set(out) <= set("ACDEFGHIKLMNPQRSTVWY")


def test_length_is_always_preserved():
    """A substitution that changed length would silently misalign every per-residue score."""
    for raw in ("MKUUXBZJO", "M", "UUUU", "MKVLAA"):
        assert len(sanitise(raw)[0]) == len(raw)


def test_unknown_letter_falls_back_rather_than_raising():
    out, changed = sanitise("MK*VL")
    assert changed and out == "MKAVL"


def test_the_modal_app_copy_has_not_drifted():
    """modal/disorder_app.py cannot import this package, so it carries a copy.

    A divergence would mean two predictors in the same benchmark were given different
    sequences for the same protein -- invisible in the outputs and fatal to the comparison.
    """
    src = APP.read_text()
    m = re.search(r"^SUBSTITUTIONS = (\{[^}]*\})", src, re.M)
    assert m, "SUBSTITUTIONS not found in modal/disorder_app.py"
    assert ast.literal_eval(m.group(1)) == SUBSTITUTIONS
    assert 'STANDARD_AA = frozenset("ACDEFGHIKLMNPQRSTVWY")' in src
