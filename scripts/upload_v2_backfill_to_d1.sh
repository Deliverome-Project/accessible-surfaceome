#!/usr/bin/env bash
# v2 deterministic-feature backfill — D1 upload (version-normalized, pinned).
#
# The sweeps ran under scratch topology_version labels (v2bf_*) for run-dir
# isolation. This normalizes each JSONL's embedded version field back to the
# EXISTING production versions so the rows extend them IN PLACE (INSERT OR
# IGNORE), never minting a new "latest" that would orphan the ~11k rows already
# there. Uploads topology + ortholog-ECD + paralog rows to BOTH private+public D1.
#
#   DRY-RUN (default, no writes):  bash scripts/upload_v2_backfill_to_d1.sh
#   EXECUTE:                       DRYRUN=0 bash scripts/upload_v2_backfill_to_d1.sh
set -uo pipefail
cd "$(git rev-parse --show-toplevel)"
DRYRUN="${DRYRUN:-1}"
DRY=""; [ "$DRYRUN" = "1" ] && DRY="--dry-run"
PUBONLY="${PUBLIC_ONLY:-0}"
PUB=""; [ "$PUBONLY" = "1" ] && PUB="--public-only"
echo "=== DRYRUN=$DRYRUN  PUBLIC_ONLY=$PUBONLY  (DRYRUN 1=no writes; PUBLIC_ONLY 1=skip private) ==="

# Existing production versions (the rows extend these in place):
TOPO_V=topo_2026_05_16                          # canonical + mouse/cyno orthologs
ISO_V=topo_2026_05_25                            # human isoforms (newer version)
OECD_V=orthologecd_topo_2026_05_16_idfix         # ortholog ECD (pin the _idfix!)
PARA_V=paralog_topo_2026_05_16                   # paralog ECD identity

C=data/processed/topology_run_v2bf_canon_2026_06_01
O=data/processed/topology_run_v2bf_ortho_2026_06_01
I=data/processed/topology_run_v2bf_iso_2026_06_01
P=data/processed/topology_run_v2bf_para_2026_06_01

# norm <jsonl> <field> <value> → writes <jsonl>.norm (originals kept for provenance)
norm() { uv run python - "$1" "$2" "$3" <<'PY'
import json, sys
src, field, val = sys.argv[1:4]; dst = src + ".norm"; n = 0
with open(src) as f, open(dst, "w") as o:
    for ln in f:
        ln = ln.strip()
        if not ln:
            continue
        r = json.loads(ln); r[field] = val; o.write(json.dumps(r) + "\n"); n += 1
print(f"  normalized {n:5d} rows  {field} -> {val}")
PY
}

echo "== normalize scratch versions → production =="
norm $C/human_canonical/topology_records.jsonl topology_version $TOPO_V
norm $O/human_canonical/topology_records.jsonl topology_version $TOPO_V
norm $O/mouse_ortholog/topology_records.jsonl topology_version $TOPO_V
norm $O/cyno_ortholog/topology_records.jsonl topology_version $TOPO_V
norm $P/human_canonical/topology_records.jsonl topology_version $TOPO_V
norm $I/human_isoforms/topology_records.jsonl topology_version $ISO_V
norm $O/ortholog_ecd_records.jsonl ortholog_ecd_version $OECD_V
norm $P/paralog_records.jsonl paralog_version $PARA_V

echo "== upload topology @ $TOPO_V (canon + ortho/para canonical + mouse + cyno) =="
uv run python scripts/upload_topology_to_d1.py --topology-version $TOPO_V \
  --cohorts-present human_canonical,mouse_ortholog,cyno_ortholog \
  --jsonl $C/human_canonical/topology_records.jsonl.norm \
  --jsonl $O/human_canonical/topology_records.jsonl.norm \
  --jsonl $O/mouse_ortholog/topology_records.jsonl.norm \
  --jsonl $O/cyno_ortholog/topology_records.jsonl.norm \
  --jsonl $P/human_canonical/topology_records.jsonl.norm $DRY $PUB

echo "== upload topology @ $ISO_V (isoforms) =="
uv run python scripts/upload_topology_to_d1.py --topology-version $ISO_V \
  --cohorts-present human_isoforms \
  --jsonl $I/human_isoforms/topology_records.jsonl.norm $DRY $PUB

echo "== upload ortholog ECD @ $OECD_V =="
uv run python scripts/upload_ortholog_ecd_to_d1.py --ortholog-ecd-version $OECD_V \
  --compara-release "Compara r112" \
  --jsonl $O/ortholog_ecd_records.jsonl.norm $DRY $PUB

echo "== upload paralogs @ $PARA_V =="
uv run python scripts/upload_paralogs_to_d1.py --paralog-version $PARA_V \
  --compara-release "Compara r112" \
  --jsonl $P/paralog_records.jsonl.norm $DRY $PUB

if [ "$DRYRUN" = "0" ]; then
  echo "== recompute paralog ECD similarity for the new close pairs =="
  uv run python scripts/compute_paralog_ecd_similarity.py --execute
  echo "== orphan check: latest versions must be UNCHANGED =="
  uv run python - <<'PY'
from accessible_surfaceome.env import load_env; load_env()
from accessible_surfaceome.agents.surfaceome_v1.d1_deterministic import (
    _latest_topology_version_for_cohort as L, _latest_ortholog_ecd_version as OE)
print("  human_canonical:", L("human_canonical"), "(expect topo_2026_05_16)")
print("  human_isoforms :", L("human_isoforms"), "(expect topo_2026_05_25)")
print("  mouse_ortholog :", L("mouse_ortholog"), "(expect topo_2026_05_16)")
print("  cyno_ortholog  :", L("cyno_ortholog"), "(expect topo_2026_05_16)")
print("  ortholog_ecd   :", OE(), "(expect orthologecd_topo_2026_05_16_idfix)")
PY
fi
echo "=== DONE (DRYRUN=$DRYRUN) ==="
