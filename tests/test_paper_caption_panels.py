"""Tests for emboldening panel markers inside figure legends.

A multi-panel legend otherwise reads as one undifferentiated paragraph:
the "a)", "b)", "c)" introducing each panel carry the same weight as the
prose, so finding the sentence that explains panel b means reading the
whole caption.

What counts as a marker is deliberately narrow, and these tests pin the
shapes that must NOT match — this manuscript's captions contain
"(\"yes\", panel a)" and gist links, either of which a loose rule would
mangle. Runs on markup, so it works in CI without pandoc.
"""
from __future__ import annotations

import sys
from pathlib import Path

import lxml.etree as ET  # ty: ignore[unresolved-import]
from lxml import html as H

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "paper"))


def _run(caption_inner: str) -> tuple[int, str]:
    from caption_panels import bold_panel_labels  # ty: ignore[unresolved-import]

    doc = H.fromstring(
        f'<body><div class="figure-block"><h5>{caption_inner}</h5></div></body>'
    )
    n = bold_panel_labels(doc)
    return n, ET.tostring(doc.xpath("//h5")[0], method="html", encoding="unicode")


def test_markers_opening_a_clause_are_bolded() -> None:
    n, html = _run("Intro text. a) First panel; b) second panel.")
    assert n == 2
    assert '<strong class="panel-label">a)</strong>' in html
    assert '<strong class="panel-label">b)</strong>' in html


def test_a_marker_after_a_comma_counts() -> None:
    """"Five axes of content: a) papers found, b) papers selected" —
    the second marker follows a comma, not a full stop."""
    n, _ = _run("Five axes of content: a) papers found, b) papers selected.")
    assert n == 2


def test_prose_mentioning_a_panel_is_not_a_marker() -> None:
    """This manuscript really contains `("yes", panel a)`. A rule that
    matched it would bold the middle of a sentence."""
    n, html = _run('Calls 87 proteins surface ("yes", panel a) and 1,021 more.')
    assert n == 0
    assert "panel-label" not in html


def test_the_caption_lead_is_left_alone() -> None:
    """The run-in "Figure N. Title." is already bold and styled."""
    n, html = _run(
        '<span class="caption-lead"><strong>Figure 5. a) Title.</strong></span>'
        " Body text."
    )
    assert n == 0
    assert "panel-label" not in html


def test_link_text_is_left_alone() -> None:
    n, html = _run('Body. <a href="#x">see a) there</a>')
    assert n == 0


def test_markers_keep_the_surrounding_text_intact() -> None:
    """Splicing elements into lxml text/tail is easy to get wrong in a
    way that silently drops characters."""
    caption = "Intro. a) First; b) second, c) third. End."
    n, html = _run(caption)
    assert n == 3
    recovered = " ".join(H.fromstring(html).text_content().split())
    assert recovered == caption


def test_only_single_letters_qualify() -> None:
    n, _ = _run("Intro. ab) not a panel; 1) not a panel either.")
    assert n == 0


def test_a_marker_opening_the_run_after_the_lead_is_bolded() -> None:
    """The first panel's marker sits at the start of the caption-lead's
    tail, where the full stop that ends the clause is inside the span
    and invisible to the matcher. It was the one panel in a legend that
    did not get bolded."""
    n, html = _run(
        '<span class="caption-lead"><strong>Figure 7. Title.</strong></span>'
        " a) The viewer homepage. b) The gene page."
    )
    assert n == 2, "the leading marker was missed"
    assert html.count('class="panel-label"') == 2


def test_the_last_marker_of_an_inline_list_is_bolded() -> None:
    # "…, and e) …" — the final panel of a comma-separated run was the
    # one marker left unbolded.
    n, html = _run("Five axes: a) papers found, b) papers selected, and c) features.")
    assert n == 3
    assert '<strong class="panel-label">c)</strong>' in html
