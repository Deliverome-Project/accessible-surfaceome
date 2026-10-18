"""The paper build's blank-figure check flags an SVG WeasyPrint draws as empty.

Needs the paper toolchain (``uv sync --extra paper``); skipped otherwise. The
static guard in ``test_paper_figure_svgs_current.py`` runs everywhere.
"""

from __future__ import annotations

import base64
import importlib.util
import io
from pathlib import Path

import pytest

_ROOT = Path(__file__).resolve().parents[1]


def _load_weasyprint() -> None:
    """Import WeasyPrint the way paper/build.py does (it patches cffi so the
    Homebrew Pango/Cairo libraries load on macOS); skip without the toolchain."""
    pytest.importorskip("pypdfium2")
    spec = importlib.util.spec_from_file_location("paper_build_libs", _ROOT / "paper/build.py")
    try:
        assert spec and spec.loader
        src = (_ROOT / "paper/build.py").read_text()
        ns: dict = {"__file__": str(_ROOT / "paper/build.py")}
        exec(compile(src.split("from weasyprint import")[0], "paper/build.py", "exec"), ns)
        import weasyprint  # noqa: F401
    except (ImportError, OSError) as exc:
        pytest.skip(f"paper toolchain unavailable: {exc}")


_load_weasyprint()


def _check():
    spec = importlib.util.spec_from_file_location(
        "figure_render_check", _ROOT / "paper/figure_render_check.py"
    )
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _png_b64() -> str:
    from PIL import Image

    buf = io.BytesIO()
    Image.new("RGB", (40, 20), (180, 40, 60)).save(buf, format="PNG")
    return base64.b64encode(buf.getvalue()).decode()


def test_blank_and_drawn_figures_are_told_apart(tmp_path: Path) -> None:
    """The check passes a normal figure and flags the converted Figure 7 that
    shipped blank on 2026-10-18 (the fixture keeps its exact SVG structure, with
    the two screenshots swapped for tiny PNGs; it still renders blank)."""
    png = _png_b64()
    drawn = tmp_path / "drawn.svg"
    drawn.write_text(
        '<svg xmlns="http://www.w3.org/2000/svg" xmlns:xlink="http://www.w3.org/1999/xlink" '
        'width="400" height="200" viewBox="0 0 400 200">'
        f'<image x="0" y="0" width="400" height="200" xlink:href="data:image/png;base64,{png}"/></svg>'
    )
    broken = _ROOT / "tests/fixtures/paper/weasyprint_blank_figure.svg"
    blank = _check().blank_figures([drawn, broken])
    assert [p.name for p in blank] == [broken.name]
