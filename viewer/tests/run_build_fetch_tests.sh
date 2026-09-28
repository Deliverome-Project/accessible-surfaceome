#!/usr/bin/env bash
# Run the build-fetch pacing/retry hardening tests (node:test, plain
# Node ESM — no CSS-loader / TSX needed since these files import only
# scripts/lib/build-fetch.mjs and the two build-*.mjs scripts).
#
#   bash tests/run_build_fetch_tests.sh
set -euo pipefail
cd "$(dirname "$0")/.."

files=(
  tests/build_fetch.test.mjs
  tests/build_data_snapshot_fetch.test.mjs
  tests/build_markdown_exports_driver.test.mjs
  tests/build_markdown_exports_genes_filter.test.mjs
)

node --test "${files[@]}"
