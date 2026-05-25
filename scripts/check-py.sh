#!/usr/bin/env bash
set -euo pipefail

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$repo_root"

if ! command -v uv >/dev/null 2>&1; then
  echo "[check-py] uv is required but not installed." >&2
  exit 1
fi

uv run --frozen ruff check src tests
uv run --frozen ty check
uv run --frozen python -m compileall -q src
uv run --frozen pytest -q

# Schema-sync tripwire: every Pydantic field reachable from
# SurfaceomeRecord must have a TS counterpart in viewer/lib/
# surfaceome-types.ts, otherwise the viewer silently drops the
# data. Pydantic is the source of truth — see the script's
# module docstring for the full intent + the per-class skip lists.
uv run --frozen python scripts/check_viewer_types_sync.py
