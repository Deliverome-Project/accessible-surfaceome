"""Tests for ``scripts/deep_dive_sweep.py`` — the safety-critical
behaviors that protect a 5,680-gene production sweep from data /
money loss:

* Per-gene cost cap is a flag, not a discard: when the v2 pipeline
  exceeds ``--max-cost-per-gene-usd``, the record IS retained on disk
  and (best-effort) mirrored to D1.
* JSON path is scoped by ``run_id``: concurrent drivers with different
  run_ids cannot collide on the same filename.
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

# ``scripts/`` isn't a Python package and isn't on ty's first-party
# search path — the live Modal workers get it via cwd. Load it
# dynamically so the test runs without putting all 49 scripts under
# the type-checker's umbrella.
_SWEEP_PATH = Path(__file__).resolve().parent.parent / "scripts" / "deep_dive_sweep.py"
_spec = importlib.util.spec_from_file_location("deep_dive_sweep", _SWEEP_PATH)
assert _spec is not None and _spec.loader is not None
_sweep = importlib.util.module_from_spec(_spec)
sys.modules["deep_dive_sweep"] = _sweep
_spec.loader.exec_module(_sweep)

GeneResult = _sweep.GeneResult
GeneRow = _sweep.GeneRow
annotate_one = _sweep.annotate_one


def _fake_bundle(symbol: str = "FOO", hgnc_id: str = "HGNC:1"):
    bundle = MagicMock()
    bundle.hgnc_symbol = symbol
    bundle.hgnc_id = hgnc_id
    return bundle


def _fake_record(symbol: str = "FOO"):
    rec = MagicMock()
    rec.gene.hgnc_symbol = symbol
    rec.search_log = [object(), object(), object()]  # len == 3
    rec.model_dump_json.return_value = '{"stub": true}'
    return rec


def _fake_annotate_result(cost: float, record: object | None):
    res = MagicMock()
    res.total_cost_usd = cost
    res.record = record
    res.blocks_used = {"methods": 1}
    res.timing = [object(), object()]  # len == 2
    res.error = None if record is not None else "no record"
    return res


def test_cost_cap_retains_record(tmp_path: Path) -> None:
    """When cost exceeds the per-gene cap, the JSON file must still be
    written and the result must carry ``record_valid=True``,
    ``cost_capped=True``. This is the dollar-loss bug the cost-cap fix
    closes — discarding the work meant we paid for the tokens and
    threw the record away.
    """
    record = _fake_record("CAPGENE")
    annotate_result = _fake_annotate_result(cost=99.50, record=record)

    with (
        patch("deep_dive_sweep.open_default_client") as m_http,
        patch("deep_dive_sweep.resolve_by_hgnc_id",
              return_value=_fake_bundle("CAPGENE")) as _,
        patch("deep_dive_sweep.annotate", return_value=annotate_result),
    ):
        m_http.return_value = MagicMock()
        result = annotate_one(
            GeneRow(hgnc_id="HGNC:9", hgnc_symbol="CAPGENE", sonnet_verdict="yes"),
            run_id="run_test",
            sink=None,
            annotations_dir=tmp_path,
            max_cost_per_gene_usd=10.0,
        )

    assert result.record_valid is True
    assert result.cost_capped is True
    assert result.cost_usd == 99.50
    assert "cost_cap_exceeded" in (result.error or "")
    # JSON landed — the whole point.
    assert (tmp_path / "run_test" / "CAPGENE.json").exists()


def test_cost_under_cap_not_flagged(tmp_path: Path) -> None:
    annotate_result = _fake_annotate_result(cost=0.50, record=_fake_record("OKGENE"))
    with (
        patch("deep_dive_sweep.open_default_client") as m_http,
        patch("deep_dive_sweep.resolve_by_hgnc_id",
              return_value=_fake_bundle("OKGENE")),
        patch("deep_dive_sweep.annotate", return_value=annotate_result),
    ):
        m_http.return_value = MagicMock()
        result = annotate_one(
            GeneRow(hgnc_id="HGNC:1", hgnc_symbol="OKGENE", sonnet_verdict="yes"),
            run_id="run_test",
            sink=None,
            annotations_dir=tmp_path,
            max_cost_per_gene_usd=10.0,
        )
    assert result.record_valid is True
    assert result.cost_capped is False
    assert result.error is None


def test_json_path_scoped_by_run_id(tmp_path: Path) -> None:
    """Two drivers running the same gene under different run_ids must
    not collide on the same JSON filename. This is the "JSON file
    race" fix — without run_id scoping, last-writer-win could store
    the record D1 intentionally skipped via ``ON CONFLICT DO
    NOTHING``.
    """
    annotate_result = _fake_annotate_result(cost=0.5, record=_fake_record("RACEGENE"))
    with (
        patch("deep_dive_sweep.open_default_client") as m_http,
        patch("deep_dive_sweep.resolve_by_hgnc_id",
              return_value=_fake_bundle("RACEGENE")),
        patch("deep_dive_sweep.annotate", return_value=annotate_result),
    ):
        m_http.return_value = MagicMock()
        for run_id in ("run_alpha", "run_beta"):
            annotate_one(
                GeneRow(hgnc_id="HGNC:7", hgnc_symbol="RACEGENE", sonnet_verdict="no"),
                run_id=run_id,
                sink=None,
                annotations_dir=tmp_path,
                max_cost_per_gene_usd=10.0,
            )

    # Both files exist, in their own subdirs. No collision.
    assert (tmp_path / "run_alpha" / "RACEGENE.json").exists()
    assert (tmp_path / "run_beta" / "RACEGENE.json").exists()
    # And the top-level <symbol>.json (legacy path) does NOT exist —
    # the path scheme actually changed.
    assert not (tmp_path / "RACEGENE.json").exists()


def test_missing_record_still_fails_clean(tmp_path: Path) -> None:
    """If the v2 pipeline returns ``record=None`` (e.g. validation
    failure), nothing is written — ``record_valid=False``,
    ``cost_capped`` stays False (we don't flag the capped state on a
    record we threw away).
    """
    annotate_result = _fake_annotate_result(cost=2.0, record=None)
    with (
        patch("deep_dive_sweep.open_default_client") as m_http,
        patch("deep_dive_sweep.resolve_by_hgnc_id",
              return_value=_fake_bundle("BADGENE")),
        patch("deep_dive_sweep.annotate", return_value=annotate_result),
    ):
        m_http.return_value = MagicMock()
        result = annotate_one(
            GeneRow(hgnc_id="HGNC:5", hgnc_symbol="BADGENE", sonnet_verdict="yes"),
            run_id="run_test",
            sink=None,
            annotations_dir=tmp_path,
            max_cost_per_gene_usd=10.0,
        )
    assert result.record_valid is False
    assert result.cost_capped is False
    assert not (tmp_path / "run_test" / "BADGENE.json").exists()


def test_geneResult_defaults_safe() -> None:
    """``cost_capped`` defaults to False so that GeneResult constructed
    on the worker-exception path (in ``run_local``) doesn't accidentally
    register as cost-capped.
    """
    r = GeneResult(
        hgnc_id="HGNC:1", hgnc_symbol="X",
        cost_usd=0.0, latency_s=0.0, blocks_used={},
        error="worker raised", record_valid=False,
    )
    assert r.cost_capped is False
    assert r.d1_mirror_ok is True
    assert r.search_log_count == 0
