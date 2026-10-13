#!/usr/bin/env bash
# Run the build-fetch pacing/retry hardening tests (node:test, plain
# Node ESM — no CSS-loader / TSX needed since these files import only
# scripts/lib/build-fetch.mjs and the two build-*.mjs scripts).
#
#   bash tests/run_build_fetch_tests.sh
#
# NOTE: build_data_snapshot_early_abort.test.mjs spawns the real script as
# a child process against a local mock HTTP server and lets its REAL
# (un-overridden) retry backoff run, so this whole run takes ~15-20s
# rather than the sub-second time of the other files — that one test is
# intentionally an exact integration pin of the I1 early-abort wiring,
# not just the pure predicate (which build_fetch.test.mjs already covers
# instantly with an injected clock).
set -euo pipefail
cd "$(dirname "$0")/.."

files=(
  tests/build_fetch.test.mjs
  tests/build_data_snapshot_fetch.test.mjs
  tests/build_data_snapshot_early_abort.test.mjs
  tests/build_markdown_exports_driver.test.mjs
  tests/build_markdown_exports_genes_filter.test.mjs
)

node --test "${files[@]}"
