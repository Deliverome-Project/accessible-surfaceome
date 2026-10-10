# /// script
# requires-python = ">=3.11"
# dependencies = ["playwright>=1.49"]
# ///
"""Main Figure 7 — `web_preview`: two screenshots of the live viewer.

Standalone reader-side mirror of ``scripts/figures/web_preview.py``.

    uv run --with playwright make_web_preview.py

One extra step versus the other figure scripts: Playwright drives a real
browser, so you need Chrome installed (the script uses ``channel="chrome"``).
It talks only to the public site — no credentials, no repo data, no TSV.

Because it screenshots the LIVE viewer, re-running this does not reproduce
the figure in the paper byte-for-byte; it reproduces the figure as the site
looks today. That is the point — it is how we catch the panels going stale.

Gist: https://gist.github.com/beccajcarlson/f8de3e35072ad91d76eb2ea5fb49cca6
"""
from __future__ import annotations

import asyncio
import base64
from pathlib import Path

# Standalone: write next to this script, wherever the reader unpacked it.
OUT_DIR = Path(__file__).resolve().parent
SLUG = "web_preview"
GIST_URL = "https://gist.github.com/beccajcarlson/f8de3e35072ad91d76eb2ea5fb49cca6"

SITE = "https://surfaceome.deliverome.org"
GENE = "SRC"

# Panel a is captured wider than panel b so the catalog table's right-hand
# columns get as much room as the table's own max-width allows.
# Panel a is wider so the widened .page-width container fits all columns.
A_WIDTH, B_WIDTH = 1520, 1490
DPR = 2

# Capture-only CSS. Three problems, all of them artifacts of screenshotting a
# live app rather than anything a reader should see in a figure:
#   1. scrollbars draw a grey gutter down the right edge of both panels;
#   2. the closed rationale drawer parks just off-screen and its box-shadow
#      bleeds back across the right edge, and hidden InfoTip popovers do the
#      same — that is the shading, not a crop artifact;
#   3. the catalog table is 1,317 px of columns inside a 1,280 px container,
#      so `STATE DEP.` is always clipped and the container paints a
#      horizontal-scroll shadow. Widening `.page-width` is the same view a
#      reader gets on a wider monitor; nothing is restyled or hidden.
CAPTURE_CSS = """
::-webkit-scrollbar{width:0!important;height:0!important;display:none!important}
html{scrollbar-width:none!important}
[class*="Drawer_drawer"],[class*="InfoTip_popover"]{display:none!important;box-shadow:none!important}
.page-width,[class*="page_page"]{width:1400px!important;max-width:none!important}
"""

# Layout constants, carried over from the hand-made SVG so the refreshed
# figure keeps its proportions: left inset, top margin, inter-panel gap,
# bottom padding, and panel a's rendered width in user units.
VIEWBOX_W = 529.71
A_LEFT, B_LEFT = 24.63, 24.53
A_TOP, GAP, BOTTOM_PAD = 3.0, 27.4, 21.5
# Both panels are scaled to a FIXED rendered width, not a fixed scale
# factor. A fixed scale silently overflows the viewBox the moment a capture
# width changes — which is exactly what happened when panel a was widened to
# fit the catalog's last column.
A_RENDERED_W = 502.74
B_RENDERED_W = 494.64
LABEL_DY = 12.04


async def _capture() -> tuple[bytes, bytes]:
    """Screenshot both panels, cropping each from live element geometry."""
    from playwright.async_api import async_playwright

    async with async_playwright() as p:
        browser = await p.chromium.launch(channel="chrome", headless=True)

        ctx = await browser.new_context(
            viewport={"width": A_WIDTH, "height": 1400}, device_scale_factor=DPR
        )
        page = await ctx.new_page()
        await page.goto(f"{SITE}/", wait_until="networkidle", timeout=90_000)
        await page.add_style_tag(content=CAPTURE_CSS)
        await page.wait_for_timeout(6_000)
        # rows[0] is the header, rows[1] the first gene — crop just below it.
        rows = page.locator("[role=row]")
        boxes = [await rows.nth(i).bounding_box() for i in range(2)]
        a_height = round(boxes[1]["y"] + boxes[1]["height"] + 6)
        panel_a = await page.screenshot(
            clip={"x": 0, "y": 0, "width": A_WIDTH, "height": a_height}
        )
        print(f"  panel a: {A_WIDTH}x{a_height} css -> {A_WIDTH * DPR}x{a_height * DPR}")
        await ctx.close()

        ctx = await browser.new_context(
            viewport={"width": B_WIDTH, "height": 1700}, device_scale_factor=DPR
        )
        page = await ctx.new_page()
        await page.goto(f"{SITE}/{GENE}/", wait_until="networkidle", timeout=90_000)
        await page.add_style_tag(content=CAPTURE_CSS)
        # The AlphaFold canvas renders late; give it time or the panel is blank.
        await page.wait_for_timeout(8_000)
        jump = await page.locator("input[placeholder*='Jump to gene']").first.bounding_box()
        glob = await page.locator("text=Globular").first.bounding_box()
        b_top = round(jump["y"] - 14)
        # +26 rather than a rounder number: it clears the "Globular" legend row
        # but stops short of the structure card's bottom border, which
        # otherwise lands on the panel's last pixel row and reads as shading.
        b_height = round(glob["y"] + glob["height"] + 12 - b_top)
        panel_b = await page.screenshot(
            clip={"x": 0, "y": b_top, "width": B_WIDTH, "height": b_height}
        )
        print(f"  panel b: {B_WIDTH}x{b_height} css -> {B_WIDTH * DPR}x{b_height * DPR}")
        await ctx.close()
        await browser.close()

    return panel_a, panel_b


