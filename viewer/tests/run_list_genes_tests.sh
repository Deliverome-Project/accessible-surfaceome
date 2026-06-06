#!/usr/bin/env bash
# Run every listSurfaceomeGenes() scenario, each in its own process so
# the module-level memo (_geneListPromise) starts fresh each time.
#
#   bash tests/run_list_genes_tests.sh
#
# Uses `npx --yes tsx` (one-off; does not modify package.json/lockfile).
set -euo pipefail
cd "$(dirname "$0")/.."

scenarios=(local happy retry5xx fail4xx entries entries-stale)
fails=0
for s in "${scenarios[@]}"; do
  if ! npx --yes tsx tests/list_surfaceome_genes.test.ts "$s"; then
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
