#!/usr/bin/env bash
# Thin wrapper — invokes the uv-managed Python build chain. The real
# work lives in paper/build.py, which uses `pypandoc-binary` (bundles
# the pandoc binary inside the wheel) + `weasyprint` (pure-Python).
# Both are installed via:
#
#     uv sync --extra paper
#
# Usage:
#
#     bash paper/build.sh path/to/manuscript.docx
#
# Outputs land in <docx-dir>/build/<stem>.{pdf,html,xml}. The PDF is
# what you feed into the manuscript bundle's `pdf_path` in
# scripts/release/publish-archive.py.
set -euo pipefail

if [[ ${#@} -lt 1 ]]; then
  echo "usage: bash $0 <path/to/manuscript.docx>" >&2
  exit 64
fi

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

# uv resolves the venv from the nearest pyproject.toml — running from
# the repo root keeps the lockfile-locked deps from this project.
exec uv --project "$REPO_ROOT" run --extra paper python "$SCRIPT_DIR/build.py" "$@"
