"""The catalog's Sonnet triage verdict must be the paper's two-stage verdict.

``/v1/catalog`` reports a triage verdict per gene. The paper's verdict is the
genome run, upgraded when any of the four literature-rescue runs calls the
gene yes or contextual (``scripts/build_candidate_universe_v3.py``). The Worker
used to pick rescue rows by ``prompt_variant = 'pubmed_ncbi'`` instead of by
run, which broke in both directions:

* a rescue cell that fell back to the ``naive`` variant (PubMed fetch failed)
  was invisible, so a rescued gene showed "no" (JMJD6, NBL1);
* SurfaceBench genes have benchmark ``pubmed_ncbi`` rows, which were treated
  as a rescue (SRC, PRAME), and their benchmark ``ncbi`` replicates outvoted
  the genome run (C3).

The live catalog therefore gave 1,106 zero-database candidates where the paper
reports 1,108. The first test pins the run lists to the universe builder; the
second runs the Worker offline against a small table covering each case.
"""
from __future__ import annotations

import ast
import os
import re
import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
WORKER = ROOT / "cloudflare/workers/surfaceome_api/src/index.js"


def _module_constant(path: Path, name: str):
    for node in ast.parse(path.read_text()).body:
        if isinstance(node, ast.Assign) and any(
            isinstance(t, ast.Name) and t.id == name for t in node.targets
        ):
            return ast.literal_eval(node.value)
    raise AssertionError(f"{name} not found in {path}")


def test_worker_run_ids_match_the_universe_builder() -> None:
    js = WORKER.read_text()
    block = re.search(r"const RESCUE_RUN_IDS = \[(.*?)\];", js, re.S)
    assert block, "RESCUE_RUN_IDS not found in the Worker"
    worker_rescue = re.findall(r'"([^"]+)"', block.group(1))
    assert worker_rescue == _module_constant(
        ROOT / "scripts/build_candidate_universe_v3.py", "RESCUE_RUNS"
    ), (
        "The Worker's RESCUE_RUN_IDS and build_candidate_universe_v3.RESCUE_RUNS "
        "differ. A lane added to one and not the other makes the live catalog "
        "disagree with the candidate universe the paper reports."
    )
    genome = re.search(r'const GENOME_RUN_ID = "([^"]+)";', js)
    assert genome and genome.group(1) == _module_constant(
        ROOT / "scripts/triage_runner.py", "CANONICAL_TRIAGE_RUN_ID"
    )


