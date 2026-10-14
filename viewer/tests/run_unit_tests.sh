#!/usr/bin/env bash
# Run the *.test.ts unit tests in one shot — the pure-function suites
# (structure projection, SURFACE-Bind EC sites, antibody links, text
# scrubbing). Companion to run_render_tests.sh, which covers *.test.tsx.
#
#   bash tests/run_unit_tests.sh
#
# These were never gated in CI, the same gap the render tests had before
# PR #275's note: a test nobody runs passes exactly like a test that does
# not exist. The MS4A1 8VGN off-by-37 projection bug is the case that
# made it matter.
#
# Uses `npx --yes tsx` (one-off; does not modify package.json/lockfile).
set -euo pipefail
cd "$(dirname "$0")/.."

# Globbed, not listed, so a newly added *.test.ts is never silently
# skipped. Plain glob rather than mapfile: macOS ships bash 3.2.
# Two are excluded on purpose: they take a scenario name on argv and
# already have their own runners (run_list_genes_tests.sh and
# run_surfaceome_record_degraded_tests.sh, the latter gated in CI).
# Running them bare just reports "unknown scenario".
scenario_driven="list_surfaceome_genes.test.ts surfaceome_record_degraded.test.ts"
tests=()
for f in tests/*.test.ts; do
  [ -e "$f" ] || continue
  base="$(basename "$f")"
  case " $scenario_driven " in *" $base "*) continue ;; esac
  tests+=("$base")
done

if [ "${#tests[@]}" -eq 0 ]; then
  echo "no *.test.ts found in tests/ — the glob is broken, not the suite"
  exit 1
fi

fails=0
for t in "${tests[@]}"; do
  echo "=== $t ==="
  if ! npx --yes tsx "tests/$t"; then
    fails=$((fails + 1))
  fi
done

echo "=== verdict ==="
if [ "$fails" -eq 0 ]; then
  echo "PASS (${#tests[@]} unit tests, all passing)"
else
  echo "FAIL ($fails of ${#tests[@]} unit tests failed)"
  exit 1
fi
