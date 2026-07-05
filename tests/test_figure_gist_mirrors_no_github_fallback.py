"""Drift guard: published-figure gist mirrors must NOT fall back to a
network fetch of the canonical TSV.

Why: each gist bundles its data TSVs alongside ``make_<slug>.py`` so
the gist's HEAD commit SHA is the SWHID for the whole reproduction
unit (script + data + README). If a mirror silently falls back to
``raw.githubusercontent.com`` when the sibling TSV is missing, the
gist can render against a *different* TSV than what it bundles —
breaking the citation guarantee.

Concrete drift scenarios this catches:

* New mirror copy-pasted from an older mirror that still had the
  ``httpx.get(url)`` fallback. The sibling-first read still works
  inside the published gist, so manual review wouldn't notice; the
  mirror only diverges from the bundled TSV if the local file is
  missing or stale and the GitHub copy has shifted forward.
* Refactor accidentally re-introduces ``urllib.request.urlopen`` or
  ``requests.get`` in a data-loading code path.

What we check:

* No ``make_<slug>.py`` imports ``httpx`` or ``requests``.
* No ``make_<slug>.py`` calls ``urllib.request.urlopen`` or
  ``urllib.request.urlretrieve``.
* The script-deps header (``# /// script`` PyPA inline metadata)
  doesn't declare ``httpx`` or ``requests`` as a dependency.

What we deliberately DON'T check:

* ``BASE = f"https://raw.githubusercontent.com/..."`` URL constants
  are fine — they're used to derive the basename for sibling lookup
  and the path-after-BASE for the in-repo dev-mode fallback. They're
  never actually fetched.
* String mentions of ``raw.githubusercontent.com`` in comments /
  docstrings are fine.
"""
from __future__ import annotations

import re
from pathlib import Path

import pytest

FIGURES_DIR = Path(__file__).resolve().parent.parent / "data" / "analysis" / "figures"

_NETWORK_IMPORT_RE = re.compile(
    r"^\s*(?:import\s+httpx|from\s+httpx\b|"
    r"import\s+requests|from\s+requests\b|"
    r"import\s+urllib\.request|from\s+urllib\.request\b)",
    re.MULTILINE,
)
_NETWORK_CALL_RE = re.compile(
    r"\b(?:httpx\.(?:get|post|stream|Client)\s*\(|"
    r"requests\.(?:get|post|head|Session)\s*\(|"
    r"urllib\.request\.(?:urlopen|urlretrieve)\s*\()",
)
_SCRIPT_DEP_HTTPX_RE = re.compile(
    r"^#\s*\"(?:httpx|requests)[<>=!]", re.MULTILINE,
)


def _mirrors() -> list[Path]:
    return sorted(FIGURES_DIR.glob("make_*.py"))


@pytest.mark.parametrize("path", _mirrors(), ids=lambda p: p.name)
def test_no_network_import(path: Path) -> None:
    """The mirror must not import a network-fetch library."""
    src = path.read_text()
    matches = [
        (i + 1, line.strip())
        for i, line in enumerate(src.splitlines())
        if _NETWORK_IMPORT_RE.match(line)
    ]
    assert not matches, (
        f"{path.name}: network-fetch imports found — figure gist mirrors "
        f"must read sibling-or-local TSV only, never the network. "
        f"Offending lines: {matches}"
    )


@pytest.mark.parametrize("path", _mirrors(), ids=lambda p: p.name)
def test_no_network_call(path: Path) -> None:
    """The mirror must not call a network-fetch function."""
    src = path.read_text()
    matches = [
        (i + 1, line.strip())
        for i, line in enumerate(src.splitlines())
        if _NETWORK_CALL_RE.search(line)
    ]
    assert not matches, (
        f"{path.name}: network-fetch calls found — figure gist mirrors "
        f"must read sibling-or-local TSV only, never the network. "
        f"Bundle the TSV via scripts/sync_figure_gists_bundle_data.py "
        f"instead. Offending lines: {matches}"
    )


@pytest.mark.parametrize("path", _mirrors(), ids=lambda p: p.name)
def test_no_network_dep_in_script_header(path: Path) -> None:
    """The PyPA inline script-deps header must not declare httpx / requests."""
    src = path.read_text()
    matches = [
        (i + 1, line.strip())
        for i, line in enumerate(src.splitlines())
        if _SCRIPT_DEP_HTTPX_RE.match(line)
    ]
    assert not matches, (
        f"{path.name}: httpx / requests still declared in `# /// script` "
        f"dependency header — drop the dep line (and the matching import). "
        f"Offending lines: {matches}"
    )
