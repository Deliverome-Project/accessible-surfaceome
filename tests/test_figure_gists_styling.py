"""Enforce that every ``data/analysis/figures/make_*.py`` gist applies the
brand styling.

The gists are mirrors of the canonical figure generators that ship with
``raw.githubusercontent.com`` URLs for Substack readers to run
standalone (``uv run make_<slug>.py``). Because they can't import the
in-repo ``_plotting_config`` module, the styling has to be **inlined**.
Without enforcement this drifts the moment someone hand-writes a gist
without copying the canonical block — that's how the
``db_correctness_by_class`` gist landed with off-brand colors initially.

The contract enforced here:

* Each gist contains the sentinel comment ``brand-style-v1`` (marks the
  inlined block — bump version when the canonical block changes).
* Each defines and **calls** ``_apply_brand_style()`` plus
  ``_register_brand_fonts()``.
* Each declares ``BRAND_PALETTE`` with the six anchor colors from
  ``src/accessible_surfaceome/audit/_plotting_config.py``.
* Each pulls Manrope into the ``font.sans-serif`` rcParam.
* Each saves PNG at ``dpi=600`` (bumped from 300 on 2026-06-24).
* Each calls ``sns.despine`` (belt-and-suspenders with the rcParam
  spines-off, matches the canonical generator's habit).
* No gist contains any of the legacy off-brand hex codes that ``ty``-passed
  but produced wrong-color figures pre-fix.
"""
from __future__ import annotations

import re
from pathlib import Path

import pytest

GISTS_DIR = Path(__file__).resolve().parents[1] / "data/analysis/figures"

# Brand palette anchors (mirror of CATEGORICAL_PALETTE in
# src/accessible_surfaceome/audit/_plotting_config.py).
BRAND_PALETTE_ANCHORS = (
    "#BC3C4C",  # maroon-light
    "#3D6B60",  # teal-mid
    "#F4AA28",  # amber-bright
    "#8878C8",  # lavender-bright
    "#6E1428",  # maroon-dark
)

# Legacy off-brand hex codes that produced the wrong-looking pre-fix
# figures. If any of these reappear in a gist as a bar/scatter/line
# color, the test catches it. (Listed as raw strings — substring match.)
LEGACY_BAD_COLORS = (
    "#5C7AE6",  # legacy "UniProt blue" — should be #BC3C4C
    "#6FB867",  # legacy "GO green"     — should be #3D6B60
    "#A35BC0",  # legacy "SURFY purple" — should be #8878C8
    "#7C8085",  # legacy "CSPA gray"    — should be #6E1428
    "#E6A23C",  # legacy "HPA orange"   — should be #F4AA28
)


def _gist_files() -> list[Path]:
    return sorted(GISTS_DIR.glob("make_*.py"))


def test_gists_dir_exists():
    assert GISTS_DIR.is_dir(), f"{GISTS_DIR} not found"
    assert _gist_files(), f"No make_*.py gists found under {GISTS_DIR}"


@pytest.mark.parametrize("gist", _gist_files(), ids=lambda p: p.name)
def test_gist_has_brand_style_sentinel(gist: Path):
    text = gist.read_text()
    # Accept any versioned sentinel (brand-style-v1, brand-style-v2, ...).
    # v2 added the static-Manrope OTFs + medium weight + ~25% size bump
    # on 2026-06-07 to fix the variable-font ExtraLight default.
    assert re.search(r"brand-style-v\d+", text), (
        f"{gist.name}: missing `brand-style-v<n>` sentinel — gists must include the "
        f"inlined brand-style block from the canonical _plotting_config.py mirror."
    )


@pytest.mark.parametrize("gist", _gist_files(), ids=lambda p: p.name)
def test_gist_defines_and_calls_apply_brand_style(gist: Path):
    text = gist.read_text()
    assert "def _apply_brand_style(" in text, (
        f"{gist.name}: missing `def _apply_brand_style(...)` — every gist must define "
        f"this helper to mirror src/accessible_surfaceome/audit/_plotting_config.py::setup_plotting_style."
    )
    # Must also CALL it (not just define). Strip the def line so the
    # check finds a real invocation, not the declaration.
    invocations = re.findall(r"(?<!def )\b_apply_brand_style\(\)", text)
    assert invocations, (
        f"{gist.name}: defines `_apply_brand_style()` but never calls it — "
        f"add `_apply_brand_style()` near the top of main()."
    )


@pytest.mark.parametrize("gist", _gist_files(), ids=lambda p: p.name)
def test_gist_registers_brand_fonts(gist: Path):
    text = gist.read_text()
    assert "def _register_brand_fonts(" in text, (
        f"{gist.name}: missing `_register_brand_fonts()` — needed so Manrope "
        f"actually resolves when running inside a repo checkout (rcParam alone "
        f"only sets the lookup priority; matplotlib needs the .ttf registered "
        f"with fontManager.addfont)."
    )
    # The fontManager.addfont call must be present (proves the function
    # does what its name says).
    assert "fontManager.addfont" in text, (
        f"{gist.name}: _register_brand_fonts() does not call "
        f"`fm.fontManager.addfont(...)` — that's the load-bearing step."
    )


