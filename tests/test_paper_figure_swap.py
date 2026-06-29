"""Tests for the paper-build figure-swap + resolution-check step.

Why: the published PDF must carry the CURRENT canonical render of each
figure (the one under ``data/analysis/figures/``, also linked from the
gist + Zenodo), NOT whatever bitmap the author pasted into the .docx
weeks ago. ``paper.figure_swap.swap_figures`` enforces that swap.

This suite covers:
  • manifest parsing (main + appendix figures, optional flag)
  • PNG DPI check (accepts 600, rejects below, tolerates matplotlib's
    599.9988 floating-point quirk)
  • SVG validation (real <svg> root vs html-by-accident; soft-warn on
    embedded raster)
  • PDF header sniff
  • End-to-end HTML rewrite (span-id → manifest key → canonical path,
    width/height/style attrs stripped from <img>)
"""
from __future__ import annotations

import json
import tempfile
from pathlib import Path

import pytest

# Skip the entire module if the paper extra isn't installed (lxml is the
# only hard dep we touch from figure_swap; Pillow is checked at use time).
pytest.importorskip("lxml")

# paper/ isn't a Python package on PYTHONPATH (it's a sibling script
# directory invoked as ``python paper/build.py ...``). Put it on
# sys.path so the test imports figure_swap the same way build.py does.
import sys  # noqa: E402
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "paper"))

from figure_swap import (  # noqa: E402  # ty: ignore[unresolved-import]
    FigureSpec,
    format_report,
    load_manifest,
    swap_figures,
    validate_canonical_asset,
)


REPO_ROOT = Path(__file__).resolve().parents[1]
FIGURES_DIR = REPO_ROOT / "data/analysis/figures"
MANIFEST_PATH = REPO_ROOT / "paper/figure_manifest.json"


# ── Manifest loader ───────────────────────────────────────────────────


def test_manifest_loads_main_and_appendix_keys(tmp_path: Path) -> None:
    raw = {
        "figures": {
            "1": {"slug": "a", "format": "svg"},
            "2": {"slug": "b", "format": "png", "min_dpi": 600},
        },
        "appendix_figures": {
            "1": {"slug": "c", "format": "png", "min_dpi": 300, "optional": True},
        },
    }
    p = tmp_path / "m.json"
    p.write_text(json.dumps(raw))
    m = load_manifest(p)
    assert set(m.keys()) == {"1", "2", "appendix-1"}
    assert m["1"].slug == "a"
    assert m["2"].min_dpi == 600
    assert m["appendix-1"].optional is True


def test_manifest_missing_returns_empty(tmp_path: Path) -> None:
    assert load_manifest(tmp_path / "nope.json") == {}


def test_real_manifest_parses() -> None:
    """The checked-in paper/figure_manifest.json must parse without errors."""
    m = load_manifest(MANIFEST_PATH)
    assert m, "expected paper/figure_manifest.json to declare at least one figure"
    for key, spec in m.items():
        assert spec.format in ("png", "svg", "pdf"), (
            f"figure {key}: unknown format {spec.format!r}"
        )


# ── Per-format validation ─────────────────────────────────────────────


def test_validate_png_passes_for_existing_600_dpi_png() -> None:
    """The committed mock figures should pass at the 600 DPI bar — the
    rounding tolerance in _validate_png handles matplotlib's 599.9988
    quirk."""
    spec = FigureSpec(
        slug="deep_dive_final_categories", format="png", min_dpi=600,
    )
    issues = validate_canonical_asset(spec, FIGURES_DIR)
    assert issues == [], f"unexpected issues: {issues}"


def test_validate_png_fails_when_dpi_below_threshold(tmp_path: Path) -> None:
    """A PNG written at the default 72 DPI must fail a 600 DPI check."""
    from PIL import Image
    png = tmp_path / "low_dpi.png"
    Image.new("RGB", (10, 10), "white").save(png)  # default DPI = 72
    spec = FigureSpec(slug="low_dpi", format="png", min_dpi=600)
    issues = validate_canonical_asset(spec, tmp_path)
    assert any("DPI" in i for i in issues), issues


