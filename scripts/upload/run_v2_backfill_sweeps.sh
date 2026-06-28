#!/usr/bin/env bash
# v2 deterministic-feature backfill — DeepTMHMM sweeps (compute only; --skip-upload).
#
# Each cohort runs under its OWN scratch topology_version label so the per-cohort
# runs land in separate run dirs (no batch-name collisions) and each resumes
# independently (the sweep skips batches whose predicted_topologies.3line exists).
# The scratch labels are normalized to the EXISTING production versions at upload
# time (separate, deliberate step) — never auto-uploaded here, so D1 is untouched
# until the version-pinned upload is arranged.
#
#   Resume: just re-run this script — completed batches are skipped.
#   Workers: WORKERS=2 by default (override with WORKERS=N).
#   DeepTMHMM: DEEPTMHMM_ROOT must point at the install (parent of
#     data/external/deeptmhmm/DeepTMHMM-Academic-License-v1.0/predict.py).
set -uo pipefail
cd "$(git rev-parse --show-toplevel)"

export DEEPTMHMM_ROOT="${DEEPTMHMM_ROOT:-/Users/rebeccacarlson/Git/deliverome-internal/analyses/surface-proteome}"
W="${WORKERS:-2}"
# Absolute path: run_topology_sweep does candidate_set_path.relative_to(REPO_ROOT),
# which raises on a relative path. pwd is the repo root (we cd'd above).
RUNDIR="$(pwd)/data/processed/topology_run_topo_2026_05_16"
log() { printf '\n========== %s ==========\n' "$*"; }

sweep() {
  # $1 = scratch label ; rest = extra args
  local label="$1"; shift
  log "SWEEP ${label} (workers=${W})"
  uv run python scripts/build/run_topology_sweep.py \
    --topology-version "${label}" \
    --max-workers "${W}" \
    --skip-upload \
    "$@" \
    || echo "!! SWEEP ${label} exited non-zero (resume by re-running this script)"
}

# A. canonical — the 71 genes with no human_canonical row
sweep v2bf_canon_2026_06_01 \
  --cohorts human_canonical \
  --candidate-set "${RUNDIR}/candidate_canonical.tsv" \
  --skip-paralogs

# C. orthologs — 1,372 genes; human_canonical included so ortholog ECD has the
#    human topology (cached canonicals are skipped, so this stays cheap)
sweep v2bf_ortho_2026_06_01 \
  --cohorts human_canonical,mouse_ortholog,cyno_ortholog \
  --candidate-set "${RUNDIR}/candidate_orthologs.tsv" \
  --skip-paralogs

# B. isoforms — 3,026 genes fed; UniProt resolution keeps only the ~3% with alts
sweep v2bf_iso_2026_06_01 \
  --cohorts human_isoforms \
  --candidate-set "${RUNDIR}/candidate_isoforms.tsv" \
  --skip-paralogs

# D. paralogs — 958 genes; paralog stage ON (computes ECD vs each paralog's
#    canonical topology, DeepTMHMM'ing only paralogs not already predicted)
sweep v2bf_para_2026_06_01 \
  --cohorts human_canonical \
  --candidate-set "${RUNDIR}/candidate_paralogs.tsv"

log "ALL SWEEPS DONE — outputs under data/processed/topology_run_v2bf_*; nothing uploaded to D1 yet."
