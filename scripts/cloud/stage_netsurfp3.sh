#!/usr/bin/env bash
# Stage NetSurfP-3.0 (DTU standalone) for the Modal disorder benchmark.
#
# Splits the DTU zip the same way as SignalP, for the same reason:
#
#   modal/.netsurfp3-pkg/   the nsp3 package + driver (~200 KB) -> baked into the image
#   Modal Volume            models/nsp3.pth (3.34 GB)           -> mounted at runtime
#
# The checkpoint is the part the public GitHub repo does NOT ship -- its Dockerfile loads
# a model_best.pth that is absent, and models/url.txt lists only the upstream language
# models. This zip is what makes NetSurfP-3.0 runnable at all.
#
# RESUMABLE: extraction caches under ~/.cache/netsurfp3-stage, so an interrupted upload
# retries without unzipping 3.3 GB again. `modal volume put` commits atomically, so an
# interrupted upload leaves nothing partial. Pass --clean to force a fresh extraction.
#
# LICENCE: NetSurfP-3.0 is DTU academic-licensed. This uploads it to YOUR OWN private
# Modal workspace. Do not make the Volume public and do not commit any part of the zip.
#
# Usage:
#   scripts/cloud/stage_netsurfp3.sh /path/to/netsurfp-3.0.Linux.zip [--clean]

set -euo pipefail

ZIP="${1:?usage: $0 /path/to/netsurfp-3.0.Linux.zip [--clean]}"
CLEAN="${2:-}"
VOLUME="netsurfp3-model"
REPO_ROOT="$(git rev-parse --show-toplevel)"
PKG_DST="${REPO_ROOT}/modal/.netsurfp3-pkg"
CACHE="${XDG_CACHE_HOME:-$HOME/.cache}/netsurfp3-stage"
CKPT="${CACHE}/nsp3.pth"
ROOT_IN_ZIP="NetSurfP-3.0_standalone"

[ -f "$ZIP" ] || { echo "error: no such file: $ZIP" >&2; exit 1; }
[ "$CLEAN" = "--clean" ] && rm -rf "$CACHE" "$PKG_DST"

if [ -s "$CKPT" ] && [ -f "$PKG_DST/nsp3.py" ]; then
    echo "==> already extracted ($(du -h "$CKPT" | cut -f1)); skipping unpack"
else
    echo "==> extracting the package (small)"
    rm -rf "$PKG_DST"; mkdir -p "$PKG_DST"
    TMP="$(mktemp -d)"; trap 'rm -rf "$TMP"' EXIT
    unzip -q -o "$ZIP" "${ROOT_IN_ZIP}/nsp3/*" "${ROOT_IN_ZIP}/nsp3.py" \
        "${ROOT_IN_ZIP}/setup.py" "${ROOT_IN_ZIP}/requirements.txt" \
        "${ROOT_IN_ZIP}/example.fasta" -d "$TMP"
    cp -R "$TMP/${ROOT_IN_ZIP}/." "$PKG_DST/"
    find "$PKG_DST" -name '__pycache__' -type d -exec rm -rf {} + 2>/dev/null || true
    find "$PKG_DST" -name '.DS_Store' -delete 2>/dev/null || true
    echo "    package -> $PKG_DST ($(du -sh "$PKG_DST" | cut -f1))"

    echo "==> extracting the checkpoint (3.34 GB)"
    mkdir -p "$CACHE"
    unzip -p "$ZIP" "${ROOT_IN_ZIP}/models/nsp3.pth" > "$CKPT"
    echo "    checkpoint -> $CKPT ($(du -h "$CKPT" | cut -f1))"
fi

echo "==> uploading the checkpoint to Modal volume '$VOLUME' (3.34 GB)"
echo "    safe to interrupt: the put commits atomically and the extraction is cached."
uv run modal volume create "$VOLUME" 2>/dev/null || true
uv run modal volume put --force "$VOLUME" "$CKPT" /nsp3.pth

echo
echo "staged. measure cost before any sweep:"
echo "    uv run modal run modal/disorder_app.py::netsurfp_canary --n 40"
