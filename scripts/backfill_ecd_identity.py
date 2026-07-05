#!/usr/bin/env python
"""Backfill corrected ECD %identity / %similarity onto existing records.

The homology-aligned ``compute_ecd_identity`` (see
``merge/paralog_ecd_identity.py``) fixes the extracellular-loop index-mispairing
bug. This recomputes, for every sequence variant a record already carries, its
ECD identity/similarity against the record's OWN canonical sequence + topology —
so it's a DETERMINISTIC function of data already in each record: **no LLM call
and no D1-table fetch needed** (the number is a pure function of the stored
sequences + topology).

Covers the three variant kinds and their record field names:
  * ``isoform_topologies[]``  → ``ecd_pct_identity_to_canonical`` / ``ecd_pct_similarity_to_canonical``
  * ``orthologs.{mouse,cynomolgus}[]`` → ``ecd_pct_identity_to_human_canonical`` / ``..._similarity_...``
  * ``paralogs[]`` (close paralogs carrying topology + sequence) → ``ecd_pct_identity`` / ``ecd_pct_similarity``

A variant is only touched when it has BOTH a ``sequence`` and a
``per_residue_topology`` (and the record has a canonical sequence + topology);
otherwise its stored value came from a D1 source table (``compara_*``) and is
corrected by the companion cohort-table recompute, not here.

Idempotent: a variant whose stored value already equals the freshly-computed
value (to 6 dp) is skipped. Additive in-place ``UPDATE`` of ``annotation_json``
— identity (gene_symbol, schema_version, record_generated_at) unchanged — so it
neither trips the publish staleness/regression guards nor needs them.

Dry-run by default; ``--execute`` mutates production D1.

    uv run python scripts/backfill_ecd_identity.py            # dry-run
    uv run python scripts/backfill_ecd_identity.py --execute  # write
"""
from __future__ import annotations

import argparse
import json
from dataclasses import dataclass, field
from typing import Any

import httpx

from accessible_surfaceome.cloud.surface_annotation import _post, _public_config_from_env
from accessible_surfaceome.env import load_env
from accessible_surfaceome.merge.paralog_ecd_identity import compute_ecd_identity
from accessible_surfaceome.paths import REPO_ROOT

DISK_DIRS = [
    REPO_ROOT / "viewer" / "public" / "data" / "surfaceome",
    REPO_ROOT / "data" / "annotations",
]
# (identity_field, similarity_field) per variant kind.
ISO_FIELDS = ("ecd_pct_identity_to_canonical", "ecd_pct_similarity_to_canonical")
ORTH_FIELDS = ("ecd_pct_identity_to_human_canonical", "ecd_pct_similarity_to_human_canonical")
PARA_FIELDS = ("ecd_pct_identity", "ecd_pct_similarity")
_EPS = 1e-6


@dataclass
class Counts:
    records_touched: int = 0
    isoform: int = 0
    ortholog: int = 0
    paralog: int = 0

    def variants(self) -> int:
        return self.isoform + self.ortholog + self.paralog

    def merge(self, o: Counts) -> None:
        self.records_touched += o.records_touched
        self.isoform += o.isoform
        self.ortholog += o.ortholog
        self.paralog += o.paralog


@dataclass
class RecordPlan:
    changed: bool = False
    isoform: int = 0
    ortholog: int = 0
    paralog: int = 0
    detail: list[str] = field(default_factory=list)


def _canon(rec: dict[str, Any]) -> tuple[str, str]:
    ct = (rec.get("deterministic_features") or {}).get("canonical_topology") or {}
    return ct.get("sequence") or "", ct.get("per_residue_topology") or ""


def _recompute(variant: dict[str, Any], cseq: str, ctopo: str):
    seq, topo = variant.get("sequence"), variant.get("per_residue_topology")
    if not (cseq and ctopo and seq and topo):
        return None
    r = compute_ecd_identity(
        human_topology=ctopo, human_sequence=cseq,
        paralog_topology=topo, paralog_sequence=seq,
    )
    return r.ecd_pct_identity, r.ecd_pct_similarity


def _differs(old, new) -> bool:
    if old is None and new is None:
        return False
    if old is None or new is None:
        return True
    return abs(float(old) - float(new)) > _EPS


def _apply_one(variant: dict, cseq: str, ctopo: str, ident_f: str, sim_f: str,
               *, write: bool) -> bool:
    rc = _recompute(variant, cseq, ctopo)
    if rc is None:
        return False  # value comes from a D1 table, not recomputable here
    new_id, new_sim = rc
    if not _differs(variant.get(ident_f), new_id) and not _differs(variant.get(sim_f), new_sim):
        return False
    if write:
        variant[ident_f] = new_id
        variant[sim_f] = new_sim
    return True


