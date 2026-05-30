"""Publish a v2 deep-dive ``SurfaceomeRecord`` to the surfaces that serve it.

The viewer reads per-gene records from two surfaces:

* ``viewer/public/data/surfaceome/{SYMBOL}.json`` — committed snapshot, used
  as the offline / Worker-down fallback.
* Public Cloudflare D1 ``surface_annotation.annotation_json`` — what the
  ``api.deliverome.org/surfaceome/v1/genes/:symbol`` Worker serves on each
  per-gene page load.

After a v2 annotate run completes, both surfaces need to receive the new
record. If only the local file is written, the viewer keeps serving the
stale (often field-incomplete) D1 row and the page either crashes or
silently renders missing sections.

:func:`publish_record` writes both surfaces atomically (snapshot first,
then D1). The D1 push is skipped with a clear log when Cloudflare env
vars aren't set (CI without secrets, offline dev), so callers can wire
it into their default path without breaking those environments.

This module is the canonical "publish a record" path — both the v2
annotate driver and the maintenance script
(``scripts/upload_viewer_snapshots_to_d1.py``) call into it so the two
surfaces never drift.
"""

from __future__ import annotations

import json
import logging
import os
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import httpx

from accessible_surfaceome.cloud.d1_client import D1Config
from accessible_surfaceome.paths import REPO_ROOT
from accessible_surfaceome.tools._shared.models import SurfaceomeRecord

logger = logging.getLogger(__name__)

API_ROOT = "https://api.cloudflare.com/client/v4"
DEFAULT_SNAPSHOT_DIR = REPO_ROOT / "viewer" / "public" / "data" / "surfaceome"

# Mirrors ``cloudflare/d1_public_schema.sql::surface_annotation``. Keep in
# sync with ``scripts/sync_public_d1.py::sync_surface_annotations``.
_COLS = [
    "gene_symbol",
    "uniprot_acc",
    "schema_version",
    "annotation_json",
    "confidence",
    "triage_signal",
    "surface_status",
    "model_path",
    "evidence_count",
    "primary_evidence_count",
    "annotated_at",
]


@dataclass
class PublishResult:
    """Outcome of one :func:`publish_record` call."""

    gene_symbol: str
    snapshot_path: Path | None
    d1_written: bool
    d1_database_id: str | None
    stale_versions_dropped: list[str]
    skipped_reason: str | None = None


def _public_config_from_env() -> D1Config | None:
    """Build a public-DB :class:`D1Config` from env, or return ``None`` on miss.

    Missing creds is a soft skip, not an error — agents on CI runners /
    fresh checkouts shouldn't crash because Cloudflare secrets aren't
    wired in. The caller logs a clear message in that case.
    """
    acct = os.environ.get("CLOUDFLARE_ACCOUNT_ID", "").strip()
    token = os.environ.get("CLOUDFLARE_API_TOKEN", "").strip()
    db = os.environ.get("CLOUDFLARE_D1_SURFACEOME_PUBLIC_ID", "").strip()
    if not (acct and token and db):
        return None
    return D1Config(account_id=acct, database_id=db, api_token=token)


def _post(
    cfg: D1Config, sql: str, params: list[Any], *, client: httpx.Client
) -> dict[str, Any]:
    url = f"{API_ROOT}/accounts/{cfg.account_id}/d1/database/{cfg.database_id}/query"
    resp = client.post(
        url,
        headers={
            "Authorization": f"Bearer {cfg.api_token}",
            "Content-Type": "application/json",
        },
        json={"sql": sql, "params": params},
    )
    resp.raise_for_status()
    body = resp.json()
    if not body.get("success"):
        raise RuntimeError(f"D1 query failed: {body}")
    return body


def _existing_versions_for(
    cfg: D1Config, gene_symbol: str, *, client: httpx.Client
) -> list[str]:
    body = _post(
        cfg,
        "SELECT schema_version FROM surface_annotation WHERE gene_symbol = ?",
        [gene_symbol],
        client=client,
    )
    return [r["schema_version"] for r in body["result"][0].get("results", [])]


def _row_from_dict(
    rec_dict: dict[str, Any], *, annotated_at: str | None = None
) -> list[Any]:
    """Project a raw record dict to the column tuple D1 expects.

    Operates on a dict (not a validated ``SurfaceomeRecord``) so the
    bulk-sync maintenance path can push historical snapshots whose
    schema has drifted from the current in-tree Pydantic model. The
    canonical source of truth for "what the viewer renders" is the
    JSON blob on disk; validation belongs at agent-write time, not at
    publish time.
    """
    gene = rec_dict.get("gene") or {}
    sb = rec_dict.get("surface_biology") or {}
    return [
        gene.get("hgnc_symbol"),
        gene.get("uniprot_acc"),
        rec_dict.get("schema_version") or "1.0.0",
        # Re-encode without indentation — the D1 blob is read by JS only,
        # so we save bytes on the wire and at rest.
        json.dumps(rec_dict, separators=(",", ":")),
        rec_dict.get("confidence"),
        rec_dict.get("triage_signal"),
        sb.get("surface_status"),
        rec_dict.get("model_path"),
        rec_dict.get("evidence_count") or 0,
        rec_dict.get("primary_evidence_count") or 0,
        annotated_at or datetime.now(UTC).isoformat(),
    ]


