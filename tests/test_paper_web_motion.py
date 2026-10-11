"""Tests for the web paper's motion layer and load-smoothness fixes.

Three separate failure modes are pinned here, all of which read to a
reader as "the page is janky" rather than as a bug:

1. **Figures with no intrinsic size.** Without ``width``/``height`` on
   the ``<img>``, the browser cannot reserve the figure's box until the
   bytes decode, so every figure shoves the prose below it down the page
   as it loads. ``build_web`` already holds the real dimensions (it opens
   each raster with Pillow to re-encode it), so the fix is free — but
   only if nothing silently drops the attributes again.

2. **Reveal animation hiding content from readers without JS.** The
   reveal starts at ``opacity: 0``. If that initial state shipped
   unconditionally, a reader whose JS failed to load — or a crawler, or
   Reader Mode — would get a blank paper. The hidden state is therefore
   gated behind a class that only ``paper.js`` can set, and these tests
   fail if any rule escapes the gate.

3. **Fonts behind a chained @import.** An ``@import`` of a Google Fonts
   URL from inside the stylesheet costs three serial round trips (our
   CSS → Google's CSS → the woff2) before a character renders in the
   brand face, which shows up as a reflow on every cold load. The link
   belongs in ``<head>`` alongside a ``preconnect``.
"""
from __future__ import annotations

import re
import sys
from pathlib import Path
from typing import Any

import pytest

REPO = Path(__file__).resolve().parents[1]
WEB_CSS = REPO / "paper/deliverome-web.css"
WEB_JS = REPO / "paper/deliverome-web.js"

sys.path.insert(0, str(REPO / "paper"))


# ── 1. Intrinsic image dimensions ───────────────────────────────────

def _png(path: Path, size: tuple[int, int]) -> Path:
    Image = pytest.importorskip("PIL.Image", reason="Pillow not installed")
    Image.new("RGB", size, (200, 180, 185)).save(path)
    return path


def test_image_hints_stamp_intrinsic_size(tmp_path: Path) -> None:
    """The <img> carries the real pixel dimensions, so the browser can
    reserve the box before the image decodes."""
    from web_assets import apply_image_hints  # ty: ignore[unresolved-import]
    from lxml import html as lxml_html

    img = lxml_html.fromstring('<img src="assets/00-fig.webp"/>')
    apply_image_hints(img, _png(tmp_path / "fig.png", (1400, 900)))

    assert img.get("width") == "1400"
    assert img.get("height") == "900"


def test_image_hints_set_lazy_decode(tmp_path: Path) -> None:
    """Unmanaged decode of a dozen dense figure rasters is what actually
    stutters the scroll; hand the browser both hints."""
    from web_assets import apply_image_hints  # ty: ignore[unresolved-import]
    from lxml import html as lxml_html

    img = lxml_html.fromstring('<img src="assets/00-fig.webp"/>')
    apply_image_hints(img, _png(tmp_path / "fig.png", (800, 600)))

    assert img.get("loading") == "lazy"
    assert img.get("decoding") == "async"


def test_image_hints_survive_an_unreadable_file(tmp_path: Path) -> None:
    """A missing or corrupt asset must not take the whole build down, and
    must not leave a bogus aspect ratio behind — worse than none, because
    the browser would reserve the WRONG box."""
    from web_assets import apply_image_hints  # ty: ignore[unresolved-import]
    from lxml import html as lxml_html

    img = lxml_html.fromstring('<img src="assets/00-fig.webp"/>')
    apply_image_hints(img, tmp_path / "does-not-exist.png")

    assert img.get("width") is None
    assert img.get("height") is None
    # The decode hints don't depend on reading the file, so they stay.
    assert img.get("loading") == "lazy"


def test_image_hints_do_not_override_an_authored_size(tmp_path: Path) -> None:
    """If something upstream already decided the size, it wins — this
    helper's job is to supply a MISSING ratio, not to relitigate one."""
    from web_assets import apply_image_hints  # ty: ignore[unresolved-import]
    from lxml import html as lxml_html

    img = lxml_html.fromstring('<img src="x.webp" width="640" height="480"/>')
    apply_image_hints(img, _png(tmp_path / "fig.png", (1400, 900)))

    assert img.get("width") == "640"
    assert img.get("height") == "480"


# ── 2. Reveal is gated so a no-JS reader sees everything ────────────

