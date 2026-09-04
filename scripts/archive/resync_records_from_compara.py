"""Re-sync each record's ortholog + paralog ECD values to the corrected compara
tables — the source of truth a FRESH deep-dive reads.

Two gaps this closes after ``recompute_compara_ecd.py`` runs:

1. **Far paralogs** — the record backfill (``backfill_ecd_identity.py``) could only
   recompute variants carrying in-record topology (isoforms, orthologs, CLOSE
   paralogs). FAR paralogs store only the compara chip value, so their ECD stayed
   stale in ~880 records.
2. **Orthologs** — the backfill recomputed ortholog ECD from the record's stored
   *projected* topology, but ``_fetch_orthologs`` stores the compara **raw**-topology
   value (``ecd_pct_identity_to_human_canonical = ecd_pct``, straight from
   ``compara_ortholog_ecd``). That made the backfilled records run 1-4 pts above
   what a fresh deep-dive would produce. This resets them to the compara value.

Method: load the corrected ``compara_ortholog_ecd`` + ``compara_paralog`` into
dicts keyed by (human_acc, variant_acc), then for every ortholog / paralog entry
in each record set its ECD (+ similarity, + n_loops for paralogs) to the compara
value, and re-derive the 3 ``filters`` rollups. Isoforms + canonical topology are
untouched (isoforms aren't in compara; the backfill already fixed them). Additive
UPDATE of ``annotation_json``; idempotent (skip when already equal). Writes public
D1 + on-disk snapshots.

    uv run python scripts/resync_records_from_compara.py            # dry-run
    uv run python scripts/resync_records_from_compara.py --execute  # write
"""
from __future__ import annotations

import argparse
import json
import time
from dataclasses import dataclass

import httpx

from accessible_surfaceome.agents.surfaceome_v1.d1_deterministic import (
    _latest_ortholog_ecd_version,
    _latest_paralog_version,
)
from accessible_surfaceome.cloud.d1_client import D1Client, D1Config
from accessible_surfaceome.cloud.surface_annotation import _post, _public_config_from_env
from accessible_surfaceome.env import load_env
from accessible_surfaceome.paths import REPO_ROOT

DISK_DIRS = [REPO_ROOT / "viewer" / "public" / "data" / "surfaceome",
             REPO_ROOT / "data" / "annotations"]
_EPS = 1e-6


def _differs(a, b) -> bool:
    if a is None and b is None:
        return False
    if a is None or b is None:
        return True
    return abs(float(a) - float(b)) > _EPS


def _rederive_facets(rec) -> list[str]:
    """Re-derive filters.{max_paralog,mouse/cyno_ortholog}_ecd_pct_identity from the
    (now-synced) deterministic_features. Mirrors backfill_ecd_identity._rederive_facets."""
    det = rec.get("deterministic_features")
    filters = rec.get("filters")
    if not isinstance(det, dict) or not isinstance(filters, dict):
        return []
    changed: list[str] = []
    pvals = [p.get("ecd_pct_identity") for p in (det.get("paralogs") or [])
             if isinstance(p, dict) and p.get("ecd_pct_identity") is not None]
    new_max = max(pvals) if pvals else None
    if _differs(filters.get("max_paralog_ecd_pct_identity"), new_max):
        filters["max_paralog_ecd_pct_identity"] = new_max
        changed.append("max_paralog")
    orth = det.get("orthologs") or {}
    for sp, key in (("mouse", "mouse_ortholog_ecd_pct_identity"),
                    ("cynomolgus", "cyno_ortholog_ecd_pct_identity")):
        new_val = None
        for e in orth.get(sp) or []:
            if isinstance(e, dict) and e.get("is_canonical"):
                new_val = e.get("ecd_pct_identity_to_human_canonical")
                break
        if _differs(filters.get(key), new_val):
            filters[key] = new_val
            changed.append(key)
    return changed


def _post_retry(cfg, sql, params, *, client, attempts=6):
    last = None
    for i in range(attempts):
        try:
            return _post(cfg, sql, params, client=client)
        except (httpx.TransportError, httpx.HTTPStatusError) as e:
            last = e
            time.sleep(0.75 * (i + 1))
    assert last is not None
    raise last


def load_compara():
    """(ortho[(h,o)]=ecd, para[(h,p)]=(ecd,sim,nloops)) from corrected public compara."""
    oecd_v = _latest_ortholog_ecd_version()
    para_v = _latest_paralog_version()
    ortho: dict[tuple, float] = {}
    para: dict[tuple, tuple] = {}
    with D1Client(D1Config.from_env_public()) as d1:
        # keyset-page all rows by (human_uniprot_acc, ortholog_uniprot_acc)
        lasto = ("", "")
        while True:
            rows = d1.query(
                "SELECT human_uniprot_acc h, ortholog_uniprot_acc o, ecd_pct_identity e "
                "FROM compara_ortholog_ecd WHERE ortholog_ecd_version=? "
                "AND (human_uniprot_acc, ortholog_uniprot_acc) > (?,?) "
                "ORDER BY human_uniprot_acc, ortholog_uniprot_acc LIMIT 8000;",
                [oecd_v, lasto[0], lasto[1]])
            if not rows:
                break
            for r in rows:
                if r["h"] and r["o"]:
                    ortho[(r["h"], r["o"])] = r["e"]
            lasto = (rows[-1]["h"] or "", rows[-1]["o"] or "")
            if len(rows) < 8000:
                break
        lastp = ("", "")
        while True:
            rows = d1.query(
                "SELECT human_uniprot_acc h, paralog_uniprot_acc p, ecd_pct_identity e, "
                "ecd_pct_similarity s, n_ecd_loops_compared n FROM compara_paralog "
                "WHERE paralog_version=? AND (human_uniprot_acc, paralog_uniprot_acc) > (?,?) "
                "ORDER BY human_uniprot_acc, paralog_uniprot_acc LIMIT 8000;",
                [para_v, lastp[0], lastp[1]])
            if not rows:
                break
            for r in rows:
                if r["h"] and r["p"]:
                    para[(r["h"], r["p"])] = (r["e"], r["s"], r["n"])
            lastp = (rows[-1]["h"] or "", rows[-1]["p"] or "")
            if len(rows) < 8000:
                break
    return ortho, para


