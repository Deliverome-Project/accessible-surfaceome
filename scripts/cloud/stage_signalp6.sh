#!/usr/bin/env bash
# Stage SignalP 6.0 slow-sequential for the Modal sweep.
#
# Splits the DTU tarball into the two things Modal needs separately:
#
#   modal/.signalp6-pkg/   the Python package, code only (~108 KB) -> baked into the image
#   Modal Volume           the six 1.63 GB checkpoints (9.2 GB)    -> mounted at runtime
#
# They are split because rebuilding the image must not mean re-uploading 9.2 GB, and
# because the GPU conversion rewrites the checkpoints in place -- that has to happen
# somewhere durable and writable, which is the Volume, not an image layer.
#
# RESUMABLE. Extraction goes to a persistent cache, not a temp dir, so an interrupted
# upload can be retried without unpacking 9.2 GB again. `modal volume put` commits
# atomically, so a killed upload leaves nothing partial on the Volume -- just re-run.
# Pass --clean to force a fresh extraction.
#
# LICENCE: SignalP 6.0 is DTU academic-licensed. This uploads it to YOUR OWN private
# Modal workspace for your own use. Do not make that Volume public, do not share the
# workspace, and do not commit any part of the tarball to git.
#
# Usage:
#   scripts/cloud/stage_signalp6.sh /path/to/signalp-6.0i.slow_sequential.tar.gz [--clean]

set -euo pipefail

TARBALL="${1:?usage: $0 /path/to/signalp-6.0i.slow_sequential.tar.gz [--clean]}"
CLEAN="${2:-}"
VOLUME="signalp6-models"
REPO_ROOT="$(git rev-parse --show-toplevel)"
PKG_DST="${REPO_ROOT}/modal/.signalp6-pkg"
CACHE="${XDG_CACHE_HOME:-$HOME/.cache}/signalp6-stage"
CKPT_DIR="${CACHE}/sequential_models_signalp6"
EXPECTED_CKPT=7

[ -f "$TARBALL" ] || { echo "error: no such file: $TARBALL" >&2; exit 1; }
[ "$CLEAN" = "--clean" ] && rm -rf "$CACHE" "$PKG_DST"

have_ckpt() {
    [ -d "$CKPT_DIR" ] && [ "$(find "$CKPT_DIR" -name '*.pt' | wc -l | tr -d ' ')" -eq "$EXPECTED_CKPT" ]
}

if have_ckpt && [ -f "$PKG_DST/setup.py" ]; then
    echo "==> already extracted at $CACHE ($(du -sh "$CKPT_DIR" | cut -f1)); skipping unpack"
    echo "    (pass --clean to force a fresh extraction)"
else
    WORK="$(mktemp -d)"
    trap 'rm -rf "$WORK"' EXIT
    echo "==> extracting (9.2 GB; this takes a few minutes)"
    tar xzf "$TARBALL" -C "$WORK"
    SRC="$(find "$WORK" -maxdepth 3 -type d -name 'signalp-6-package' | head -1)"
    [ -n "$SRC" ] || { echo "error: signalp-6-package not found in the tarball" >&2; exit 1; }

    echo "==> separating code from checkpoints"
    rm -rf "$PKG_DST"; mkdir -p "$PKG_DST"
    # Everything except the checkpoints. The package still declares them as package_data,
    # but --model_dir overrides that at run time.
    (cd "$SRC" && tar cf - --exclude='models/sequential_models_signalp6' .) | tar xf - -C "$PKG_DST"
    mkdir -p "$PKG_DST/models/sequential_models_signalp6"

    rm -rf "$CACHE"; mkdir -p "$CACHE"
    mv "$SRC/models/sequential_models_signalp6" "$CKPT_DIR"
    echo "    package     -> $PKG_DST ($(du -sh "$PKG_DST" | cut -f1))"
    echo "    checkpoints -> $CKPT_DIR ($(du -sh "$CKPT_DIR" | cut -f1))"
    have_ckpt || echo "    WARNING: expected $EXPECTED_CKPT .pt files, found $(find "$CKPT_DIR" -name '*.pt' | wc -l | tr -d ' ')"
fi

echo "==> fingerprinting"
# Nothing else identifies these weights. The package version ("signalp-6.0+h") names the
# code, not the checkpoints, so a re-stage from a fresh DTU download could differ silently
# and no published row would show it. DeepTMHMM2 avoids this by digesting its checkpoints
# into tool_version; this does the same, and writes the result next to the weights so the
# volume is self-describing.
ARCHIVE_SHA="$(shasum -a 256 "$TARBALL" | cut -d' ' -f1)"
CKPT_SHA="$(cd "$CKPT_DIR" && find . -name '*.pt' -type f | sort | xargs shasum -a 256 | shasum -a 256 | cut -d' ' -f1)"
SHORT="${CKPT_SHA:0:12}"
cat > "${CACHE}/PROVENANCE.json" <<JSON
{
  "tool": "signalp-6.0+h",
  "mode": "slow-sequential",
  "tool_version": "signalp-6.0+h+ckpt.${SHORT}",
  "archive_filename": "$(basename "$TARBALL")",
  "archive_sha256": "${ARCHIVE_SHA}",
  "checkpoints_sha256": "${CKPT_SHA}",
  "n_checkpoints": ${n_ckpt:-7},
  "staged_at": "$(date -u +%Y-%m-%dT%H:%M:%SZ)"
}
JSON
echo "    archive     sha256 ${ARCHIVE_SHA:0:16}..."
echo "    checkpoints sha256 ${CKPT_SHA:0:16}..."
echo "    tool_version -> signalp-6.0+h+ckpt.${SHORT}"

echo "==> uploading checkpoints to Modal volume '$VOLUME' (9.2 GB, ~20 min)"
echo "    safe to interrupt: the put commits atomically, so re-running resumes from"
echo "    the cached extraction rather than the tarball."
uv run modal volume create "$VOLUME" 2>/dev/null || true
uv run modal volume put --force "$VOLUME" "$CKPT_DIR" /cpu/sequential_models_signalp6
uv run modal volume put --force "$VOLUME" "${CACHE}/PROVENANCE.json" /PROVENANCE.json

echo
echo "staged. publish with --tool-version signalp-6.0+h+ckpt.${SHORT}"
echo
echo "next, convert the checkpoints for GPU (one-time, on Modal):"
echo "    uv run modal run modal/signalp6_app.py::convert_models"
echo
echo "then measure cost before any sweep:"
echo "    uv run modal run modal/signalp6_app.py::canary --n 200"
echo
echo "the $(du -sh "$CACHE" | cut -f1) extraction cache at $CACHE can be deleted once converted."
