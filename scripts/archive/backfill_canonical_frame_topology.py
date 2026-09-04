#!/usr/bin/env python
"""Backfill ``per_residue_topology_canonical_frame`` onto existing records.

The field (schema-optional; added to ``IsoformTopology`` / ``OrthologEntry`` /
``ParalogEntry``) carries each sequence variant's per-residue topology re-indexed
onto the CANONICAL coordinate axis, so the viewer's ``IsoformsCard`` can render
every variant's topology bar on one shared axis and line homologous features up
(see ``merge/canonical_frame_topology.py``). New annotations get it from the
deterministic-features builder (``d1_deterministic._project_canonical_frame``);
this script computes it for records that predate the field.

It is a DETERMINISTIC function of data ALREADY IN each record — the canonical
sequence (``deterministic_features.canonical_topology.sequence``) plus each
variant's own ``sequence`` + ``per_residue_topology`` — so **no LLM call and no
network fetch** are needed. The projection reuses the same BLOSUM62 aligner the
isoform-identity numbers already flow through.

Covers all THREE variant types:
  * ``deterministic_features.isoform_topologies[]``
  * ``deterministic_features.orthologs.{mouse,cynomolgus}[]``
  * ``deterministic_features.paralogs[]`` (only the close paralogs that carry
    topology + sequence; far / ECD-less / chip-strip paralogs stay ``None``)

For each such variant that has BOTH a ``sequence`` and a ``per_residue_topology``
(and whose record has a canonical sequence), it sets the field; variants missing
either input are left ``None`` (the viewer falls back to raw length-scaling).

Idempotent: a variant whose stored value already equals the freshly-computed
projection is skipped, so re-running is a no-op.

Targets (each independently skippable):
  * on-disk snapshots — ``viewer/public/data/surfaceome/*.json`` +
    ``data/annotations/*.json`` (the in-tree source of truth / SSG fallback);
  * public D1 ``surface_annotation.annotation_json`` — what the Worker serves
    (the live site). Patched in place with an additive ``UPDATE`` (the record's
    ``record_generated_at`` is unchanged, and only a new field is added, so this
    neither trips the publish staleness/regression guards nor needs them);
  * private D1 ``deep_dive_run.record_json`` — agent-run history (opt-in via
    ``--include-deep-dive-run`` since it's the private ``surfaceome_agents`` DB).

Dry-run by default — reports how many records / variants WOULD be patched,
broken down by variant type. Pass ``--execute`` to write.

    uv run python scripts/backfill_canonical_frame_topology.py            # dry-run
    uv run python scripts/backfill_canonical_frame_topology.py --execute  # write

NOTE: ``--execute`` mutates production D1. This script is intentionally shipped
dry-run-by-default; a human runs the write.
"""
from __future__ import annotations

import argparse
import json
from dataclasses import dataclass, field
from typing import Any

import httpx

from accessible_surfaceome.cloud.surface_annotation import (
    _post,
    _public_config_from_env,
)
from accessible_surfaceome.env import load_env
from accessible_surfaceome.merge.canonical_frame_topology import (
    project_topology_onto_canonical_frame,
)
from accessible_surfaceome.paths import REPO_ROOT

DISK_DIRS = [
    REPO_ROOT / "viewer" / "public" / "data" / "surfaceome",
    REPO_ROOT / "data" / "annotations",
]

FIELD = "per_residue_topology_canonical_frame"


@dataclass
class Counts:
    """Per-run tally, split by variant type."""

    records_touched: int = 0
    isoform: int = 0
    ortholog: int = 0
    paralog: int = 0

    def variants(self) -> int:
        return self.isoform + self.ortholog + self.paralog

    def merge(self, other: Counts) -> None:
        self.records_touched += other.records_touched
        self.isoform += other.isoform
        self.ortholog += other.ortholog
        self.paralog += other.paralog


@dataclass
class RecordPlan:
    """What a single record's backfill would change (before writing)."""

    changed: bool = False
    isoform: int = 0
    ortholog: int = 0
    paralog: int = 0
    # Per-variant-type list of (label, projected-or-None) — only for the
    # variants whose stored value differs, so the caller can apply them.
    detail: list[str] = field(default_factory=list)


def _canonical_sequence(rec: dict[str, Any]) -> str:
    det = rec.get("deterministic_features") or {}
    ct = det.get("canonical_topology") or {}
    return ct.get("sequence") or ""


def _projected_for(variant: dict[str, Any], canon_seq: str) -> str | None:
    """The canonical-frame projection for one variant, or None when it can't
    be computed (missing canonical/variant sequence or topology)."""
    seq = variant.get("sequence")
    topo = variant.get("per_residue_topology")
    if not canon_seq or not seq or not topo:
        return None
    return project_topology_onto_canonical_frame(
        canonical_sequence=canon_seq,
        variant_sequence=seq,
        variant_topology=topo,
    )


