#!/usr/bin/env bash
# Run the *.test.tsx render tests, plus the plain *.test.ts unit tests
# written with node:test, in one shot. The render tests mount
# components via ``react-dom/server.renderToStaticMarkup`` and assert on
# the rendered HTML; they need the CSS-module loader registered via
# tests/helpers/register.mjs so the ``.module.css`` imports resolve to
# proxied class-name objects instead of literal CSS source.
#
#   bash tests/run_render_tests.sh
#
# Uses ``npx --yes tsx`` (one-off; does not modify package.json /
# lockfile). Mirrors the convention of ``run_list_genes_tests.sh``.
set -euo pipefail
cd "$(dirname "$0")/.."

# Globbed, not listed. The list was hardcoded, so a newly added *.test.tsx was
# silently never run — the same way a test that does not exist passes. Sorted so
# the run order is deterministic.
# Plain glob rather than mapfile: macOS ships bash 3.2, where mapfile does not
# exist, and this script has to run the same locally and in CI. Glob expansion
# is already sorted.
tests=()
for f in tests/*.test.tsx; do
  [ -e "$f" ] || continue
  tests+=("$(basename "$f")")
done
# *.test.ts files are mixed: some are node:test suites, others are
# one-scenario-per-process scripts that need an argument and have their own
# runners (run_list_genes_tests.sh, run_surfaceome_record_degraded_tests.sh,
# ...). Take only the node:test ones, by what they import.
for f in tests/*.test.ts; do
  [ -e "$f" ] || continue
  grep -q 'from "node:test"' "$f" && tests+=("$(basename "$f")")
done

if [ "${#tests[@]}" -eq 0 ]; then
  echo "no tests found in tests/ — the glob is broken, not the suite"
  exit 1
fi

fails=0
for t in "${tests[@]}"; do
  echo "=== $t ==="
  if ! npx --yes tsx --import ./tests/helpers/register.mjs --test "tests/$t"; then
    fails=$((fails + 1))
  fi
done

echo "=== verdict ==="
if [ "$fails" -eq 0 ]; then
  echo "PASS (${#tests[@]} render tests, all passing)"
else
  echo "FAIL ($fails of ${#tests[@]} render tests failed)"
  exit 1
fi
