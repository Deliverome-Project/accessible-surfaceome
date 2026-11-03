"""Load-smoothness helpers for the web edition of the paper.

Kept apart from ``build.py`` on purpose: that module imports pypandoc at
import time, which only exists under the ``paper`` extra, so anything
living there can only be tested where that extra is installed — and CI
runs a plain ``uv sync --frozen``. These two helpers need nothing but
Pillow and lxml, both of which are base dependencies, so their contract
is enforced on every CI run rather than skipped.
"""
from __future__ import annotations

import re
from pathlib import Path
from typing import Any

# ``<head>`` elements for the brand web fonts, in the order they must be
# emitted.
#
# These used to live as an ``@import`` at the top of deliverome-web.css,
# which is the slowest path a web font can take: the browser has to
# download our stylesheet, parse it, discover the @import, fetch
# Google's stylesheet, parse THAT, and only then fetch the woff2 —
# three serial round trips before a single character renders in Manrope
# or Playfair. On a cold load that shows up as the whole paper
# reflowing once the real faces land.
#
# In ``<head>`` the stylesheet is discovered by the preload scanner
# while the HTML is still parsing, and the two preconnects open both TLS
# connections in parallel with it. The fonts themselves are served from
# fonts.gstatic.com, a DIFFERENT origin from the stylesheet, which is
# why there are two — and why the gstatic one needs ``crossorigin``:
# font files are always fetched in CORS mode, and a preconnect whose
# CORS mode doesn't match the eventual request warms a connection the
# browser then declines to reuse.
FONT_HEAD_LINKS: tuple[str, ...] = (
    '<link rel="preconnect" href="https://fonts.googleapis.com"/>',
    '<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin="crossorigin"/>',
    '<link rel="stylesheet" href="https://fonts.googleapis.com/css2?'
    "family=Manrope:wght@400;500;600;700&amp;"
    "family=Playfair+Display:ital,wght@0,500;0,600;0,700;1,500&amp;"
    'display=swap"/>',
)


def _svg_size(path: Path) -> tuple[int, int] | None:
    """(width, height) of an SVG, from width/height or the viewBox.

    Most figures in this paper are SVG, and Pillow can't read them — so
    without this the aspect-ratio reservation that the whole exercise is
    for would miss exactly the images that matter. Units are stripped
    rather than converted: these numbers are only ever read as a RATIO
    (the stylesheet sets the drawn size), so pt vs px makes no odds as
    long as both axes use the same one, which SVG requires.
    """
    try:
        from xml.etree import ElementTree

        root = ElementTree.parse(path).getroot()
    except Exception:  # noqa: BLE001
        return None

    def _num(value: str | None) -> float | None:
        """A length, or None for anything that isn't an intrinsic one.

        Percentages are rejected rather than parsed: ``width="100%"``
        means "as wide as my container", and reserving a box 100 units
        across would be worse than reserving none at all.
        """
        if not value or value.strip().endswith("%"):
            return None
        m = re.match(r"\s*([0-9]*\.?[0-9]+)", value)
        return float(m.group(1)) if m else None

    w, h = _num(root.get("width")), _num(root.get("height"))
    if w is None or h is None:
        box = (root.get("viewBox") or "").replace(",", " ").split()
        if len(box) == 4:
            w, h = _num(box[2]), _num(box[3])
    if not w or not h:
        return None
    return round(w), round(h)


def _intrinsic_size(path: Path) -> tuple[int, int] | None:
    """(width, height) of an image file, or None if it can't be read."""
    if path.suffix.lower() == ".svg":
        return _svg_size(path)
    try:
        from PIL import Image
    except ImportError:
        return None
    try:
        Image.MAX_IMAGE_PIXELS = None  # the source figures are legitimately huge
        with Image.open(path) as im:
            return im.width, im.height
    except Exception:  # noqa: BLE001 — an unreadable asset is not a build failure
        return None


