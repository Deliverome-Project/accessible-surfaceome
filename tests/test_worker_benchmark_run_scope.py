"""The benchmark endpoints read only the SurfaceBench run, never the genome sweeps.

The 147 bench genes also sit in the genome-wide Sonnet/NCBI sweep and in the
PubMed rescue lanes. Those runs write the same (gene, claude-sonnet-4-6,
ncbi | pubmed_ncbi) cells with a later ``created_at`` and ``correct = 0``
(they have no truth to score against). ``/v1/benchmark/matrix`` and
``/v1/benchmark/export.tsv`` pick the latest replicate per cell, so without a
``run_id`` pin the genome row won: every Sonnet 4.6/ncbi cell served
``correct: 0``, CD19 included. This runs the Worker's own SQL on a fixture with
that shape and checks the bench replicate wins.
"""

from __future__ import annotations

import re
import sqlite3
from pathlib import Path

_WORKER = (
    Path(__file__).resolve().parents[1]
    / "cloudflare/workers/surfaceome_api/src/index.js"
)
_MODELS = ["claude-sonnet-4-6"]
_VARIANTS = ["ncbi", "pubmed_ncbi"]


def _src() -> str:
    return _WORKER.read_text(encoding="utf-8")


def _function_body(name: str) -> str:
    src = _src()
    start = src.index(f"async function {name}(")
    end = src.index("\nasync function ", start + 1)
    return src[start:end]


def _sql(body: str, head: str) -> str:
    m = re.search(r"`(" + re.escape(head) + r"[\s\S]*?)`", body)
    assert m, head
    return (
        m.group(1)
        .replace("${variantPlaceholders}", ",".join("?" * len(_VARIANTS)))
        .replace("${modelPlaceholders}", ",".join("?" * len(_MODELS)))
    )


def _fixture() -> sqlite3.Connection:
    con = sqlite3.connect(":memory:")
    con.row_factory = sqlite3.Row
    con.executescript(
        """
        CREATE TABLE benchmark_version (bench_version TEXT, gene_symbol TEXT,
          uniprot_acc TEXT, truth_verdict TEXT, truth_signal TEXT, truth_reason TEXT);
        CREATE TABLE triage_run_public (run_id TEXT, gene_symbol TEXT, model TEXT,
          prompt_variant TEXT, replicate INTEGER, predicted_verdict TEXT,
          predicted_reason TEXT, predicted_confidence TEXT,
          predicted_key_uncertainty TEXT, verdict_reasoning TEXT, correct INTEGER,
          latency_s REAL, n_web_searches INTEGER, created_at TEXT, error TEXT,
          cost_usd REAL, prompt_tokens INTEGER, completion_tokens INTEGER,
          cache_creation_tokens INTEGER, cache_read_tokens INTEGER);
        CREATE TABLE candidate_universe_public (gene_symbol TEXT, universe_version TEXT,
          go_surface_flag INTEGER, surfy_surface_flag INTEGER, hpa_surface_flag INTEGER);
        CREATE TABLE db_optimized_cutoff_public (accession TEXT,
          uniprot_optimized INTEGER, cspa_optimized INTEGER);
        INSERT INTO benchmark_version VALUES
          ('bench1', 'CD19', 'P15391', 'yes', 'likely_accessible', 'classical');
        INSERT INTO triage_run_public
          (run_id, gene_symbol, model, prompt_variant, replicate, predicted_verdict,
           correct, created_at)
        VALUES
          ('mainbench_canonical_v2', 'CD19', 'claude-sonnet-4-6', 'ncbi', 1, 'yes', 1,
           '2026-05-31 23:02:50'),
          ('mainbench_canonical_v2', 'CD19', 'claude-sonnet-4-6', 'ncbi', 2, 'yes', 1,
           '2026-05-31 23:02:51'),
          ('mainbench_canonical_v2', 'CD19', 'claude-sonnet-4-6', 'ncbi', 3, 'yes', 1,
           '2026-06-01 02:07:11'),
          ('genome_full_sonnet_ncbi_v2', 'CD19', 'claude-sonnet-4-6', 'ncbi', 1, 'yes', 0,
           '2026-06-01 03:41:11'),
          ('mainbench_canonical_v2', 'CD19', 'claude-sonnet-4-6', 'pubmed_ncbi', 3, 'yes', 1,
           '2026-06-01 02:11:44'),
          ('genome_1db_trim_pubmed_ncbi_v1', 'CD19', 'claude-sonnet-4-6', 'pubmed_ncbi', 1,
           'yes', 0, '2026-09-21 12:00:20');
        """
    )
    return con


def test_bench_run_id_constant() -> None:
    assert 'const BENCH_RUN_ID = "mainbench_canonical_v2";' in _src()


def test_matrix_serves_the_bench_replicate() -> None:
    body = _function_body("handleBenchmarkMatrix")
    assert (
        ".bind(benchVersion, BENCH_RUN_ID, ...wantedVariants, ...BENCH_MATRIX_MODELS)"
        in body
    )
    sql = _sql(body, "WITH bench_genes AS")
    params = ["bench1", "mainbench_canonical_v2", *_VARIANTS, *_MODELS]
    rows = _fixture().execute(sql, params).fetchall()
    got = {r["prompt_variant"]: (r["correct"], r["created_at"]) for r in rows}
    assert got == {
        "ncbi": (1, "2026-06-01 02:07:11"),
        "pubmed_ncbi": (1, "2026-06-01 02:11:44"),
    }


def test_export_serves_the_bench_replicate() -> None:
    body = _function_body("handleBenchmarkExport")
    assert re.search(
        r"\.bind\(\s*benchVersion, BENCH_RUN_ID,\s*"
        r"\.\.\.BENCH_MATRIX_VARIANTS, \.\.\.BENCH_MATRIX_MODELS,"
        r"\s*benchVersion, universeVersion,",
        body,
    )
    sql = _sql(body, "WITH ranked AS")
    params = ["bench1", "mainbench_canonical_v2", *_VARIANTS, *_MODELS, "bench1", "cu1"]
    rows = _fixture().execute(sql, params).fetchall()
    # The genome / rescue rows are replicate 1; the bench's latest is replicate 3.
    assert {r["prompt_variant"]: r["replicate"] for r in rows} == {
        "ncbi": 3,
        "pubmed_ncbi": 3,
    }


def test_triage_cell_is_pinned_to_the_bench_run() -> None:
    body = _function_body("handleTriageCell")
    assert ".bind(BENCH_RUN_ID, sym, model, variant)" in body
