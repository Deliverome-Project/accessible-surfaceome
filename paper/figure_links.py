"""Catch figure and table cross-references that never became links.

``filters/figures.lua`` turns "Figure 3" / "Figure S4" in the prose into
links to the figure. When a reference does not match its patterns the
filter leaves it as plain text and prints a warning — but pandoc's
warnings scroll past in a long build and the exit status stays 0, so a
dead cross-reference ships silently. It shipped once: the draft reads
``(Figure S4)Two of five changed`` with no space after the bracket, the
tokeniser saw ``S4)Two``, and that one reference was plain text in both
the PDF and the web edition for several builds.

This checks the rendered HTML instead of trusting the filter's stderr,
so it covers both outputs and needs nothing but lxml — which means it
can be tested in CI, where the pandoc extra is not installed.
"""
from __future__ import annotations

import re
from typing import Any

# "Figure 3", "Figures S1", "Supplementary Figure 12". Deliberately not
# anchored at a word boundary on the right: a reference glued to the
# next word is exactly the failure this exists to catch.
REFERENCE = re.compile(
    r"\b((?:Supplementary |Appendix )?(?:Figures?|Tables?))"
    r"\s+(S?\d+)([a-z](?:[^\w\s][a-z])?)?",
    re.I,
)

# Places a bare "Figure N" is NOT a cross-reference and must be ignored:
# a caption naming itself, the contents rail, and the lightbox's copy of
# a caption.
SKIP_TAGS = {"h5", "script", "style", "title"}
SKIP_CLASSES = ("caption-lead", "figure-lightbox")
SKIP_IDS = ("TOC",)


def _skip(el: Any) -> bool:
    node = el
    while node is not None:
        if isinstance(node.tag, str):
            if node.tag in SKIP_TAGS:
                return True
            if node.get("id") in SKIP_IDS:
                return True
            cls = node.get("class") or ""
            if any(c in cls for c in SKIP_CLASSES):
                return True
        node = node.getparent()
    return False


def find_unlinked_figure_refs(html: str | Any) -> tuple[list[str], list[str]]:
    """Figure references in the prose that are not inside a link.

    Returns (broken, panel_suffixed).

    `broken` are plain references the filter should have linked and did
    not — these are defects and the build stops on them.

    `panel_suffixed` are "Figure 4a" / "Figure 6a-c". The filter
    declines these by design (`tail_match` takes a bare integer), so
    they are reported separately rather than failing the build: a
    deliberate choice should not read as a regression. They are still
    listed, because "Figure 4" linking while "Figure 4a" does not is
    the kind of inconsistency worth seeing.

    Accepts a path, a markup string, or a parsed tree.
    """
    from lxml import html as lxml_html

    if isinstance(html, str):
        root = (
            lxml_html.parse(html).getroot()
            if not html.lstrip().startswith("<")
            else lxml_html.fromstring(html)
        )
    else:
        root = html

    broken: list[str] = []
    panels: list[str] = []
    for el in root.iter():
        if not isinstance(el.tag, str) or _skip(el):
            continue
        # `text` belongs to this element; `tail` belongs to its parent's
        # flow, so an <a> element's tail is NOT inside the link.
        for attr in ("text", "tail"):
            if attr == "text" and el.tag == "a":
                continue
            if attr == "tail" and el.getparent() is not None and _skip(el.getparent()):
                continue
            chunk = getattr(el, attr) or ""
            for m in REFERENCE.finditer(chunk):
                begin = max(0, m.start() - 40)
                snippet = " ".join(chunk[begin : m.end() + 40].split())
                ref = " ".join(m.group(0).split())
                entry = f"{ref!r} in ...{snippet}..."
                (panels if m.group(3) else broken).append(entry)
    return broken, panels
