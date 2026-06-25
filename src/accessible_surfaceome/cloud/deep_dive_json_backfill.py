"""Backfill missing private ``deep_dive_run`` parents from JSON artifacts.

The Modal sweep writes the canonical per-gene record to the Volume before it
mirrors to private D1. If the JSON write succeeds but the private D1 parent
insert fails entirely, resume will not see the gene and a rerun can re-spend.

This module covers that parent-missing case. Existing parent rows are left
alone; incomplete children for existing parents are repaired by
``deep_dive_audit.backfill_from_record`` / ``scripts/audit_deep_dive_orphans.py``.
"""

from __future__ import annotations

import csv
from dataclasses import dataclass
from pathlib import Path

from pydantic import ValidationError

from accessible_surfaceome.cloud.d1_client import D1Client
from accessible_surfaceome.cloud.deep_dive_upload import D1DeepDiveSink
from accessible_surfaceome.tools._shared.models import SurfaceomeRecord


@dataclass(frozen=True)
class BackfillMetadata:
    cost_usd: float = 0.0
    latency_s: float = 0.0
    n_tool_calls: int = 0


@dataclass(frozen=True)
class JsonBackfillCandidate:
    path: Path
    gene_symbol: str | None
    record: SurfaceomeRecord | None
    action: str
    error: str | None = None


@dataclass(frozen=True)
class JsonBackfillOutcome:
    path: Path
    gene_symbol: str | None
    action: str
    error: str | None = None


def run_dir(annotations_dir: Path, run_id: str) -> Path:
    return annotations_dir / run_id


def load_metadata_tsv(path: Path | None) -> dict[str, BackfillMetadata]:
    """Read optional per-gene cost/latency metadata.

    Expected columns: ``gene_symbol`` and any of ``cost_usd``, ``latency_s``,
    ``n_tool_calls``. Missing numeric fields default to zero.
    """

    if path is None:
        return {}
    out: dict[str, BackfillMetadata] = {}
    with path.open(newline="") as fh:
        reader = csv.DictReader(fh, delimiter="\t")
        if "gene_symbol" not in (reader.fieldnames or []):
            raise ValueError(f"{path} must include a gene_symbol column")
        for row in reader:
            symbol = (row.get("gene_symbol") or "").strip()
            if not symbol:
                continue
            out[symbol] = BackfillMetadata(
                cost_usd=_safe_float(row.get("cost_usd")),
                latency_s=_safe_float(row.get("latency_s")),
                n_tool_calls=_safe_int(row.get("n_tool_calls")),
            )
    return out


def load_candidates(path: Path) -> list[JsonBackfillCandidate]:
    """Load every ``*.json`` record from one run directory."""

    if not path.exists():
        return [
            JsonBackfillCandidate(
                path=path,
                gene_symbol=None,
                record=None,
                action="run_dir_missing",
                error=f"{path} does not exist",
            )
        ]
    out: list[JsonBackfillCandidate] = []
    for json_path in sorted(path.glob("*.json")):
        try:
            record = SurfaceomeRecord.model_validate_json(json_path.read_text())
        except ValidationError as exc:
            out.append(
                JsonBackfillCandidate(
                    path=json_path,
                    gene_symbol=json_path.stem,
                    record=None,
                    action="json_invalid",
                    error=str(exc),
                )
            )
            continue
        symbol = record.gene.hgnc_symbol
        out.append(
            JsonBackfillCandidate(
                path=json_path,
                gene_symbol=symbol,
                record=record,
                action="loaded",
            )
        )
    return out


def existing_private_genes(d1: D1Client, run_id: str) -> set[str]:
    rows = d1.query(
        "SELECT gene_symbol FROM deep_dive_run WHERE run_id = ?;",
        [run_id],
    )
    return {str(r["gene_symbol"]) for r in rows}


def plan_json_backfill(
    candidates: list[JsonBackfillCandidate],
    existing: set[str],
) -> list[JsonBackfillOutcome]:
    outcomes: list[JsonBackfillOutcome] = []
    for candidate in candidates:
        if candidate.record is None or candidate.gene_symbol is None:
            outcomes.append(
                JsonBackfillOutcome(
                    path=candidate.path,
                    gene_symbol=candidate.gene_symbol,
                    action=candidate.action,
                    error=candidate.error,
                )
            )
            continue
        if candidate.gene_symbol in existing:
            outcomes.append(
                JsonBackfillOutcome(
                    path=candidate.path,
                    gene_symbol=candidate.gene_symbol,
                    action="existing",
                )
            )
        else:
            outcomes.append(
                JsonBackfillOutcome(
                    path=candidate.path,
                    gene_symbol=candidate.gene_symbol,
                    action="would_backfill",
                )
            )
    return outcomes


def execute_json_backfill(
    *,
    run_id: str,
    candidates: list[JsonBackfillCandidate],
    existing: set[str],
    metadata: dict[str, BackfillMetadata],
    d1: D1Client,
) -> list[JsonBackfillOutcome]:
    outcomes: list[JsonBackfillOutcome] = []
    with D1DeepDiveSink(run_id=run_id, client=d1) as sink:
        for candidate in candidates:
            if candidate.record is None or candidate.gene_symbol is None:
                outcomes.append(
                    JsonBackfillOutcome(
                        path=candidate.path,
                        gene_symbol=candidate.gene_symbol,
                        action=candidate.action,
                        error=candidate.error,
                    )
                )
                continue
            if candidate.gene_symbol in existing:
                outcomes.append(
                    JsonBackfillOutcome(
                        path=candidate.path,
                        gene_symbol=candidate.gene_symbol,
                        action="existing",
                    )
                )
                continue
            meta = metadata.get(candidate.gene_symbol, BackfillMetadata())
            ok = sink.insert(
                candidate.record,
                cost_usd=meta.cost_usd,
                latency_s=meta.latency_s,
                n_tool_calls=meta.n_tool_calls,
            )
            if ok:
                existing.add(candidate.gene_symbol)
                outcomes.append(
                    JsonBackfillOutcome(
                        path=candidate.path,
                        gene_symbol=candidate.gene_symbol,
                        action="backfilled",
                    )
                )
            else:
                outcomes.append(
                    JsonBackfillOutcome(
                        path=candidate.path,
                        gene_symbol=candidate.gene_symbol,
                        action="backfill_failed",
                        error="D1DeepDiveSink.insert returned False",
                    )
                )
    return outcomes


def _safe_float(raw: str | None) -> float:
    try:
        return float(raw or 0.0)
    except (TypeError, ValueError):
        return 0.0


def _safe_int(raw: str | None) -> int:
    try:
        return int(raw or 0)
    except (TypeError, ValueError):
        return 0


__all__ = [
    "BackfillMetadata",
    "JsonBackfillCandidate",
    "JsonBackfillOutcome",
    "execute_json_backfill",
    "existing_private_genes",
    "load_candidates",
    "load_metadata_tsv",
    "plan_json_backfill",
    "run_dir",
]