def plan_record(rec: dict[str, Any]) -> RecordPlan:
    """Compute what would change for one record, mutating nothing.

    A variant is counted as a change only when its freshly-projected value
    differs from what's stored (idempotency). Note that a variant which
    legitimately projects to ``None`` (no sequence/topology) and already
    stores ``None`` is NOT a change.
    """
    plan = RecordPlan()
    det = rec.get("deterministic_features")
    if not isinstance(det, dict):
        return plan
    canon_seq = _canonical_sequence(rec)

    def consider(variant: dict[str, Any], kind: str, label: str) -> None:
        if not isinstance(variant, dict):
            return
        projected = _projected_for(variant, canon_seq)
        # Only a change when the value actually differs from what's stored.
        if variant.get(FIELD) == projected:
            return
        # Don't churn a record to write None over an absent key — that's not a
        # meaningful backfill (the field is optional and defaults to None).
        if projected is None and FIELD not in variant:
            return
        plan.changed = True
        if kind == "isoform":
            plan.isoform += 1
        elif kind == "ortholog":
            plan.ortholog += 1
        else:
            plan.paralog += 1
        shown = "None" if projected is None else f"len={len(projected)}"
        plan.detail.append(f"{kind}:{label} -> {shown}")

    for iso in det.get("isoform_topologies") or []:
        consider(iso, "isoform", (iso or {}).get("isoform_id") or "?")
    orth = det.get("orthologs") or {}
    for species in ("mouse", "cynomolgus"):
        for e in orth.get(species) or []:
            consider(e, "ortholog", (e or {}).get("ortholog_uniprot_acc") or "?")
    for p in det.get("paralogs") or []:
        consider(p, "paralog", (p or {}).get("paralog_uniprot_acc") or "?")
    return plan


def apply_record(rec: dict[str, Any]) -> None:
    """Write the projection onto every projectable variant, in place.

    Sets the field only where a variant has sequence + topology (and the
    record has a canonical sequence); leaves it untouched otherwise so we
    don't spray ``None`` across the record. Mirrors ``plan_record`` — the two
    must agree on which variants get written.
    """
    det = rec.get("deterministic_features")
    if not isinstance(det, dict):
        return
    canon_seq = _canonical_sequence(rec)

    def write(variant: dict[str, Any]) -> None:
        if not isinstance(variant, dict):
            return
        projected = _projected_for(variant, canon_seq)
        if projected is None and FIELD not in variant:
            return
        variant[FIELD] = projected

    for iso in det.get("isoform_topologies") or []:
        write(iso)
    orth = det.get("orthologs") or {}
    for species in ("mouse", "cynomolgus"):
        for e in orth.get(species) or []:
            write(e)
    for p in det.get("paralogs") or []:
        write(p)


def _print_plan(location: str, plan: RecordPlan, *, execute: bool) -> None:
    verb = "patched" if execute else "would patch"
    print(
        f"  {verb} {location}: "
        f"{plan.isoform} iso, {plan.ortholog} ortholog, {plan.paralog} paralog"
    )


# --------------------------------------------------------------------------- #
# Disk snapshots
# --------------------------------------------------------------------------- #
def backfill_disk(*, execute: bool, genes: set[str] | None = None) -> Counts:
    counts = Counts()
    for d in DISK_DIRS:
        if not d.exists():
            print(f"  (skip, missing) {d.relative_to(REPO_ROOT)}")
            continue
        for path in sorted(d.glob("*.json")):
            if genes is not None and path.stem.upper() not in genes:
                continue
            try:
                rec = json.loads(path.read_text())
            except (OSError, json.JSONDecodeError) as exc:
                print(f"  (skip, bad JSON) {path.name}: {exc}")
                continue
            plan = plan_record(rec)
            if not plan.changed:
                continue
            counts.records_touched += 1
            counts.isoform += plan.isoform
            counts.ortholog += plan.ortholog
            counts.paralog += plan.paralog
            _print_plan(str(path.relative_to(REPO_ROOT)), plan, execute=execute)
            if execute:
                apply_record(rec)
                path.write_text(json.dumps(rec, indent=2, ensure_ascii=False) + "\n")
    return counts


# --------------------------------------------------------------------------- #
# Public D1 (surface_annotation.annotation_json) — the live site
# --------------------------------------------------------------------------- #
def backfill_public_d1(*, execute: bool, genes: set[str] | None = None) -> Counts:
    counts = Counts()
    cfg = _public_config_from_env()
    if cfg is None:
        print("  (skip) public D1 creds not set (CLOUDFLARE_*)")
        return counts
    # When restricted to a gene set, filter server-side so we don't pull the
    # whole (wide annotation_json) table over the wire / trip D1's memory cap.
    where, params = "", []
    if genes:
        where = f" WHERE gene_symbol IN ({','.join('?' * len(genes))})"
        params = sorted(genes)
    with httpx.Client(timeout=60) as client:
        rows = _post(
            cfg,
            "SELECT gene_symbol, schema_version, annotation_json "
            f"FROM surface_annotation{where}",
            params,
            client=client,
        )["result"][0]["results"]
        for r in rows:
            try:
                rec = json.loads(r["annotation_json"])
            except (json.JSONDecodeError, KeyError, TypeError) as exc:
                print(f"  (skip, bad JSON) {r.get('gene_symbol')}: {exc}")
                continue
            plan = plan_record(rec)
            if not plan.changed:
                continue
            counts.records_touched += 1
            counts.isoform += plan.isoform
            counts.ortholog += plan.ortholog
            counts.paralog += plan.paralog
            _print_plan(
                f"D1 {r['gene_symbol']}@{r['schema_version']}",
                plan,
                execute=execute,
            )
            if execute:
                apply_record(rec)
                # Additive in-place patch — the record's identity
                # (gene_symbol, schema_version, record_generated_at) is
                # unchanged, so this can't trip the publish staleness /
                # regression guards; a bare UPDATE is the minimal write.
                _post(
                    cfg,
                    "UPDATE surface_annotation SET annotation_json = ? "
                    "WHERE gene_symbol = ? AND schema_version = ?",
                    [
                        json.dumps(rec, separators=(",", ":")),
                        r["gene_symbol"],
                        r["schema_version"],
                    ],
                    client=client,
                )
    return counts


