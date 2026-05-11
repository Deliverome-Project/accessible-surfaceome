#!/usr/bin/env bash
# Snapshot the Cloudflare D1 `deliverome_agent_runs` database to a local SQL file.
#
# Cloudflare's Time Travel covers accidental data loss for 7-30 days. This
# script is the *belt-and-suspenders* layer: a portable SQL dump you can
# diff, grep, and re-import anywhere.
#
# Per the standard project rule, dumps land under data/processed/cloudflare/
# with a timestamped filename — older dumps are kept (gitignore them via
# the existing data/* rules; pin specific ones with `git lfs track` if you
# want them in the repo).
#
# USAGE
#   bash scripts/d1_triage_backup.sh
#   bash scripts/d1_triage_backup.sh /custom/output/dir
#
# REQUIREMENTS
#   * wrangler installed via `npm ci` at the repo root — pins the version
#     in package.json; available under node_modules/.bin and via
#     `npx wrangler`. Authenticated against the Deliverome Cloudflare
#     account either via `wrangler login` or by setting
#     CLOUDFLARE_API_TOKEN + CLOUDFLARE_ACCOUNT_ID in the shell.
#   * The DB named `deliverome_agent_runs` must already exist (see
#     cloudflare/README.md).

set -euo pipefail

OUTPUT_DIR="${1:-data/processed/cloudflare/d1_backups}"
mkdir -p "$OUTPUT_DIR"

TIMESTAMP="$(date -u +%Y%m%dT%H%M%SZ)"
OUT_FILE="$OUTPUT_DIR/deliverome_agent_runs_${TIMESTAMP}.sql"

echo "Exporting D1 deliverome_agent_runs → $OUT_FILE"
npx --yes wrangler d1 export deliverome_agent_runs \
    --remote \
    --output="$OUT_FILE"

# Generate a content-SHA companion file so we can integrity-check restores.
SHA="$(shasum -a 256 "$OUT_FILE" | awk '{print $1}')"
echo "$SHA  $(basename "$OUT_FILE")" > "$OUT_FILE.sha256"

BYTES=$(wc -c < "$OUT_FILE" | tr -d ' ')
echo
echo "✓ Dumped $BYTES bytes"
echo "  $OUT_FILE"
echo "  sha256: $SHA"
echo
echo "Older dumps in $OUTPUT_DIR:"
ls -lh "$OUTPUT_DIR"/deliverome_agent_runs_*.sql 2>/dev/null | tail -5 || echo "  (this is the first)"
