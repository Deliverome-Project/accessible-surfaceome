#!/usr/bin/env bash
# Sync in-repo figure mirrors to their GitHub gists.
#
# Usage:
#   bash scripts/sync_figure_gists.sh              # sync all
#   bash scripts/sync_figure_gists.sh zero_db_rescues_by_triage  # sync one
#
# Reads the slug→gist-ID map from data/analysis/figures/gist_map.json.
# Each gist has two files: 01_<slug>.md (README) and make_<slug>.py.
#
# Requires: gh (GitHub CLI, authenticated with gist scope), jq

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
FIGURES_DIR="$REPO_ROOT/data/analysis/figures"
GIST_MAP="$FIGURES_DIR/gist_map.json"

if ! command -v gh &>/dev/null; then
  echo "error: gh CLI not found" >&2; exit 1
fi
if ! command -v jq &>/dev/null; then
  echo "error: jq not found" >&2; exit 1
fi
if [[ ! -f "$GIST_MAP" ]]; then
  echo "error: gist map not found at $GIST_MAP" >&2; exit 1
fi

slugs=()
if [[ $# -gt 0 ]]; then
  slugs=("$@")
else
  while IFS= read -r slug; do
    slugs+=("$slug")
  done < <(jq -r 'keys[]' "$GIST_MAP")
fi

synced=0
failed=0

for slug in "${slugs[@]}"; do
  gist_id=$(jq -r --arg s "$slug" '.[$s] // empty' "$GIST_MAP")
  if [[ -z "$gist_id" ]]; then
    echo "SKIP  $slug — not in gist_map.json" >&2
    continue
  fi

  readme="$FIGURES_DIR/01_${slug}.md"
  script="$FIGURES_DIR/make_${slug}.py"

  if [[ ! -f "$readme" ]]; then
    echo "SKIP  $slug — $readme not found" >&2
    continue
  fi
  if [[ ! -f "$script" ]]; then
    echo "SKIP  $slug — $script not found" >&2
    continue
  fi

  readme_name="01_${slug}.md"
  script_name="make_${slug}.py"

  # Build the JSON payload with both files' content
  payload=$(jq -n \
    --arg rn "$readme_name" \
    --rawfile rc "$readme" \
    --arg sn "$script_name" \
    --rawfile sc "$script" \
    '{files: {($rn): {content: $rc}, ($sn): {content: $sc}}}')

  if gh api --method PATCH "gists/$gist_id" --input - <<< "$payload" >/dev/null 2>&1; then
    echo "OK    $slug → $gist_id"
    ((synced++))
  else
    echo "FAIL  $slug → $gist_id" >&2
    ((failed++))
  fi
done

echo ""
echo "Done: $synced synced, $failed failed (of ${#slugs[@]} total)"
[[ $failed -eq 0 ]]
