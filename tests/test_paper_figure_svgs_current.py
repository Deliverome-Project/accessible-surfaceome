"""Guard: the paper build's vector figures exist and match their source PDF.

``paper/figure_manifest.json`` points most figures at an SVG in
``paper/figures/``, converted from the canonical render
``data/analysis/figures/<slug>.pdf`` by ``paper/convert_figure_svgs.py``. The
conversion is a manual step, and it has gone wrong three times:

* Supp S16's SVG had never been made, so the build silently kept the .docx's
  bitmap for it (2026-10-12).
* S2, S4 and S15 were re-rendered after their SVGs were made, so the PDF and
  web editions shipped the old figures. The build's .docx comparison did not
  flag them because the .docx carried the same old versions (2026-10-12).
* S15 was re-rendered again on 2026-10-13 without re-converting. An earlier
  version of this test compared git commit dates, which CI's shallow clone
  cannot see, so it passed there.

Each SVG now carries the SHA-256 of the PDF it was converted from, so this
check works in any checkout. Fix a failure with
``uv run python paper/convert_figure_svgs.py <slug>``.
"""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MANIFEST = ROOT / "paper/figure_manifest.json"
SEARCH = [ROOT / "paper/figures", ROOT / "data/analysis/figures"]


def _converter():
    spec = importlib.util.spec_from_file_location(
        "convert_figure_svgs", ROOT / "paper/convert_figure_svgs.py"
    )
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _entries() -> list[dict]:
    m = json.loads(MANIFEST.read_text())
    return [
        e
        for key in ("figures", "appendix_figures", "supplementary_figures")
        for e in (m.get(key) or {}).values()
    ]


def test_every_manifest_figure_has_its_asset() -> None:
    missing = [
        f"{e['slug']}.{e['format']}"
        for e in _entries()
        if not any((d / f"{e['slug']}.{e['format']}").is_file() for d in SEARCH)
    ]
    assert not missing, (
        f"figure_manifest.json assets not found in paper/ or data/analysis/figures/: {missing}"
    )


def test_converted_svgs_match_their_source_pdf() -> None:
    conv = _converter()
    stale = []
    for slug in conv.svg_slugs():
        svg = conv.SVG_DIR / f"{slug}.svg"
        if svg.is_file() and conv.stamp_of(svg) != conv.pdf_sha256(slug):
            stale.append(slug)
    assert not stale, (
        "paper/figures SVGs not converted from the current canonical PDF; run "
        f"`uv run python paper/convert_figure_svgs.py {' '.join(stale)}`"
    )


def test_composed_svgs_match_their_reader_copy() -> None:
    conv = _converter()
    differ = [
        f"{slug} (re-run {script})"
        for slug, script in conv.COMPOSED.items()
        if (conv.SVG_DIR / f"{slug}.svg").read_bytes()
        != (conv.PDF_DIR / f"{slug}.svg").read_bytes()
    ]
    assert not differ, (
        f"composed paper SVGs differ from data/analysis/figures copies: {differ}"
    )


def test_no_paper_svg_places_an_image_through_use() -> None:
    """No paper SVG uses pdftocairo's raster construct (an ``<image>`` placed
    via ``<use>``).

    WeasyPrint drew nothing for the converted Figure 7, which is built this way.
    The exact trigger is unknown, so this is a cheap CI-side heuristic; the
    paper build's render check (``paper/figure_render_check.py``) is the real
    guard.
    """
    import re

    bad = []
    for e in _entries():
        if e["format"] != "svg":
            continue
        path = next((d / f"{e['slug']}.svg" for d in SEARCH if (d / f"{e['slug']}.svg").is_file()), None)
        if path is None:
            continue
        text = path.read_text(encoding="utf-8")
        image_ids = set(re.findall(r'<image[^>]*\bid="([^"]+)"', text))
        if any(ref in image_ids for ref in re.findall(r'<use[^>]*xlink:href="#([^"]+)"', text)):
            bad.append(str(path.relative_to(ROOT)))
    assert not bad, f"SVGs that place an image via <use> (render blank in WeasyPrint): {bad}"
