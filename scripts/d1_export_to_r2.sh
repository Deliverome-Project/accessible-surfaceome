#!/usr/bin/env bash
# Export the Cloudflare D1 `deliverome_agent_runs` database to a SQL file
# and upload it to the R2 bucket `deliverome-d1-backups`.
#
# This is the CI-driven offsite backup layer (layer 2.5 in the
# disaster-recovery taxonomy): SQL dumps live in R2 with cross-region
# durability, automatically versioned by timestamped object key.
#
# REQUIREMENTS
#   * wrangler installed via `npm ci` at the repo root (pins the version
#     in package.json). Available under node_modules/.bin and via
#     `npx wrangler` — this script calls `npx --yes wrangler ...` so the
#     pinned version always wins over any globally installed wrangler.
#     Authenticate via `wrangler login` or by setting CLOUDFLARE_API_TOKEN
#     + CLOUDFLARE_ACCOUNT_ID in the shell.
#   * R2 bucket `deliverome-d1-backups` must exist
#       npx --yes wrangler r2 bucket create deliverome-d1-backups
#   * D1 database `deliverome_agent_runs` must exist
#
# USAGE
#   bash scripts/d1_export_to_r2.sh
#   bash scripts/d1_export_to_r2.sh --keep-local   # also retain local copy
#
# CI USAGE
#   See .github/workflows/d1-backup.yml — runs on push/PR that touches
#   the D1 schema, eval data, or uploaders. Auth via the CLOUDFLARE_*
#   secrets in repo settings.

set -euo pipefail

DB_NAME="deliverome_agent_runs"
BUCKET="deliverome-d1-backups"
KEEP_LOCAL=0
if [[ "${1:-}" == "--keep-local" ]]; then KEEP_LOCAL=1; fi

TIMESTAMP="$(date -u +%Y%m%dT%H%M%SZ)"
TMPDIR="$(mktemp -d)"
trap 'if [[ $KEEP_LOCAL -eq 0 ]]; then rm -rf "$TMPDIR"; fi' EXIT
SQL_FILE="$TMPDIR/${DB_NAME}_${TIMESTAMP}.sql"

echo "==> Exporting D1 $DB_NAME → $SQL_FILE"
npx --yes wrangler d1 export "$DB_NAME" \
    --remote \
    --output="$SQL_FILE"

BYTES=$(wc -c < "$SQL_FILE" | tr -d ' ')
SHA="$(shasum -a 256 "$SQL_FILE" | awk '{print $1}')"
echo "    $BYTES bytes  sha256=$SHA"

# R2 object layout:
#   d1-backups/<DB_NAME>/<YYYY>/<MM>/<DB_NAME>_<UTC-timestamp>.sql
#   d1-backups/<DB_NAME>/latest.sql           (also pushed to a stable key)
YEAR="${TIMESTAMP:0:4}"
MONTH="${TIMESTAMP:4:2}"
DATED_KEY="d1-backups/${DB_NAME}/${YEAR}/${MONTH}/${DB_NAME}_${TIMESTAMP}.sql"
LATEST_KEY="d1-backups/${DB_NAME}/latest.sql"

echo "==> Uploading to R2: $BUCKET/$DATED_KEY"
npx --yes wrangler r2 object put "$BUCKET/$DATED_KEY" \
    --file="$SQL_FILE" \
    --content-type="application/sql" \
    --remote

echo "==> Updating R2: $BUCKET/$LATEST_KEY"
npx --yes wrangler r2 object put "$BUCKET/$LATEST_KEY" \
    --file="$SQL_FILE" \
    --content-type="application/sql" \
    --remote

# Sidecar manifest — small JSON with sha + bytes for integrity checks.
MANIFEST="$TMPDIR/manifest_${TIMESTAMP}.json"
cat > "$MANIFEST" <<EOF
{
  "db_name": "$DB_NAME",
  "timestamp": "$TIMESTAMP",
  "bytes": $BYTES,
  "sha256": "$SHA",
  "dated_key": "$DATED_KEY"
}
EOF
npx --yes wrangler r2 object put "$BUCKET/d1-backups/${DB_NAME}/${YEAR}/${MONTH}/${DB_NAME}_${TIMESTAMP}.manifest.json" \
    --file="$MANIFEST" \
    --content-type="application/json" \
    --remote

echo
echo "✓ D1 export uploaded to R2"
echo "  bucket:       $BUCKET"
echo "  dated_key:    $DATED_KEY"
echo "  latest_key:   $LATEST_KEY"
echo "  bytes:        $BYTES"
echo "  sha256:       $SHA"

if [[ $KEEP_LOCAL -eq 1 ]]; then
    LOCAL_DIR="data/processed/cloudflare/d1_backups"
    mkdir -p "$LOCAL_DIR"
    cp "$SQL_FILE" "$LOCAL_DIR/"
    cp "$MANIFEST" "$LOCAL_DIR/"
    echo "  local copy:   $LOCAL_DIR/$(basename "$SQL_FILE")"
fi
