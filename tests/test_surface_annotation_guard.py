"""Regression-guard tests for the surface_annotation publish path.

The guard refuses to overwrite a populated deterministic block in D1 with
an empty one — the failure mode where a record generated with unhydrated
data / a degraded resolver (surface_bind has_data=False for every gene; no
family tags) gets published over good D1 data and silently wipes it. It
covers both ``surface_bind.has_data`` and the deterministic family tags
(``executive_summary.uniprot_family`` / ``hgnc_gene_groups``).

D1 is mocked at the ``_post`` boundary — no network.
"""

from __future__ import annotations

import json

import pytest

from accessible_surfaceome.cloud import surface_annotation as sa


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


# --- surface_bind regression -------------------------------------------


def test_blocks_surface_bind_true_to_false(monkeypatch: pytest.MonkeyPatch) -> None:
    _set_public_env(monkeypatch)
    writes: list = []
    _install_fake_post(
        monkeypatch,
        existing_record=_rec(sb_has_data=True, uniprot_family="kinase fam"),
        writes=writes,
    )
    res = sa.publish_record_dict(
        _rec(sb_has_data=False, uniprot_family="kinase fam"), write_snapshot=False
    )
    assert res.d1_written is False
    assert "surface_bind" in (res.skipped_reason or "")
    assert writes == []


def test_allows_surface_bind_false_to_true(monkeypatch: pytest.MonkeyPatch) -> None:
    _set_public_env(monkeypatch)
    writes: list = []
    _install_fake_post(
        monkeypatch,
        existing_record=_rec(sb_has_data=False, uniprot_family="kinase fam"),
        writes=writes,
    )
    res = sa.publish_record_dict(
        _rec(sb_has_data=True, uniprot_family="kinase fam"), write_snapshot=False
    )
    assert res.d1_written is True
    assert any("INSERT OR REPLACE" in s for s, _ in writes)


# --- deterministic family regression -----------------------------------


def test_blocks_family_populated_to_empty(monkeypatch: pytest.MonkeyPatch) -> None:
    _set_public_env(monkeypatch)
    writes: list = []
    _install_fake_post(
        monkeypatch,
        existing_record=_rec(
            sb_has_data=True,
            uniprot_family="protein kinase superfamily",
            hgnc_groups=["ErbB family receptor tyrosine kinases"],
        ),
        writes=writes,
    )
    # surface_bind unchanged (True) but the family tags got blanked.
    res = sa.publish_record_dict(
        _rec(sb_has_data=True, uniprot_family=None, hgnc_groups=()),
        write_snapshot=False,
    )
    assert res.d1_written is False
    assert "family" in (res.skipped_reason or "")
    assert writes == []


def test_allows_family_when_genuinely_absent(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # Existing row also has no family → empty incoming is not a regression.
    _set_public_env(monkeypatch)
    writes: list = []
    _install_fake_post(
        monkeypatch, existing_record=_rec(sb_has_data=True), writes=writes
    )
    res = sa.publish_record_dict(_rec(sb_has_data=True), write_snapshot=False)
    assert res.d1_written is True


def test_allows_family_upgrade_empty_to_populated(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _set_public_env(monkeypatch)
    writes: list = []
    _install_fake_post(
        monkeypatch, existing_record=_rec(sb_has_data=True), writes=writes
    )
    res = sa.publish_record_dict(
        _rec(sb_has_data=True, uniprot_family="protein kinase superfamily"),
        write_snapshot=False,
    )
    assert res.d1_written is True


# --- escape hatch + new-gene ------------------------------------------


def test_force_overrides_guard(monkeypatch: pytest.MonkeyPatch) -> None:
    _set_public_env(monkeypatch)
    writes: list = []
    _install_fake_post(
        monkeypatch,
        existing_record=_rec(sb_has_data=True, uniprot_family="kinase"),
        writes=writes,
    )
    res = sa.publish_record_dict(
        _rec(sb_has_data=False, uniprot_family=None), write_snapshot=False, force=True
    )
    assert res.d1_written is True
    assert any("INSERT OR REPLACE" in s for s, _ in writes)


def test_no_existing_row_allows_publish(monkeypatch: pytest.MonkeyPatch) -> None:
    # Brand-new gene, nothing in D1 → no prior data to regress.
    _set_public_env(monkeypatch)
    writes: list = []
    _install_fake_post(monkeypatch, existing_record=None, writes=writes)
    res = sa.publish_record_dict(_rec(sb_has_data=False), write_snapshot=False)
    assert res.d1_written is True


# --- staleness guard ---------------------------------------------------
# Both records here are fully populated (has_data=True, family set), so the
# regression guard never fires — these exercise the NEW staleness guard,
# which is what protects an already-published run from being clobbered by a
# staler on-disk snapshot during a bulk re-sync.

_OLDER = "2026-05-31T04:00:00+00:00"
_NEWER = "2026-05-31T15:00:00+00:00"


def test_blocks_stale_overwrite(monkeypatch: pytest.MonkeyPatch) -> None:
    _set_public_env(monkeypatch)
    writes: list = []
    _install_fake_post(
        monkeypatch,
        existing_record=_rec(
            sb_has_data=True, uniprot_family="kinase", generated_at=_NEWER
        ),
        writes=writes,
    )
    # Incoming snapshot is OLDER than the D1 row — must be refused.
    res = sa.publish_record_dict(
        _rec(sb_has_data=True, uniprot_family="kinase", generated_at=_OLDER),
        write_snapshot=False,
    )
    assert res.d1_written is False
    assert "stale" in (res.skipped_reason or "").lower()
    assert writes == []


def test_allows_newer_overwrite(monkeypatch: pytest.MonkeyPatch) -> None:
    _set_public_env(monkeypatch)
    writes: list = []
    _install_fake_post(
        monkeypatch,
        existing_record=_rec(
            sb_has_data=True, uniprot_family="kinase", generated_at=_OLDER
        ),
        writes=writes,
    )
    res = sa.publish_record_dict(
        _rec(sb_has_data=True, uniprot_family="kinase", generated_at=_NEWER),
        write_snapshot=False,
    )
    assert res.d1_written is True
    assert any("INSERT OR REPLACE" in s for s, _ in writes)


def test_stale_overwrite_allowed_with_force(monkeypatch: pytest.MonkeyPatch) -> None:
    _set_public_env(monkeypatch)
    writes: list = []
    _install_fake_post(
        monkeypatch,
        existing_record=_rec(sb_has_data=True, generated_at=_NEWER),
        writes=writes,
    )
    res = sa.publish_record_dict(
        _rec(sb_has_data=True, generated_at=_OLDER), write_snapshot=False, force=True
    )
    assert res.d1_written is True


def test_is_stale_pure() -> None:
    older = {"record_generated_at": _OLDER}
    newer = {"record_generated_at": _NEWER}
    # _is_stale(incoming, existing): True when existing is newer than incoming.
    assert sa._is_stale(older, newer) is True
    assert sa._is_stale(newer, older) is False
    assert sa._is_stale(newer, newer) is False
    # Missing/unparseable timestamps are conservative (never block).
    assert sa._is_stale({}, newer) is False
    assert sa._is_stale(newer, {}) is False
    assert sa._is_stale({"record_generated_at": "garbage"}, newer) is False
