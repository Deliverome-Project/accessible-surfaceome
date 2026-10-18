"""The SurfaceBench endpoints serve the paper's per-cell majority.

The paper and ``data/processed/triage_bench/mainbench_canonical_v2.tsv`` score
each (gene, model, variant) cell by the majority verdict over its three
replicates, with refused replicates out of the vote. ``/v1/benchmark/matrix``
used to serve the single latest replicate instead, so the SurfaceBench page
disagreed with the paper (Sonnet 4.6 / ncbi read 142/147 against the paper's
144/147).

This replays the committed per-replicate TSV (``mainbench_replicates_v2.tsv``,
the same 7,938 rows public D1 holds for the bench run) through the Worker's
own handlers on an in-memory SQLite database and checks every cell of the
matrix, the export TSV and the per-cell drawer endpoint against the committed
majority TSV. A few rows from other runs (the genome-wide sweep and a PubMed
rescue lane write the same Sonnet 4.6 cells with a later ``created_at``) ride
along to prove the endpoints stay pinned to the bench run.
"""

from __future__ import annotations

import csv
import json
import os
import shutil
import subprocess
from collections import Counter, defaultdict
from pathlib import Path

import pytest

_ROOT = Path(__file__).resolve().parents[1]
_BENCH = _ROOT / "data/processed/triage_bench"
_REPLICATES = _BENCH / "mainbench_replicates_v2.tsv"
_MAJORITY = _BENCH / "mainbench_canonical_v2.tsv"
_TRUTH = _ROOT / "data/eval/triage_benchmark_v1.tsv"
_RUN_ID = "mainbench_canonical_v2"
_TOTALS = [
    "prompt_tokens",
    "completion_tokens",
    "cache_creation_tokens",
    "cache_read_tokens",
    "n_web_searches",
    "cost_usd",
    "latency_s",
]
# An all-refused cell for the drawer spot-check; _drawer_samples adds more.
_DRAWER_CELLS = [
    ("NRROS", "claude-opus-5-5", "ncbi"),
]

_HARNESS = r"""
import assert from "node:assert/strict";
import { readFileSync, writeFileSync } from "node:fs";
import { DatabaseSync } from "node:sqlite";
import worker from "./worker.mjs";

const fixture = JSON.parse(readFileSync(process.argv[2], "utf8"));
const db = new DatabaseSync(":memory:");
db.exec(`
  CREATE TABLE benchmark_version (bench_version TEXT, gene_symbol TEXT,
    uniprot_acc TEXT, class TEXT, truth_verdict TEXT, truth_signal TEXT,
    truth_reason TEXT, rationale TEXT, created_at TEXT);
  CREATE TABLE triage_run_public (id INTEGER PRIMARY KEY AUTOINCREMENT,
    run_id TEXT, gene_symbol TEXT, model TEXT, prompt_variant TEXT,
    replicate INTEGER, predicted_verdict TEXT, predicted_reason TEXT,
    predicted_confidence TEXT, predicted_key_uncertainty TEXT,
    verdict_reasoning TEXT, correct INTEGER, latency_s REAL,
    n_web_searches INTEGER, created_at TEXT, error TEXT, cost_usd REAL,
    prompt_tokens INTEGER, completion_tokens INTEGER,
    cache_creation_tokens INTEGER, cache_read_tokens INTEGER);
  CREATE TABLE candidate_universe_release (universe_version TEXT, loaded_at TEXT);
  CREATE TABLE candidate_universe_public (gene_symbol TEXT, uniprot_acc TEXT,
    universe_version TEXT, uniprot_surface_flag INTEGER, go_surface_flag INTEGER,
    surfy_surface_flag INTEGER, cspa_surface_flag INTEGER, hpa_surface_flag INTEGER,
    n_sources_surface INTEGER);
  CREATE TABLE db_optimized_cutoff_public (accession TEXT,
    uniprot_optimized INTEGER, cspa_optimized INTEGER);
  INSERT INTO candidate_universe_release VALUES ('cu1', '2026-01-01');
`);
const ins = (table, row) => {
  const cols = Object.keys(row);
  db.prepare(`INSERT INTO ${table} (${cols.join(",")}) VALUES (${cols.map(() => "?").join(",")})`)
    .run(...cols.map((c) => row[c]));
};
for (const r of fixture.benchmark_version) ins("benchmark_version", r);
for (const r of fixture.triage_run_public) ins("triage_run_public", r);

let queries = 0;
const env = {
  CF_VERSION_METADATA: { id: "test" },
  DB: {
    prepare(sql) {
      let args = [];
      return {
        bind(...v) { args = v; return this; },
        async all() { queries++; return { results: db.prepare(sql).all(...args) }; },
        async first() { queries++; return db.prepare(sql).get(...args) ?? null; },
      };
    },
  },
};
globalThis.caches = { default: { match: async () => undefined, put: async () => {} } };
async function call(path) {
  const pending = [];
  const r = await worker.fetch(new Request("https://api.deliverome.org/surfaceome" + path),
                               env, { waitUntil(p) { pending.push(p); } });
  await Promise.all(pending);
  assert.equal(r.status, 200, path);
  return r;
}

const before = queries;
const matrix = await (await call("/v1/benchmark/matrix")).json();
const matrixQueries = queries - before;
const exportTsv = await (await call("/v1/benchmark/export.tsv")).text();
const drawer = {};
for (const [sym, model, variant] of fixture.drawer_cells) {
  drawer[`${sym}\t${model}\t${variant}`] =
    await (await call(`/v1/triage/${sym}/${model}/${variant}`)).json();
}
writeFileSync(process.argv[3], JSON.stringify({ matrix, matrixQueries, exportTsv, drawer }));
"""