def _strip_comments(css: str) -> str:
    """Drop /* … */ so prose explaining a selector can't be mistaken for
    one. These rules are heavily commented on purpose, and the comments
    naturally mention the very class names being matched."""
    return re.sub(r"/\*.*?\*/", "", css, flags=re.S)


def _rule_bodies(css: str) -> list[tuple[str, str]]:
    """(selector, body) for every declaration block mentioning .reveal."""
    return [
        (m.group(1).strip(), m.group(2))
        for m in re.finditer(
            r"([^{}]*\.reveal[^{}]*)\{([^{}]*)\}", _strip_comments(css)
        )
    ]


def _media_blocks(css: str, query: str) -> list[str]:
    """Bodies of every @media rule whose prelude contains `query`.

    Every, not the first: the stylesheet already carries an unrelated
    ``@media print`` block (the browser-print fallback), so asking only
    about the first one tests the wrong rule.

    Brace-matched rather than regexed: an @media block contains nested
    blocks, which a non-recursive regex cannot span, and getting that
    subtly wrong would make these tests pass against a stylesheet that
    doesn't actually carry the escape.
    """
    css = _strip_comments(css)
    out = []
    for m in re.finditer(r"@media([^{]*)\{", css):
        if query not in m.group(1):
            continue
        depth, i = 1, m.end()
        while i < len(css) and depth:
            depth += {"{": 1, "}": -1}.get(css[i], 0)
            i += 1
        out.append(css[m.end() : i - 1])
    return out


def test_reveal_hidden_state_is_gated_on_the_js_class() -> None:
    """Every rule that hides reveal content must require the class that
    only paper.js sets. Ungated, a failed script = a blank paper."""
    css = WEB_CSS.read_text()
    offenders = [
        sel
        for sel, body in _rule_bodies(css)
        if re.search(r"opacity\s*:\s*0\s*(;|$)", body.strip())
        and ".js-reveal" not in sel
    ]
    assert not offenders, (
        "reveal rules hide content without requiring the JS gate, so a "
        f"reader whose script failed would see nothing: {offenders}"
    )


def test_reveal_transition_is_armed_separately_from_the_hidden_state() -> None:
    """Content already on screen at first paint must appear instantly,
    not fade in — the title is what the reader came for. The transition
    therefore hangs off its own class, applied a frame later."""
    css = WEB_CSS.read_text()
    assert ".reveal-armed" in css
    transition_rules = [
        sel
        for sel, body in _rule_bodies(css)
        if "transition:" in body
        # `transition: none` DISABLES motion (the reduced-motion and
        # print escapes); only a rule that switches a transition ON can
        # make above-the-fold content animate, so only those need the gate.
        and not re.search(r"transition:\s*none", body)
    ]
    assert transition_rules, "no reveal transition rule found"
    assert all(".reveal-armed" in sel for sel in transition_rules), (
        "a reveal transition applies before arming, so above-the-fold "
        f"content would animate on load: {transition_rules}"
    )


def test_reveal_has_reduced_motion_and_print_escapes() -> None:
    """Both escapes must force the VISIBLE state, not merely disable the
    transition — disabling the transition alone leaves opacity at 0."""
    css = WEB_CSS.read_text()
    for query in ("prefers-reduced-motion", "print"):
        blocks = _media_blocks(css, query)
        assert blocks, f"no @media {query} block at all"
        assert any(".reveal" in b and "opacity: 1" in b for b in blocks), (
            f"@media {query} does not force reveal content visible; "
            "disabling the transition alone leaves opacity at 0"
        )


def test_bootstrap_sets_the_gate_inline_and_capability_checked() -> None:
    """The gate must be set before first paint, which means inline in
    <head> rather than from the deferred paper.js — and only when the
    browser can also UN-hide the content again."""
    from web_assets import REVEAL_BOOTSTRAP_SCRIPT  # ty: ignore[unresolved-import]

    assert "js-reveal" in REVEAL_BOOTSTRAP_SCRIPT
    assert "src=" not in REVEAL_BOOTSTRAP_SCRIPT, (
        "an external script can't be guaranteed to run before first paint"
    )
    assert "IntersectionObserver" in REVEAL_BOOTSTRAP_SCRIPT, (
        "hiding content in a browser that can't observe scroll is a "
        "one-way trip to a blank paper"
    )


