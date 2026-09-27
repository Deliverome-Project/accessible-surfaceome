"""A publish archives the new record; failures never fail the publish."""

from __future__ import annotations

import httpx
import pytest

from accessible_surfaceome.cloud import surface_annotation as sa


def test_purge_paths_is_public_and_reused_by_cohort_purge() -> None:
    assert callable(sa.purge_paths)
    assert sa.purge_cohort_surfaces([]) is None  # no paths → nothing to do


def test_maybe_archive_skips_without_token(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("ARCHIVE_BYPASS_TOKEN", raising=False)
    assert sa._maybe_archive("EGFR", client=httpx.Client()) is None


def test_maybe_archive_swallows_failures(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("ARCHIVE_BYPASS_TOKEN", "tok")

    def boom(*_a, **_k):
        raise RuntimeError("R2 down")

    monkeypatch.setattr(sa, "_open_revision_store", boom)
    assert sa._maybe_archive("EGFR", client=httpx.Client()) == "failed"


def test_maybe_archive_reports_status(monkeypatch: pytest.MonkeyPatch) -> None:
    from accessible_surfaceome.cloud.record_history import archive as arch

    monkeypatch.setenv("ARCHIVE_BYPASS_TOKEN", "tok")

    class _Store:
        def __enter__(self):
            return self

        def __exit__(self, *_):
            return None

    monkeypatch.setattr(sa, "_open_revision_store", lambda: _Store())
    monkeypatch.setattr(
        arch,
        "archive_gene",
        lambda sym, **kw: arch.ArchiveResult(sym, "created", 3),
    )
    assert sa._maybe_archive("EGFR", client=httpx.Client()) == "created"


def test_publish_result_carries_archive_status() -> None:
    r = sa.PublishResult(
        gene_symbol="X",
        snapshot_path=None,
        d1_written=False,
        d1_database_id=None,
        stale_versions_dropped=[],
    )
    assert r.archive_status is None
