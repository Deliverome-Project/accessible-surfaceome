#!/usr/bin/env bash
# Render k_of_5_agreement.html to PDF (via headless Chrome) and PNG (via pdftoppm).
# Usage: bash docs/reports/figures/build-k-of-5.sh
set -euo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
HTML="$HERE/k_of_5_agreement.html"
PDF="$HERE/k_of_5_agreement.pdf"
PNG_PREFIX="$HERE/k_of_5_agreement"
PNG="$HERE/k_of_5_agreement.png"

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

PDFTOPPM="${PDFTOPPM:-$(command -v pdftoppm 2>/dev/null || true)}"

echo "rendering $HTML → $PDF"
"$CHROME_BIN" \
  --headless=new \
  --disable-gpu \
  --no-sandbox \
  --hide-scrollbars \
  --virtual-time-budget=10000 \
  --no-pdf-header-footer \
  --print-to-pdf-no-header \
  --print-to-pdf="$PDF" \
  "file://$HTML"
echo "wrote $PDF"

if [[ -n "$PDFTOPPM" && -x "$PDFTOPPM" ]]; then
  echo "rendering $PDF → $PNG (300 dpi)"
  "$PDFTOPPM" -r 300 -f 1 -l 1 -png -singlefile "$PDF" "$PNG_PREFIX"
  echo "wrote $PNG"
else
  echo "note: pdftoppm not found; skipping PNG export. Install poppler (brew install poppler) to enable." >&2
fi