def test_paper_js_arms_the_transition() -> None:
    """The gate is set by the bootstrap; arming is this script's job."""
    js = WEB_JS.read_text()
    assert "reveal-armed" in js


# ── 4. What gets marked ─────────────────────────────────────────────

def _marked(fragment: str) -> Any:
    from lxml import html as lxml_html

    from web_assets import apply_reveal_markup  # ty: ignore[unresolved-import]

    doc = lxml_html.fromstring(
        f'<html><body class="paper-root">{fragment}</body></html>'
    )
    apply_reveal_markup(doc)
    return doc


def _classes(doc: Any, tag: str) -> list[str]:
    return [el.get("class") or "" for el in doc.iter(tag)]


def test_title_band_never_reveals() -> None:
    """It is above the fold on every viewport and it is the one thing the
    reader came for."""
    doc = _marked(
        '<header class="paper-header"><h1>T</h1><h2>By-line</h2></header>'
        "<h2>Abstract</h2><h2>Introduction</h2><h2>Results</h2>"
    )
    header_h2 = doc.find(".//header/h2")
    assert "reveal" not in (header_h2.get("class") or "")


def test_leading_block_is_left_alone() -> None:
    """The first revealable heading sits in the opening screen, where the
    parse-time hidden state could be painted before the deferred script
    arms. Below the fold nobody ever sees that beat."""
    doc = _marked(
        "<h2>Abstract</h2><p>The abstract.</p><h2>Introduction</h2><h2>Results</h2>"
    )
    # Abstract heading AND its paragraph stay put; everything after moves.
    assert _classes(doc, "h2") == ["", "reveal", "reveal"]
    assert _classes(doc, "p") == [""]


def test_prose_is_revealed() -> None:
    """Prose IS the effect. Structure-only left 97 of 184 blocks static
    and the page read as though nothing was happening — a reader spends
    almost all of their scrolling inside paragraphs, not headings."""
    doc = _marked("<h2>A</h2><p>lead</p><p>prose</p><p>more prose</p>")
    assert _classes(doc, "p")[1:] == ["reveal", "reveal"]


def test_find_in_page_drops_the_reveal() -> None:
    """Hidden prose would otherwise strand a searching reader in a blank
    stretch. This is why prose can be revealed at all."""
    js = WEB_JS.read_text()
    assert "beforematch" in js
    assert "metaKey" in js and "ctrlKey" in js


def test_comment_island_is_not_revealed() -> None:
    """The reader comment form isn't part of the paper."""
    doc = _marked(
        '<h2>A</h2><p>b</p><section class="paper-comments"><p>Intro</p>'
        "</section>"
    )
    section = doc.find('.//section')
    assert all("reveal" not in (e.get("class") or "") for e in section.iter())


def test_contents_rail_is_not_revealed() -> None:
    """It has its own dock-on-scroll fade; revealing it too would fight."""
    doc = _marked(
        '<h2>A</h2><h2>B</h2><nav id="TOC"><ul><li><a href="#a">A</a></li>'
        "</ul><table><tr><td>x</td></tr></table></nav>"
    )
    toc = doc.get_element_by_id("TOC")
    assert "reveal" not in (toc.get("class") or "")
    assert all("reveal" not in (el.get("class") or "") for el in toc.iter())


def test_figures_reveal_as_one_piece() -> None:
    """Figures here are single composite renders, not panel grids, so
    there are no siblings to stagger — offsetting a caption from its own
    image would just look like the caption lagging."""
    doc = _marked(
        '<h2>A</h2><p>lead</p><div class="figure-block">'
        '<p><img src="a.webp"/></p><h5>Caption</h5></div>'
    )
    fig = doc.find('.//div[@class="figure-block reveal"]')
    assert "reveal" in (fig.get("class") or "")
    assert fig.get("data-reveal-stagger") is None


def test_reference_list_staggers_with_a_capped_delay() -> None:
    """Pinned to the markup pandoc actually emits — <ol><li><p><span> —
    where neither the anchor's parent nor its grandparent is the list.
    An earlier version stopped at the <li>, found one anchor, and
    silently staggered nothing in the real build."""
    from web_assets import STAGGER_INDEX_CAP  # ty: ignore[unresolved-import]

    items = "".join(
        f'<li><p><span id="ref-{i}"></span>Reference {i}</p></li>'
        for i in range(20)
    )
    doc = _marked(f"<h2>A</h2><ol>{items}</ol>")
    refs = doc.find(".//ol")
    assert refs is not None and refs.get("data-reveal-stagger") is not None
    indices = [int((c.get("style") or "").split(":")[1]) for c in refs]
    assert indices[:3] == [0, 1, 2]
    assert max(indices) == STAGGER_INDEX_CAP


