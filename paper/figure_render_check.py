"""Fail the paper build when a swapped-in figure renders blank in WeasyPrint.

WeasyPrint has its own SVG renderer and silently draws nothing for constructs
it cannot handle, with no warning. Figure 7 shipped as an empty box in the PDF
(2026-10-18) because WeasyPrint drew nothing for pdftocairo's conversion of it;
plain ``<use>``, large rasters and clip paths each render fine on their own, so
the exact construct is unknown. Rather than guess at patterns, this check
renders each figure the build is about to use on its own page and measures
whether anything was drawn.
"""

from __future__ import annotations

from collections.abc import Iterable
from pathlib import Path

# Pixel-value standard deviation of the rendered page. A blank page is 0.0;
# the sparsest real figure in the manuscript renders above 10.
BLANK_STDDEV = 1.0


def blank_figures(paths: Iterable[Path]) -> list[Path]:
    """Return the figure files that render as an empty page in WeasyPrint."""
    import pypdfium2 as pdfium  # ty: ignore[unresolved-import]
    from PIL import ImageStat
    from weasyprint import HTML  # ty: ignore[unresolved-import]

    blank: list[Path] = []
    for path in sorted({Path(p).resolve() for p in paths}):
        html = (
            '<html><body style="margin:0">'
            f'<img src="{path.as_uri()}" style="width:6.5in">'
            "</body></html>"
        )
        pdf = pdfium.PdfDocument(HTML(string=html).write_pdf())
        try:
            image = pdf[0].render(scale=0.5).to_pil().convert("L")
        finally:
            pdf.close()
        if ImageStat.Stat(image).stddev[0] < BLANK_STDDEV:
            blank.append(path)
    return blank