def plan_and_apply(rec: dict[str, Any], *, write: bool) -> RecordPlan:
    plan = RecordPlan()
    det = rec.get("deterministic_features")
    if not isinstance(det, dict):
        return plan
    cseq, ctopo = _canon(rec)

    for iso in det.get("isoform_topologies") or []:
        if isinstance(iso, dict) and _apply_one(iso, cseq, ctopo, *ISO_FIELDS, write=write):
            plan.isoform += 1
            plan.changed = True
    orth = det.get("orthologs") or {}
    for sp in ("mouse", "cynomolgus"):
        for e in orth.get(sp) or []:
            if isinstance(e, dict) and _apply_one(e, cseq, ctopo, *ORTH_FIELDS, write=write):
                plan.ortholog += 1
                plan.changed = True
    for p in det.get("paralogs") or []:
        if isinstance(p, dict) and _apply_one(p, cseq, ctopo, *PARA_FIELDS, write=write):
            plan.paralog += 1
            plan.changed = True
    return plan


def backfill_disk(*, execute: bool) -> Counts:
    counts = Counts()
    for d in DISK_DIRS:
        if not d.exists():
            continue
        for path in sorted(d.glob("*.json")):
            try:
                rec = json.loads(path.read_text())
            except (OSError, json.JSONDecodeError):
                continue
            # Plan on a copy first so a dry-run doesn't mutate.
            plan = plan_and_apply(rec, write=execute)
            if not plan.changed:
                continue
            counts.records_touched += 1
            counts.isoform += plan.isoform
            counts.ortholog += plan.ortholog
            counts.paralog += plan.paralog
            print(f"  {'patched' if execute else 'would patch'} {path.name}: "
                  f"{plan.isoform} iso, {plan.ortholog} ortholog, {plan.paralog} paralog")
            if execute:
                path.write_text(json.dumps(rec, indent=2, ensure_ascii=False) + "\n")
    return counts


def backfill_public_d1(*, execute: bool) -> Counts:
    counts = Counts()
    cfg = _public_config_from_env()
    if cfg is None:
        print("  (skip) public D1 creds not set")
        return counts
    with httpx.Client(timeout=60) as client:
        rows = _post(cfg,
            "SELECT gene_symbol, schema_version, annotation_json FROM surface_annotation",
            [], client=client)["result"][0]["results"]
        for r in rows:
            try:
                rec = json.loads(r["annotation_json"])
            except (json.JSONDecodeError, KeyError, TypeError):
                continue
            plan = plan_and_apply(rec, write=execute)
            if not plan.changed:
                continue
            counts.records_touched += 1
            counts.isoform += plan.isoform
            counts.ortholog += plan.ortholog
            counts.paralog += plan.paralog
            print(f"  {'patched' if execute else 'would patch'} D1 {r['gene_symbol']}: "
                  f"{plan.isoform} iso, {plan.ortholog} ortholog, {plan.paralog} paralog")
            if execute:
                _post(cfg,
                    "UPDATE surface_annotation SET annotation_json=? "
                    "WHERE gene_symbol=? AND schema_version=?",
                    [json.dumps(rec, separators=(",", ":")), r["gene_symbol"], r["schema_version"]],
                    client=client)
    return counts


def main() -> int:
    ap = argparse.ArgumentParser(description="Backfill corrected ECD identity/similarity onto records.")
    ap.add_argument("--execute", action="store_true", help="Write (default dry-run). Mutates production D1.")
    ap.add_argument("--skip-disk", action="store_true")
    ap.add_argument("--skip-d1", action="store_true")
    args = ap.parse_args()
    load_env()

    print(f"=== ECD-identity record backfill [{'EXECUTE' if args.execute else 'DRY-RUN'}] ===")
    total = Counts()
    print("disk snapshots:")
    if not args.skip_disk:
        total.merge(backfill_disk(execute=args.execute))
    print("public D1 surface_annotation:")
    if not args.skip_d1:
        total.merge(backfill_public_d1(execute=args.execute))
    print(f"\n{'patched' if args.execute else 'would patch'}: {total.records_touched} record(s), "
          f"{total.variants()} variant(s) "
          f"({total.isoform} isoform, {total.ortholog} ortholog, {total.paralog} paralog)")
    if not args.execute:
        print("(dry-run — re-run with --execute; --execute mutates production D1)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
