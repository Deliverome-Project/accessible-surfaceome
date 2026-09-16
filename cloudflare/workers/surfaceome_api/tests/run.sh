#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/../../../.."
bundle=cloudflare/workers/surfaceome_api/tests/worker.bundle.mjs
trap 'rm -f "$bundle"' EXIT
viewer/node_modules/.bin/esbuild cloudflare/workers/surfaceome_api/src/index.js --bundle --format=esm --platform=browser --outfile="$bundle"
node --test cloudflare/workers/surfaceome_api/tests/feedback.test.mjs
