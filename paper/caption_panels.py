"""Embolden the panel markers inside figure legends.

A multi-panel legend reads as one undifferentiated paragraph: the
"a)", "b)", "c)" that introduce each panel's sentence carry the same
weight as the prose around them, so finding the sentence that explains
panel b means reading the whole caption. Bolding them turns the legend
into something you can scan.

Applied to the rendered HTML rather than inside the Lua filter so that
the PDF and the web edition get the identical treatment from one
implementation, and so it can be tested without pandoc.

What counts as a marker is deliberately narrow. The markers in this
manuscript start a clause, so a letter only qualifies when the text
before it ends a clause — which is what keeps ``("yes", panel a)`` and
``(Sonnet 4.6, a)`` from being mistaken for one.
"""
from __future__ import annotations

import re
from typing import Any

# A single lowercase letter + ")" that opens a clause: preceded by
# clause-ending punctuation and a space, or sitting at the start of the
# text run.
#
# The start-of-run arm matters more than it looks. A marker right after
# the caption's run-in lives at the start of that span's TAIL, where the
# full stop that ends the clause is inside the span and so invisible
# here — without it, the first panel of a legend was the one panel that
# did not get bolded.
PANEL = re.compile(r"(?:(?<=[.;:,]\s)|(?<=^)|(?<=^\s))([a-h]\))(?=\s)")

# Never touch the run-in "Figure N. Title." (already bold) or the
# trailing "Figure data and script." link.
SKIP_TAGS = {"a", "strong"}
SKIP_CLASSES = ("caption-lead",)


def _skip(el: Any) -> bool:
    node = el
    while node is not None:
        if isinstance(node.tag, str):
            if node.tag in SKIP_TAGS:
                return True
            cls = node.get("class") or ""
            if any(c in cls for c in SKIP_CLASSES):
                return True
        node = node.getparent()
    return False


def _split_text(text: str) -> list[tuple[str, str]] | None:
    """[(literal, marker), ...] plus a trailing literal, or None."""
    if not text or not PANEL.search(text):
        return None
    parts: list[tuple[str, str]] = []
    pos = 0
    for m in PANEL.finditer(text):
        parts.append((text[pos : m.start()], m.group(1)))
        pos = m.end()
    parts.append((text[pos:], ""))
    return parts


def _emphasise(node: Any, attr: str, make: Any) -> int:
    """Wrap every marker in one text run. Returns how many were wrapped.

    lxml keeps text in `.text` and `.tail`, so a match has to become a
    real element spliced into the parent at the right position — there
    is no "replace this substring with markup" operation. Each new
    element carries the literal text that FOLLOWS it as its tail.
    """
    text = node.text if attr == "text" else node.tail
    parts = _split_text(text or "")
    if parts is None:
        return 0

    # text  -> children of the node itself, starting at 0
    # tail  -> siblings of the node, starting just after it
    host = node if attr == "text" else node.getparent()
    if host is None:
        return 0
    base = 0 if attr == "text" else list(host).index(node) + 1

    if attr == "text":
        node.text = parts[0][0]
    else:
        node.tail = parts[0][0]

    for offset, (_, marker) in enumerate(parts[:-1]):
        el = make("strong")
        el.set("class", "panel-label")
        el.text = marker
        el.tail = parts[offset + 1][0]
        host.insert(base + offset, el)
    return len(parts) - 1


def bold_panel_labels(root: Any) -> int:
    """Bold panel markers in every figure legend under `root`."""
    from lxml import html as lxml_html

    total = 0
    captions = root.xpath(
        "//*[contains(concat(' ', @class, ' '), ' figure-block ')]//h5"
    )
    for cap in captions:
        for el in list(cap.iter()):
            if not isinstance(el.tag, str):
                continue
            if not _skip(el):
                total += _emphasise(el, "text", lxml_html.Element)
            parent = el.getparent()
            if el is not cap and parent is not None and not _skip(parent):
                total += _emphasise(el, "tail", lxml_html.Element)
    return total