def test_validate_png_missing_file_returns_issue(tmp_path: Path) -> None:
    spec = FigureSpec(slug="nope", format="png", min_dpi=600)
    issues = validate_canonical_asset(spec, tmp_path)
    assert len(issues) == 1
    assert "missing" in issues[0]


def test_validate_png_optional_marks_missing_softly(tmp_path: Path) -> None:
    spec = FigureSpec(slug="nope", format="png", min_dpi=600, optional=True)
    issues = validate_canonical_asset(spec, tmp_path)
    assert "marked optional" in issues[0]


def test_validate_svg_accepts_real_svg(tmp_path: Path) -> None:
    p = tmp_path / "x.svg"
    p.write_bytes(b'<?xml version="1.0"?><svg xmlns="http://www.w3.org/2000/svg" '
                  b'viewBox="0 0 10 10"><circle cx="5" cy="5" r="2"/></svg>')
    spec = FigureSpec(slug="x", format="svg")
    issues = validate_canonical_asset(spec, tmp_path)
    assert issues == []


def test_validate_svg_soft_warns_on_embedded_raster(tmp_path: Path) -> None:
    """An SVG wrapping a base64 raster keeps the raster's resolution —
    flag it as a soft issue so the author knows."""
    p = tmp_path / "x.svg"
    p.write_bytes(
        b'<?xml version="1.0"?><svg xmlns="http://www.w3.org/2000/svg" '
        b'viewBox="0 0 10 10"><image href="data:image/png;base64,iVBORw0K..."/>'
        b'</svg>'
    )
    spec = FigureSpec(slug="x", format="svg")
    issues = validate_canonical_asset(spec, tmp_path)
    assert any("base64-embedded raster" in i for i in issues), issues


def test_validate_pdf_accepts_real_pdf(tmp_path: Path) -> None:
    p = tmp_path / "x.pdf"
    p.write_bytes(b"%PDF-1.7\nfake body\n%%EOF")
    spec = FigureSpec(slug="x", format="pdf")
    issues = validate_canonical_asset(spec, tmp_path)
    assert issues == []


def test_validate_pdf_rejects_non_pdf(tmp_path: Path) -> None:
    p = tmp_path / "x.pdf"
    p.write_bytes(b"not actually a pdf")
    spec = FigureSpec(slug="x", format="pdf")
    issues = validate_canonical_asset(spec, tmp_path)
    assert any("not a PDF" in i for i in issues), issues


# ── End-to-end HTML rewrite ───────────────────────────────────────────


_PANDOC_SHAPED_HTML = """<!DOCTYPE html>
<html><body>
<p><span id="figure-1-deep-dive-flow"></span><img src="/old/path/word_image_1.png" width="500" height="300" style="border:1px solid red"/></p>
<h5 id="">Figure 1. Deep-dive pipeline.</h5>
<p>Body text referencing Figure 1.</p>
<p><span id="figure-2-categories"></span><img src="/old/path/word_image_2.png"/></p>
<h5>Figure 2. Category distribution.</h5>
<p><span id="appendix-figure-1-tdd"></span><img src="/old/path/word_image_3.png"/></p>
<h5>Appendix Figure 1. Confusion matrix.</h5>
</body></html>
"""


