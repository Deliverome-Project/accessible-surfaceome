"""Drift guard: ``data/analysis/figures/gist_map.json`` ↔ each
``make_<slug>.py``'s ``GIST_URL`` constant.

Why: every published-figure mirror under ``data/analysis/figures/``
declares its own ``GIST_URL = "https://gist.github.com/<owner>/<id>"``
constant (embedded into the PNG ``Source`` tEXt chunk + PDF
``Subject`` field — see ``_plotting_config.save_figure``). The registry
at ``gist_map.json`` is meant to mirror that same set of IDs so
``embed_figure_gist_metadata.py`` and similar tooling can look up the
URL for a slug without grepping every mirror.

These two surfaces drift the moment someone adds a new figure and
forgets to register it. ``topology_coverage_by_source`` rode that
exact failure mode: its mirror had the URL embedded for months while
the registry sat at 9 entries (now 11). This test pins both halves of
the contract so the same gap can't reopen.

Failure modes covered:

  • Mirror declares ``GIST_URL`` but slug missing from gist_map.json
    → add to the registry, OR drop the GIST_URL declaration if the
    figure isn't gist-published.
  • gist_map.json carries a slug with no matching ``make_<slug>.py``
    → orphan entry; remove from the registry, OR add the mirror.
  • Slug present in both but gist IDs disagree → typically a
    re-published-as-new-gist mistake; reconcile to the URL the gist
    actually serves (verify with ``gh gist view <id>``).
"""
from __future__ import annotations

import json
import re
from pathlib import Path

import pytest

FIGURES_DIR = Path(__file__).resolve().parent.parent / "data" / "analysis" / "figures"
MAP_PATH = FIGURES_DIR / "gist_map.json"

_GIST_URL_RE = re.compile(
    r'^GIST_URL\s*=\s*["\']https://gist\.github\.com/[^/]+/([0-9a-f]+)["\']',
    re.MULTILINE,
)


def _gist_id_from_mirror(mirror_path: Path) -> str | None:
    """Extract the gist ID from a mirror's ``GIST_URL`` constant.

    Returns ``None`` when the mirror doesn't declare one (some
    not-yet-published figures may legitimately ship without a gist;
    those are exempt from the registry until they're published).
    """
    m = _GIST_URL_RE.search(mirror_path.read_text())
    return m.group(1) if m else None


def _load_registry() -> dict[str, str]:
    if not MAP_PATH.is_file():
        pytest.fail(f"gist_map.json missing at {MAP_PATH}")
    return json.loads(MAP_PATH.read_text())


def _mirror_slugs_with_gist() -> dict[str, str]:
    """Walk every ``make_*.py`` and return ``{slug: gist_id}`` for the
    ones that declare a ``GIST_URL``."""
    if not FIGURES_DIR.is_dir():
        pytest.skip(f"{FIGURES_DIR} not in this checkout")
    out: dict[str, str] = {}
    for mirror in sorted(FIGURES_DIR.glob("make_*.py")):
        slug = mirror.stem.removeprefix("make_")
        gid = _gist_id_from_mirror(mirror)
        if gid is not None:
            out[slug] = gid
    return out


def test_every_mirror_with_gist_url_is_registered() -> None:
    """If a mirror declares ``GIST_URL``, that slug + ID must be in the
    registry. Catches the ``topology_coverage_by_source`` failure mode
    where the URL was on the figure but never registered."""
    registry = _load_registry()
    mirrors = _mirror_slugs_with_gist()
    missing: list[str] = []
    mismatched: list[str] = []
    for slug, gid in sorted(mirrors.items()):
        if slug not in registry:
            missing.append(f"  {slug}: declared GIST_URL={gid!r} in "
                           f"make_{slug}.py but slug absent from gist_map.json")
        elif registry[slug] != gid:
            mismatched.append(
                f"  {slug}: make_{slug}.py declares {gid!r} but "
                f"gist_map.json carries {registry[slug]!r}"
            )

    msgs = missing + mismatched
    assert not msgs, (
        "Drift between gist_map.json and the per-mirror GIST_URL constants:\n"
        + "\n".join(msgs)
        + "\n\nFix: add the missing entry to "
        "data/analysis/figures/gist_map.json (or correct the divergent ID). "
        "Verify the gist actually exists with `gh gist view <id>`."
    )


def test_every_registry_entry_has_a_mirror() -> None:
    """Reverse direction: every slug in ``gist_map.json`` must have a
    matching ``make_<slug>.py`` whose ``GIST_URL`` agrees. Catches
    orphan registry entries from deleted/renamed figures."""
    registry = _load_registry()
    mirrors = _mirror_slugs_with_gist()
    orphans: list[str] = []
    for slug, gid in sorted(registry.items()):
        if slug not in mirrors:
            mirror_path = FIGURES_DIR / f"make_{slug}.py"
            if not mirror_path.is_file():
                orphans.append(
                    f"  {slug}: registered with gist={gid!r} but "
                    f"no make_{slug}.py exists"
                )
            else:
                orphans.append(
                    f"  {slug}: registered with gist={gid!r} but "
                    f"make_{slug}.py declares no GIST_URL"
                )

    assert not orphans, (
        "Orphan entries in gist_map.json with no backing mirror:\n"
        + "\n".join(orphans)
        + "\n\nFix: either drop the orphan from gist_map.json, or add "
        "the missing make_<slug>.py / GIST_URL declaration."
    )