def _read(path: Path) -> list[dict[str, str]]:
    with path.open() as fh:
        return list(csv.DictReader(fh, delimiter="\t"))


def _num(v: str) -> float | int | None:
    if v == "":
        return None
    f = float(v)
    return int(f) if f.is_integer() and "." not in v else f


def _fixture() -> dict:
    truth = [
        {
            "bench_version": "bench1",
            "gene_symbol": r["gene_symbol"],
            "uniprot_acc": r["uniprot_acc"],
            "class": r["class"],
            "truth_verdict": r["ground_truth_verdict"],
            "truth_signal": r["ground_truth_signal"],
            "truth_reason": r["ground_truth_reason"],
            "rationale": r["rationale"],
            "created_at": "2026-05-01",
        }
        for r in _read(_TRUTH)
    ]
    reps = []
    for r in _read(_REPLICATES):
        verdict = r["predicted_verdict"] or None
        reps.append(
            {
                "run_id": _RUN_ID,
                "gene_symbol": r["gene_symbol"],
                "model": r["model"],
                "prompt_variant": r["prompt_variant"],
                "replicate": int(r["replicate"]),
                "predicted_verdict": verdict,
                "predicted_reason": r["predicted_reason"] or None,
                "predicted_confidence": r["predicted_confidence"] or None,
                "verdict_reasoning": (
                    f"reasoning {r['gene_symbol']} {r['model']} {r['prompt_variant']} "
                    f"rep{r['replicate']}"
                    if verdict
                    else None
                ),
                "error": "refusal"
                if r["refused"] == "1"
                else (None if verdict else "invalid"),
                # Later replicate = later timestamp, so "latest replicate" is
                # replicate 3: the old single-replicate pick, not the majority.
                "created_at": f"2026-05-31 0{r['replicate']}:00:00",
                **{c: _num(r[c]) for c in _TOTALS},
            }
        )
    # Other runs write the same Sonnet 4.6 cells later, scored correct = 0.
    # A bench-scoped endpoint must never see them.
    for run_id, variant in [
        ("genome_full_sonnet_ncbi_v2", "ncbi"),
        ("genome_1db_trim_pubmed_ncbi_v1", "pubmed_ncbi"),
    ]:
        for g in ("CD19", "FOLR1", "MUC1"):
            for rep in (1, 2, 3, 4):
                reps.append(
                    {
                        "run_id": run_id,
                        "gene_symbol": g,
                        "model": "claude-sonnet-4-6",
                        "prompt_variant": variant,
                        "replicate": rep,
                        "predicted_verdict": "no",
                        "predicted_reason": "cytoplasmic",
                        "predicted_confidence": "high",
                        "correct": 0,
                        "created_at": "2026-09-21 12:00:00",
                        "cost_usd": 99.0,
                    }
                )
    return {
        "benchmark_version": truth,
        "triage_run_public": reps,
        "drawer_cells": [list(c) for c in _DRAWER_CELLS + _drawer_samples()],
    }