@dataclass
class Plan:
    changed: bool = False
    ortholog: int = 0
    paralog: int = 0
    facets: int = 0


def _human_acc(rec) -> str | None:
    det = rec.get("deterministic_features") or {}
    ct = det.get("canonical_topology") or {}
    return ct.get("uniprot_acc") or (rec.get("gene") or {}).get("uniprot_acc")


def plan_and_apply(rec, ortho, para) -> Plan:
    plan = Plan()
    det = rec.get("deterministic_features")
    if not isinstance(det, dict):
        return plan
    h = _human_acc(rec)
    if not h:
        return plan
    orth = det.get("orthologs") or {}
    for sp in ("mouse", "cynomolgus"):
        for e in orth.get(sp) or []:
            if not isinstance(e, dict):
                continue
            new = ortho.get((h, e.get("ortholog_uniprot_acc")))
            if new is None:
                continue
            if _differs(e.get("ecd_pct_identity_to_human_canonical"), new):
                e["ecd_pct_identity_to_human_canonical"] = new
                e["ecd_pct_similarity_to_human_canonical"] = new  # mirror (schema convention)
                plan.ortholog += 1
                plan.changed = True
    for p in det.get("paralogs") or []:
        if not isinstance(p, dict):
            continue
        hit = para.get((h, p.get("paralog_uniprot_acc")))
        if hit is None:
            continue
        ecd, _sim, _nl = hit
        # ParalogEntry carries ONLY ecd_pct_identity (extra="forbid"); never
        # write ecd_pct_similarity / n_ecd_loops_compared onto a paralog.
        if _differs(p.get("ecd_pct_identity"), ecd):
            p["ecd_pct_identity"] = ecd
            plan.paralog += 1
            plan.changed = True
    facets = _rederive_facets(rec)
    if facets:
        plan.facets = len(facets)
        plan.changed = True
    return plan


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--execute", action="store_true")
    ap.add_argument("--skip-disk", action="store_true")
    ap.add_argument("--skip-d1", action="store_true")
    args = ap.parse_args()
    load_env()

    print(f"=== record re-sync from corrected compara [{'EXECUTE' if args.execute else 'DRY-RUN'}] ===")
    ortho, para = load_compara()
    print(f"loaded compara: {len(ortho)} ortholog pairs, {len(para)} paralog pairs")

    tot_rec = tot_o = tot_p = tot_f = 0
    if not args.skip_disk:
        for d in DISK_DIRS:
            if not d.exists():
                continue
            for path in sorted(d.glob("*.json")):
                try:
                    rec = json.loads(path.read_text())
                except (OSError, json.JSONDecodeError):
                    continue
                plan = plan_and_apply(rec, ortho, para)
                if not plan.changed:
                    continue
                tot_rec += 1
                tot_o += plan.ortholog
                tot_p += plan.paralog
                tot_f += plan.facets
                print(f"  {'patched' if args.execute else 'would patch'} disk {path.name}: "
                      f"{plan.ortholog} ortholog, {plan.paralog} paralog, {plan.facets} facet")
                if args.execute:
                    path.write_text(json.dumps(rec, indent=2, ensure_ascii=False) + "\n")

    if not args.skip_d1:
        cfg = _public_config_from_env()
        if cfg is not None:
            with httpx.Client(timeout=60) as client:
                rows = _post_retry(cfg, "SELECT gene_symbol, schema_version, annotation_json "
                                        "FROM surface_annotation", [], client=client)["result"][0]["results"]
                for r in rows:
                    try:
                        rec = json.loads(r["annotation_json"])
                    except (json.JSONDecodeError, KeyError, TypeError):
                        continue
                    plan = plan_and_apply(rec, ortho, para)
                    if not plan.changed:
                        continue
                    tot_rec += 1
                    tot_o += plan.ortholog
                    tot_p += plan.paralog
                    tot_f += plan.facets
                    print(f"  {'patched' if args.execute else 'would patch'} D1 {r['gene_symbol']}: "
                          f"{plan.ortholog} ortholog, {plan.paralog} paralog, {plan.facets} facet")
                    if args.execute:
                        _post_retry(cfg, "UPDATE surface_annotation SET annotation_json=? "
                                         "WHERE gene_symbol=? AND schema_version=?",
                                    [json.dumps(rec, separators=(",", ":")), r["gene_symbol"], r["schema_version"]],
                                    client=client)

    print(f"\n{'patched' if args.execute else 'would patch'}: {tot_rec} record(s) "
          f"({tot_o} ortholog, {tot_p} paralog values, {tot_f} facets)")
    if not args.execute:
        print("(dry-run — re-run with --execute)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
