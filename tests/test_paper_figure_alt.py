"""Tests for figure alt text.

Pandoc carries no alt text out of the .docx, so 22 of this paper's 27
images had no ``alt`` attribute at all — not empty, absent — and a
screen reader announced nothing for almost every figure in both the PDF
and the web edition.

The legend's lead sentence is the source: already written, already
copy-edited, and it cannot drift from the caption.
"""
from __future__ import annotations

import sys
from pathlib import Path

from lxml import html as H

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "paper"))


def _run(block: str):
    from figure_alt import add_figure_alt_text  # ty: ignore[unresolved-import]

    doc = H.fromstring(f"<body>{block}</body>")
    n = add_figure_alt_text(doc)
    return n, doc


FIG = (
    '<div class="figure-block"><p><img src="a.svg"/></p>'
    '<h5><span class="caption-lead"><strong>Figure 3. The agent rescues 1,108'
    " candidates.</strong></span> Bars group each verdict by rationale.</h5></div>"
)


def test_alt_comes_from_the_caption_lead() -> None:
    n, doc = _run(FIG)
    assert n == 1
    assert doc.xpath("//img")[0].get("alt") == (
        "Figure 3. The agent rescues 1,108 candidates."
    )


def test_existing_alt_is_left_alone() -> None:
    """The title band's brand marks set their own, and those are better
    than anything derivable from a caption."""
    n, doc = _run(FIG.replace('<img src="a.svg"/>', '<img src="a.svg" alt="bioRxiv"/>'))
    assert n == 0
    assert doc.xpath("//img")[0].get("alt") == "bioRxiv"


def test_every_image_in_a_multipanel_block_is_covered() -> None:
    n, doc = _run(
        FIG.replace("<p><img src=\"a.svg\"/></p>",
                    '<p><img src="a.svg"/></p><p><img src="b.svg"/></p>')
    )
    assert n == 2
    assert all(i.get("alt") for i in doc.xpath("//img"))


def test_a_caption_without_a_marked_lead_still_yields_alt() -> None:
    """figures.lua cannot always resolve the lead clause; falling back
    to the caption's first sentence beats no alt text at all."""
    n, doc = _run(
        '<div class="figure-block"><p><img src="a.svg"/></p>'
        "<h5>Figure 9. A plain caption with no lead span. More prose.</h5></div>"
    )
    assert n == 1
    assert doc.xpath("//img")[0].get("alt") == (
        "Figure 9. A plain caption with no lead span."
    )


def test_very_long_leads_are_truncated() -> None:
    """A screen reader cannot skim; the full legend is adjacent anyway."""
    from figure_alt import MAX_ALT  # ty: ignore[unresolved-import]

    long_lead = "Figure 4. " + ("word " * 200) + "."
    n, doc = _run(
        f'<div class="figure-block"><p><img src="a.svg"/></p><h5>{long_lead}</h5></div>'
    )
    assert n == 1
    alt = doc.xpath("//img")[0].get("alt")
    assert len(alt) <= MAX_ALT
    assert alt.endswith("…")
