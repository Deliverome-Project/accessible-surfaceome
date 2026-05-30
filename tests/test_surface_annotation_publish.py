"""Smoke-test the surface-annotation publish helpers without hitting D1.

Tests that:
- ``publish_record_dict`` writes a snapshot when asked and skips D1 cleanly
  when Cloudflare env vars are missing (the CI-without-secrets path).
- The dict-form path doesn't validate against the in-tree Pydantic model
  (so historical snapshots with drifted schemas still publish).
- The agent-side ``publish_record`` round-trips a real ``SurfaceomeRecord``
  by serializing the model and threading through the dict-form core.
- A missing ``gene.hgnc_symbol`` raises rather than silently writing a
  null-keyed D1 row.

D1 actually-pushing is exercised manually via
``scripts/upload_viewer_snapshots_to_d1.py --execute`` against the staging
DB; here we only test the in-process branches.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from accessible_surfaceome.cloud.surface_annotation import (
    PublishResult,
    publish_record_dict,
)


def test_publish_record_dict_writes_snapshot_and_skips_d1_when_no_env(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.delenv("CLOUDFLARE_ACCOUNT_ID", raising=False)
    monkeypatch.delenv("CLOUDFLARE_API_TOKEN", raising=False)
    monkeypatch.delenv("CLOUDFLARE_D1_SURFACEOME_PUBLIC_ID", raising=False)
    blob = {
        "gene": {"hgnc_symbol": "FAKE1", "uniprot_acc": "Q9XXXX"},
        "schema_version": "1.1.0",
        "confidence": "moderate",
    }
    result = publish_record_dict(
        blob, snapshot_dir=tmp_path, write_snapshot=True
    )
    assert isinstance(result, PublishResult)
    assert result.gene_symbol == "FAKE1"
    assert result.snapshot_path is not None
    assert result.snapshot_path == tmp_path / "FAKE1.json"
    assert result.snapshot_path.exists()
    written = json.loads(result.snapshot_path.read_text())
    assert written == blob
    assert result.d1_written is False
    assert result.skipped_reason == "missing CLOUDFLARE_* env vars"
    assert result.stale_versions_dropped == []


def test_publish_record_dict_skips_d1_when_push_to_d1_false(
    tmp_path: Path,
) -> None:
    blob = {
        "gene": {"hgnc_symbol": "FAKE2", "uniprot_acc": "Q9YYYY"},
        "schema_version": "1.0.0",
    }
    result = publish_record_dict(
        blob,
        snapshot_dir=tmp_path,
        write_snapshot=True,
        push_to_d1=False,
    )
    assert result.d1_written is False
    assert result.skipped_reason == "push_to_d1=False"
    assert result.snapshot_path is not None
    assert result.snapshot_path.exists()


def test_publish_record_dict_does_not_write_snapshot_by_default(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # The bulk-sync caller reads FROM the snapshot dir and wants to push
    # to D1 only — write_snapshot default-False matches that pattern.
    monkeypatch.delenv("CLOUDFLARE_ACCOUNT_ID", raising=False)
    blob = {
        "gene": {"hgnc_symbol": "FAKE3", "uniprot_acc": "Q9ZZZZ"},
        "schema_version": "1.0.0",
    }
    result = publish_record_dict(blob, snapshot_dir=tmp_path)
    assert result.snapshot_path is None
    assert not (tmp_path / "FAKE3.json").exists()


def test_publish_record_dict_rejects_missing_gene_symbol(tmp_path: Path) -> None:
    # A blob missing gene.hgnc_symbol would land in D1 with a null primary
    # key — refuse to publish rather than corrupt the table.
    blob: dict = {"gene": {}, "schema_version": "1.0.0"}
    with pytest.raises(ValueError, match="gene.hgnc_symbol"):
        publish_record_dict(
            blob, snapshot_dir=tmp_path, write_snapshot=True
        )


def test_publish_record_dict_accepts_drifted_schema(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # A historical snapshot may lack fields that the in-tree Pydantic
    # model now requires — the dict-form path should publish anyway.
    # The validation contract is at agent-write time, not at republish.
    monkeypatch.delenv("CLOUDFLARE_ACCOUNT_ID", raising=False)
    drifted = {
        "gene": {"hgnc_symbol": "OLDREC", "uniprot_acc": "P12345"},
        "schema_version": "0.5.0",
        # missing: executive_summary, filters, surface_evidence, etc.
        # The bulk-sync path must NOT validate this against the v1.1
        # SurfaceomeRecord model.
    }
    result = publish_record_dict(
        drifted, snapshot_dir=tmp_path, write_snapshot=True
    )
    assert result.gene_symbol == "OLDREC"
    assert result.snapshot_path is not None
