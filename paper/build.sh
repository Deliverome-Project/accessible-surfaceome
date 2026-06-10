#!/usr/bin/env bash
# Render a .docx manuscript into a Deliverome-branded PDF + JATS XML.
#
#   bash paper/build.sh path/to/manuscript.docx
#
# Outputs three files under <docx-dir>/build/:
#   <stem>.html  — pandoc-rendered HTML with the deliverome stylesheet
#                  attached (intermediate; useful for debugging the
#                  print layout in a browser)
#   <stem>.pdf   — WeasyPrint output. This is the polished
#                  publication-style PDF — feed it to the
#                  manuscript-bundle's `pdf_path` in
#                  scripts/release/publish-archive.py.
#   <stem>.xml   — pandoc-rendered JATS XML. Feed it to the
#                  manuscript-bundle's `jats_filename` (or it's
#                  rendered there automatically when the bundle entry
#                  is enabled).
#
# Requires:
#   pandoc       brew install pandoc          (or apt install pandoc)
#   weasyprint   pip install weasyprint       (or pipx install)
#
# WeasyPrint also needs Pango / Cairo / GDK-PixBuf on Linux —
# install the OS packages it warns about on first run.
set -euo pipefail

if [[ ${#@} -lt 1 ]]; then
  echo "usage: bash $0 <path/to/manuscript.docx>" >&2
  exit 64
fi

SRC="$1"
if [[ ! -f "$SRC" ]]; then
  echo "error: source manuscript not found: $SRC" >&2
  exit 66
fi

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
CSS="$SCRIPT_DIR/deliverome-print.css"
if [[ ! -f "$CSS" ]]; then
  echo "error: deliverome-print.css not found at $CSS" >&2
  exit 66
fi

STEM="$(basename "${SRC%.*}" | tr ' ' '_')"
OUT_DIR="$(dirname "$SRC")/build"
mkdir -p "$OUT_DIR"
MEDIA_DIR="$OUT_DIR/media-$STEM"

# Pre-flight tool checks — pandoc is required for everything, weasyprint
# only for the PDF. Skip the WeasyPrint step gracefully if it's not
# installed so the user can still get the JATS + HTML out.
if ! command -v pandoc >/dev/null; then
  echo "error: pandoc not on PATH. Install with: brew install pandoc" >&2
  exit 69
fi

HAVE_WEASYPRINT=1
if ! command -v weasyprint >/dev/null; then
  HAVE_WEASYPRINT=0
  echo "warn: weasyprint not on PATH — skipping PDF step." >&2
  echo "      Install with: pip install weasyprint" >&2
fi

# 1. pandoc → standalone HTML with the deliverome stylesheet linked.
#    --extract-media pulls embedded .docx images out as separate files
#    so WeasyPrint can load them; the path is relative to the HTML so
#    the link stays valid wherever the build dir lives.
echo "→ pandoc $SRC → $OUT_DIR/$STEM.html"
pandoc "$SRC" \
  --from docx \
  --to html5 \
  --standalone \
  --section-divs \
  --extract-media "$MEDIA_DIR" \
  --css "$CSS" \
  -o "$OUT_DIR/$STEM.html"

# 2. WeasyPrint → PDF. The --base-url anchors relative paths (CSS @import
#    of the design tokens at ../viewer/app/design-tokens.css, and the
#    extracted media images) to the HTML file's directory. WeasyPrint
#    can hit the Google Fonts URL directly to pull Manrope + Playfair
#    Display; the resulting PDF embeds the font subsets it needs.
if [[ "$HAVE_WEASYPRINT" == "1" ]]; then
  echo "→ weasyprint → $OUT_DIR/$STEM.pdf"
  weasyprint \
    "$OUT_DIR/$STEM.html" \
    "$OUT_DIR/$STEM.pdf" \
    --base-url "$OUT_DIR"
fi

# 3. pandoc → JATS XML. Same source, different writer; for the Zenodo
#    deposit, machine-readable references and figure metadata.
echo "→ pandoc $SRC → $OUT_DIR/$STEM.xml"
pandoc "$SRC" \
  --from docx \
  --standalone \
  --to jats \
  -o "$OUT_DIR/$STEM.xml"

echo ""
echo "✓ Wrote:"
echo "  $OUT_DIR/$STEM.html"
[[ "$HAVE_WEASYPRINT" == "1" ]] && echo "  $OUT_DIR/$STEM.pdf"
echo "  $OUT_DIR/$STEM.xml"
echo ""
echo "Iterating on the print look:"
echo "  open $OUT_DIR/$STEM.html in a browser — Chrome's"
echo "  DevTools 'Rendering > Emulate CSS media type: print' shows"
echo "  exactly what WeasyPrint will see. Tweak"
echo "  paper/deliverome-print.css and re-run."
