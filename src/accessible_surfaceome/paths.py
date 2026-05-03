"""Single source of truth for repository paths.

Everything else under ``src/accessible_surfaceome/`` derives data locations from
the constants here. Computing ``Path(__file__).resolve().parents[N]`` in
each script is brittle: a file moves up or down the tree and silently
points at the wrong directory.
"""

from __future__ import annotations

from pathlib import Path

# ``src/accessible_surfaceome/paths.py`` -> repo root is parents[2].
REPO_ROOT = Path(__file__).resolve().parents[2]

DATA_DIR = REPO_ROOT / "data"
DATA_RAW_DIR = DATA_DIR / "raw"
DATA_EXTERNAL_DIR = DATA_DIR / "external"
DATA_PROCESSED_DIR = DATA_DIR / "processed"
DATA_ANALYSIS_DIR = DATA_DIR / "analysis"


def relative_to_repo(path: Path) -> str:
    """POSIX-style path relative to the repo root, with absolute fallback."""
    try:
        return path.resolve().relative_to(REPO_ROOT.resolve()).as_posix()
    except ValueError:
        return path.resolve().as_posix()
