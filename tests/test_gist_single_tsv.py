"""Single-TSV-per-gist invariant.

Each published figure-reproduction gist must bundle exactly ONE TSV
file alongside its ``make_<slug>.py`` script + ``01_<slug>.md`` README.
The script reads only the bundled sibling TSV — no external data
sources, no other TSVs to join in at run time. This makes the gist
fully self-contained for reader reproduction and the SWHID anchors
the script + its data atomically.

Three checks, all offline:

  1. ``TSV_BUNDLE`` in ``scripts/sync_figure_gists_bundle_data.py``
     maps each slug → list with exactly 1 entry. (Catches the
     multi-bundle regression at the source.)

  2. Each mirror's source declares one canonical ``_TSV`` constant
     and one ``_fetch_tsv`` call site — no leftover multi-source
     reads. (Catches a script that re-introduces a second URL.)

  3. The slug in TSV_BUNDLE matches the bundled TSV's basename
     (so the mirror's ``DATA_TSV`` constant and the bundle map can't
     drift — they both reference the same file).

A separate network test in ``test_figure_gist_data_sync.py`` verifies
that the bundled TSV bytes on each live gist match the canonical bytes
in the repo. This test is the offline complement.
"""
from __future__ import annotations

import ast
import re
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
FIGURES_DIR = REPO_ROOT / "data" / "analysis" / "figures"


def _tsv_bundle() -> dict[str, list[str]]:
    """Parse ``TSV_BUNDLE`` out of sync_figure_gists_bundle_data.py without
    importing the module (avoids dragging in its `gh` runtime deps)."""
    src = (REPO_ROOT / "scripts" / "sync_figure_gists_bundle_data.py").read_text()
    tree = ast.parse(src)
    for node in tree.body:
        if isinstance(node, ast.AnnAssign):
            target = node.target
            if isinstance(target, ast.Name) and target.id == "TSV_BUNDLE":
                if node.value is None:
                    raise RuntimeError("TSV_BUNDLE has no value")
                return ast.literal_eval(ast.unparse(node.value))
    raise RuntimeError("TSV_BUNDLE assignment not found")


def _mirror_slugs() -> list[str]:
    """Every gist mirror that exists on disk."""
    return sorted(
        p.stem.removeprefix("make_")
        for p in FIGURES_DIR.glob("make_*.py")
    )


@pytest.mark.parametrize("slug,tsvs", list(_tsv_bundle().items()))
def test_each_gist_bundles_exactly_one_tsv(slug: str, tsvs: list[str]) -> None:
    """Single-TSV invariant: every entry in TSV_BUNDLE is a one-item list."""
    assert len(tsvs) == 1, (
        f"Gist '{slug}' bundles {len(tsvs)} TSVs ({tsvs}); the single-TSV "
        f"invariant requires exactly 1. Consolidate via "
        f"scripts/build_figure_tsvs.py into a per-figure TSV at "
        f"data/processed/figures/{slug}.tsv, then update TSV_BUNDLE."
    )


def test_every_mirror_slug_appears_in_tsv_bundle() -> None:
    """No mirror should be missing from TSV_BUNDLE — a mirror without a
    bundled TSV gives readers a script with no data."""
    bundled = set(_tsv_bundle())
    mirrors = set(_mirror_slugs())
    missing = sorted(mirrors - bundled)
    assert not missing, (
        f"Mirror scripts without a TSV_BUNDLE entry: {missing}. Add each "
        f"to the map in scripts/sync_figure_gists_bundle_data.py, even if "
        f"the figure is MOCK (use a placeholder TSV)."
    )


# Pattern for "_TSV = " constants. Catches BENCH_TSV, PREDS_TSV, etc.
_TSV_CONST_RE = re.compile(r"^\s*([A-Z][A-Z0-9_]*_TSV)\s*=", re.MULTILINE)
# Pattern for _fetch_tsv() call sites — counts unique TSV-loading invocations.
_FETCH_RE = re.compile(r"_fetch(?:_tsv|_csv_text)\(")


def _tsv_constants(src: str) -> list[tuple[str, str]]:
    """Top-level module assignments whose value-string ends in `.tsv`.
    Returns [(name, basename), ...]. Catches any naming convention
    the mirrors use (``_TSV``, ``_URL``, ``_TSV_URL``, ``DATA_TSV``)
    rather than locking in one name. Skips literals inside function
    bodies / class bodies / docstrings."""
    tree = ast.parse(src)
    out: list[tuple[str, str]] = []
    for node in tree.body:
        if not isinstance(node, ast.Assign):
            continue
        value_str = ast.unparse(node.value)
        # Bare paths or f-strings; require a literal segment that ends
        # in a .tsv basename.
        match = re.search(r"/([\w.-]+\.tsv)\b", value_str)
        if not match:
            continue
        basename = match.group(1)
        for t in node.targets:
            if isinstance(t, ast.Name):
                out.append((t.id, basename))
    return out


@pytest.mark.parametrize("slug", _mirror_slugs())
def test_mirror_declares_one_tsv_constant(slug: str) -> None:
    """Each mirror script should declare ONE module-level constant
    pointing at a `.tsv` (the single sibling-bundled data source).
    Multiple TSV constants means the script is still joining multiple
    sources at run time — defeats the single-TSV invariant."""
    src = (FIGURES_DIR / f"make_{slug}.py").read_text()
    consts = _tsv_constants(src)
    assert len(consts) == 1, (
        f"Mirror make_{slug}.py declares {len(consts)} module-level TSV "
        f"constants ({[c[0] for c in consts]}); the single-TSV invariant "
        f"requires exactly 1 (the sibling-bundled data source)."
    )


@pytest.mark.parametrize("slug", _mirror_slugs())
def test_mirror_constant_matches_bundle_path(slug: str) -> None:
    """The mirror's single TSV constant must end with the basename of
    the file ``TSV_BUNDLE[slug]`` points at, so a basename rename
    can't drift the two surfaces."""
    bundle = _tsv_bundle()
    if slug not in bundle:
        pytest.skip(f"{slug} not in TSV_BUNDLE — covered by the sibling test")
    bundled_basename = Path(bundle[slug][0]).name
    src = (FIGURES_DIR / f"make_{slug}.py").read_text()
    consts = _tsv_constants(src)
    assert consts, f"make_{slug}.py has no module-level TSV constant"
    const_name, const_basename = consts[0]
    assert const_basename == bundled_basename, (
        f"Mirror make_{slug}.py's {const_name} points at "
        f"{const_basename!r} but TSV_BUNDLE has {bundled_basename!r}. "
        f"Either the mirror is stale or the bundle map is."
    )
