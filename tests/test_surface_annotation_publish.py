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
``scripts/upload/upload_viewer_snapshots_to_d1.py --execute`` against the staging
DB; here we only test the in-process branches.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from accessible_surfaceome.cloud.surface_annotation import (
    PublishResult,
    _maybe_purge,
    _purge_urls_for,
    publish_record_dict,
)


@pytest.fixture(autouse=True)
def _block_dotenv_load(monkeypatch: pytest.MonkeyPatch) -> None:
    """Stub the in-helper ``.env`` reader so tests that ``delenv`` the
    CLOUDFLARE_* vars don't get them re-populated by the loader walking
    up to a symlinked ``.env`` at the repo root. Matches the pattern in
    ``tests/test_d1_env_preflight.py::_isolate_env``."""
    monkeypatch.setattr(
        "accessible_surfaceome.cloud.d1_env.load_env", lambda: None
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


def test_publish_record_default_skips_snapshot(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The Pydantic-model entry point used to write the viewer snapshot
    by default. After the June-2026 fallback-removal, the viewer no
    longer reads from a per-gene JSON file — D1 is the only source — so
    ``publish_record`` now defaults to ``write_snapshot=False`` too.
    This test pins that default; flipping it back would silently
    reintroduce the fallback the viewer no longer needs."""
    monkeypatch.delenv("CLOUDFLARE_ACCOUNT_ID", raising=False)
    monkeypatch.delenv("CLOUDFLARE_API_TOKEN", raising=False)
    monkeypatch.delenv("CLOUDFLARE_D1_SURFACEOME_PUBLIC_ID", raising=False)
    from accessible_surfaceome.cloud.surface_annotation import publish_record
    from accessible_surfaceome.tools._shared.models import (
        ExecutiveSummary,
        GeneIdentifier,
        SurfaceomeRecord,
    )

    # Minimal-but-valid record; the model's defaults populate the rest.
    rec = SurfaceomeRecord.model_construct(
        schema_version="2.6.0",
        gene=GeneIdentifier(
            hgnc_symbol="FAKE4",
            hgnc_id="HGNC:1",
            uniprot_acc="P00001",
            ncbi_gene_id=1,
            ensembl_gene="ENSG00000000001",
        ),
        executive_summary=ExecutiveSummary.model_construct(),
    )
    # Stub out D1 path entirely — we only care about the snapshot default.
    result = publish_record(rec, snapshot_dir=tmp_path, push_to_d1=False)
    assert result.snapshot_path is None
    assert list(tmp_path.iterdir()) == [], (
        "publish_record default must not touch the snapshot dir — "
        "the viewer no longer reads JSON fallbacks"
    )


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


# --- edge-cache purge-on-publish -------------------------------------------


def test_purge_urls_for_targets_record_catalog_and_list() -> None:
    # A surface_annotation write invalidates exactly three cached surfaces:
    # the per-gene record, the genome-wide catalog (carries the gene's ddf
    # projection), and the gene-list index. Nothing else (orthologs /
    # triage / benchmark) — a tighter set avoids disturbing the rest of the
    # shared deliverome.org zone cache.
    urls = _purge_urls_for("EGFR")
    assert urls == [
        "https://api.deliverome.org/surfaceome/v1/genes/EGFR",
        "https://api.deliverome.org/surfaceome/v1/catalog",
        "https://api.deliverome.org/surfaceome/v1/genes",
    ]


def test_purge_urls_are_query_string_free() -> None:
    # The cache rule makes the cache key query-string-insensitive, so the
    # bare URL is the canonical key — there must be no "?x=" variants to
    # chase, or the purge would miss the cached object.
    assert all("?" not in u for u in _purge_urls_for("CD19"))


def test_maybe_purge_soft_skips_without_zone_id(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # Missing CLOUDFLARE_ZONE_ID is a soft skip (returns None, no raise),
    # mirroring how a missing D1 config skips the push — CI / offline dev
    # must never crash on the purge step.
    monkeypatch.delenv("CLOUDFLARE_ZONE_ID", raising=False)
    out = _maybe_purge("EGFR", token="unused", client=None)  # type: ignore[arg-type]  # ty: ignore[invalid-argument-type]
    assert out is None


def test_maybe_purge_returns_false_on_http_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # A purge failure (network / auth / 5xx) must never break a publish —
    # it returns False and the record just goes live on TTL instead.
    monkeypatch.setenv("CLOUDFLARE_ZONE_ID", "zone123")

    class _BoomClient:
        def post(self, *_args, **_kwargs):
            raise RuntimeError("network down")

    out = _maybe_purge("EGFR", token="tok", client=_BoomClient())  # type: ignore[arg-type]  # ty: ignore[invalid-argument-type]
    assert out is False


def test_maybe_purge_returns_true_on_success(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("CLOUDFLARE_ZONE_ID", "zone123")
    captured: dict = {}

    class _Resp:
        def raise_for_status(self) -> None:
            return None

        def json(self) -> dict:
            return {"success": True}

    class _OKClient:
        def post(self, url, *, headers, json):  # noqa: A002 — match httpx kw
            captured["url"] = url
            captured["files"] = json["files"]
            captured["auth"] = headers["Authorization"]
            return _Resp()

    out = _maybe_purge("EGFR", token="tok", client=_OKClient())  # type: ignore[arg-type]  # ty: ignore[invalid-argument-type]
    assert out is True
    assert captured["url"].endswith("/zones/zone123/purge_cache")
    assert captured["auth"] == "Bearer tok"
    # Targeted file purge — never purge_everything (shared zone).
    assert captured["files"] == _purge_urls_for("EGFR")