@pytest.mark.parametrize("gist", _gist_files(), ids=lambda p: p.name)
def test_gist_declares_brand_palette(gist: Path):
    text = gist.read_text()
    for anchor in BRAND_PALETTE_ANCHORS:
        assert anchor in text, (
            f"{gist.name}: missing brand palette anchor color {anchor!r}. "
            f"Every gist must declare BRAND_PALETTE with the six anchors "
            f"from src/accessible_surfaceome/audit/_plotting_config.py::CATEGORICAL_PALETTE."
        )


@pytest.mark.parametrize("gist", _gist_files(), ids=lambda p: p.name)
def test_gist_lists_manrope_in_font_sans_serif(gist: Path):
    text = gist.read_text()
    assert '"Manrope"' in text, (
        f"{gist.name}: Manrope is not listed in font.sans-serif. Add it as "
        f"the first preference so figures match the rest of the project visual identity."
    )


@pytest.mark.parametrize("gist", _gist_files(), ids=lambda p: p.name)
def test_gist_saves_at_600_dpi(gist: Path):
    text = gist.read_text()
    # Allow `dpi=600` as a kwarg OR `"savefig.dpi": 600` in the rcParam
    # update; either yields a 600 DPI PNG. Bumped from 300 → 600 on
    # 2026-06-24 so figures stay sharp at print scale + retina zoom in
    # the published PDF (PNGs rasterize at this DPI; PDF stays vector
    # so DPI is moot there).
    has_dpi_600 = "dpi=600" in text or '"savefig.dpi": 600' in text
    assert has_dpi_600, (
        f"{gist.name}: figures must be saved at 600 DPI. "
        f"Set `dpi=600` on the `fig.savefig(...)` PNG call (PDF is vector so DPI is moot there)."
    )


@pytest.mark.parametrize("gist", _gist_files(), ids=lambda p: p.name)
def test_gist_calls_sns_despine(gist: Path):
    text = gist.read_text()
    assert "sns.despine" in text, (
        f"{gist.name}: must call `sns.despine(...)` on each axes after creation. "
        f"The brand rcParams turn top/right spines off, but the canonical generator "
        f"always despines explicitly as belt-and-suspenders — keep parity."
    )


@pytest.mark.parametrize("gist", _gist_files(), ids=lambda p: p.name)
def test_gist_embeds_gist_url_metadata(gist: Path):
    """Every gist must declare a `GIST_URL = "https://gist.github.com/..."`
    constant and pass it into `fig.savefig(..., metadata={"Source": GIST_URL})`
    (PNG) / `metadata={"Subject": GIST_URL}` (PDF). Mirrors the
    save_figure(gist_url=...) helper in
    src/accessible_surfaceome/audit/_plotting_config.py — the URL then
    travels in the PNG's Source tEXt chunk + PDF's Subject info field so
    a figure dragged into Substack / Slack / email still tells you where
    it came from. Read back with `exiftool figure.png | grep Source`."""
    text = gist.read_text()
    assert re.search(
        r'GIST_URL\s*=\s*["\']https://gist\.github\.com/', text
    ), (
        f"{gist.name}: missing `GIST_URL = \"https://gist.github.com/...\"` "
        f"constant. Add the published reproduction-gist URL so the figure "
        f"carries its source URL in PNG/PDF metadata."
    )
    assert 'metadata={"Source": GIST_URL}' in text or "metadata={'Source': GIST_URL}" in text, (
        f"{gist.name}: PNG `fig.savefig(...)` does not pass "
        f"`metadata={{'Source': GIST_URL}}`. Without this, the embedded "
        f"PNG `Source` tEXt chunk is missing."
    )
    assert 'metadata={"Subject": GIST_URL}' in text or "metadata={'Subject': GIST_URL}" in text, (
        f"{gist.name}: PDF `fig.savefig(...)` does not pass "
        f"`metadata={{'Subject': GIST_URL}}`. Without this, the embedded "
        f"PDF `Subject` info field is missing."
    )


@pytest.mark.parametrize("gist", _gist_files(), ids=lambda p: p.name)
def test_gist_has_no_legacy_bad_colors(gist: Path):
    text = gist.read_text()
    bad = [c for c in LEGACY_BAD_COLORS if c in text]
    assert not bad, (
        f"{gist.name}: legacy off-brand hex codes found: {bad}. "
        f"Replace with the BRAND_PALETTE / BRAND_SEQUENTIAL anchors from "
        f"src/accessible_surfaceome/audit/_plotting_config.py."
    )