def _png_size(data: bytes) -> tuple[int, int]:
    """Width/height straight out of the PNG IHDR — avoids a Pillow dep."""
    return (
        int.from_bytes(data[16:20], "big"),
        int.from_bytes(data[20:24], "big"),
    )


def build_svg(panel_a: bytes, panel_b: bytes) -> str:
    aw, ah = _png_size(panel_a)
    bw, bh = _png_size(panel_b)
    a_scale = A_RENDERED_W / aw
    b_scale = B_RENDERED_W / bw
    b_top = A_TOP + ah * a_scale + GAP
    viewbox_h = b_top + bh * b_scale + BOTTOM_PAD
    a64 = base64.b64encode(panel_a).decode()
    b64 = base64.b64encode(panel_b).decode()
    return f"""<?xml version="1.0" encoding="UTF-8"?>
<svg id="Layer_1" data-name="Layer 1" xmlns="http://www.w3.org/2000/svg" xmlns:xlink="http://www.w3.org/1999/xlink" viewBox="0 0 {VIEWBOX_W} {viewbox_h:.2f}">
  <defs>
    <style>
      .cls-1 {{
        fill: #231f20;
        font-family: Manrope-ExtraBold, Manrope;
        font-size: 14px;
        font-variation-settings: 'wght' 800;
        font-weight: 700;
      }}
    </style>
  </defs>
  <image width="{bw}" height="{bh}" transform="translate({B_LEFT} {b_top:.2f}) scale({b_scale:.6f})" xlink:href="data:image/png;base64,{b64}"/>
  <g id="NACWnK.tif">
    <image id="Layer_0" data-name="Layer 0" width="{aw}" height="{ah}" transform="translate({A_LEFT} {A_TOP}) scale({a_scale:.6f})" xlink:href="data:image/png;base64,{a64}"/>
  </g>
  <text class="cls-1" transform="translate(12.64 15.04)"><tspan x="0" y="0">a</tspan></text>
  <text class="cls-1" transform="translate(9.12 {b_top + LABEL_DY:.2f})"><tspan x="0" y="0">b</tspan></text>
</svg>
"""


async def _render(svg_path: Path) -> None:
    """SVG -> PDF + PNG, so Figure 7 ships the same pair as every other
    figure (and so ``by_paper_number/`` symlinks it like the rest)."""
    from playwright.async_api import async_playwright

    svg = svg_path.read_text()
    vb = svg.split('viewBox="0 0 ', 1)[1].split('"', 1)[0].split()
    w_pt, h_pt = float(vb[0]), float(vb[1])
    # 2 x 1103 css px ~= 2206 px wide ~= 300 DPI at the figure's 7.36 in width.
    css_w = 1103
    shell = svg_path.parent / "_web_preview_shell.html"
    shell.write_text(
        '<html><body style="margin:0;background:#fff">'
        f'<img src="{svg_path.name}" style="width:{css_w}px;display:block"></body></html>'
    )
    try:
        async with async_playwright() as p:
            browser = await p.chromium.launch(channel="chrome", headless=True)
            ctx = await browser.new_context(
                viewport={"width": css_w, "height": round(css_w * h_pt / w_pt)},
                device_scale_factor=2,
            )
            page = await ctx.new_page()
            await page.goto(shell.resolve().as_uri())
            await page.wait_for_timeout(3_000)
            await page.screenshot(path=str(svg_path.with_suffix(".png")))
            # Playwright's pdf() rejects "pt", so hand it inches (72 pt = 1 in)
            # and the PDF still lands at the SVG's exact user-unit size.
            await page.pdf(
                path=str(svg_path.with_suffix(".pdf")),
                width=f"{w_pt / 72:.4f}in",
                height=f"{h_pt / 72:.4f}in",
                print_background=True,
                margin={"top": "0", "bottom": "0", "left": "0", "right": "0"},
            )
            await browser.close()
    finally:
        shell.unlink(missing_ok=True)


async def _main() -> None:
    panel_a, panel_b = await _capture()
    svg_path = OUT_DIR / f"{SLUG}.svg"
    svg_path.write_text(build_svg(panel_a, panel_b))
    print(f"  Saved: {svg_path}")
    await _render(svg_path)
    for ext in ("pdf", "png"):
        print(f"  Saved: {svg_path.with_suffix('.' + ext)}")


if __name__ == "__main__":
    asyncio.run(_main())