# --------------------------------------------------------------------------- #
# Private D1 (deep_dive_run.record_json) — agent-run history, opt-in
# --------------------------------------------------------------------------- #
def backfill_deep_dive_run(*, execute: bool, genes: set[str] | None = None) -> Counts:
    counts = Counts()
    # Local import so the public-only path doesn't require the private DB env.
    from accessible_surfaceome.cloud.d1_client import D1Client, D1Config, D1Error

    try:
        cfg = D1Config.from_env()  # private surfaceome_agents DB
    except D1Error as exc:
        print(f"  (skip) private D1 creds not set: {exc}")
        return counts
    where, params = "", []
    if genes:
        where = f" WHERE gene_symbol IN ({','.join('?' * len(genes))})"
        params = sorted(genes)
    with D1Client(config=cfg) as d1:
        rows = d1.query(
            f"SELECT id, gene_symbol, record_json FROM deep_dive_run{where}", params
        )
        for r in rows:
            try:
                rec = json.loads(r["record_json"])
            except (json.JSONDecodeError, KeyError, TypeError) as exc:
                print(f"  (skip, bad JSON) deep_dive_run id={r.get('id')}: {exc}")
                continue
            plan = plan_record(rec)
            if not plan.changed:
                continue
            counts.records_touched += 1
            counts.isoform += plan.isoform
            counts.ortholog += plan.ortholog
            counts.paralog += plan.paralog
            _print_plan(
                f"deep_dive_run id={r['id']} ({r.get('gene_symbol')})",
                plan,
                execute=execute,
            )
            if execute:
                apply_record(rec)
                d1.query(
                    "UPDATE deep_dive_run SET record_json = ? WHERE id = ?",
                    [json.dumps(rec, separators=(",", ":")), r["id"]],
                )
    return counts


def main() -> int:
    ap = argparse.ArgumentParser(
        description="Backfill per_residue_topology_canonical_frame onto records."
    )
    ap.add_argument(
        "--execute",
        action="store_true",
        help="Write changes (default: dry-run). NOTE: mutates production D1.",
    )
    ap.add_argument(
        "--gene",
        action="append",
        metavar="SYMBOL",
        help=(
            "Limit the backfill to one or more gene symbols (repeatable, "
            "case-insensitive). Targets a single-gene patch/preview before the "
            "full run, e.g. --gene CD63."
        ),
    )
    ap.add_argument("--skip-disk", action="store_true", help="Skip on-disk snapshots.")
    ap.add_argument(
        "--skip-d1", action="store_true", help="Skip public D1 surface_annotation."
    )
    ap.add_argument(
        "--include-deep-dive-run",
        action="store_true",
        help=(
            "Also patch private D1 deep_dive_run.record_json (agent-run "
            "history). Off by default — that's the private surfaceome_agents DB."
        ),
    )
    args = ap.parse_args()
    load_env()

    genes = {g.upper() for g in args.gene} if args.gene else None

    mode = "EXECUTE" if args.execute else "DRY-RUN"
    print(f"=== canonical-frame topology backfill [{mode}] ===")
    if genes:
        print(f"  (restricted to {len(genes)} gene(s): {', '.join(sorted(genes))})")

    total = Counts()

    print("disk (viewer snapshots + data/annotations):")
    if args.skip_disk:
        print("  (skipped)")
    else:
        total.merge(backfill_disk(execute=args.execute, genes=genes))

    print("public D1 surface_annotation:")
    if args.skip_d1:
        print("  (skipped)")
    else:
        total.merge(backfill_public_d1(execute=args.execute, genes=genes))

    if args.include_deep_dive_run:
        print("private D1 deep_dive_run:")
        total.merge(backfill_deep_dive_run(execute=args.execute, genes=genes))

    verb = "patched" if args.execute else "would patch"
    print()
    print(
        f"{verb}: {total.records_touched} record(s), {total.variants()} variant(s) "
        f"({total.isoform} isoform, {total.ortholog} ortholog, {total.paralog} paralog)"
    )
    if not args.execute:
        print("(dry-run — re-run with --execute to apply; --execute mutates production D1)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
