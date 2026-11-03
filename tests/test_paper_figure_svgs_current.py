"""Guard: the paper build's vector figures exist and are not older than their source.

``paper/figure_manifest.json`` points most figures at an SVG in
``paper/figures/``, converted from the canonical render with
``pdftocairo -svg data/analysis/figures/<slug>.pdf paper/figures/<slug>.svg``.
The conversion is a manual step, and two things went wrong with it on
2026-10-12:

* Supp S16's SVG had never been made, so the build silently kept the .docx's
  bitmap for it.
* S2, S4 and S15 were re-rendered after their SVGs were made, so the PDF and
  web editions shipped the old figures. The build's .docx comparison did not
  flag them because the .docx carried the same old versions.

Re-convert with the command above whenever a canonical PDF changes.
"""

from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
MANIFEST = ROOT / "paper/figure_manifest.json"
SEARCH = [ROOT / "paper/figures", ROOT / "data/analysis/figures"]


def _entries() -> list[dict]:
    m = json.loads(MANIFEST.read_text())
    return [
        e
        for key in ("figures", "appendix_figures", "supplementary_figures")
        for e in (m.get(key) or {}).values()
    ]


def _commit_time(path: Path) -> int | None:
    out = subprocess.run(
        ["git", "log", "-1", "--format=%ct", "--", str(path.relative_to(ROOT))],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    ).stdout.strip()
    return int(out) if out else None


def test_every_manifest_figure_has_its_asset() -> None:
    missing = [
        f"{e['slug']}.{e['format']}"
        for e in _entries()
        if not any((d / f"{e['slug']}.{e['format']}").is_file() for d in SEARCH)
    ]
    assert not missing, f"figure_manifest.json assets not found in paper/ or data/analysis/figures/: {missing}"


@pytest.mark.skipif(shutil.which("git") is None, reason="needs git")
def test_converted_svgs_are_not_older_than_their_pdf() -> None:
    stale = []
    for e in _entries():
        svg = ROOT / "paper/figures" / f"{e['slug']}.svg"
        pdf = ROOT / "data/analysis/figures" / f"{e['slug']}.pdf"
        if e["format"] != "svg" or not svg.is_file() or not pdf.is_file():
            continue
        s, p = _commit_time(svg), _commit_time(pdf)
        if s is not None and p is not None and p > s:
            stale.append(e["slug"])
    assert not stale, (
        "paper/figures SVGs committed before their canonical PDF was last changed; "
        f"re-run pdftocairo -svg for: {stale}"
    )
