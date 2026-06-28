from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

from accessible_surfaceome.cloud.deep_dive_json_backfill import (
    BackfillMetadata,
    JsonBackfillCandidate,
    execute_json_backfill,
    load_metadata_tsv,
    plan_json_backfill,
)


def _candidate(symbol: str = "GENE") -> JsonBackfillCandidate:
    record = MagicMock()
    record.gene.hgnc_symbol = symbol
    return JsonBackfillCandidate(
        path=Path(f"{symbol}.json"),
        gene_symbol=symbol,
        record=record,
        action="loaded",
    )


def test_plan_marks_existing_and_missing() -> None:
    outcomes = plan_json_backfill(
        [_candidate("A"), _candidate("B")],
        existing={"A"},
    )

    assert [(o.gene_symbol, o.action) for o in outcomes] == [
        ("A", "existing"),
        ("B", "would_backfill"),
    ]


def test_plan_preserves_invalid_json_outcome() -> None:
    bad = JsonBackfillCandidate(
        path=Path("bad.json"),
        gene_symbol="bad",
        record=None,
        action="json_invalid",
        error="broken",
    )

    outcomes = plan_json_backfill([bad], existing=set())

    assert outcomes[0].action == "json_invalid"
    assert outcomes[0].error == "broken"


def test_load_metadata_tsv_defaults_missing_values(tmp_path: Path) -> None:
    path = tmp_path / "meta.tsv"
    path.write_text("gene_symbol\tcost_usd\nA\t1.25\nB\tbad\n")

    meta = load_metadata_tsv(path)

    assert meta["A"] == BackfillMetadata(cost_usd=1.25, latency_s=0.0, n_tool_calls=0)
    assert meta["B"] == BackfillMetadata()


def test_execute_uses_sink_for_missing_rows_only() -> None:
    candidate_a = _candidate("A")
    candidate_b = _candidate("B")
    sink = MagicMock()
    sink.__enter__.return_value = sink
    sink.insert.return_value = True

    with patch(
        "accessible_surfaceome.cloud.deep_dive_json_backfill.D1DeepDiveSink",
        return_value=sink,
    ) as sink_cls:
        outcomes = execute_json_backfill(
            run_id="run",
            candidates=[candidate_a, candidate_b],
            existing={"A"},
            metadata={"B": BackfillMetadata(cost_usd=2.0, latency_s=3.0, n_tool_calls=4)},
            d1=MagicMock(),
        )

    sink_cls.assert_called_once()
    sink.insert.assert_called_once_with(
        candidate_b.record,
        cost_usd=2.0,
        latency_s=3.0,
        n_tool_calls=4,
    )
    assert [(o.gene_symbol, o.action) for o in outcomes] == [
        ("A", "existing"),
        ("B", "backfilled"),
    ]
