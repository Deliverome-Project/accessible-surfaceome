#!/usr/bin/env bash
# Deploy the L1 design overlay + review page backend to PRODUCTION, in order.
#
# Dry-run by default: prints every command and runs only the read-only checks.
# Pass --execute to write. Run from a clean checkout of freshly fetched origin/main
# that contains the L1 Worker changes, with the real cloudflare/workers/surfaceome_api/
# wrangler.toml (copied from the canonical checkout; it is gitignored).
#
#   bash scripts/cloud/deploy_l1_design.sh --data-dir DIR [--redacted] [--skip-r2]
#                                          [--tagged-s3 URI] [--tagged-release TAG]
#                                          [--skip-token] [--execute]
#   (--base REF replaces origin/main in the checks, for a dry run before merge only)
#
# DIR is the loader's --data-dir: it holds l1_design_load.sql (full provenance) and
# l1_design_load.redacted.sql (--redacted: provenance columns withheld on the public API).
#
# What it does (each step is additive and re-runnable):
#   1. shared-API checks from CLAUDE.md: HEAD == origin/main for the Worker source,
#      no route that exists only on origin/dev, Worker contract tests;
#   2. public D1: CREATE TABLE IF NOT EXISTS for the L1 tables (incl. member annotations);
#   3. public D1: the load (INSERT OR IGNORE; the load row last);
#   4. private D1 (surfaceome_agents): the review tables + additive v2 migrations;
#   5. R2: tagged-refold PDBs under library-colabfold-tagged/<release>/ (existing keys skipped);
#   6. the L1_INVITE_TOKENS / L1_REVIEW_TOKEN secret check (prompts only if neither is set);
#   7. wrangler deploy, then a read-back of /v1/l1-design.
#
# Requested by Becca Carlson (2026-11-11/12); written by Claude Code session
# l1-viewer-tag-sites, which is not permitted to write production itself.
set -euo pipefail

DATA_DIR=""; REDACTED=0; SKIP_R2=0; SKIP_TOKEN=0; EXECUTE=0; BASE="origin/main"
TAGGED_S3="s3://deliverome-processed/sprint4/s4e9-orf-design-fg-panel/predicted-structures/tagged/2026-11-12/"
TAGGED_RELEASE="2026-11-12"
TMP=""
cleanup() {
  if [ -n "$TMP" ] && [ -d "$TMP" ]; then
    rm -rf "$TMP"
  fi
}
trap cleanup EXIT

while [ $# -gt 0 ]; do
  case "$1" in
    --data-dir) DATA_DIR="$2"; shift 2 ;;
    --redacted) REDACTED=1; shift ;;
    --skip-r2) SKIP_R2=1; shift ;;
    --tagged-s3) TAGGED_S3="$2"; shift 2 ;;
    --tagged-release) TAGGED_RELEASE="$2"; shift 2 ;;
    # Step 6 prompts for a production secret. An agent session must not invent or type
    # one, so it deploys with --skip-token and leaves the value to a person; the read
    # routes (/v1/l1-design) serve without it, only review writes stay closed.
    --skip-token) SKIP_TOKEN=1; shift ;;
    --execute) EXECUTE=1; shift ;;
    --base) BASE="$2"; shift 2 ;;  # dry-run testing only; a real deploy uses origin/main
    *) echo "unknown argument: $1" >&2; exit 2 ;;
  esac
done
[ -n "$DATA_DIR" ] || { echo "--data-dir is required" >&2; exit 2; }
LOAD="$DATA_DIR/l1_design_load.sql"; [ "$REDACTED" = 1 ] && LOAD="$DATA_DIR/l1_design_load.redacted.sql"
[ -f "$LOAD" ] || { echo "missing $LOAD (run build_l1_design_tables.py build + sql)" >&2; exit 2; }

ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
WORKER_DIR="$ROOT/cloudflare/workers/surfaceome_api"
WRANGLER=(npx --yes wrangler)

print_cmd() {
  printf '+'
  printf ' %q' "$@"
  printf '\n'
}

run_worker() {
  print_cmd "$@"
  if [ "$EXECUTE" = 1 ]; then
    (cd "$WORKER_DIR" && "$@")
  fi
}

run_root() {
  print_cmd "$@"
  if [ "$EXECUTE" = 1 ]; then
    (cd "$ROOT" && "$@")
  fi
}

# SQLite ALTER TABLE ADD COLUMN fails with "duplicate column name" when re-run;
# tolerate that exact message so the deploy script remains additive and re-runnable.
run_worker_alter() {
  print_cmd "$@"
  if [ "$EXECUTE" = 1 ]; then
    local out="" status=0
    out="$(cd "$WORKER_DIR" && "$@" 2>&1)" || status=$?
    if [ "$status" -ne 0 ]; then
      if printf '%s\n' "$out" | grep -qi "duplicate column name"; then
        echo "  (already applied — duplicate column name ignored)"
      else
        printf '%s\n' "$out" >&2
        return "$status"
      fi
    elif [ -n "$out" ]; then
      printf '%s\n' "$out"
    fi
  fi
}

