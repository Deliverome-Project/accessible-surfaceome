"""Drift guard: canonical figure generator (``scripts/<slug>.py``) vs
gist mirror (``data/analysis/figures/make_<slug>.py``).

Every published figure has two source files by convention:

  • ``scripts/<slug>.py`` — canonical generator, uses the project's
    ``_plotting_config`` import (centralized styling), reads from
    in-repo TSVs / D1.
  • ``data/analysis/figures/make_<slug>.py`` — standalone gist mirror,
    PyPA inline script metadata + inline brand styling, reads from raw.githubusercontent.

Historically font-cap / layout-bump commits touched only the gist
mirror (the author edited the gist + synced the mirror file via
``gh gist edit``) — the canonical generator silently fell behind so
re-running it produced the OLD layout. The two files that this guard
caught regressions on:

  • ``zero_db_rescues_by_triage.py`` — subpanel a/b labels +
    figsize/height_ratios/hspace bumps stayed mirror-only
  • ``db_vs_sonnet_whole_proteome.py`` — figsize, label sizes (8/11
    inline → 14/20 cap), ylabel wrap, ``fig.tight_layout()``

This test compares a **layout fingerprint** extracted by regex from
both files and fails when they diverge. Fingerprint covers the
visual-output knobs that drift most often:

  • ``figsize=(W, H)``
  • ``axes.labelsize``, ``xtick.labelsize``, ``ytick.labelsize``,
    ``legend.fontsize`` rcParams overrides
  • ``set_ylabel`` newline (``\\n``) — wraps-or-not is intentional
  • ``fig.tight_layout()`` presence

When the test fails, the fix is to update both files in the same
commit per the convention in CLAUDE.md "Canonical generator vs gist
mirror".
"""
from __future__ import annotations

import re
from pathlib import Path

import pytest

from accessible_surfaceome.paths import REPO_ROOT

SCRIPTS_DIR = REPO_ROOT / "scripts"
FIGURES_SCRIPTS_DIR = REPO_ROOT / "scripts" / "figures"
MIRROR_DIR = REPO_ROOT / "data/analysis/figures"

# Slug → both files. A "pair" is a slug that has BOTH
# ``scripts/figures/<slug>.py`` (canonical generator) AND
# ``data/analysis/figures/make_<slug>.py`` (gist mirror).
# Mirror-only figures (where the canonical generator lives inside a
# multi-figure script, e.g. ``triage_bench_db_barplot.py``)
# are out of scope for the per-file drift guard — they need a different
# treatment.


def _canonical_slug_map() -> dict[str, Path]:
    """Map slug → canonical generator path, searching scripts/figures/ first
    then scripts/ (for top-level entry points that double as figure scripts)."""
    slugs: dict[str, Path] = {}
    for p in SCRIPTS_DIR.glob("*.py"):
        slugs[p.stem] = p
    # figures/ takes priority — canonical generators live here after the
    # scripts/build|figures|audit|… reorganisation
    for p in FIGURES_SCRIPTS_DIR.glob("*.py"):
        slugs[p.stem] = p
    return slugs


def _list_pairs() -> list[str]:
    if not SCRIPTS_DIR.exists() or not MIRROR_DIR.exists():
        return []
    canonical_slugs = set(_canonical_slug_map())
    mirror_slugs = {
        p.stem.removeprefix("make_")
        for p in MIRROR_DIR.glob("make_*.py")
    }
    return sorted(canonical_slugs & mirror_slugs)


def _extract_layout_fingerprint(path: Path) -> dict[str, str | None]:
    """Pull the layout knobs that drift most often from a figure file.

    Returns ``None`` for any knob the file doesn't set explicitly — a
    missing value matches across files. Raises ``FileNotFoundError`` if
    the file doesn't exist.
    """
    text = path.read_text()
    fp: dict[str, str | None] = {}

    # figsize=(W, H) — the first match in the file. Normalize whitespace
    # so figsize=(19, 13) and figsize=( 19 , 13 ) compare equal.
    m = re.search(r"figsize\s*=\s*\(\s*([\d.]+)\s*,\s*([\d.]+)\s*\)", text)
    fp["figsize"] = f"({m.group(1)}, {m.group(2)})" if m else None

    # rcParams overrides — typed as either dict-key strings or
    # `plt.rcParams[...] = ...` lines. Both forms collapse to one
    # int per knob (the LAST occurrence wins, matching matplotlib's
    # later-call-wins semantics).
    for knob in ("axes.labelsize", "xtick.labelsize",
                 "ytick.labelsize", "legend.fontsize",
                 "axes.titlesize", "font.size"):
        # Two patterns: "axes.labelsize": 20  OR  rcParams['axes.labelsize'] = 20
        pat = rf'["\']{re.escape(knob)}["\']\s*:\s*([\d.]+)'
        ms = re.findall(pat, text)
        if not ms:
            pat2 = rf'rcParams\s*\[\s*["\']{re.escape(knob)}["\']\s*\]\s*=\s*([\d.]+)'
            ms = re.findall(pat2, text)
        fp[knob] = ms[-1] if ms else None

    # Y-label wrap. Wrapping a long y-label is a project convention
    # (figure_ylabel_wrap memory). Drift here means one side wraps and
    # the other doesn't, so the rendered label visibly differs.
    m = re.search(r"set_ylabel\s*\(\s*(['\"])((?:[^'\"\\]|\\.)+?)\1", text)
    fp["ylabel_wraps"] = "yes" if (m and r"\n" in m.group(2)) else (
        "no" if m else None
    )

    # ``fig.tight_layout()`` presence — toggles whether matplotlib's
    # automatic margin compaction runs.
    fp["tight_layout"] = "yes" if re.search(r"\.tight_layout\s*\(", text) else "no"

    return fp


@pytest.mark.parametrize("slug", _list_pairs() or ["<no-pairs>"])
def test_figure_canonical_mirror_layout_in_sync(slug: str) -> None:
    """The canonical generator and the gist mirror must agree on the
    layout fingerprint. See CLAUDE.md "Canonical generator vs gist
    mirror" for the rule."""
    if slug == "<no-pairs>":
        pytest.skip("no scripts/figures/<slug>.py ↔ data/analysis/figures/make_<slug>.py "
                    "pairs found (partial checkout?)")
    slug_map = _canonical_slug_map()
    canonical = slug_map[slug]
    mirror = MIRROR_DIR / f"make_{slug}.py"
    assert canonical.exists() and mirror.exists()

    fp_canonical = _extract_layout_fingerprint(canonical)
    fp_mirror = _extract_layout_fingerprint(mirror)

    diffs: list[str] = []
    for knob in sorted(set(fp_canonical) | set(fp_mirror)):
        a = fp_canonical.get(knob)
        b = fp_mirror.get(knob)
        if a != b:
            diffs.append(f"  {knob:24s} canonical={a!r:>12s}  mirror={b!r}")

    assert not diffs, (
        f"Figure layout drift between canonical generator and gist mirror "
        f"for slug={slug!r}:\n  {canonical.relative_to(REPO_ROOT)}  ↔  "
        f"data/analysis/figures/make_{slug}.py\n" + "\n".join(diffs)
        + "\n\nFix: per CLAUDE.md \"Canonical generator vs gist mirror\", "
        "edit both files in the same commit, then regenerate the figure "
        f"with `uv run python {canonical.relative_to(REPO_ROOT)}`."
    )
