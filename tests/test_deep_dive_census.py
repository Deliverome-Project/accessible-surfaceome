"""Tests for the post-run cross-surface census classifier.

The reconciliation core (:func:`build_census`) is pure, so these pin the
status taxonomy and the worst-first ladder without touching D1 or disk:

* every drift class is reachable and named correctly,
* ``missing`` (never completed) is distinguished from drift (landed unevenly),
* public-not-checked suppresses the public classes rather than flagging every
  gene as ``public_missing``,
* the gate exit code separates drift (1) from coverage (2).
"""

from __future__ import annotations

from pathlib import Path

from accessible_surfaceome.cloud.deep_dive_census import (
    build_census,
    exit_code,
    load_cohort_symbols,
    scan_volume_json,
    summarize,
)


def _one(
    symbol: str = "G",
    *,
    cohort: list[str] | None = None,
    volume: dict[str, str | None] | None = None,
    private: dict[str, str] | None = None,
    orphans: set[str] | None = None,
    public: dict[str, str] | None = None,
):
    rows = build_census(
        cohort_symbols=cohort if cohort is not None else [symbol],
        volume=volume or {},
        private=private or {},
        orphan_symbols=orphans or set(),
        public=public,
    )
    return next(r for r in rows if r.gene_symbol == symbol)


def test_ok_when_present_everywhere_at_matching_schema() -> None:
    r = _one(
        volume={"G": "v0.4.0"},
        private={"G": "v0.4.0"},
        public={"G": "v0.4.0"},
    )
    assert r.status == "ok"
    assert r.is_ok and not r.is_drift


def test_missing_when_absent_everywhere() -> None:
    r = _one(volume={}, private={}, public={})
    assert r.status == "missing"
    assert not r.is_drift  # coverage, not drift


def test_private_missing_when_json_present_but_no_parent() -> None:
    r = _one(volume={"G": "v0.4.0"}, private={}, public={})
    assert r.status == "private_missing"
    assert r.is_drift


def test_orphan_children_takes_priority() -> None:
    # Incomplete children outranks every other problem on the ladder.
    r = _one(
        volume={"G": "v0.4.0"},
        private={"G": "v0.4.0"},
        orphans={"G"},
        public={},  # also public_missing, but orphan wins
    )
    assert r.status == "orphan_children"


def test_public_missing_when_private_present_but_not_public() -> None:
    r = _one(volume={"G": "v0.4.0"}, private={"G": "v0.4.0"}, public={})
    assert r.status == "public_missing"
    assert r.is_drift


def test_public_stale_when_schema_differs() -> None:
    r = _one(
        volume={"G": "v0.4.0"},
        private={"G": "v0.4.0"},
        public={"G": "v0.3.0"},
    )
    assert r.status == "public_stale"
    assert r.is_drift


def test_json_missing_when_derived_rows_exist_without_canonical() -> None:
    r = _one(volume={}, private={"G": "v0.4.0"}, public={"G": "v0.4.0"})
    assert r.status == "json_missing"
    assert r.is_drift


def test_public_not_checked_suppresses_public_classes() -> None:
    # public=None → don't flag public_missing even though no public row exists.
    r = _one(volume={"G": "v0.4.0"}, private={"G": "v0.4.0"}, public=None)
    assert r.status == "ok"
    assert r.public_checked is False
    assert r.public_schema_current is None


def test_unexpected_when_on_surface_but_not_in_cohort() -> None:
    rows = build_census(
        cohort_symbols=["A"],
        volume={"B": "v0.4.0"},
        private={"B": "v0.4.0"},
        orphan_symbols=set(),
        public={"B": "v0.4.0"},
    )
    statuses = {r.gene_symbol: r.status for r in rows}
    assert statuses["A"] == "missing"
    assert statuses["B"] == "unexpected"


def test_exit_code_prioritizes_drift_over_missing() -> None:
    rows = build_census(
        cohort_symbols=["A", "B"],
        volume={"A": "v0.4.0"},  # A: private_missing (drift)
        private={},
        orphan_symbols=set(),
        public={},
    )  # B: missing
    assert exit_code(rows) == 1  # drift dominates


def test_exit_code_two_when_only_missing() -> None:
    rows = build_census(
        cohort_symbols=["A"], volume={}, private={}, orphan_symbols=set(), public={}
    )
    assert exit_code(rows) == 2


def test_exit_code_zero_when_all_ok() -> None:
    rows = build_census(
        cohort_symbols=["A"],
        volume={"A": "v0.4.0"},
        private={"A": "v0.4.0"},
        orphan_symbols=set(),
        public={"A": "v0.4.0"},
    )
    assert exit_code(rows) == 0
    assert summarize(rows)["ok"] == 1


def test_scan_volume_json_keys_on_record_symbol(tmp_path: Path) -> None:
    run_dir = tmp_path / "run1"
    run_dir.mkdir()
    # Filename stem differs from the record's hgnc_symbol — the record wins.
    (run_dir / "FILE.json").write_text(
        '{"gene": {"hgnc_symbol": "REAL"}, "schema_version": "v0.4.0"}'
    )
    (run_dir / "bad.json").write_text("{not json")
    out = scan_volume_json(run_dir)
    assert out["REAL"] == "v0.4.0"
    assert out["bad"] is None  # unreadable still counts as present


def test_scan_volume_json_missing_dir_is_empty(tmp_path: Path) -> None:
    assert scan_volume_json(tmp_path / "nope") == {}


def test_load_cohort_symbols_accepts_either_column(tmp_path: Path) -> None:
    tsv = tmp_path / "cohort.tsv"
    tsv.write_text(
        "hgnc_id\thgnc_symbol\tsonnet_verdict\n"
        "HGNC:1\tAAA\tyes\n"
        "HGNC:2\tBBB\tno\n"
        "HGNC:3\t\tyes\n"  # blank symbol skipped
    )
    assert load_cohort_symbols(tsv) == ["AAA", "BBB"]

    tsv2 = tmp_path / "cohort2.tsv"
    tsv2.write_text("gene_symbol\nCCC\n")  # legacy column name
    assert load_cohort_symbols(tsv2) == ["CCC"]
