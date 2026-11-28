"""Monotonic ratchet on source file length and core Python function length.

Prevents monolith drift across the Worker, Next.js viewer, Python library, and
scripts:

- No new source file under ``SCAN_ROOTS`` may exceed ``MAX_FILE_LINES`` (600).
- No new function under ``src/`` may exceed ``MAX_SRC_FUNCTION_LINES`` (150).
- Existing legacy files/functions recorded in
  ``tests/file_size_ratchet_baseline.json`` may shrink, never grow.
- Once a legacy file or function is refactored back within the limit (or
  removed), CI fails with a reminder to delete its stale baseline entry so the
  ratchet stays tight.

To tighten the baseline after refactoring (strictly monotonic — never raises a
cap), run::

    uv run python tests/test_file_size_ratchet.py --tighten
"""

from __future__ import annotations

import ast
import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
BASELINE_PATH = Path(__file__).resolve().with_name("file_size_ratchet_baseline.json")

SCAN_ROOTS = (
    "cloudflare/workers",
    "viewer/app",
    "viewer/components",
    "viewer/lib",
    "src",
    "scripts",
)
SOURCE_EXTS = frozenset({".py", ".js", ".mjs", ".ts", ".tsx"})
EXCLUDED_PARTS = frozenset({"tests", "node_modules", ".wrangler", ".next", "__pycache__"})

MAX_FILE_LINES = 600
MAX_SRC_FUNCTION_LINES = 150


def _iter_source_files() -> list[Path]:
    found: list[Path] = []
    for root_rel in SCAN_ROOTS:
        root_dir = REPO_ROOT / root_rel
        if not root_dir.is_dir():
            continue
        for path in sorted(root_dir.rglob("*")):
            if not path.is_file() or path.suffix not in SOURCE_EXTS:
                continue
            rel_parts = path.relative_to(REPO_ROOT).parts
            if any(part in EXCLUDED_PARTS for part in rel_parts):
                continue
            found.append(path)
    return found


def _measure_long_files() -> dict[str, int]:
    observed: dict[str, int] = {}
    for path in _iter_source_files():
        rel = path.relative_to(REPO_ROOT).as_posix()
        n_lines = len(path.read_text(encoding="utf-8").splitlines())
        if n_lines > MAX_FILE_LINES:
            observed[rel] = n_lines
    return observed


def _measure_long_src_functions() -> dict[str, int]:
    observed: dict[str, int] = {}
    for path in sorted((REPO_ROOT / "src").rglob("*.py")):
        rel_parts = path.relative_to(REPO_ROOT).parts
        if any(part in EXCLUDED_PARTS for part in rel_parts):
            continue
        rel = path.relative_to(REPO_ROOT).as_posix()
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=rel)
        for node in ast.walk(tree):
            if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                continue
            if node.end_lineno is None:
                continue
            length = node.end_lineno - node.lineno + 1
            if length > MAX_SRC_FUNCTION_LINES:
                key = f"{rel}:{node.name}"
                observed[key] = max(observed.get(key, 0), length)
    return observed


def _load_baseline() -> dict[str, object]:
    data = json.loads(BASELINE_PATH.read_text(encoding="utf-8"))
    assert isinstance(data, dict)
    return data


def test_file_length_ratchet() -> None:
    baseline = _load_baseline()
    assert baseline["max_file_lines"] == MAX_FILE_LINES
    budgets = baseline["files"]
    assert isinstance(budgets, dict)

    observed = _measure_long_files()
    failures: list[str] = []
    for rel, n_lines in sorted(observed.items()):
        cap = budgets.get(rel)
        if cap is None:
            failures.append(
                f"NEW oversized file {rel}: {n_lines}L (limit {MAX_FILE_LINES}L) — split into smaller modules"
            )
        elif n_lines > cap:
            failures.append(
                f"{rel} grew from {cap}L to {n_lines}L (ratchet cap {cap}L) — extract new code instead of appending"
            )

    stale = sorted(set(budgets) - set(observed))
    assert not failures, "File-size ratchet failed:\n  " + "\n  ".join(failures)
    assert not stale, (
        "Remove refactored/deleted files from tests/file_size_ratchet_baseline.json "
        "(run `uv run python tests/test_file_size_ratchet.py --tighten`):\n  " + "\n  ".join(stale)
    )


def test_src_function_length_ratchet() -> None:
    baseline = _load_baseline()
    assert baseline["max_src_function_lines"] == MAX_SRC_FUNCTION_LINES
    budgets = baseline["src_functions"]
    assert isinstance(budgets, dict)

    observed = _measure_long_src_functions()
    failures: list[str] = []
    for key, length in sorted(observed.items()):
        cap = budgets.get(key)
        if cap is None:
            failures.append(
                f"NEW long function {key}: {length}L (limit {MAX_SRC_FUNCTION_LINES}L) — decompose into helpers"
            )
        elif length > cap:
            failures.append(
                f"{key} grew from {cap}L to {length}L (ratchet cap {cap}L)"
            )

    stale = sorted(set(budgets) - set(observed))
    assert not failures, "src/ function-length ratchet failed:\n  " + "\n  ".join(failures)
    assert not stale, (
        "Remove refactored/deleted functions from tests/file_size_ratchet_baseline.json "
        "(run `uv run python tests/test_file_size_ratchet.py --tighten`):\n  " + "\n  ".join(stale)
    )


def _tighten_baseline() -> int:
    """Strictly tighten baseline caps down to current measurements (never raises a cap)."""
    baseline = _load_baseline()
    old_files = baseline["files"]
    old_funcs = baseline["src_functions"]
    assert isinstance(old_files, dict) and isinstance(old_funcs, dict)

    obs_files = _measure_long_files()
    obs_funcs = _measure_long_src_functions()

    new_files = {k: min(int(old_files[k]), obs_files[k]) for k in sorted(obs_files) if k in old_files}
    new_funcs = {k: min(int(old_funcs[k]), obs_funcs[k]) for k in sorted(obs_funcs) if k in old_funcs}

    updated = {
        "max_file_lines": MAX_FILE_LINES,
        "max_src_function_lines": MAX_SRC_FUNCTION_LINES,
        "files": new_files,
        "src_functions": new_funcs,
    }
    BASELINE_PATH.write_text(json.dumps(updated, indent=2) + "\n", encoding="utf-8")
    print(
        f"Tightened {BASELINE_PATH.name}: {len(old_files)} -> {len(new_files)} files, "
        f"{len(old_funcs)} -> {len(new_funcs)} src functions"
    )
    return 0


if __name__ == "__main__":
    if "--tighten" in sys.argv[1:]:
        raise SystemExit(_tighten_baseline())
    print("Usage: uv run python tests/test_file_size_ratchet.py --tighten", file=sys.stderr)
    raise SystemExit(2)