def _write_canonical_assets(td: Path) -> dict[str, FigureSpec]:
    """Make tiny placeholder PNG/SVG files so the validator passes
    without depending on the in-repo figures (keeps the test
    hermetic + independent of figure re-renders)."""
    from PIL import Image
    png = td / "deep_dive_final_categories.png"
    Image.new("RGB", (10, 10), "white").save(png, dpi=(600, 600))
    appendix_png = td / "triage_vs_deep_dive_reason.png"
    Image.new("RGB", (10, 10), "white").save(appendix_png, dpi=(600, 600))
    svg = td / "deep_dive_flow.svg"
    svg.write_bytes(b'<?xml version="1.0"?><svg xmlns="http://www.w3.org/2000/svg" '
                    b'viewBox="0 0 10 10"><circle cx="5" cy="5" r="2"/></svg>')
    return {
        "1": FigureSpec(slug="deep_dive_flow", format="svg"),
        "2": FigureSpec(slug="deep_dive_final_categories", format="png", min_dpi=600),
        "appendix-1": FigureSpec(slug="triage_vs_deep_dive_reason", format="png",
                                  min_dpi=600),
    }


def test_swap_figures_rewrites_img_src() -> None:
    with tempfile.TemporaryDirectory() as td:
        td_path = Path(td)
        manifest = _write_canonical_assets(td_path)
        html = td_path / "test.html"
        html.write_text(_PANDOC_SHAPED_HTML)

        report = swap_figures(html, manifest, td_path)
        assert len(report.swapped) == 3
        assert not report.issues, f"unexpected issues: {report.issues}"

        out = html.read_text()
        # All three canonical files should appear in img src attrs.
        assert "deep_dive_flow.svg" in out
        assert "deep_dive_final_categories.png" in out
        assert "triage_vs_deep_dive_reason.png" in out
        # The originals should be gone.
        assert "word_image_1.png" not in out
        assert "word_image_2.png" not in out
        assert "word_image_3.png" not in out


def test_swap_figures_strips_inline_sizing_hints() -> None:
    """width / height / style attrs on the <img> would override the
    print CSS's figure-card layout — drop them so the CSS controls
    sizing uniformly."""
    with tempfile.TemporaryDirectory() as td:
        td_path = Path(td)
        manifest = _write_canonical_assets(td_path)
        html = td_path / "test.html"
        html.write_text(_PANDOC_SHAPED_HTML)
        swap_figures(html, manifest, td_path)
        out = html.read_text()
        # The first img originally had width=500 height=300 style="..."
        # — these must be gone from the swapped img.
        assert 'width="500"' not in out
        assert 'height="300"' not in out
        assert "border:1px solid red" not in out


def test_swap_figures_with_empty_manifest_is_a_noop() -> None:
    with tempfile.TemporaryDirectory() as td:
        td_path = Path(td)
        html = td_path / "test.html"
        html.write_text(_PANDOC_SHAPED_HTML)
        report = swap_figures(html, {}, td_path)
        assert report.swapped == {}
        assert report.skipped == []
        assert report.issues == []
        # File is unchanged when no manifest entries to apply.
        assert html.read_text() == _PANDOC_SHAPED_HTML


def test_swap_skips_when_anchor_has_no_manifest_entry() -> None:
    with tempfile.TemporaryDirectory() as td:
        td_path = Path(td)
        # Manifest only knows about figure 1 — figure 2 / appendix-1 should be skipped.
        manifest = {"1": FigureSpec(slug="deep_dive_flow", format="svg")}
        td_path.joinpath("deep_dive_flow.svg").write_bytes(
            b'<?xml version="1.0"?><svg xmlns="http://www.w3.org/2000/svg" '
            b'viewBox="0 0 10 10"/>'
        )
        html = td_path / "test.html"
        html.write_text(_PANDOC_SHAPED_HTML)
        report = swap_figures(html, manifest, td_path)
        assert len(report.swapped) == 1
        assert "figure-1-deep-dive-flow" in report.swapped
        # Figure 2 + appendix-1 should be in skipped, NOT in issues
        # (a missing manifest entry isn't a build-failing issue —
        # the author just hasn't manifested that figure yet).
        assert len(report.skipped) == 2


def test_format_report_handles_empty_report() -> None:
    from figure_swap import SwapReport  # ty: ignore[unresolved-import]
    out = format_report(SwapReport())
    assert "manifest empty" in out or "no figures matched" in out
