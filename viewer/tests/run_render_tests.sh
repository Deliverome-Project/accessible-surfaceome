#!/usr/bin/env bash
# Run the *.test.tsx render tests in one shot. These tests mount
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

tests=(
  biological_context_card_rationale.test.tsx
  accessibility_risks_card_rationale.test.tsx
  biological_context_card_sort.test.tsx
  chip_jump_button.test.tsx
  filters_card_chip_jump.test.tsx
  surface_evidence_card_chip_jump.test.tsx
)

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
