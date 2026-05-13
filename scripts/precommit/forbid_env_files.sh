#!/usr/bin/env bash
# Block any `.env` (or `.env.<suffix>` other than `.env.example`) from
# being committed. `.env` is already in .gitignore, but `git add -f`
# or a different working directory can still slip one past — this hook
# gives a loud named error so the credential never lands.
#
# pre-commit invokes this with the matched files as arguments.
set -euo pipefail

if [ "$#" -eq 0 ]; then
  exit 0
fi

printf '\n\e[31mERROR: Refusing to commit credential-bearing file(s):\e[0m\n' >&2
for f in "$@"; do
  printf '  %s\n' "$f" >&2
done
printf '\n' >&2
printf '  .env files hold secrets and must NEVER be committed.\n' >&2
printf '  • If this is a real .env, leave it gitignored.\n' >&2
printf '  • If this is a template, name it `.env.example` (allowlisted).\n' >&2
printf '  • If you genuinely need to ship a non-secret env file, edit\n' >&2
printf '    scripts/precommit/forbid_env_files.sh to allowlist its name.\n\n' >&2

exit 1