def apply_image_hints(img: Any, path: Path) -> None:
    """Stamp intrinsic size + decode hints onto one ``<img>`` element.

    **Why the dimensions matter.** Without them the browser cannot know
    a figure's aspect ratio until the bytes decode, so it reserves zero
    height and then shoves everything below down the page when the image
    lands. On a figure-dense paper that is the single largest source of
    "this page feels janky" — far more than any animation.

    Stamping the INTRINSIC size (not a display size) is what makes this
    safe: the web stylesheet sets ``img { max-width: 100%; height: auto }``,
    so the attributes are read only as a ratio to reserve the right box,
    and CSS still decides how big the figure actually draws.

    Note the ordering constraint — ``figure_swap.swap_figures`` strips
    ``width``/``height``/``style`` off every ``<img>`` it rewrites, so
    this has to run after the swap or the attributes vanish again.

    An existing authored size always wins: the job here is to supply a
    ratio that is MISSING, not to overrule one someone set deliberately.
    An unreadable file leaves the dimensions off entirely rather than
    guessing — a wrong reserved box is worse than no reserved box.
    """
    # `loading="lazy"` is a pessimisation above the fold: it defers the
    # very images the reader is already looking at, which costs LCP for
    # nothing. The title band's logo and resource icons are the only
    # images up there, so exempt the header and lazy-load the rest.
    # (Requires the header to have been grouped already — see build.py.)
    if not _is_inside(img, "paper-header"):
        img.set("loading", "lazy")
    img.set("decoding", "async")

    if img.get("width") or img.get("height"):
        return
    size = _intrinsic_size(path)
    if size is None:
        return
    img.set("width", str(size[0]))
    img.set("height", str(size[1]))


# Sets the gate that the reveal CSS keys off. Emitted INLINE in <head>,
# which is load-bearing in two directions:
#
#   * It must run before first paint. paper.js is deferred, so it runs
#     after the HTML parses — a gate set there would let the page paint
#     fully visible and only then blank out and fade back in. A flash of
#     content that disappears is worse than no animation at all.
#   * It must be the ONLY thing that turns the hidden state on. The
#     `reveal` classes stamped into the markup below do nothing by
#     themselves, so a reader with JS disabled, a crawler, or Reader
#     Mode gets an ordinary fully-visible paper.
#
# Gated on IntersectionObserver because that is what later un-hides the
# content: without it, hiding anything would be a one-way trip.
REVEAL_BOOTSTRAP_SCRIPT = (
    "<script>"
    'if("IntersectionObserver" in window)'
    'document.documentElement.classList.add("js-reveal");'
    "</script>"
)

# Structural blocks only — headings, figures, tables, block quotes.
#
# Prose is deliberately NOT revealed. Two reasons, one aesthetic and one
# not: paragraph-by-paragraph fade-in at reading speed looks fidgety
# rather than composed, and `opacity: 0` text is still matched by
# find-in-page, so a reader searching the paper could be scrolled to a
# blank region. Animating only the things a reader actually notices
# arriving — a new section, a figure, a table — gets the feeling of
# motion with neither cost.
# Prose included, deliberately.
#
# An earlier version revealed only structure — headings, figures,
# tables — on the reasoning that `opacity: 0` text is still matched by
# find-in-page, so a searching reader could be scrolled to a blank
# region. That reasoning was sound and the result was still wrong: in
# this manuscript it left 97 of 184 top-level blocks static, and since
# prose is what a reader spends almost all of their scrolling inside,
# the page read as though nothing was happening at all. The reference
# page for this work animates 129 of its 129 paragraphs; the motion IS
# the prose moving, and structure-only is a different, duller effect.
#
# Find-in-page is handled where the problem actually is instead — see
# the Cmd/Ctrl+F handler in deliverome-web.js, which drops the whole
# reveal the moment a reader starts searching.
#
# Every heading level, too: the manuscript uses h4 for Methods
# subsections ("UniProt", "SURFY", "CSPA") and h6 below that, so an
# h2/h3-only selector left 31 headings static. h5 is the figure-caption
# level, but captions live inside a .figure-block and are excluded with
# it, so the only h5 reached here is a table caption.
REVEAL_SELECTOR = "h2 | h3 | h4 | h5 | h6 | p | table | blockquote"

# Delay index is capped so a long block (the reference list runs to
# three figures of entries) doesn't schedule its tail seconds out.
STAGGER_INDEX_CAP = 8

# Revealable blocks at the very top of the document are left alone.
#
# The hidden state ships from parse time, and the script that un-hides
# it is deferred — so on a long document, which the browser paints
# incrementally, the top of the page can be painted hidden a beat
# before the script runs. For content below the fold nobody ever sees
# that beat. For content in the opening screen it is a visible flicker.
#
# paper.js also marks whatever is already on screen as visible before it
# arms the transition, which covers tall viewports; this is the half of
# the fix that does not depend on winning a race. One block is the right
# number because the title band is already excluded and the first
# revealable heading after it (Abstract) is above the fold at any
# viewport size worth designing for — plus the abstract paragraph
# under it, now that prose reveals too.
REVEAL_SKIP_LEADING = 2


