#!/usr/bin/env bash
set -euo pipefail

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
git -C "$repo_root" config core.hooksPath .githooks

for hook in "$repo_root/.githooks/"*; do
  if [[ -f "$hook" ]]; then
    chmod +x "$hook"
  fi
done

echo "Configured git hooks path to .githooks"