def _drawer_samples() -> list[tuple[str, str, str]]:
    """Cells where a naive pick goes wrong: a split cell whose winning
    verdict's reasons disagree, a unanimous cell whose replicate 1 gives the
    minority reason (the old drawer showed replicate 1's), and a cell with
    one refused replicate."""
    by_cell: dict[tuple[str, str, str], list[dict[str, str]]] = defaultdict(list)
    for r in _read(_REPLICATES):
        by_cell[(r["gene_symbol"], r["model"], r["prompt_variant"])].append(r)
    for reps in by_cell.values():
        reps.sort(key=lambda r: int(r["replicate"]))
    minority_first = next(
        k
        for k, reps in sorted(by_cell.items())
        if len({r["predicted_verdict"] for r in reps}) == 1
        and Counter(r["predicted_reason"] for r in reps)[reps[0]["predicted_reason"]]
        == 1
        and len({r["predicted_reason"] for r in reps}) == 2
    )
    split = next(
        k
        for k, reps in sorted(by_cell.items())
        if len({r["predicted_verdict"] for r in reps}) == 2
        and len({r["predicted_reason"] for r in reps if r["predicted_verdict"]}) == 3
    )
    refused = next(
        k
        for k, reps in sorted(by_cell.items())
        if sum(r["refused"] == "1" for r in reps) == 1
    )
    return [split, minority_first, refused]


