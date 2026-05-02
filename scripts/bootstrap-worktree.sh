#!/usr/bin/env bash
set -euo pipefail

usage() {
  cat <<'EOF'
usage: scripts/bootstrap-worktree.sh [none|candidate|all|<data-include-pattern>]

Bootstrap an agent-created worktree with local env wiring and optional data
hydration. The mode argument is intentionally data-backend neutral so this
script can later switch from Git LFS to DVC/R2 without changing agent prompts.

Modes:
  none       Symlink .env only; do not hydrate data. Default.
  candidate  Hydrate candidate-universe artifacts only.
  all        Hydrate all data artifacts.
  <pattern>  Hydrate a custom data include pattern.
EOF
}

mode="${1:-none}"

if [[ "${mode}" == "-h" || "${mode}" == "--help" ]]; then
  usage
  exit 0
fi

repo_root="$(git rev-parse --show-toplevel)"
cd "$repo_root"

env_source="${ACCESSIBLE_SURFACEOME_ENV_SOURCE:-}"
if [[ -z "$env_source" ]]; then
  current_dir="$(pwd -P)"
  env_source="${current_dir}/.env"

  while parent="$(dirname "$current_dir")" && [[ "$parent" != "$current_dir" ]]; do
    candidate="${parent}/accessible-surfaceome/.env"
    if [[ -f "$candidate" ]]; then
      env_source="$candidate"
      break
    fi
    current_dir="$parent"
  done
fi

if [[ -f "$env_source" ]]; then
  env_target="${repo_root}/.env"
  if [[ -e "$env_target" && ! -L "$env_target" ]]; then
    echo "[bootstrap-worktree] .env exists and is not a symlink; leaving it unchanged." >&2
  elif [[ ! -e "$env_target" ]]; then
    ln -s "$env_source" "$env_target"
    echo "[bootstrap-worktree] linked .env -> $env_source"
  fi
else
  echo "[bootstrap-worktree] no .env source found; set ACCESSIBLE_SURFACEOME_ENV_SOURCE if needed." >&2
fi

hydrate_lfs() {
  local include_pattern="$1"
  git lfs pull --include="$include_pattern"
}

case "$mode" in
  none)
    echo "[bootstrap-worktree] data hydration skipped."
    ;;
  candidate)
    hydrate_lfs "data/processed/candidate_universe/**"
    ;;
  all)
    git lfs pull
    git lfs fsck
    ;;
  *)
    hydrate_lfs "$mode"
    ;;
esac
