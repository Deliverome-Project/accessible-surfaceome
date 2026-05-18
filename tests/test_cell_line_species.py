"""Tests for the cell-line → species gazetteer.

Three behavior contracts:

1. Common lines resolve to the right species across separator variants
   ("MC3T3-E1", "MC3T3 E1", "MC3T3E1" → mouse).
2. Ambiguous text (multi-species mention) returns ``None`` — the post-pass
   prefers misses over false positives.
3. No-match text returns ``None``.
"""

from __future__ import annotations

import pytest

from accessible_surfaceome.tools._shared.cell_line_species import (
    infer_species_from_text,
)


@pytest.mark.parametrize(
    "text, expected",
    [
        # SRC-sample cases
        ("Osteoblast (MC3T3-E1 mouse cell line)", "mouse"),
        ("MC3T3 E1 cells were treated", "mouse"),
        ("MC3T3E1 cells", "mouse"),
        ("U251 MG glioblastoma cells", "human"),
        ("U251MG", "human"),
        ("FRTL-5 thyroid cells from rat", "rat"),
        # Other widely-cited workhorses
        ("HeLa cells", "human"),
        ("HEK293T transfection", "human"),
        ("MCF7 breast cancer line", "human"),
        ("Jurkat T cells", "human"),
        ("RAW 264.7 macrophages", "mouse"),
        ("NIH-3T3 fibroblasts", "mouse"),
        ("CHO cells", "other"),  # hamster → "other" since enum lacks it
        ("MDCK monolayer", "dog"),
        ("PC12 neurons", "rat"),
        # Title-bearing cases (from sample contexts)
        ("U251 MG glioblastoma cells; sulfo-NHS biotin labeling", "human"),
    ],
)
def test_known_cell_line_resolves(text: str, expected: str) -> None:
    assert infer_species_from_text(text) == expected


def test_no_match_returns_none() -> None:
    assert infer_species_from_text("clinical tumor tissue sections") is None
    assert infer_species_from_text("") is None
    assert infer_species_from_text("Some cells were processed") is None


def test_multi_species_conflict_returns_none() -> None:
    # The "false positives are worse than misses" policy: if a row
    # mentions both a human line AND a mouse line, we don't guess.
    assert infer_species_from_text(
        "HeLa cells and NIH-3T3 fibroblasts were compared"
    ) is None
    assert infer_species_from_text(
        "MC3T3-E1 osteoblasts vs HUVEC endothelial"
    ) is None


def test_multiple_same_species_mentions_still_resolve() -> None:
    # Two HUMAN lines in the same row → still resolves to human.
    assert infer_species_from_text(
        "HeLa, MCF7, and Jurkat cell lines were used"
    ) == "human"
