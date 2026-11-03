"""A publish archives the new record; failures never fail the publish."""

from __future__ import annotations

import json

import httpx
import pytest

from accessible_surfaceome.cloud import surface_annotation as sa


def test_purge_paths_is_public_and_reused_by_cohort_purge() -> None:
    assert callable(sa.purge_paths)
    assert sa.purge_cohort_surfaces([]) is None  # no paths → nothing to do


def test_maybe_archive_skips_without_token(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("ARCHIVE_BYPASS_TOKEN", raising=False)
    with httpx.Client() as c:
        assert sa._maybe_archive("EGFR", client=c) is None


def test_maybe_archive_swallows_failures(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("ARCHIVE_BYPASS_TOKEN", "tok")

    def boom(*_a, **_k):
        raise RuntimeError("R2 down")

    monkeypatch.setattr(sa, "_open_revision_store", boom)
    with httpx.Client() as c:
        assert sa._maybe_archive("EGFR", client=c) == "failed"


def test_maybe_archive_reports_status(monkeypatch: pytest.MonkeyPatch) -> None:
    from accessible_surfaceome.cloud.record_history import archive as arch

    monkeypatch.setenv("ARCHIVE_BYPASS_TOKEN", "tok")

    class _Store:
        def __enter__(self):
            return self

        def __exit__(self, *_):
            return None

    monkeypatch.setattr(sa, "_open_revision_store", lambda: _Store())

    calls: list[tuple[tuple, dict]] = []

    def fake_archive_gene(sym, **kw):
        calls.append(((sym,), kw))
        return arch.ArchiveResult(sym, "created", 3)

    monkeypatch.setattr(arch, "archive_gene", fake_archive_gene)

    with httpx.Client() as c:
        assert sa._maybe_archive("EGFR", client=c) == "created"

        assert len(calls) == 1
        (sym,), kw = calls[0]
        assert sym == "EGFR"
        assert kw["source"] == "publish"
        assert kw["http"] is c
        assert kw["token"] == "tok"
        assert kw["purge"] is sa.purge_paths


def test_publish_result_carries_archive_status() -> None:
    r = sa.PublishResult(
        gene_symbol="X",
        snapshot_path=None,
        d1_written=False,
        d1_database_id=None,
        stale_versions_dropped=[],
    )
    assert r.archive_status is None


# ---------------------------------------------------------------------------
# Wiring: `_publish_dict` calls `_maybe_archive` after a successful D1 write,
# and NOT when a guard refuses the publish before the write happens.
# ---------------------------------------------------------------------------
# Mirrors the ``_set_public_env`` / ``_install_fake_post`` helpers in
# tests/test_surface_annotation_guard.py — D1 is mocked at the ``_post``
# boundary, no network.


def _set_public_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("CLOUDFLARE_ACCOUNT_ID", "acct")
    monkeypatch.setenv("CLOUDFLARE_API_TOKEN", "tok")
    monkeypatch.setenv("CLOUDFLARE_D1_SURFACEOME_PUBLIC_ID", "db")


def _install_fake_post(
    monkeypatch: pytest.MonkeyPatch,
    *,
    existing_record: dict | None,
    writes: list[tuple[str, list]],
) -> None:
    """Patch ``_post`` to simulate the existing D1 row + capture writes."""
    blob = json.dumps(existing_record) if existing_record is not None else None

    def fake_post(cfg, sql, params, *, client):  # noqa: ANN001, ANN202
        s = sql.strip()
        if s.startswith("SELECT annotation_json"):
            results = [{"annotation_json": blob}] if blob else []
            return {"result": [{"results": results}], "success": True}
        if s.startswith("SELECT schema_version"):
            return {"result": [{"results": []}], "success": True}
        writes.append((s, params))  # INSERT OR REPLACE / DELETE
        return {"result": [{"results": []}], "success": True}

    monkeypatch.setattr(sa, "_post", fake_post)


def _rec(
    *, sb_has_data: bool, uniprot_family=None, hgnc_groups=(), generated_at=None
) -> dict:
    rec = {
        "gene": {"hgnc_symbol": "EGFR", "uniprot_acc": "P00533"},
        "schema_version": "1.1.0",
        "executive_summary": {
            "uniprot_family": uniprot_family,
            "hgnc_gene_groups": list(hgnc_groups),
        },
        "deterministic_features": {"surface_bind": {"has_data": sb_has_data}},
    }
    if generated_at is not None:
        rec["record_generated_at"] = generated_at
    return rec


def test_publish_calls_maybe_archive_after_successful_write(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _set_public_env(monkeypatch)
    writes: list = []
    _install_fake_post(monkeypatch, existing_record=None, writes=writes)

    calls: list[str] = []

    def fake_maybe_archive(sym, *, client):  # noqa: ANN001
        calls.append(sym)
        return "created"

    monkeypatch.setattr(sa, "_maybe_archive", fake_maybe_archive)

    res = sa.publish_record_dict(
        _rec(sb_has_data=True, uniprot_family="kinase fam", hgnc_groups=["g"]),
        write_snapshot=False,
    )

    assert res.d1_written is True
    assert any("INSERT OR REPLACE" in s for s, _ in writes)
    assert calls == ["EGFR"]
    assert res.archive_status == "created"


def test_publish_skips_maybe_archive_when_guard_blocks(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _set_public_env(monkeypatch)
    writes: list = []
    _older = "2026-05-31T04:00:00+00:00"
    _newer = "2026-05-31T15:00:00+00:00"
    _install_fake_post(
        monkeypatch,
        existing_record=_rec(
            sb_has_data=True, uniprot_family="kinase", generated_at=_newer
        ),
        writes=writes,
    )

    calls: list[str] = []

    def fake_maybe_archive(sym, *, client):  # noqa: ANN001
        calls.append(sym)
        return "created"

    monkeypatch.setattr(sa, "_maybe_archive", fake_maybe_archive)

    # Incoming snapshot is OLDER than the D1 row — the staleness guard
    # refuses the publish before any D1 write happens.
    res = sa.publish_record_dict(
        _rec(sb_has_data=True, uniprot_family="kinase", generated_at=_older),
        write_snapshot=False,
    )

    assert res.d1_written is False
    assert writes == []
    assert calls == []
    assert res.archive_status is None