@pytest.fixture(scope="module")
def served(tmp_path_factory: pytest.TempPathFactory) -> dict:
    node = shutil.which("node")
    if node is None:
        if os.environ.get("REQUIRE_WORKER_NODE") == "1":
            pytest.fail("Worker checks require Node; refusing to skip")
        pytest.skip("Node is required for Worker tests")
    tmp = tmp_path_factory.mktemp("bench_majority")
    source = (_ROOT / "cloudflare/workers/surfaceome_api/src/index.js").read_text()
    source = source.replace(
        'import { deepDiveTier, isLowLiteratureSurface } from "../../../../viewer/lib/catalog-presets";',
        "const deepDiveTier = () => ({tier: 'likely', facet: null}); "
        "const isLowLiteratureSurface = () => false;",
    )
    shutil.copy2(
        _ROOT / "cloudflare/workers/surfaceome_api/src/contact-sites.js",
        tmp / "contact-sites.js",
    )
    (tmp / "worker.mjs").write_text(source)
    (tmp / "harness.mjs").write_text(_HARNESS)
    (tmp / "fixture.json").write_text(json.dumps(_fixture()))
    result = subprocess.run(
        [
            node,
            "--no-warnings",
            str(tmp / "harness.mjs"),
            str(tmp / "fixture.json"),
            str(tmp / "out.json"),
        ],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stderr
    return json.loads((tmp / "out.json").read_text())


def _expected() -> dict[tuple[str, str, str], dict[str, str]]:
    return {
        (r["gene_symbol"], r["model"], r["prompt_variant"]): r for r in _read(_MAJORITY)
    }


def _served_cells(matrix: dict) -> dict[tuple[str, str, str], dict]:
    out = {}
    for row in matrix["rows"]:
        for model, by_variant in row["verdicts"].items():
            for variant, cell in by_variant.items():
                if cell is not None:
                    out[(row["gene_symbol"], model, variant)] = cell
    return out


def test_matrix_cells_equal_the_majority_tsv(served: dict) -> None:
    expected = _expected()
    cells = _served_cells(served["matrix"])
    scored = {k: c for k, c in cells.items() if c["verdict"] is not None}
    assert scored.keys() == expected.keys()
    for key, want in expected.items():
        got = scored[key]
        assert got["verdict"] == want["predicted_verdict"], key
        assert got["reason"] == want["predicted_reason"], key
        assert got["confidence"] == want["predicted_confidence"], key
        assert got["n_reps"] == int(want["n_reps"]), key
        assert got["majority_agreement"] == float(want["majority_agreement"]), key
        assert got["correct"] == int(want["is_match"]), key
        for col in _TOTALS:
            assert got["totals"][col] == pytest.approx(float(want[col]), abs=1e-6), (
                key,
                col,
            )
        # The reasoning shown belongs to a replicate that made the majority call.
        assert got["reasoning"] == (
            f"reasoning {key[0]} {key[1]} {key[2]} rep{got['replicate']}"
        ), key


def test_per_model_accuracy_equals_the_paper(served: dict) -> None:
    def tally(pairs):
        acc: dict[tuple[str, str], Counter] = defaultdict(Counter)
        for (_, model, variant), correct in pairs:
            acc[(model, variant)]["n"] += 1
            acc[(model, variant)]["ok"] += correct
        return {k: (v["ok"], v["n"]) for k, v in acc.items()}

    cells = _served_cells(served["matrix"])
    got = tally((k, c["correct"]) for k, c in cells.items() if c["correct"] is not None)
    want = tally((k, int(r["is_match"])) for k, r in _expected().items())
    assert got == want
    assert len(got) == 18
    assert got[("claude-sonnet-4-6", "ncbi")] == (144, 147)
    assert got[("claude-opus-5-5", "ncbi")] == (139, 146)


def test_all_refused_cell_is_present_but_never_scored(served: dict) -> None:
    cells = _served_cells(served["matrix"])
    unscored = {k for k, c in cells.items() if c["verdict"] is None}
    assert unscored == set(_expected().keys() ^ {k for k in cells})
    assert len(unscored) == 3
    for key in unscored:
        c = cells[key]
        assert (c["correct"], c["n_reps"], c["error"], c["reasoning"]) == (
            None,
            0,
            "refusal",
            None,
        ), key


def test_endpoints_stay_pinned_to_the_bench_run(served: dict) -> None:
    cells = _served_cells(served["matrix"])
    for g in ("CD19", "FOLR1", "MUC1"):
        for variant in ("ncbi", "pubmed_ncbi"):
            c = cells[(g, "claude-sonnet-4-6", variant)]
            assert c["totals"]["cost_usd"] < 99, (g, variant)
            assert c["replicate"] in (1, 2, 3)
            assert c["correct"] == 1
    lines = served["exportTsv"].rstrip("\n").split("\n")
    header = lines[0].split("\t")
    rows = [dict(zip(header, line.split("\t"), strict=True)) for line in lines[1:]]
    assert all(float(r["cost_usd_total"] or 0) < 99 for r in rows)


def test_matrix_reads_d1_in_a_bounded_number_of_queries(served: dict) -> None:
    # bench_version, truth, universe pointer, universe flags, replicates,
    # representative reasoning: one round-trip each, never one per cell.
    assert served["matrixQueries"] <= 6
    m = served["matrix"]
    assert m["cell_aggregation"] == "majority_of_replicates"
    assert m["run_id"] == _RUN_ID


def test_export_tsv_rows_equal_the_majority_tsv(served: dict) -> None:
    lines = served["exportTsv"].rstrip("\n").split("\n")
    header = lines[0].split("\t")
    # Existing columns keep their positions; new ones are appended.
    assert header[:24] == [
        "gene_symbol",
        "uniprot_acc",
        "db_uniprot",
        "db_go",
        "db_surfy",
        "db_cspa",
        "db_hpa",
        "n_db_surface",
        "truth_verdict",
        "truth_signal",
        "truth_reason",
        "model",
        "prompt_variant",
        "replicate",
        "predicted_verdict",
        "predicted_reason",
        "predicted_confidence",
        "prompt_tokens",
        "completion_tokens",
        "cache_creation_tokens",
        "cache_read_tokens",
        "n_web_searches",
        "cost_usd",
        "latency_s",
    ]
    rows = [dict(zip(header, line.split("\t"), strict=True)) for line in lines[1:]]
    expected = _expected()
    scored = {
        (r["gene_symbol"], r["model"], r["prompt_variant"]): r
        for r in rows
        if r["predicted_verdict"]
    }
    assert scored.keys() == expected.keys()
    assert len(rows) == len(expected) + 3
    for key, want in expected.items():
        got = scored[key]
        for col in (
            "predicted_verdict",
            "predicted_reason",
            "predicted_confidence",
            "n_reps",
            "is_match",
        ):
            assert got[col] == want[col], (key, col)
        assert float(got["majority_agreement"]) == float(want["majority_agreement"]), (
            key
        )
        for col in _TOTALS:
            assert float(got[f"{col}_total"]) == pytest.approx(
                float(want[col]), abs=1e-6
            )
    keys = [(r["gene_symbol"], r["model"], r["prompt_variant"]) for r in rows]
    assert keys == sorted(keys)


def test_drawer_majority_matches_the_matrix_cell(served: dict) -> None:
    cells = _served_cells(served["matrix"])
    for key, detail in served["drawer"].items():
        sym, model, variant = key.split("\t")
        cell = cells[(sym, model, variant)]
        maj = detail["majority"]
        if cell["verdict"] is None:
            assert maj is None
            continue
        assert (
            maj["verdict"],
            maj["reason"],
            maj["confidence"],
            maj["n_reps"],
            maj["agreement"],
            maj["reasoning"],
        ) == (
            cell["verdict"],
            cell["reason"],
            cell["confidence"],
            cell["n_reps"],
            cell["majority_agreement"],
            cell["reasoning"],
        ), key
