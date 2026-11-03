"""Recompute every published record's ECD %identity with the fixed metric,
find variants whose value moves materially, and check whether the agent's PROSE
cited the OLD (wrong) number. Read-only — no writes."""
import json
import re

from accessible_surfaceome.cloud.d1_client import D1Client, D1Config
from accessible_surfaceome.env import load_env
from accessible_surfaceome.merge.paralog_ecd_identity import compute_ecd_identity

load_env()
DELTA = 15.0  # points

with D1Client(D1Config.from_env_public()) as pub:
    rows = pub.query("SELECT gene_symbol, annotation_json FROM surface_annotation;")


def recompute(ctopo, cseq, vtopo, vseq):
    if not (ctopo and cseq and vtopo and vseq):
        return None
    r = compute_ecd_identity(
        human_topology=ctopo, human_sequence=cseq,
        paralog_topology=vtopo, paralog_sequence=vseq,
    )
    return r.ecd_pct_identity


PROSE_KEYS = ("executive_summary", "biological_context", "accessibility_risks",
              "surface_evidence")
ECD_TALK = re.compile(
    r"ecd|extracellular domain|%\s*identit|percent identit|cross[- ]?react|"
    r"conserv|specificit|off[- ]?target|multitarget", re.I)

n_material = 0
n_prose_ecd = 0
n_old_number_cited = 0
examples = []  # (sym, top_label, old, new, cites_old, ecd_talk)

for r in rows:
    rec = json.loads(r["annotation_json"])
    det = rec.get("deterministic_features") or {}
    ct = det.get("canonical_topology") or {}
    cseq, ctopo = ct.get("sequence"), ct.get("per_residue_topology")
    changes = []  # (label, old, new)

    for iso in det.get("isoform_topologies") or []:
        new = recompute(ctopo, cseq, iso.get("per_residue_topology"), iso.get("sequence"))
        old = iso.get("ecd_pct_identity_to_canonical")
        if old is not None and new is not None and abs(new - old) >= DELTA:
            changes.append((iso.get("isoform_id") or "iso", old, new))
    orth = det.get("orthologs") or {}
    for sp in ("mouse", "cynomolgus"):
        for e in orth.get(sp) or []:
            new = recompute(ctopo, cseq, e.get("per_residue_topology"), e.get("sequence"))
            old = e.get("ecd_pct_identity_to_human_canonical")
            if old is not None and new is not None and abs(new - old) >= DELTA:
                changes.append((e.get("ortholog_uniprot_acc") or sp, old, new))
    for p in det.get("paralogs") or []:
        new = recompute(ctopo, cseq, p.get("per_residue_topology"), p.get("sequence"))
        old = p.get("ecd_pct_identity")
        if old is not None and new is not None and abs(new - old) >= DELTA:
            changes.append((p.get("paralog_symbol") or "paralog", old, new))

    if not changes:
        continue
    n_material += 1
    prose = " ".join(json.dumps(rec.get(k) or {}) for k in PROSE_KEYS)
    ecd_talk = bool(ECD_TALK.search(prose))
    # Does the prose cite the OLD number (rounded) next to a % sign?
    cites_old = any(
        re.search(rf"(?<!\d){round(old)}(\.\d+)?\s*%", prose) for _, old, _ in changes
    )
    if ecd_talk:
        n_prose_ecd += 1
    if cites_old:
        n_old_number_cited += 1
    top = max(changes, key=lambda c: abs(c[2] - c[1]))
    examples.append((r["gene_symbol"], top[0], top[1], top[2], cites_old, ecd_talk))

examples.sort(key=lambda x: abs(x[3] - x[2]), reverse=True)
print(f"records scanned: {len(rows)}")
print(f"genes with >={DELTA:.0f}-pt ECD delta on a record-recomputable variant: {n_material}")
print(f"  ...whose prose discusses ECD/specificity/conservation at all: {n_prose_ecd}")
print(f"  ...whose prose CITES the old number next to '%' (prose factually wrong): {n_old_number_cited}")
print("\ntop 20 by delta magnitude (variant, old% -> new%, cites_old, ecd_talk):")
for sym, lab, old, new, co, et in examples[:20]:
    print(f"  {sym:<12} {lab:<12} {old:5.1f}% -> {new:5.1f}%   cites_old={co}  ecd_talk={et}")
