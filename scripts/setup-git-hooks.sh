#!/usr/bin/env bash
set -euo pipefail

if [[ "${1:-}" == "-h" || "${1:-}" == "--help" ]]; then
  cat <<'USAGE'
Usage: scripts/setup-git-hooks.sh

Points this clone at the tracked hooks: sets core.hooksPath to .githooks
and makes each hook executable. Takes no options.
USAGE
  exit 0
fi

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
git -C "$repo_root" config core.hooksPath .githooks

for hook in "$repo_root/.githooks/"*; do
  if [[ -f "$hook" ]]; then
    chmod +x "$hook"
  fi
done

echo "Configured git hooks path to .githooks"