def test_body_is_not_mistaken_for_the_reference_list() -> None:
    """<body> contains every anchor too. What distinguishes the real list
    is that its children each carry one."""
    doc = _marked(
        "<h2>A</h2><h2>B</h2>"
        '<p>Prose <span id="ref-1"></span> more <span id="ref-2"></span>.</p>'
        '<p>And <span id="ref-3"></span> again.</p>'
    )
    body = doc.find("body")
    assert body.get("data-reveal-stagger") is None
    assert all(el.get("data-reveal-stagger") is None for el in body.iter())


def test_inline_citations_are_not_mistaken_for_the_bibliography() -> None:
    """A paragraph carrying two inline citation anchors is prose."""
    doc = _marked(
        "<h2>A</h2><h2>B</h2>"
        '<p>As shown <span id="ref-1"></span> and <span id="ref-2"></span>.</p>'
    )
    para = doc.find(".//p")
    assert para.getparent().get("data-reveal-stagger") is None


# ── 3b. SVG figures get a ratio too ─────────────────────────────────

def _svg(path: Path, attrs: str) -> Path:
    path.write_text(f'<svg xmlns="http://www.w3.org/2000/svg" {attrs}></svg>')
    return path


def test_svg_dimensions_come_from_width_and_height(tmp_path: Path) -> None:
    """Most figures in this paper are SVG, which Pillow cannot read — so
    without this the reservation misses exactly the images it is for."""
    from web_assets import apply_image_hints  # ty: ignore[unresolved-import]
    from lxml import html as lxml_html

    img = lxml_html.fromstring('<img src="assets/f.svg"/>')
    apply_image_hints(img, _svg(tmp_path / "f.svg", 'width="612pt" height="396pt"'))
    assert (img.get("width"), img.get("height")) == ("612", "396")


def test_svg_dimensions_fall_back_to_the_viewbox(tmp_path: Path) -> None:
    from web_assets import apply_image_hints  # ty: ignore[unresolved-import]
    from lxml import html as lxml_html

    img = lxml_html.fromstring('<img src="assets/f.svg"/>')
    apply_image_hints(img, _svg(tmp_path / "f.svg", 'viewBox="0 0 800 450"'))
    assert (img.get("width"), img.get("height")) == ("800", "450")


def test_percentage_width_svg_uses_the_viewbox(tmp_path: Path) -> None:
    """A width of "100%" is not an intrinsic size; reserving a box 100
    units wide would be worse than reserving none."""
    from web_assets import apply_image_hints  # ty: ignore[unresolved-import]
    from lxml import html as lxml_html

    img = lxml_html.fromstring('<img src="assets/f.svg"/>')
    apply_image_hints(
        img, _svg(tmp_path / "f.svg", 'width="100%" height="100%" viewBox="0 0 640 480"')
    )
    assert (img.get("width"), img.get("height")) == ("640", "480")


# ── 3c. Above-the-fold images are not lazy ──────────────────────────

def test_title_band_images_are_not_lazy(tmp_path: Path) -> None:
    """The logo and resource icons sit in the opening screen; deferring
    them costs LCP and buys nothing."""
    from web_assets import apply_image_hints  # ty: ignore[unresolved-import]
    from lxml import html as lxml_html

    doc = lxml_html.fromstring(
        '<body class="paper-root"><header class="paper-header">'
        '<img src="logo.webp"/></header><div class="figure-block">'
        '<img src="fig.webp"/></div></body>'
    )
    logo, fig = doc.xpath("//img")
    apply_image_hints(logo, _png(tmp_path / "a.png", (100, 40)))
    apply_image_hints(fig, _png(tmp_path / "b.png", (800, 600)))

    assert logo.get("loading") is None
    assert fig.get("loading") == "lazy"
    # Both still get the decode hint and a reserved box.
    assert logo.get("decoding") == "async" and logo.get("width") == "100"


# ── 3. Fonts load from <head>, not a chained @import ────────────────

