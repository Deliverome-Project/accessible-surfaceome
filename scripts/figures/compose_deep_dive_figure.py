"""Stack the cohort funnel over the deep-dive pipeline as one two-panel figure.

Main-paper Figure 4 becomes (a) how the 5,130-gene cohort is nominated
and trimmed, then (b) what the pipeline does to each of those genes.
Panel a is generated (``scripts/figures/pipeline_funnel.py``); panel b is
the author-drawn Illustrator export, used unmodified.

Both panels are inlined into one SVG rather than referenced, because the
paper build hands the file to WeasyPrint, which will not follow an
external image reference out of an SVG. Inlining is safe here: panel b
names its styles ``.st0``-``.st15`` and its groups ``stage1-*``, while
``pdftocairo`` names panel a's glyphs ``glyph-N-M``, so nothing collides.

``PANEL_A_TEXT_SCALE`` is the knob for reconciling the two panels' type
scales, and the measured answer is to leave it at 1.0. The panels were
drawn independently — panel a in a 1,650-unit canvas at 12 pt body text,
panel b in a 1,260-unit canvas — so it was not obvious they would agree.
Rendered at equal width they differ by roughly a tenth, panel b's type
being marginally the larger, which is below the threshold at which a
reader notices. Equal-width panels are worth more than closing that gap;
an earlier 0.80 here made panel a visibly the smaller of the two.

Outputs:
  paper/figures/deep_dive_flow.svg   the print asset the manifest resolves

Panel b's own gist still serves the single-panel schematic; the composite
is a print asset, not a new published figure.
"""

from __future__ import annotations

import re
import subprocess
import tempfile
from pathlib import Path

from accessible_surfaceome.paths import REPO_ROOT

PANEL_A_PDF = REPO_ROOT / "data/analysis/figures/pipeline_funnel.pdf"
PANEL_B_SVG = REPO_ROOT / "data/analysis/figures/deep_dive_flow.svg"
OUT_SVG = REPO_ROOT / "paper/figures/deep_dive_flow.svg"

# Panel a's width as a fraction of panel b's. 1.0 = equal width; see the
# module docstring for why that beats matching the type exactly.
PANEL_A_TEXT_SCALE = 1.0
GUTTER = 34.0          # vertical space between the panels
LETTER_GAP = 26.0      # space a panel letter occupies above its panel
MARGIN = 6.0

LETTER_STYLE = (
    'font-family="Manrope, Manrope ExtraBold, sans-serif" '
    'font-weight="800" font-size="30" fill="#1F1718"'
)


def _viewbox(svg: str) -> tuple[float, float]:
    m = re.search(r'viewBox="\s*([\d.+-]+)[ ,]+([\d.+-]+)[ ,]+([\d.+-]+)[ ,]+([\d.+-]+)', svg)
    if not m:
        raise SystemExit("no viewBox on the source SVG")
    return float(m.group(3)), float(m.group(4))


def _inner(svg: str) -> str:
    """Strip the XML prolog and the outer <svg> wrapper."""
    start = svg.index(">", svg.index("<svg")) + 1
    return svg[start : svg.rindex("</svg>")]


def main() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        panel_a_svg = Path(tmp) / "panel_a.svg"
        subprocess.run(
            ["pdftocairo", "-svg", str(PANEL_A_PDF), str(panel_a_svg)],
            check=True,
        )
        a_src = panel_a_svg.read_text(encoding="utf-8")
    b_src = PANEL_B_SVG.read_text(encoding="utf-8")

    aw, ah = _viewbox(a_src)
    bw, bh = _viewbox(b_src)

    # Panel b sets the composite width; panel a is scaled to a fraction of
    # it and centred so the two type scales agree.
    target_a_w = bw * PANEL_A_TEXT_SCALE
    sa = target_a_w / aw
    a_h = ah * sa
    a_x = MARGIN + (bw - target_a_w) / 2.0

    total_w = bw + 2 * MARGIN
    a_y = MARGIN + LETTER_GAP
    b_y = a_y + a_h + GUTTER + LETTER_GAP
    total_h = b_y + bh + MARGIN

    out = [
        '<?xml version="1.0" encoding="UTF-8"?>',
        f'<svg xmlns="http://www.w3.org/2000/svg" '
        f'xmlns:xlink="http://www.w3.org/1999/xlink" version="1.1" '
        f'viewBox="0 0 {total_w:.2f} {total_h:.2f}">',
        f'<rect x="0" y="0" width="{total_w:.2f}" height="{total_h:.2f}" fill="#ffffff"/>',
        f'<text x="{MARGIN:.2f}" y="{a_y - 4:.2f}" {LETTER_STYLE}>a</text>',
        f'<g transform="translate({a_x:.3f} {a_y:.3f}) scale({sa:.6f})">',
        _inner(a_src),
        "</g>",
        f'<text x="{MARGIN:.2f}" y="{b_y - 4:.2f}" {LETTER_STYLE}>b</text>',
        f'<g transform="translate({MARGIN:.3f} {b_y:.3f})">',
        _inner(b_src),
        "</g>",
        "</svg>",
    ]
    OUT_SVG.write_text("\n".join(out), encoding="utf-8")
    print(
        f"  panel a {aw:.0f}x{ah:.0f} -> scale {sa:.4f} ({target_a_w:.0f} wide)\n"
        f"  panel b {bw:.0f}x{bh:.0f} -> scale 1.0\n"
        f"  composite {total_w:.0f}x{total_h:.0f} -> {OUT_SVG}"
    )


if __name__ == "__main__":
    main()
