#!/usr/bin/env bash
# Export a Cloudflare D1 database to SQL, gzip it, split it into
# fixed-size parts, and upload the parts plus a manifest to the R2
# bucket `deliverome-d1-backups`.
#
# WHY PARTS: `wrangler r2 object put` refuses files over 300 MiB, and
# the surfaceome_agents dump passed 2 GiB in mid-2026 — every backup run
# from 2026-06-29 onward failed on that limit. gzip alone is not
# guaranteed to get under the cap, so the compressed dump is always
# split into fixed-size parts (default 250 MiB) and reassembled on
# restore. Before anything is uploaded the script reassembles the parts
# itself and checks the sha256 against the raw dump.
#
# This is the CI-driven offsite backup layer (layer 2.5 in the
# disaster-recovery taxonomy): dumps live in R2 with cross-region
# durability, automatically versioned by timestamped object key.
#
# REQUIREMENTS
#   * wrangler installed via `npm ci` at the repo root (pins the version
#     in package.json) — this script calls `npx --yes wrangler ...` so
#     the pinned version wins over any global install. Authenticate via
#     `wrangler login` or CLOUDFLARE_API_TOKEN + CLOUDFLARE_ACCOUNT_ID.
#   * R2 bucket `deliverome-d1-backups` must exist
#       npx --yes wrangler r2 bucket create deliverome-d1-backups
#   * The target D1 database must exist
#
# USAGE
#   bash scripts/cloud/d1_export_to_r2.sh                        # default surfaceome_agents
#   bash scripts/cloud/d1_export_to_r2.sh --db surfaceome_public
#   bash scripts/cloud/d1_export_to_r2.sh --keep-local           # also retain a local copy
#   bash scripts/cloud/d1_export_to_r2.sh --dry-run              # package + verify, print the uploads, skip R2
#   bash scripts/cloud/d1_export_to_r2.sh --from-sql dump.sql    # package an existing dump (no D1 export)
#   bash scripts/cloud/d1_export_to_r2.sh --part-bytes 1048576   # smaller parts (testing)
#
# R2 LAYOUT (one dated prefix per run; parts are uploaded once)
#   d1-backups/<DB>/<YYYY>/<MM>/<DB>_<UTC>.sql.gz.part-aa, -ab, ...
#   d1-backups/<DB>/<YYYY>/<MM>/<DB>_<UTC>.manifest.json
#   d1-backups/<DB>/latest.manifest.json          (stable pointer to the newest run)
#
# RESTORE (the manifest's `restore` field repeats this for its own run)
#   npx --yes wrangler r2 object get deliverome-d1-backups/<part-key> --file <part> --remote   # each part
#   cat <DB>_<UTC>.sql.gz.part-* | gunzip > <DB>_<UTC>.sql
#   shasum -a 256 <DB>_<UTC>.sql                  # must equal manifest.sql_sha256
#   npx --yes wrangler d1 execute <DB> --remote --file <DB>_<UTC>.sql
#
# CI USAGE
#   See .github/workflows/d1-backup.yml — runs on push that touches the
#   D1 schema, eval data, or uploaders. Auth via the CLOUDFLARE_* secrets.

set -euo pipefail

DB_NAME="surfaceome_agents"
BUCKET="deliverome-d1-backups"
KEEP_LOCAL=0
DRY_RUN=0
FROM_SQL=""
PART_BYTES=262144000   # 250 MiB — comfortably under wrangler's 300 MiB put limit

while [[ $# -gt 0 ]]; do
    case "$1" in
        --db)         DB_NAME="$2"; shift 2 ;;
        --keep-local) KEEP_LOCAL=1; shift ;;
        --dry-run)    DRY_RUN=1; shift ;;
        --from-sql)   FROM_SQL="$2"; shift 2 ;;
        --part-bytes) PART_BYTES="$2"; shift 2 ;;
        -h|--help)    sed -n '2,49p' "$0"; exit 0 ;;
        *)
            echo "unknown flag: $1" >&2
            echo "usage: $0 [--db <name>] [--keep-local] [--dry-run] [--from-sql <file>] [--part-bytes <n>]" >&2
            exit 2
            ;;
    esac
