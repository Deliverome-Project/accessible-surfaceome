#!/usr/bin/env bash
# Render index.html to m1-candidate-universe.pdf via headless Chrome.
# Usage: bash analyses/surface-proteome/docs/onepagers/m1-candidate-universe/build-pdf.sh
set -euo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$HERE/../../.." && pwd)"
HTML="$HERE/index.html"
OUT="$HERE/m1-candidate-universe.pdf"

CHROME_BIN="${CHROME_BIN:-}"
if [[ -z "$CHROME_BIN" ]]; then
  for candidate in \
    "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome" \
    "/Applications/Chromium.app/Contents/MacOS/Chromium" \
    "$(command -v google-chrome 2>/dev/null || true)" \
    "$(command -v chromium 2>/dev/null || true)"; do
    if [[ -n "$candidate" && -x "$candidate" ]]; then
      CHROME_BIN="$candidate"
      break
    fi
  done
fi

if [[ -z "$CHROME_BIN" || ! -x "$CHROME_BIN" ]]; then
  echo "error: could not locate Chrome/Chromium. Set CHROME_BIN=/path/to/chrome." >&2
  exit 1
fi

echo "rendering $HTML → $OUT"
echo "using $CHROME_BIN"

"$CHROME_BIN" \
  --headless=new \
  --disable-gpu \
  --no-sandbox \
  --hide-scrollbars \
  --virtual-time-budget=10000 \
  --no-pdf-header-footer \
  --print-to-pdf-no-header \
  --print-to-pdf="$OUT" \
  "file://$HTML"

echo "wrote $OUT"
