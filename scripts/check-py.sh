#!/usr/bin/env bash
set -euo pipefail

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$repo_root"

if ! command -v uv >/dev/null 2>&1; then
  echo "[check-py] uv is required but not installed." >&2
  exit 1
fi

uv run --frozen ruff check src tests main.py
uv run --frozen python -m compileall -q src main.py
uv run --frozen pytest -q
