"""Guard: the paper build's figure manifest matches the canonical figure order.

``paper/figure_manifest.json`` tells ``paper/build.py`` which repo render to
swap in under each figure number in the .docx. ``FIGURE_ORDER`` in
``scripts/build_figure_index.py`` is the canonical number -> slug mapping and
is what ``paper/figure_index.md`` and ``by_paper_number/`` are built from.

Nothing tied the two together, and they drifted: the manifest had **S3/S4 and
S11/S12 swapped**, so the built PDF placed four supplementary figures under
the wrong captions, and it stopped at S14 after S15 was added. A reviewer
caught the S11/S12 pair by eye in the PDF; the S3/S4 pair had gone unnoticed.

The manifest's ``format`` / ``min_dpi`` / ``description`` fields are per-slug
rendering decisions (is the vector conversion smaller than a 600-DPI raster?),
so when a number->slug assignment is corrected the WHOLE entry moves with the
slug. This test only pins the slug mapping; the rendering fields are the
manifest's own business.
"""
from __future__ import annotations

import importlib.util
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MANIFEST = ROOT / "paper/figure_manifest.json"
ORDER_SCRIPT = ROOT / "scripts/build_figure_index.py"


def _figure_order() -> list[tuple[str, str]]:
    spec = importlib.util.spec_from_file_location("_bfi", ORDER_SCRIPT)
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return list(mod.FIGURE_ORDER)


def _expected() -> tuple[dict[str, str], dict[str, str]]:
    main: dict[str, str] = {}
    supp: dict[str, str] = {}
    for label, slug in _figure_order():
        if label.startswith("Supp S"):
            supp[label.removeprefix("Supp S")] = slug
        elif label.startswith("Figure "):
            main[label.removeprefix("Figure ")] = slug
    return main, supp


def _manifest() -> dict:
    return json.loads(MANIFEST.read_text())


def test_main_figure_slugs_match_figure_order() -> None:
    expected, _ = _expected()
    got = {k: v.get("slug") for k, v in _manifest()["figures"].items()}
    assert got == expected, (
        "paper/figure_manifest.json['figures'] disagrees with FIGURE_ORDER in "
        "scripts/build_figure_index.py. The manifest decides which render the "
        "PDF build swaps in per figure number, so a mismatch ships the wrong "
        f"figure under a caption.\n  manifest: {got}\n  expected: {expected}"
    )


def test_supplementary_figure_slugs_match_figure_order() -> None:
    _, expected = _expected()
    got = {k: v.get("slug") for k, v in _manifest()["supplementary_figures"].items()}
    assert got == expected, (
        "paper/figure_manifest.json['supplementary_figures'] disagrees with "
        "FIGURE_ORDER. This is the drift that put S3/S4 and S11/S12 under each "
        "other's captions in the built PDF. Move the WHOLE manifest entry "
        "(slug + format + description) when correcting an assignment — the "
        "rendering fields belong to the slug, not the number.\n"
        f"  manifest: {got}\n  expected: {expected}"
    )


def test_every_ordered_figure_has_a_manifest_entry() -> None:
    main, supp = _expected()
    man = _manifest()
    missing_main = sorted(set(main) - set(man["figures"]), key=int)
    missing_supp = sorted(set(supp) - set(man["supplementary_figures"]), key=int)
    assert not missing_main and not missing_supp, (
        "A figure in FIGURE_ORDER has no manifest entry, so the PDF build "
        "leaves the .docx's original image in place instead of swapping in the "
        "canonical render — silently, which is how S15 shipped unswapped.\n"
        f"  missing main: {missing_main}\n  missing supplementary: {missing_supp}"
    )
