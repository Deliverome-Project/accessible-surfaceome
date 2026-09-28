#!/usr/bin/env bash
# Stage SignalP 6.0 slow-sequential for the Modal sweep.
#
# Splits the DTU tarball into the two things Modal needs separately:
#
#   modal/.signalp6-pkg/   the Python package, code only (~100 KB) -> baked into the image
#   Modal Volume           the six 1.63 GB checkpoints (9.8 GB)    -> mounted at runtime
#
# They are split because rebuilding the image must not mean re-uploading 9.8 GB, and
# because the GPU conversion rewrites the checkpoints in place -- that has to happen
# somewhere durable and writable, which is the Volume, not an image layer.
#
# LICENCE: SignalP 6.0 is DTU academic-licensed. This uploads it to YOUR OWN private
# Modal workspace for your own use. Do not make that Volume public, do not share the
# workspace, and do not commit any part of the tarball to git.
#
# Usage:
#   scripts/cloud/stage_signalp6.sh /path/to/signalp-6.0i.slow_sequential.tar.gz

set -euo pipefail

TARBALL="${1:?usage: $0 /path/to/signalp-6.0i.slow_sequential.tar.gz}"
VOLUME="signalp6-models"
REPO_ROOT="$(git rev-parse --show-toplevel)"
PKG_DST="${REPO_ROOT}/modal/.signalp6-pkg"
WORK="$(mktemp -d)"
trap 'rm -rf "$WORK"' EXIT

[ -f "$TARBALL" ] || { echo "error: no such file: $TARBALL" >&2; exit 1; }

echo "==> extracting (9.8 GB; this takes a few minutes)"
tar xzf "$TARBALL" -C "$WORK"
SRC="$(find "$WORK" -type d -name 'signalp-6-package' -maxdepth 3 | head -1)"
[ -n "$SRC" ] || { echo "error: signalp-6-package not found in the tarball" >&2; exit 1; }

echo "==> separating code from checkpoints"
rm -rf "$PKG_DST"
mkdir -p "$PKG_DST"
# Everything except the checkpoints. The package still declares them as package_data,
# but --model_dir overrides that at run time.
(cd "$SRC" && tar cf - --exclude='models/sequential_models_signalp6' .) | tar xf - -C "$PKG_DST"
mkdir -p "$PKG_DST/models/sequential_models_signalp6"

CKPT_SRC="$SRC/models/sequential_models_signalp6"
n_ckpt="$(find "$CKPT_SRC" -name '*.pt' | wc -l | tr -d ' ')"
echo "    package -> $PKG_DST ($(du -sh "$PKG_DST" | cut -f1))"
echo "    checkpoints: $n_ckpt files, $(du -sh "$CKPT_SRC" | cut -f1)"
[ "$n_ckpt" -eq 7 ] || echo "    WARNING: expected 7 (.pt) files, found $n_ckpt"

echo "==> uploading checkpoints to Modal volume '$VOLUME' (slow: 9.8 GB)"
uv run modal volume create "$VOLUME" 2>/dev/null || true
uv run modal volume put "$VOLUME" "$CKPT_SRC" /cpu/sequential_models_signalp6

echo
echo "staged. next, convert the checkpoints for GPU (one-time, on Modal):"
echo "    uv run modal run modal/signalp6_app.py::convert_models"
echo
echo "then measure cost before any sweep:"
echo "    uv run modal run modal/signalp6_app.py::canary --n 200"