def test_web_css_does_not_import_fonts() -> None:
    """The @import costs a third serial round trip before any text
    renders in Manrope/Playfair."""
    css = WEB_CSS.read_text()
    assert "fonts.googleapis.com" not in css, (
        "web font @import still in the stylesheet; move it to <head>"
    )


def test_build_emits_preconnect_before_the_font_stylesheet() -> None:
    """preconnect must precede the stylesheet link, or it buys nothing:
    the point is to open the TLS connection while the HTML still parses.
    Both Google hosts are needed — the CSS and the woff2 are on
    different origins, and gstatic must be crossorigin."""
    from web_assets import FONT_HEAD_LINKS  # ty: ignore[unresolved-import]

    joined = "\n".join(FONT_HEAD_LINKS)
    assert joined.index("preconnect") < joined.index('rel="stylesheet"')
    assert "fonts.googleapis.com" in joined
    assert "fonts.gstatic.com" in joined
    gstatic = next(x for x in FONT_HEAD_LINKS if "gstatic" in x)
    assert "crossorigin" in gstatic, (
        "the font files are fetched in CORS mode; a preconnect without "
        "crossorigin warms the wrong connection and is wasted"
    )
    assert "display=swap" in joined, "no swap = invisible text while loading"


def test_every_heading_level_reveals() -> None:
    """The manuscript's subsection headings are h4 and h6, not h3. An
    earlier selector listed only h2/h3 and left 31 headings static —
    most of what a reader scrolling Methods actually passes."""
    doc = _marked(
        "<h2>Lead</h2><h2>Methods</h2><h3>Sub</h3><h4>UniProt</h4>"
        "<h5>Table caption</h5><h6>Discovery</h6>"
    )
    for tag in ("h3", "h4", "h5", "h6"):
        el = doc.find(f".//{tag}")
        assert "reveal" in (el.get("class") or ""), f"<{tag}> does not reveal"


def test_figure_captions_do_not_reveal_separately() -> None:
    """h5 is also the caption level, but a caption reveals with its
    figure — animating it on its own would lag the image."""
    doc = _marked(
        '<h2>A</h2><p>lead</p><div class="figure-block">'
        '<p><img src="a.webp"/></p><h5>Figure 1. Caption.</h5></div>'
    )
    caption = doc.find(".//h5")
    assert "reveal" not in (caption.get("class") or "")


def test_large_blocks_get_their_own_slower_motion() -> None:
    """A figure moved as far and as fast as a line of prose reads as
    simply appearing — the travel is tiny next to its own height."""
    css = _strip_comments(WEB_CSS.read_text())
    block = re.search(
        r"\.paper-root \.figure-block\.reveal,\s*\.paper-root table\.reveal\s*\{([^}]*)\}",
        css,
    )
    assert block, "figures and tables share the default reveal distance"
    base_d = int(re.search(r"--reveal-distance:\s*(\d+)px", css).group(1))
    base_t = int(re.search(r"--reveal-duration:\s*(\d+)ms", css).group(1))
    fig_d = int(re.search(r"--reveal-distance:\s*(\d+)px", block.group(1)).group(1))
    fig_t = int(re.search(r"--reveal-duration:\s*(\d+)ms", block.group(1)).group(1))
    assert fig_d > base_d and fig_t > base_t


def test_reveal_is_held_until_the_block_is_on_screen() -> None:
    """Fired at the viewport edge, the animation completes below where
    anyone is looking and the page just seems to have been that way."""
    js = WEB_JS.read_text()
    m = re.search(r'rootMargin:\s*"0px 0px -(\d+)% 0px"', js)
    assert m and int(m.group(1)) >= 12, (
        "reveal triggers too close to the viewport edge to be seen"
    )


# ── 5. The lightbox fits the screen ─────────────────────────────────

def test_lightbox_never_scrolls() -> None:
    """Opening a figure full-screen is for seeing the whole figure; a
    lightbox you have to scroll has given back the thing it was for."""
    css = _strip_comments(WEB_CSS.read_text())
    overlay = re.search(r"\.figure-lightbox\s*\{([^}]*)\}", css)
    assert overlay, "no .figure-lightbox rule"
    assert not re.search(r"overflow(-y)?:\s*auto", overlay.group(1)), (
        "the lightbox overlay scrolls instead of fitting its contents"
    )


