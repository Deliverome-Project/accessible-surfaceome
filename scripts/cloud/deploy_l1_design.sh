#!/usr/bin/env bash
# Deploy the L1 design overlay + review page backend to PRODUCTION, in order.
#
# Dry-run by default: prints every command and runs only the read-only checks.
# Pass --execute to write. Run from a clean checkout of freshly fetched origin/main
# that contains the L1 Worker changes, with the real cloudflare/workers/surfaceome_api/
# wrangler.toml (copied from the canonical checkout; it is gitignored).
#
#   bash scripts/cloud/deploy_l1_design.sh --data-dir DIR [--redacted] [--skip-r2] [--execute]
#
# DIR is the loader's --data-dir: it holds l1_design_load.sql (full provenance) and
# l1_design_load.redacted.sql (--redacted: provenance columns withheld on the public API).
#
# What it does (each step is additive and re-runnable):
#   1. shared-API checks from CLAUDE.md: HEAD == origin/main for the Worker source,
#      no route that exists only on origin/dev, Worker contract tests;
#   2. public D1: CREATE TABLE IF NOT EXISTS for the L1 tables;
#   3. public D1: the load (INSERT OR IGNORE; the load row last);
#   4. private D1 (surfaceome_agents): the review tables;
#   5. R2: tagged-refold PDBs under library-colabfold-tagged/<release>/ (existing keys skipped);
#   6. the L1_REVIEW_TOKEN secret, if it is not set yet (prompts for the value);
#   7. wrangler deploy, then a read-back of /v1/l1-design.
#
# Requested by Becca Carlson (2026-11-11/12); written by Claude Code session
# l1-viewer-tag-sites, which is not permitted to write production itself.
set -euo pipefail

DATA_DIR=""; REDACTED=0; SKIP_R2=0; EXECUTE=0
TAGGED_S3="s3://deliverome-processed/sprint4/s4e9-orf-design-fg-panel/predicted-structures/tagged/2026-11-12/"
TAGGED_RELEASE="2026-11-12"
while [ $# -gt 0 ]; do
  case "$1" in
    --data-dir) DATA_DIR="$2"; shift 2 ;;
    --redacted) REDACTED=1; shift ;;
    --skip-r2) SKIP_R2=1; shift ;;
    --execute) EXECUTE=1; shift ;;
    *) echo "unknown argument: $1" >&2; exit 2 ;;
  esac
done
[ -n "$DATA_DIR" ] || { echo "--data-dir is required" >&2; exit 2; }
LOAD="$DATA_DIR/l1_design_load.sql"; [ "$REDACTED" = 1 ] && LOAD="$DATA_DIR/l1_design_load.redacted.sql"
[ -f "$LOAD" ] || { echo "missing $LOAD (run build_l1_design_tables.py build + sql)" >&2; exit 2; }

ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
WORKER_DIR="$ROOT/cloudflare/workers/surfaceome_api"
WRANGLER="npx --yes wrangler"
run() {
  echo "+ $*"
  if [ "$EXECUTE" = 1 ]; then (cd "$WORKER_DIR" && eval "$@"); fi
}

echo "== 1. shared-API checks (read-only)"
[ -f "$WORKER_DIR/wrangler.toml" ] || { echo "no $WORKER_DIR/wrangler.toml; copy it from the canonical checkout" >&2; exit 1; }
git -C "$ROOT" fetch -q origin
if ! git -C "$ROOT" diff --quiet origin/main -- cloudflare/workers/surfaceome_api/src; then
  echo "HEAD's Worker source differs from origin/main: deploy from main (CLAUDE.md shared-API rule)" >&2; exit 1
fi
routes() { git -C "$ROOT" show "$1:cloudflare/workers/surfaceome_api/src/index.js" | grep -oE 'path\.match\(/[^)]*\)|path === "[^"]*"' | sort -u; }
DEV_ONLY="$(comm -13 <(routes origin/main) <(routes origin/dev) || true)"
if [ -n "$DEV_ONLY" ]; then echo "routes only on origin/dev; port them first:" >&2; echo "$DEV_ONLY" >&2; exit 1; fi
(cd "$ROOT" && REQUIRE_WORKER_NODE=1 uv run pytest -q tests/test_worker_*.py tests/test_l1_design.py)
echo "load: $(head -1 "$LOAD")"

echo "== 2-3. public D1: L1 tables + the load"
run "$WRANGLER d1 execute surfaceome_public --remote --file '$ROOT/cloudflare/migrations/l1_design_v1.sql'"
run "$WRANGLER d1 execute surfaceome_public --remote --file '$LOAD'"

echo "== 4. private D1: review tables"
run "$WRANGLER d1 execute surfaceome_agents --remote --file '$ROOT/cloudflare/migrations/l1_review_v1.sql'"

echo "== 5. R2: tagged-refold coordinates"
if [ "$SKIP_R2" = 0 ]; then
  TMP="$(mktemp -d)"
  run "aws s3 sync '$TAGGED_S3' '$TMP/' --exclude '*' --include '*.pdb' --only-show-errors"
  run "(cd '$ROOT' && uv run python scripts/cloud/ingest_library_structures_to_r2.py --from-dir '$TMP' --release $TAGGED_RELEASE --prefix library-colabfold-tagged)"
fi

echo "== 6. review token secret"
if (cd "$WORKER_DIR" && $WRANGLER secret list 2>/dev/null | grep -q L1_REVIEW_TOKEN); then
  echo "L1_REVIEW_TOKEN already set"
else
  run "$WRANGLER secret put L1_REVIEW_TOKEN"
fi

echo "== 7. Worker deploy + read-back"
run "$WRANGLER deploy"
if [ "$EXECUTE" = 1 ]; then
  curl -s https://api.deliverome.org/surfaceome/v1/l1-design | python3 -c \
    "import json,sys; d=json.load(sys.stdin); print('served load', (d.get('load') or {}).get('load_version'), len(d.get('members', [])), 'members')"
else
  echo "dry run: nothing written. Re-run with --execute."
fi
