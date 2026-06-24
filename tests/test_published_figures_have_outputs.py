"""Co-location guard: every published-figure standalone mirror has
its rendered PDF + PNG sitting next to it.

Convention (CLAUDE.md "Final-Figure Gist Convention" section): for
every gist-mirrored figure script under
``data/analysis/figures/make_<slug>.py``, the rendered PDF and PNG
outputs of that figure live in the same folder as
``data/analysis/figures/<slug>.{pdf,png}``. The rendered outputs are
what the Zenodo deposit + the reader-facing figure folder serve;
keeping them co-located with the standalone mirror means a reader
who clones the gist can grep the repo for the same slug and find the
already-rendered figure without re-running anything.

Without this guard, figure outputs drift into per-analysis subdirs
(``data/analysis/<some-area>/<slug>.pdf``) instead of the canonical
figure folder — happened once with ``topology_coverage_by_source``,
which originally rendered into ``data/analysis/db_vs_sonnet_inclusion/``
before being relocated.
"""
from __future__ import annotations

from pathlib import Path

import pytest

FIGURES_DIR = Path(__file__).resolve().parent.parent / "data" / "analysis" / "figures"


def _gist_slugs() -> list[str]:
    """Return every ``<slug>`` for which ``make_<slug>.py`` exists in
    the published-figures folder."""
    if not FIGURES_DIR.is_dir():
        pytest.skip(f"{FIGURES_DIR} not present in this checkout")
    return sorted(
        path.stem.removeprefix("make_")
        for path in FIGURES_DIR.glob("make_*.py")
    )


@pytest.mark.parametrize("slug", _gist_slugs())
def test_published_figure_has_pdf_output(slug: str) -> None:
    """Every ``make_<slug>.py`` must have a matching ``<slug>.pdf``
    in the same folder."""
    pdf = FIGURES_DIR / f"{slug}.pdf"
    assert pdf.is_file(), (
        f"Missing rendered PDF for published figure {slug!r}. "
        f"Convention: render the canonical generator and commit the "
        f"PDF to {pdf} so the figure folder + the published gist + the "
        f"Zenodo deposit all reference the same artifact. See the "
        f"'Final-Figure Gist Convention' section in CLAUDE.md."
    )


@pytest.mark.parametrize("slug", _gist_slugs())
def test_published_figure_has_png_output(slug: str) -> None:
    """Every ``make_<slug>.py`` must have a matching ``<slug>.png``
    in the same folder."""
    png = FIGURES_DIR / f"{slug}.png"
    assert png.is_file(), (
        f"Missing rendered PNG for published figure {slug!r}. "
        f"Convention: render the canonical generator and commit the "
        f"PNG to {png} so the figure folder + the published gist + the "
        f"Zenodo deposit all reference the same artifact. See the "
        f"'Final-Figure Gist Convention' section in CLAUDE.md."
    )


@pytest.mark.parametrize("slug", _gist_slugs())
def test_published_figure_has_gist_readme(slug: str) -> None:
    """Every ``make_<slug>.py`` must have a matching ``01_<slug>.md``
    README in the same folder — the README is the gist's top file
    (alphabetical prefix forces it first) and explains how to run
    the script."""
    readme = FIGURES_DIR / f"01_{slug}.md"
    assert readme.is_file(), (
        f"Missing 01_{slug}.md gist README for published figure "
        f"{slug!r}. Convention: every gist has 2 files — the "
        f"01_<slug>.md README and make_<slug>.py script. Both must "
        f"sit in {FIGURES_DIR} alongside the rendered PDF/PNG."
    )