done

TIMESTAMP="$(date -u +%Y%m%dT%H%M%SZ)"
TMPDIR="$(mktemp -d)"
trap 'if [[ $KEEP_LOCAL -eq 0 ]]; then rm -rf "$TMPDIR"; fi' EXIT
SQL_FILE="$TMPDIR/${DB_NAME}_${TIMESTAMP}.sql"

# Upload helper — the only place wrangler r2 is called, so --dry-run
# can swap it for a print.
r2_put() {  # r2_put <key> <file> <content-type>
    local key="$1" file="$2" ctype="$3"
    if [[ $DRY_RUN -eq 1 ]]; then
        echo "    [dry-run] put $BUCKET/$key  ← $(basename "$file")  ($(wc -c < "$file" | tr -d ' ') bytes)"
        return 0
    fi
    npx --yes wrangler r2 object put "$BUCKET/$key" \
        --file="$file" \
        --content-type="$ctype" \
        --remote
}

# ---- 1. export --------------------------------------------------------
if [[ -n $FROM_SQL ]]; then
    echo "==> Packaging existing dump $FROM_SQL (skipping D1 export)"
    cp "$FROM_SQL" "$SQL_FILE"
else
    echo "==> Exporting D1 $DB_NAME → $SQL_FILE"
    npx --yes wrangler d1 export "$DB_NAME" \
        --remote \
        --output="$SQL_FILE"
fi
SQL_BYTES=$(wc -c < "$SQL_FILE" | tr -d ' ')
SQL_SHA="$(shasum -a 256 "$SQL_FILE" | awk '{print $1}')"
echo "    sql: $SQL_BYTES bytes  sha256=$SQL_SHA"

# ---- 2. compress + split ---------------------------------------------
GZ_FILE="$SQL_FILE.gz"
echo "==> Compressing → $(basename "$GZ_FILE")"
gzip -c "$SQL_FILE" > "$GZ_FILE"
GZ_BYTES=$(wc -c < "$GZ_FILE" | tr -d ' ')
GZ_SHA="$(shasum -a 256 "$GZ_FILE" | awk '{print $1}')"
echo "    gz:  $GZ_BYTES bytes  sha256=$GZ_SHA  ($(( 100 * GZ_BYTES / SQL_BYTES ))% of raw)"

# Alphabetic 2-char suffixes (-a 2, not GNU-only -d) so this runs on
# both the ubuntu CI runner and a macOS laptop; the glob below sorts
# them back into split order.
PART_PREFIX="$GZ_FILE.part-"
echo "==> Splitting into ${PART_BYTES}-byte parts"
split -b "$PART_BYTES" -a 2 "$GZ_FILE" "$PART_PREFIX"
PARTS=( "$PART_PREFIX"* )
echo "    ${#PARTS[@]} part(s)"

# ---- 3. prove the parts restore before uploading anything ------------
echo "==> Verifying reassembly (cat parts | gunzip → sha256 must match raw dump)"
ROUNDTRIP_SHA="$(cat "${PARTS[@]}" | gunzip -c | shasum -a 256 | awk '{print $1}')"
if [[ $ROUNDTRIP_SHA != "$SQL_SHA" ]]; then
    echo "ERROR: reassembled parts do not match the raw dump — aborting, nothing uploaded" >&2
    echo "  expected $SQL_SHA" >&2
    echo "  got      $ROUNDTRIP_SHA" >&2
    exit 1
fi
echo "    roundtrip OK"

