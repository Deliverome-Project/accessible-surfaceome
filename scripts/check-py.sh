#!/usr/bin/env bash
set -euo pipefail

if [[ "${1:-}" == "-h" || "${1:-}" == "--help" ]]; then
  cat <<'USAGE'
Usage: scripts/check-py.sh

Runs everything CI runs, in order:
  ruff check src tests scripts   lint
  ty check                       type check
  compileall src                 syntax check
  pytest -q                      the test suite
  check_viewer_types_sync.py     viewer TS interfaces vs Pydantic models

Takes no options. Requires uv.
USAGE
  exit 0
fi

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$repo_root"

if ! command -v uv >/dev/null 2>&1; then
  echo "[check-py] uv is required but not installed." >&2
  exit 1
fi

# Match the pre-commit ruff scope (everything but data/) so the local gate
# can't pass while CI's pre-commit hook fails on a scripts/ lint error.
uv run --frozen ruff check src tests scripts
uv run --frozen ty check
uv run --frozen python -m compileall -q src
uv run --frozen pytest -q

# Schema-sync tripwire: every Pydantic field reachable from
# SurfaceomeRecord must have a TS counterpart in viewer/lib/
# surfaceome-types.ts, otherwise the viewer silently drops the
# data. Pydantic is the source of truth — see the script's
# module docstring for the full intent + the per-class skip lists.
uv run --frozen python scripts/check_viewer_types_sync.py