def _publish_dict(
    rec_dict: dict[str, Any],
    *,
    snapshot_dir: Path | None,
    write_snapshot: bool,
    push_to_d1: bool,
    pretty_snapshot: bool,
) -> PublishResult:
    """Shared core: write the snapshot + push to D1 from a raw record dict."""
    gene = rec_dict.get("gene") or {}
    sym = gene.get("hgnc_symbol")
    if not sym:
        raise ValueError("record dict missing required gene.hgnc_symbol")

    snap_dir = snapshot_dir or DEFAULT_SNAPSHOT_DIR
    snap_path: Path | None = None
    if write_snapshot:
        snap_dir.mkdir(parents=True, exist_ok=True)
        snap_path = snap_dir / f"{sym}.json"
        snap_path.write_text(
            json.dumps(rec_dict, indent=2 if pretty_snapshot else None)
        )
        logger.info("snapshot written: %s", snap_path)

    if not push_to_d1:
        return PublishResult(
            gene_symbol=sym,
            snapshot_path=snap_path,
            d1_written=False,
            d1_database_id=None,
            stale_versions_dropped=[],
            skipped_reason="push_to_d1=False",
        )

    cfg = _public_config_from_env()
    if cfg is None:
        logger.warning(
            "public D1 env vars missing (CLOUDFLARE_ACCOUNT_ID / "
            "CLOUDFLARE_API_TOKEN / CLOUDFLARE_D1_SURFACEOME_PUBLIC_ID) — "
            "skipping D1 publish for %s. Snapshot was still written.",
            sym,
        )
        return PublishResult(
            gene_symbol=sym,
            snapshot_path=snap_path,
            d1_written=False,
            d1_database_id=None,
            stale_versions_dropped=[],
            skipped_reason="missing CLOUDFLARE_* env vars",
        )

    row = _row_from_dict(rec_dict)
    new_version = row[2]
    with httpx.Client(timeout=60) as client:
        # Drop any stale schema_versions for this gene before upserting. The
        # Worker tie-breaks on ``ORDER BY schema_version DESC LIMIT 1``, but
        # leaving stale rows in D1 means a future schema rollback or
        # `<` ordering could resurface the old field-incomplete record.
        existing = _existing_versions_for(cfg, sym, client=client)
        stale = [v for v in existing if v != new_version]
        for ver in stale:
            _post(
                cfg,
                "DELETE FROM surface_annotation WHERE gene_symbol = ? AND schema_version = ?",
                [sym, ver],
                client=client,
            )
            logger.info("dropped stale %s@%s from D1", sym, ver)

        # INSERT OR REPLACE on (gene_symbol, schema_version).
        cols_sql = ", ".join(_COLS)
        placeholders = "(" + ", ".join(["?"] * len(_COLS)) + ")"
        sql = (
            f"INSERT OR REPLACE INTO surface_annotation ({cols_sql}) "
            f"VALUES {placeholders}"
        )
        _post(cfg, sql, row, client=client)
        logger.info("D1 upserted: %s@%s -> %s", sym, new_version, cfg.database_id)

    return PublishResult(
        gene_symbol=sym,
        snapshot_path=snap_path,
        d1_written=True,
        d1_database_id=cfg.database_id,
        stale_versions_dropped=stale,
        skipped_reason=None,
    )


def publish_record(
    record: SurfaceomeRecord,
    *,
    snapshot_dir: Path | None = None,
    write_snapshot: bool = True,
    push_to_d1: bool = True,
) -> PublishResult:
    """Write a freshly-validated ``SurfaceomeRecord`` to snapshot + D1.

    The standard agent-side entry point: takes a validated Pydantic model
    (so the record is known good), serializes it to disk and pushes to
    public D1. Returns a :class:`PublishResult` describing what landed.

    For pushing arbitrary on-disk JSON (the bulk-sync maintenance path)
    use :func:`publish_record_dict` — it skips validation so older
    snapshots whose schema has drifted can still be published.

    Args:
        record: The validated ``SurfaceomeRecord`` to publish.
        snapshot_dir: Override for the viewer-snapshot directory. Defaults
            to ``viewer/public/data/surfaceome``.
        write_snapshot: Skip the viewer-snapshot write when False.
        push_to_d1: Skip the D1 push when False (e.g. ``--no-publish``).
    """
    rec_dict = json.loads(record.model_dump_json())
    return _publish_dict(
        rec_dict,
        snapshot_dir=snapshot_dir,
        write_snapshot=write_snapshot,
        push_to_d1=push_to_d1,
        pretty_snapshot=True,
    )


def publish_record_dict(
    rec_dict: dict[str, Any],
    *,
    snapshot_dir: Path | None = None,
    write_snapshot: bool = False,
    push_to_d1: bool = True,
    pretty_snapshot: bool = True,
) -> PublishResult:
    """Push a raw record dict — no Pydantic validation.

    Companion to :func:`publish_record` for the bulk-sync path
    (``scripts/upload_viewer_snapshots_to_d1.py``) where on-disk
    snapshots may predate field additions in the current Pydantic model.
    The validation contract is: "if it's on disk under
    ``viewer/public/data/surfaceome``, the viewer's allowed to render
    it, so D1 should mirror it". Validation happens at agent-write
    time, not republish time.

    Defaults to ``write_snapshot=False`` because the typical caller for
    this entry point is reading FROM the snapshot dir and just wants to
    push that content to D1.
    """
    return _publish_dict(
        rec_dict,
        snapshot_dir=snapshot_dir,
        write_snapshot=write_snapshot,
        push_to_d1=push_to_d1,
        pretty_snapshot=pretty_snapshot,
    )
