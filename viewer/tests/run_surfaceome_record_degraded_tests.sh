#!/usr/bin/env bash
# Run every surfaceome_record_degraded.test.ts scenario, each in its own
# process (module-level fetch stub + import must start fresh each time).
#
#   bash tests/run_surfaceome_record_degraded_tests.sh
#
# Uses `npx --yes tsx` (one-off; does not modify package.json/lockfile).
# Mirrors run_list_genes_tests.sh's convention.
set -euo pipefail
cd "$(dirname "$0")/.."

scenarios=(degraded-then-healthy persistent-degraded retry-after)
fails=0
for s in "${scenarios[@]}"; do
  if ! npx --yes tsx tests/surfaceome_record_degraded.test.ts "$s"; then
    fails=$((fails + 1))
  fi
done

echo "=== verdict ==="
if [ "$fails" -eq 0 ]; then
  echo "PASS (all ${#scenarios[@]} scenarios)"
else
  echo "FAIL ($fails of ${#scenarios[@]} scenarios)"
  exit 1
fi