# ---- 4. upload parts once under the dated prefix ---------------------
YEAR="${TIMESTAMP:0:4}"
MONTH="${TIMESTAMP:4:2}"
DATED_PREFIX="d1-backups/${DB_NAME}/${YEAR}/${MONTH}/${DB_NAME}_${TIMESTAMP}"
MANIFEST_KEY="${DATED_PREFIX}.manifest.json"
LATEST_KEY="d1-backups/${DB_NAME}/latest.manifest.json"

PART_ENTRIES=()
for part in "${PARTS[@]}"; do
    suffix="${part##*.part-}"
    key="${DATED_PREFIX}.sql.gz.part-${suffix}"
    pbytes=$(wc -c < "$part" | tr -d ' ')
    psha="$(shasum -a 256 "$part" | awk '{print $1}')"
    echo "==> Uploading part $suffix → $BUCKET/$key ($pbytes bytes)"
    r2_put "$key" "$part" "application/gzip"
    PART_ENTRIES+=("    { \"key\": \"$key\", \"bytes\": $pbytes, \"sha256\": \"$psha\" }")
done
PARTS_JSON="$(printf '%s,\n' "${PART_ENTRIES[@]}" | sed '$ s/,$//')"

# ---- 5. manifest: dated copy + stable latest pointer -----------------
MANIFEST="$TMPDIR/${DB_NAME}_${TIMESTAMP}.manifest.json"
cat > "$MANIFEST" <<EOF
{
  "db_name": "$DB_NAME",
  "timestamp": "$TIMESTAMP",
  "format": "sql.gz split into fixed-size parts; concatenate parts in order, then gunzip",
  "sql_bytes": $SQL_BYTES,
  "sql_sha256": "$SQL_SHA",
  "gz_bytes": $GZ_BYTES,
  "gz_sha256": "$GZ_SHA",
  "part_bytes": $PART_BYTES,
  "n_parts": ${#PARTS[@]},
  "parts": [
$PARTS_JSON
  ],
  "restore": [
    "for each parts[].key: npx --yes wrangler r2 object get $BUCKET/<key> --file <local> --remote",
    "cat ${DB_NAME}_${TIMESTAMP}.sql.gz.part-* | gunzip > ${DB_NAME}_${TIMESTAMP}.sql",
    "shasum -a 256 ${DB_NAME}_${TIMESTAMP}.sql   # must equal sql_sha256",
    "npx --yes wrangler d1 execute ${DB_NAME} --remote --file ${DB_NAME}_${TIMESTAMP}.sql"
  ]
}
EOF
if command -v python3 >/dev/null 2>&1; then
    python3 -m json.tool "$MANIFEST" >/dev/null || { echo "ERROR: manifest is not valid JSON" >&2; exit 1; }
fi
echo "==> Uploading manifest → $BUCKET/$MANIFEST_KEY"
r2_put "$MANIFEST_KEY" "$MANIFEST" "application/json"
echo "==> Updating stable pointer → $BUCKET/$LATEST_KEY"
r2_put "$LATEST_KEY" "$MANIFEST" "application/json"

echo
if [[ $DRY_RUN -eq 1 ]]; then echo "✓ dry run complete (nothing uploaded)"; else echo "✓ D1 export uploaded to R2"; fi
echo "  bucket:       $BUCKET"
echo "  dated_prefix: $DATED_PREFIX"
echo "  latest_key:   $LATEST_KEY"
echo "  sql_bytes:    $SQL_BYTES   sha256=$SQL_SHA"
echo "  gz_bytes:     $GZ_BYTES   in ${#PARTS[@]} part(s) of ≤$PART_BYTES bytes"

if [[ $KEEP_LOCAL -eq 1 ]]; then
    LOCAL_DIR="data/processed/cloudflare/d1_backups"
    mkdir -p "$LOCAL_DIR"
    cp "$SQL_FILE" "$MANIFEST" "${PARTS[@]}" "$LOCAL_DIR/"
    echo "  local copy:   $LOCAL_DIR/$(basename "$SQL_FILE") (+ parts + manifest)"
fi