def test_catalog_triage_verdict_follows_the_two_stage_rule(tmp_path: Path) -> None:
    node = shutil.which("node")
    if node is None:
        if os.environ.get("REQUIRE_WORKER_NODE") == "1":
            pytest.fail("Worker checks require Node; refusing to skip")
        pytest.skip("Node is required for Worker tests")
    source = WORKER.read_text().replace(
        'import { deepDiveTier, isLowLiteratureSurface } from "../../../../viewer/lib/catalog-presets";',
        "const deepDiveTier = () => ({tier: 'likely', facet: null}); "
        "const isLowLiteratureSurface = () => false;",
    )
    shutil.copy2(WORKER.parent / "contact-sites.js", tmp_path / "contact-sites.js")
    (tmp_path / "worker.mjs").write_text(source)
    (tmp_path / "test.mjs").write_text(r'''
import assert from "node:assert/strict";
import worker from "./worker.mjs";

globalThis.caches = { default: { match: async () => undefined, put: async () => {} } };

const S = "claude-sonnet-4-6", H = "claude-haiku-4-5";
const GENOME = "genome_full_sonnet_ncbi_v2", BENCH = "mainbench_canonical_v2";
const L1 = "genome_full_sonnet_pubmed_ncbi_v1", L2 = "genome_intracellular_pubmed_ncbi_v1",
      L3 = "genome_1db_trim_pubmed_ncbi_v1", L4 = "genome_optcut_zerodb_pubmed_ncbi_v1";
let t = 0;
const row = (gene_symbol, run_id, model, prompt_variant, predicted_verdict, predicted_reason) =>
  ({ gene_symbol, run_id, model, prompt_variant, predicted_verdict, predicted_reason,
     created_at: `2026-01-01 00:00:${String(t++).padStart(2, "0")}` });
const table = [
  // A: rescued by a cell that fell back to the naive variant.
  row("A", GENOME, S, "ncbi", "no", "nuclear"),
  row("A", L4, S, "naive", "contextual", "dual_localization"),
  // B: positive in one lane, "no" in a later lane. Any positive lane rescues.
  row("B", GENOME, S, "ncbi", "no", "secreted_only"),
  row("B", L1, S, "naive", "contextual", "stable_surface_attachment"),
  row("B", L4, S, "pubmed_ncbi", "no", "secreted_only"),
  // C: benchmark gene. Benchmark ncbi replicates must not outvote the genome
  // run, and benchmark pubmed_ncbi rows are not a rescue.
  row("C", GENOME, S, "ncbi", "no", "cytoplasmic"),
  row("C", BENCH, S, "ncbi", "contextual", "cell_state_induced"),
  row("C", BENCH, S, "ncbi", "contextual", "cell_state_induced"),
  row("C", BENCH, S, "ncbi", "no", "cytoplasmic"),
  row("C", BENCH, S, "pubmed_ncbi", "contextual", "cell_state_induced"),
  row("C", BENCH, S, "pubmed_ncbi", "contextual", "cell_state_induced"),
  row("C", BENCH, S, "pubmed_ncbi", "contextual", "cell_state_induced"),
  row("C", BENCH, H, "ncbi", "contextual", "cell_state_induced"),
  // D: a rescue "no" never overrides a positive stage-one call.
  row("D", GENOME, S, "ncbi", "yes", "transmembrane_ecd"),
  row("D", L3, S, "pubmed_ncbi", "no", "cytoplasmic"),
  // E: two positive lanes that differ; the more inclusive verdict wins.
  row("E", GENOME, S, "ncbi", "no", "cytoplasmic"),
  row("E", L2, S, "pubmed_ncbi", "contextual", "cell_state_induced"),
  row("E", L3, S, "pubmed_ncbi", "yes", "gpi_anchored"),
  // F: not in the genome run; the benchmark replicates are the fallback.
  row("F", BENCH, S, "ncbi", "yes", "transmembrane_ecd"),
  row("F", BENCH, S, "ncbi", "yes", "transmembrane_ecd"),
  row("F", BENCH, S, "ncbi", "no", "cytoplasmic"),
];
const genes = ["A", "B", "C", "D", "E", "F"];
let sawRescueQuery = false;
const env = {
  CF_VERSION_METADATA: { id: "test" },
  DB: { prepare(sql) {
    let args = [];
    return {
      bind(...v) { args = v; return this; },
      async first() {
        if (/FROM candidate_universe_release/.test(sql)) return { universe_version: "u1", n_rows: genes.length, loaded_at: "x" };
        if (/FROM benchmark_version/.test(sql)) return { bench_version: "b1" };
        return null;
      },
      async all() {
        if (/FROM triage_run_public/.test(sql) && /run_id IN/.test(sql)) {
          sawRescueQuery = true;
          assert.doesNotMatch(sql, /prompt_variant/, "rescue rows are selected by run, not by variant");
          assert.deepEqual(args, [L1, L2, L3, L4]);
          return { results: table.filter(r => args.includes(r.run_id) && r.model === S) };
        }
        if (/FROM triage_run_public/.test(sql) && /prompt_variant = 'ncbi'/.test(sql)) {
          assert.match(sql, /run_id/, "the ncbi query must return run_id");
          return { results: table.filter(r => r.prompt_variant === "ncbi") };
        }
        if (/universe_version = \?/.test(sql)) return { results: genes.map(g => ({ gene_symbol: g })) };
        return { results: [] };
      },
    };
  } },
};
const pending = [];
const res = await worker.fetch(new Request("https://api.deliverome.org/surfaceome/v1/catalog"),
                               env, { waitUntil(p) { pending.push(p); } });
await Promise.all(pending);
assert.equal(res.status, 200);
const body = await res.json();
assert.ok(sawRescueQuery);
const sonnet = Object.fromEntries(body.rows.map(r => [r.symbol, r.tr?.[1] ?? null]));
assert.deepEqual(sonnet.A, ["contextual", "dual_localization"]);
assert.deepEqual(sonnet.B, ["contextual", "stable_surface_attachment"]);
assert.deepEqual(sonnet.C, ["no", "cytoplasmic"]);
assert.deepEqual(sonnet.D, ["yes", "transmembrane_ecd"]);
assert.deepEqual(sonnet.E, ["yes", "gpi_anchored"]);
assert.deepEqual(sonnet.F, ["yes", "transmembrane_ecd"]);
// The other model columns are untouched by the Sonnet rules.
assert.deepEqual(body.rows.find(r => r.symbol === "C").tr[0], ["contextual", "cell_state_induced"]);
console.log("ok");
''')
    proc = subprocess.run([node, "test.mjs"], cwd=tmp_path, capture_output=True, text=True)
    assert proc.returncode == 0, proc.stdout + proc.stderr