def _is_inside(el: Any, *classes: str) -> bool:
    node = el.getparent()
    while node is not None:
        cls = (node.get("class") or "").split()
        if any(c in cls for c in classes):
            return True
        node = node.getparent()
    return False


def _add_class(el: Any, name: str) -> None:
    cls = (el.get("class") or "").split()
    if name not in cls:
        cls.append(name)
    el.set("class", " ".join(cls))


def apply_reveal_markup(doc: Any) -> int:
    """Stamp reveal classes onto the structural blocks. Returns the count.

    Skips the title band: it is above the fold on every viewport, and
    the title is the one thing the reader came for — making them watch
    it arrive is a cost with no benefit. Also skips the contents rail,
    which has its own fade, and anything inside a figure block, which
    reveals as a unit.
    """
    body = doc.find("body")
    if body is None:
        return 0

    blocks = list(body.xpath(REVEAL_SELECTOR)) + list(
        body.xpath("//*[contains(concat(' ', @class, ' '), ' figure-block ')]")
    )
    eligible = [
        el
        for el in blocks
        if not _is_inside(el, "paper-header", "figure-lightbox", "figure-block")
        and el.get("id") != "TOC"
        and not _is_inside_toc(el)
    ]
    # Document order, so "leading" means what it says: xpath() returns
    # each query in order but the two queries above are concatenated.
    eligible.sort(key=lambda el: _document_index(body, el))

    marked = 0
    for el in eligible[REVEAL_SKIP_LEADING:]:
        _add_class(el, "reveal")
        marked += 1

    _apply_stagger(body)
    return marked


def _document_index(body: Any, el: Any) -> int:
    """Position of `el` in a document-order walk of `body`."""
    for i, node in enumerate(body.iter()):
        if node is el:
            return i
    return -1


def _is_inside_toc(el: Any) -> bool:
    node = el.getparent()
    while node is not None:
        if node.get("id") == "TOC":
            return True
        node = node.getparent()
    return False


def _apply_stagger(body: Any) -> None:
    """Offset the children of the reference list.

    The bibliography is the one place in the paper where the eye takes
    in a column of near-identical sibling items at once, and a small
    offset helps it resolve them into an order. Everything else reveals
    as one piece — including figures, which in this manuscript are
    single composite images rather than panel grids, so there are no
    siblings to stagger.
    """
    refs = _reference_list(body)
    if refs is None:
        return
    children = [c for c in refs if isinstance(c.tag, str)]
    if len(children) < 2:
        return
    _add_class(refs, "reveal")
    refs.set("data-reveal-stagger", "")
    for i, child in enumerate(children):
        style = (child.get("style") or "").rstrip("; ")
        index = min(i, STAGGER_INDEX_CAP)
        child.set("style", f"{style + '; ' if style else ''}--reveal-i: {index}")


def _reference_list(body: Any) -> Any | None:
    """The element holding the bibliography, found by where the reference
    anchors actually are rather than by a markup shape.

    ``filters/citations.lua`` puts an empty ``<span id="ref-…">`` at the
    start of each reference, but how deeply that sits inside the list is
    pandoc's business and has changed shape before — today it is
    ``<ol><li><p><span>``, so neither the span's parent nor its
    grandparent is the list. Walk up instead and take the DEEPEST
    ancestor that holds most of the anchors, one per child.

    That last condition is what stops ``<body>`` matching: it contains
    every anchor, but almost none of its children do.
    """
    anchors = body.xpath("//span[starts-with(@id, 'ref-')]")
    if len(anchors) < 3:
        return None

    # Ancestors of the first anchor, deepest first.
    chain = []
    node = anchors[0].getparent()
    while node is not None:
        chain.append(node)
        node = node.getparent()

    for candidate in chain:
        held = len(candidate.xpath(".//span[starts-with(@id, 'ref-')]"))
        if held < 3:
            continue
        children = [c for c in candidate if isinstance(c.tag, str)]
        if not children:
            continue
        carrying = sum(
            1
            for c in children
            if c.xpath(".//span[starts-with(@id, 'ref-')]")
            or (c.tag == "span" and (c.get("id") or "").startswith("ref-"))
        )
        if carrying >= max(3, len(children) // 2):
            return candidate
    return None