echo "== 1. shared-API checks (read-only)"
[ -f "$WORKER_DIR/wrangler.toml" ] || { echo "no $WORKER_DIR/wrangler.toml; copy it from the canonical checkout" >&2; exit 1; }
git -C "$ROOT" fetch -q origin
if [ "$EXECUTE" = 1 ] && [ "$BASE" != "origin/main" ]; then echo "--execute requires --base origin/main" >&2; exit 2; fi
if ! git -C "$ROOT" diff --quiet "$BASE" -- cloudflare/workers/surfaceome_api/src; then
  echo "HEAD's Worker source differs from origin/main: deploy from main (CLAUDE.md shared-API rule)" >&2; exit 1
fi
routes() { git -C "$ROOT" show "$1:cloudflare/workers/surfaceome_api/src/index.js" | grep -oE 'path\.match\(/[^)]*\)|path === "[^"]*"' | sort -u; }
DEV_ONLY="$(comm -13 <(routes "$BASE") <(routes origin/dev) || true)"
if [ -n "$DEV_ONLY" ]; then echo "routes only on origin/dev; port them first:" >&2; echo "$DEV_ONLY" >&2; exit 1; fi
(cd "$ROOT" && REQUIRE_WORKER_NODE=1 uv run pytest -q tests/test_worker_*.py tests/test_l1_design.py)
echo "load: $(head -1 "$LOAD")"

echo "== 2-3. public D1: L1 tables + the load"
run_worker "${WRANGLER[@]}" d1 execute surfaceome_public --remote --file "$ROOT/cloudflare/migrations/l1_design_v1.sql"
run_worker "${WRANGLER[@]}" d1 execute surfaceome_public --remote --file "$ROOT/cloudflare/migrations/l1_member_annotation_v1.sql"
run_worker "${WRANGLER[@]}" d1 execute surfaceome_public --remote --file "$ROOT/cloudflare/migrations/l1_member_annotation_v2_sp_metrics.sql"
run_worker "${WRANGLER[@]}" d1 execute surfaceome_public --remote --file "$LOAD"

echo "== 4. private D1: review tables"
run_worker "${WRANGLER[@]}" d1 execute surfaceome_agents --remote --file "$ROOT/cloudflare/migrations/l1_review_v1.sql"
run_worker_alter "${WRANGLER[@]}" d1 execute surfaceome_agents --remote --file "$ROOT/cloudflare/migrations/l1_review_v2.sql"
run_worker_alter "${WRANGLER[@]}" d1 execute surfaceome_agents --remote --file "$ROOT/cloudflare/migrations/l1_review_v2_site_sig.sql"

echo "== 5. R2: tagged-refold coordinates"
if [ "$SKIP_R2" = 0 ]; then
  TMP="$(mktemp -d)"
  run_root aws s3 sync "$TAGGED_S3" "$TMP/" --exclude '*' --include '*.pdb' --only-show-errors
  run_root uv run python scripts/cloud/ingest_library_structures_to_r2.py --from-dir "$TMP" --release "$TAGGED_RELEASE" --prefix library-colabfold-tagged
fi

echo "== 6. review token secret"
SECRETS_OUT="$(cd "$WORKER_DIR" && "${WRANGLER[@]}" secret list 2>/dev/null || true)"
if printf '%s\n' "$SECRETS_OUT" | grep -qE 'L1_INVITE_TOKENS|L1_REVIEW_TOKEN'; then
  echo "L1 review write token secret already set"
elif [ "$SKIP_TOKEN" = 1 ]; then
  echo "Neither L1_INVITE_TOKENS nor L1_REVIEW_TOKEN set, skipped (--skip-token): /v1/l1-design reads work;"
  echo "  review writes return an error until a person runs, in $WORKER_DIR:"
  echo "    npx wrangler secret put L1_INVITE_TOKENS"
else
  run_worker "${WRANGLER[@]}" secret put L1_INVITE_TOKENS
fi

echo "== 7. Worker deploy + read-back"
run_worker "${WRANGLER[@]}" deploy
if [ "$EXECUTE" = 1 ]; then
  curl -s https://api.deliverome.org/surfaceome/v1/l1-design | python3 -c \
    "import json,sys; d=json.load(sys.stdin); print('served load', (d.get('load') or {}).get('load_version'), len(d.get('members', [])), 'members')"
else
  echo "dry run: nothing written. Re-run with --execute."
fi