def test_lightbox_figure_area_can_actually_shrink() -> None:
    """A flex item defaults to `min-height: auto`, which refuses to go
    below its intrinsic size — the usual reason a max-height on a
    flexbox image appears to do nothing at all. The figure's window is
    what shrinks now; the image fills it and is transformed inside."""
    css = _strip_comments(WEB_CSS.read_text())
    vp = re.search(r"\.figure-lightbox__viewport\s*\{([^}]*)\}", css)
    assert vp, "no figure viewport rule"
    assert re.search(r"min-height:\s*0", vp.group(1)), "figure area cannot shrink"
    img = re.search(r"\.figure-lightbox__viewport img\s*\{([^}]*)\}", css)
    assert img, "no lightbox image rule"
    assert "object-fit: contain" in img.group(1), "image would distort"


def test_lightbox_shows_the_whole_legend() -> None:
    """Opening a figure full-screen and still not being able to read its
    legend is the worst of both. The caption keeps its natural height and
    the full panel width; the image takes what is left."""
    css = _strip_comments(WEB_CSS.read_text())
    cap = re.search(r"\.figure-lightbox__inner figcaption\s*\{([^}]*)\}", css)
    assert cap, "no lightbox caption rule"
    body = cap.group(1)
    assert not re.search(r"overflow(-y)?:\s*(auto|scroll)", body), (
        "the legend scrolls instead of being shown whole"
    )
    assert not re.search(r"max-height", body), "the legend is height-capped"
    assert not re.search(r"max-width", body), (
        "the legend is narrower than the lightbox, which wraps it into "
        "more lines and makes it harder to fit"
    )


def test_figure_zooms_inside_its_own_frame() -> None:
    """Zooming happens within the figure's window, so the panel keeps its
    shape and the legend stays put and readable — rather than the figure
    popping out to fill the viewport, which is a different gesture."""
    css = _strip_comments(WEB_CSS.read_text())
    vp = re.search(r"\.figure-lightbox__viewport\s*\{([^}]*)\}", css)
    assert vp, "no figure viewport"
    assert "overflow: hidden" in vp.group(1), (
        "the viewport is not a window, so a scaled image would escape it"
    )
    assert "touch-action: none" in vp.group(1), (
        "the browser will claim pinch for page zoom before the handler sees it"
    )
    assert ".figure-lightbox.is-zoomed figcaption" not in css, (
        "the old pop-out zoom (which hid the legend) is still present"
    )


def test_pinch_and_wheel_both_zoom() -> None:
    """A trackpad pinch reaches the page only as a ctrl+wheel event."""
    js = WEB_JS.read_text()
    assert 'addEventListener(\n    "wheel"' in js or '"wheel"' in js
    assert "passive: false" in js, "a passive wheel listener cannot preventDefault"
    assert "pointerdown" in js and "Math.hypot" in js, "no two-finger pinch"


def test_zoom_keeps_the_point_under_the_cursor() -> None:
    """Zooming about the centre drifts whatever you were looking at off
    screen, which is what makes a zoom feel broken."""
    js = WEB_JS.read_text()
    assert "function zoomAt(" in js
    assert "px - ((px - tx) * next) / scale" in js


def test_panning_does_not_dismiss_the_lightbox() -> None:
    """A drag that ends on the image fires a click too, and the overlay
    dismisses on click."""
    js = WEB_JS.read_text()
    assert "if (panned || scale > MIN_SCALE) return;" in js


def test_zoom_resets_between_figures() -> None:
    """Stepping through figures should show them comparably, not inherit
    the previous one's zoom."""
    js = WEB_JS.read_text()
    opened = js[js.index('overlay.classList.add("is-open")'):][:400]
    assert "resetZoom();" in opened


def test_figure_window_gets_its_shape_from_the_image() -> None:
    """Without a shape of its own the window is sized BY the image, then
    shrinks to make room for the legend — and the image, whose
    `max-height: 100%` resolves against a height derived from itself,
    keeps its original size and is clipped top and bottom."""
    js = WEB_JS.read_text()
    assert "setViewportRatio(" in js
    assert "aspectRatio" in js
    css = _strip_comments(WEB_CSS.read_text())
    vp = re.search(r"\.figure-lightbox__viewport\s*\{([^}]*)\}", css)
    assert vp and "min-height: 0" in vp.group(1)
    img = re.search(r"\.figure-lightbox__viewport img\s*\{([^}]*)\}", css)
    assert img, "no lightbox image rule"
    # Absolutely filling a window that has its own shape is what removes
    # the circular dependency.
    assert "position: absolute" in img.group(1)
    assert "object-fit: contain" in img.group(1)


