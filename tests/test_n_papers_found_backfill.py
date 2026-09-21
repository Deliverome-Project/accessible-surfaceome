"""Tests for the ``n_papers_found`` D1-direct backfill.

``n_papers_found`` is the pre-trim discovery corpus (median ~215, range
~1-395) — the "is this gene generally understudied?" signal the low-lit
badge (``is_low_literature_surface``) and the catalog's "understudied"
chip read via ``n_papers_found < LOW_LIT_PAPERS_MAX`` (=100). It is
shed at publish time and can only be recomputed by re-running discovery
(see ``scripts/build/backfill_n_papers_found.py``).

~485/5130 published records carry a NULL ``n_papers_found`` even at
schema 2.14.2 (a per-record capture gap, not a schema-vintage split), so
the badge is silently withheld on the UniProt-positive subset of those
(FAM234A / Q9H0X4 is the exemplar). These genes live only in D1 with no
committed ``viewer/public/data/surfaceome/*.json`` snapshot (only 3 exist),
so the snapshot-scoped legacy backfill cannot reach them — hence the
D1-direct path exercised here.

The pure helpers (``needs_backfill`` / ``patch_n_papers_found`` /
``NEEDS_BACKFILL_SQL``) run offline in CI. The whole-cohort invariant
(``test_all_published_records_have_n_papers_found``) is ``network``-marked:
it queries live public D1 and is the acceptance gate for the backfill —
RED before the run (485 offenders), GREEN after. It is skipped in CI
(no ``--run-network`` / no ``CLOUDFLARE_*`` creds).
"""
from __future__ import annotations

import copy
import json
from pathlib import Path

import pytest

from accessible_surfaceome.cloud.n_papers_found_backfill import (
    NEEDS_BACKFILL_SQL,
    needs_backfill,
    patch_n_papers_found,
)
from accessible_surfaceome.tools._shared.models import SurfaceomeRecord

_FIXTURE = Path(__file__).parent / "fixtures" / "klk2_record_snapshot.json"


def _load_fixture() -> dict:
    # KLK2 snapshot: a genuine affected-record shape — filters.n_papers_found
    # is None while n_papers_selected is populated (10). Validates against the
    # current SurfaceomeRecord.
    return json.loads(_FIXTURE.read_text())


def test_fixture_is_a_genuine_affected_record() -> None:
    rec = _load_fixture()
    assert rec["filters"]["n_papers_found"] is None
    assert rec["filters"]["n_papers_selected"] == 10


# ---- needs_backfill --------------------------------------------------------


def test_needs_backfill_true_when_null() -> None:
    assert needs_backfill(_load_fixture()) is True


def test_needs_backfill_true_when_key_missing() -> None:
    rec = _load_fixture()
    del rec["filters"]["n_papers_found"]
    assert needs_backfill(rec) is True


def test_needs_backfill_true_when_filters_block_absent() -> None:
    assert needs_backfill({"gene": {"hgnc_symbol": "X"}}) is True


def test_needs_backfill_false_when_populated() -> None:
    rec = _load_fixture()
    rec["filters"]["n_papers_found"] = 215
    assert needs_backfill(rec) is False


def test_needs_backfill_false_on_real_zero() -> None:
    # None ("unknown corpus") is distinct from a real 0 ("known: empty
    # corpus"). A real zero is a valid measurement — never re-run discovery.
    rec = _load_fixture()
    rec["filters"]["n_papers_found"] = 0
    assert needs_backfill(rec) is False


# ---- patch_n_papers_found --------------------------------------------------


def test_patch_sets_the_field() -> None:
    patched = patch_n_papers_found(_load_fixture(), 215)
    assert patched["filters"]["n_papers_found"] == 215


def test_patch_preserves_sibling_and_other_blocks() -> None:
    rec = _load_fixture()
    patched = patch_n_papers_found(rec, 215)
    # sibling count untouched
    assert patched["filters"]["n_papers_selected"] == 10
    # unrelated top-level blocks carried through byte-for-byte
    assert patched["gene"] == rec["gene"]
    assert patched.get("evidence") == rec.get("evidence")


def test_patch_does_not_mutate_input() -> None:
    rec = _load_fixture()
    before = copy.deepcopy(rec)
    patch_n_papers_found(rec, 215)
    assert rec == before  # input left pristine


def test_patched_record_still_validates() -> None:
    # The validate-before-D1-write contract: a patched record must round-trip
    # through the Pydantic model before it is allowed near an UPDATE.
    patched = patch_n_papers_found(_load_fixture(), 215)
    model = SurfaceomeRecord.model_validate(patched)
    assert model.filters.n_papers_found == 215


def test_patch_rejects_negative() -> None:
    with pytest.raises(ValueError):
        patch_n_papers_found(_load_fixture(), -1)


# ---- selection SQL ---------------------------------------------------------


def test_needs_backfill_sql_targets_null_discovery_corpus() -> None:
    # Identifier-only projection (no full annotation_json blob — that whole-
    # cohort pull is the ~145 MB isolate-memory-cap crash of PR #104), and the
    # predicate must key on a NULL discovery corpus specifically.
    sql = NEEDS_BACKFILL_SQL
    assert "surface_annotation" in sql
    assert "$.filters.n_papers_found" in sql
    assert "IS NULL" in sql
    assert "annotation_json AS" not in sql  # never SELECT the raw blob


# ---- whole-cohort invariant (acceptance gate; live D1) ---------------------


@pytest.mark.network
def test_all_published_records_have_n_papers_found() -> None:
    """Every published ``surface_annotation`` row carries a non-null
    ``n_papers_found``. The backfill's acceptance gate — RED (offenders
    listed) until the D1-direct backfill runs, GREEN after.

    ``network``-marked (skipped without ``--run-network``); also skipped
    when public-D1 creds are absent, matching CI.
    """
    from accessible_surfaceome.cloud.d1_client import D1Client, D1Config
    from accessible_surfaceome.env import load_env

    load_env()
    try:
        cfg = D1Config.from_env_public()
    except Exception as exc:  # noqa: BLE001 — no creds in this env: skip, don't fail
        pytest.skip(f"public D1 not configured: {exc}")

    with D1Client(cfg) as d1:
        offenders = d1.query(
            "SELECT gene_symbol FROM surface_annotation "
            "WHERE json_extract(annotation_json, '$.filters.n_papers_found') "
            "IS NULL ORDER BY gene_symbol;",
            [],
        )
    symbols = [r["gene_symbol"] for r in offenders]
    assert not symbols, (
        f"{len(symbols)} published records still have NULL n_papers_found "
        f"(badge/understudied-chip silently withheld): "
        f"{', '.join(symbols[:15])}{' ...' if len(symbols) > 15 else ''}"
    )
