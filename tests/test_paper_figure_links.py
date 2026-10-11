"""Tests for the dead-cross-reference guard.

Why this exists: ``filters/figures.lua`` warns about references it could
not link, but pandoc warnings scroll past in a long build and the exit
status stays 0. A reference that silently stayed plain text shipped in
both the PDF and the web edition for several builds — the draft reads
``(Figure S4)Two of five changed`` with no space after the bracket, the
tokeniser saw ``S4)Two``, and nothing failed.

These run against markup rather than through pandoc, so they work in CI,
where the ``paper`` extra (and therefore pypandoc) is not installed.
"""
from __future__ import annotations

import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "paper"))


def _check(fragment: str) -> tuple[list[str], list[str]]:
    from figure_links import find_unlinked_figure_refs  # ty: ignore[unresolved-import]

    return find_unlinked_figure_refs(f"<body>{fragment}</body>")


def test_a_plain_reference_is_reported() -> None:
    broken, _ = _check("<p>as shown in Figure 3 the trend holds</p>")
    assert len(broken) == 1
    assert "Figure 3" in broken[0]


def test_a_linked_reference_is_not_reported() -> None:
    """A checker that fires on success is worse than no checker."""
    broken, _ = _check('<p>as shown in <a href="#figure-3">Figure 3</a> it holds</p>')
    assert broken == []


def test_text_after_a_link_is_still_checked() -> None:
    """An <a>'s tail belongs to the parent's flow, not to the link — so
    a reference sitting right after one must still be caught."""
    broken, _ = _check(
        '<p><a href="#figure-1">Figure 1</a> and also Figure 2 nearby</p>'
    )
    assert len(broken) == 1
    assert "Figure 2" in broken[0]


def test_the_glued_bracket_case_is_caught() -> None:
    """The exact shape that shipped: no space after the bracket."""
    broken, _ = _check("<p>kept the best variant (Figure S4)Two of five changed</p>")
    assert len(broken) == 1
    assert "Figure S4" in broken[0]


def test_a_caption_naming_itself_is_not_a_reference() -> None:
    """Every caption starts "Figure N." — treating those as broken
    cross-references would make the guard fire on all 22 figures."""
    broken, _ = _check(
        '<div class="figure-block"><h5><strong>Figure 2.</strong> A caption.</h5></div>'
    )
    assert broken == []


def test_the_contents_rail_is_not_checked() -> None:
    broken, _ = _check('<nav id="TOC"><ul><li>Figure 4 overview</li></ul></nav>')
    assert broken == []


def test_panel_suffixed_references_are_reported_separately() -> None:
    """These link to their figure now, so an unlinked one is a defect —
    but it is kept in its own bucket because the cause differs from a
    malformed reference and the build message should say which."""
    broken, panels = _check("<p>the split is clear (Figure 4a) and (Figure 6a-c)</p>")
    assert broken == []
    assert len(panels) == 2


def test_a_linked_panel_reference_is_not_reported() -> None:
    broken, panels = _check(
        '<p>see <a href="#figure-4">Figure 4a</a> and'
        ' <a href="#figure-6">Figure 6a-c</a></p>'
    )
    assert broken == [] and panels == []


def test_supplementary_and_appendix_prefixes_are_recognised() -> None:
    broken, _ = _check(
        "<p>see Supplementary Figure 12 and Appendix Figure 2 for detail</p>"
    )
    assert len(broken) == 2


def test_table_references_are_checked_too() -> None:
    """Tables are captioned and cited exactly like figures, and were the
    last reference shape in the paper still rendering as plain text
    while every figure around them linked."""
    broken, _ = _check("<p>the taxonomy is given in Table S1 for reference</p>")
    assert len(broken) == 1
    assert "Table S1" in broken[0]


def test_a_linked_table_reference_is_not_reported() -> None:
    broken, panels = _check(
        '<p>see <a href="#supplementary-table-1">Table S1</a> for the taxonomy</p>'
    )
    assert broken == [] and panels == []