def test_panning_cannot_strand_the_reader_off_the_figure() -> None:
    js = WEB_JS.read_text()
    assert "function clampPan()" in js
    assert "Math.min(0, Math.max(w * (1 - scale), tx))" in js


def test_scrolling_pans_once_zoomed_in() -> None:
    """Zoomed in, a two-finger scroll is how anyone expects to move
    around a magnified image. Mapping it to zoom instead leaves the
    reader magnified with no way to reach the rest of the figure."""
    js = WEB_JS.read_text()
    wheel = js[js.index('"wheel"'):][:900]
    assert "else if (scale > MIN_SCALE)" in wheel
    assert "tx -= e.deltaX" in wheel and "ty -= e.deltaY" in wheel


def test_dragging_the_image_is_not_a_native_image_drag() -> None:
    """Otherwise the pointer stream stops, a ghost thumbnail follows the
    cursor, and the pan silently never happens."""
    js = WEB_JS.read_text()
    assert 'draggable="false"' in js
    down = js[js.index('addEventListener("pointerdown"'):]
    down = down[: down.index("});")]
    assert "e.preventDefault();" in down, (
        "pointerdown does not suppress the native image drag"
    )
    css = _strip_comments(WEB_CSS.read_text())
    img = re.search(r"\.figure-lightbox__viewport img\s*\{([^}]*)\}", css)
    assert img and "user-drag: none" in img.group(1)


def test_there_is_a_visible_way_to_reset_the_zoom() -> None:
    """Double-click and Escape both reset, but neither is visible, so
    neither is a way out for a reader who doesn't already know."""
    js = WEB_JS.read_text()
    assert "figure-lightbox__reset" in js
    css = _strip_comments(WEB_CSS.read_text())
    shown = re.search(
        r"\.figure-lightbox__viewport\.is-zoomed \.figure-lightbox__reset\s*\{([^}]*)\}",
        css,
    )
    assert shown, "the reset control is never shown"
    assert "pointer-events: auto" in shown.group(1), "shown but not clickable"
    hidden = re.search(r"\.figure-lightbox__reset\s*\{([^}]*)\}", css)
    assert "pointer-events: none" in hidden.group(1), (
        "the control is clickable while invisible"
    )


# ── 6. Typography the reader navigates by ───────────────────────────

def _font_px(css: str, selector: str) -> float:
    """rem/px font-size declared for a top-level element selector.

    Anchored at line start so `h2` doesn't match inside, say,
    `.figure-lightbox h2`.
    """
    m = re.search(
        r"^" + re.escape(selector) + r"\s*\{[^}]*?font-size:\s*([0-9.]+)(rem|px)",
        css,
        re.M | re.S,
    )
    assert m, f"no font-size for {selector}"
    return float(m.group(1)) * (16 if m.group(2) == "rem" else 1)


def test_section_headings_outrank_their_subsections() -> None:
    """h2 was set as a small tracked label at 0.82rem, leaving every
    major section heading SMALLER than the subsections beneath it — 13px
    against h3's 20px — so the hierarchy read backwards and crossing
    into a new section registered as nothing at all."""
    css = _strip_comments(WEB_CSS.read_text())
    sizes = [_font_px(css, s) for s in ("h2", "h3", "h4", "h6")]
    assert sizes == sorted(sizes, reverse=True), (
        f"heading sizes are not monotonic by level: {sizes}"
    )
    body = _font_px(css, ".paper-root")
    assert sizes[0] > body * 1.2, "section headings barely outweigh body text"


def test_figure_legend_shares_the_body_text_column() -> None:
    """The legend is prose. It sits inside .figure-block, which is
    deliberately wider than the measure so figures can be wide — without
    its own width it inherits that and every caption hangs a couple of
    dozen pixels outside the text column, which reads as a mistake."""
    css = _strip_comments(WEB_CSS.read_text())
    rule = re.search(r"\.paper-root > \.figure-block h5\s*\{([^}]*)\}", css)
    assert rule, "the figure legend has no width of its own"
    body = rule.group(1)
    assert "var(--measure)" in body, "legend width is not tied to the text column"
    assert "margin-inline: auto" in body, "legend is not centred on the column"
