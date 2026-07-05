"""Guard: ``data/analysis/figures/by_paper_number/`` symlinks match FIGURE_ORDER.

The ``by_paper_number/`` folder holds paper-numbered symlinks
(``figure_NN_<slug>`` / ``suppfig_NN_<slug>``) into the canonical figures, so the
manuscript can cite a stable numbered name that always points at the current
render. It is **hand-maintained** (no generator script), so it drifted silently
once: S12 (``deep_dive_vs_sonnet_benchmark``) was added to
``scripts/build_figure_index.py::FIGURE_ORDER`` but its symlink was never
created, leaving the folder stale through S13. This test pins the folder to
FIGURE_ORDER so that gap can't reopen — the same drift-guard treatment the
canonical↔mirror and gist checks get.
"""
from __future__ import annotations

import ast
import re

import pytest

from accessible_surfaceome.paths import REPO_ROOT

BYNUM = REPO_ROOT / "data/analysis/figures/by_paper_number"
FIGURES = REPO_ROOT / "data/analysis/figures"
INDEX = REPO_ROOT / "scripts/build_figure_index.py"


def _figure_order() -> list[tuple[str, str]]:
    """Parse ``FIGURE_ORDER`` out of build_figure_index.py without importing it
    (avoids dragging in the script's runtime deps)."""
    tree = ast.parse(INDEX.read_text())
    for node in tree.body:
        if isinstance(node, ast.AnnAssign):
            target, value = node.target, node.value
        elif isinstance(node, ast.Assign) and node.targets:
            target, value = node.targets[0], node.value
        else:
            continue
        if (
            isinstance(target, ast.Name)
            and target.id == "FIGURE_ORDER"
            and value is not None
        ):
            return ast.literal_eval(ast.unparse(value))
    raise RuntimeError("FIGURE_ORDER not found in scripts/build_figure_index.py")


def _prefix(label: str) -> str:
    """``"Figure 3" -> "figure_03"``, ``"Supp S12" -> "suppfig_12"``."""
    m = re.fullmatch(r"Figure (\d+)", label)
    if m:
        return f"figure_{int(m.group(1)):02d}"
    m = re.fullmatch(r"Supp S(\d+)", label)
    if m:
        return f"suppfig_{int(m.group(1)):02d}"
    raise AssertionError(f"unrecognized FIGURE_ORDER label: {label!r}")


def _exts(slug: str) -> list[str]:
    """SVG mockups ship a single ``.svg``; every other figure ships ``.pdf`` + ``.png``."""
    return ["svg"] if (FIGURES / f"{slug}.svg").is_file() else ["pdf", "png"]


def _expected_names() -> set[str]:
    out: set[str] = set()
    for label, slug in _figure_order():
        prefix = _prefix(label)
        for ext in _exts(slug):
            out.add(f"{prefix}_{slug}.{ext}")
    return out


@pytest.mark.parametrize("label,slug", _figure_order())
def test_paper_number_symlink_resolves(label: str, slug: str) -> None:
    """Every FIGURE_ORDER entry has a ``by_paper_number/`` symlink that resolves
    to the canonical ``../<slug>.<ext>``."""
    prefix = _prefix(label)
    for ext in _exts(slug):
        link = BYNUM / f"{prefix}_{slug}.{ext}"
        assert link.is_symlink(), (
            f"{label} = {slug}: missing symlink {link.name} in by_paper_number/. "
            f"Create it:  ln -s ../{slug}.{ext} {link.name}"
        )
        resolved = link.resolve()
        assert resolved.is_file() and resolved.name == f"{slug}.{ext}", (
            f"{link.name} -> {link.readlink()} does not resolve to ../{slug}.{ext}"
        )


def test_no_stale_or_missing_paper_number_symlinks() -> None:
    """``by_paper_number/`` contains EXACTLY the FIGURE_ORDER set — no stale
    entries (from renamed/renumbered figures) and none missing."""
    if not BYNUM.is_dir():
        pytest.skip(f"{BYNUM} not in this checkout")
    expected = _expected_names()
    actual = {p.name for p in BYNUM.iterdir() if not p.name.startswith(".")}
    stale = sorted(actual - expected)
    missing = sorted(expected - actual)
    assert not stale and not missing, (
        "by_paper_number/ out of sync with scripts/build_figure_index.py::FIGURE_ORDER:\n"
        f"  stale (remove):  {stale}\n"
        f"  missing (add):   {missing}\n"
        "The symlinks are hand-maintained — update them to match FIGURE_ORDER."
    )
