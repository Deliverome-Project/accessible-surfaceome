#!/usr/bin/env bash
# Refresh the Ensembl Compara ortholog snapshot used by the deep-dive agent.
#
# Does three things in lockstep:
#   1. Runs the Compara producer (BioMart fetch, ~5 min, no LLM cost).
#   2. Uploads the refreshed CSV to the Cloudflare D1 `surfaceome_agents`
#      database under a date-stamped release_version.
#   3. Stamps a provenance marker (`.last_refresh`) so the deep-dive pack
#      loader can identify the active release at runtime.
#
# Requires Cloudflare D1 env vars (see cloudflare/README.md):
#   CLOUDFLARE_ACCOUNT_ID
#   CLOUDFLARE_D1_SURFACEOME_AGENTS_ID
#   CLOUDFLARE_API_TOKEN
#
# Idempotent on (release_version, human_ensembl_gene, species,
# ortholog_ensembl_gene): rerunning with the same date suffix produces
# no duplicate rows. Bump `--release` to capture a true second snapshot.

set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")"/.. && pwd)"
cd "$ROOT_DIR"

RELEASE_DATE="$(date -u +%Y_%m_%d)"
RELEASE_VERSION="${RELEASE_VERSION:-ensembl_compara_${RELEASE_DATE}}"
COMPARA_DIR="data/external/ensembl_compara_surfaceome_expressed"
JOIN_CSV="${COMPARA_DIR}/compara_mouse_cyno_one2one_highconf_by_ensembl_query.csv"

echo "==> Running Ensembl Compara producer (BioMart fetch)…"
uv run python -m accessible_surfaceome.sources.ensembl_compara download

if [[ ! -f "$JOIN_CSV" ]]; then
  echo "ERROR: expected $JOIN_CSV after producer run; file missing" >&2
  exit 1
fi

N_ROWS=$(($(wc -l < "$JOIN_CSV") - 1))
echo "==> Refreshed CSV has ${N_ROWS} ortholog rows (release_version=${RELEASE_VERSION})"

echo "==> Uploading to Cloudflare D1…"
uv run python scripts/upload_compara_to_d1.py \
  --release "$RELEASE_VERSION" \
  --csv "$JOIN_CSV" \
  --notes "refresh_compara.sh on $(date -u +%Y-%m-%dT%H:%M:%SZ)"

# Stamp provenance marker for the deep-dive pack loader.
echo "$RELEASE_VERSION" > "${COMPARA_DIR}/.last_refresh"
echo "==> Wrote ${COMPARA_DIR}/.last_refresh = ${RELEASE_VERSION}"

echo "==> Done. Active release: ${RELEASE_VERSION} (${N_ROWS} rows)."
