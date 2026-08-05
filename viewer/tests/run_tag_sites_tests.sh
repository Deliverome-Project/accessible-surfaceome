#!/usr/bin/env bash
# Run the tagged-sites foundation logic tests, each in its own process.
# These are lib-level unit tests (data contracts, junction/compartment
# derivation, static-JSON loaders, seed fixtures) — not render tests, so
# they run standalone like tests/surface_bind_ec_sites.test.ts rather than
# through tests/run_render_tests.sh.
#
#   bash tests/run_tag_sites_tests.sh
#
# Uses `npx --yes tsx` (one-off; does not modify package.json/lockfile).
set -euo pipefail
cd "$(dirname "$0")/.."

tests=(
  tag_sites_types.test.ts
  tag_sites_derive.test.ts
  tag_sites_loader.test.ts
  tag_sites_fixture.test.ts
  tag_sites_colors.test.ts
  tag_sites_overlay.test.ts
  tag_sites_client.test.ts
  internalization_client.test.ts
)

fails=0
for t in "${tests[@]}"; do
  echo "=== $t ==="
  if ! npx --yes tsx "tests/$t"; then
    fails=$((fails + 1))
  fi
done

echo "=== verdict ==="
if [ "$fails" -eq 0 ]; then
  echo "PASS (all ${#tests[@]} tag-sites foundation tests)"
else
  echo "FAIL ($fails of ${#tests[@]} tag-sites tests failed)"
  exit 1
fi
