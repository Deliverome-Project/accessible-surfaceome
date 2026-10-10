"""Exercise the Worker's reproducibility-replicate routes offline.

The replicates (Supplementary Figure 15) live in public D1 ``deep_dive_replicate``
and are served API-only. What this pins: every response is labelled as a
replicate, the per-record route attaches the shared deep-dive tier and returns
the stored record untouched, input is validated before D1 is read, and the
index never selects ``annotation_json``.
"""

from __future__ import annotations

import os
import shutil
import subprocess
from pathlib import Path

import pytest


def test_replicate_routes(tmp_path: Path) -> None:
    node = shutil.which("node")
    if node is None:
        if os.environ.get("REQUIRE_WORKER_NODE") == "1":
            pytest.fail("Worker checks require Node; refusing to skip")
        pytest.skip("Node is required for Worker tests")
    root = Path(__file__).resolve().parents[1]
    source = (root / "cloudflare/workers/surfaceome_api/src/index.js").read_text()
    source = source.replace(
        'import { deepDiveTier, isLowLiteratureSurface } from "../../../../viewer/lib/catalog-presets";',
        "const deepDiveTier = () => ({tier: 'likely', facet: null}); "
        "const isLowLiteratureSurface = () => false;",
    )
    shutil.copy2(
        root / "cloudflare/workers/surfaceome_api/src/contact-sites.js",
        tmp_path / "contact-sites.js",
    )
    (tmp_path / "worker.mjs").write_text(source)
    (tmp_path / "test.mjs").write_text(r'''
import assert from "node:assert/strict";
import worker from "./worker.mjs";

globalThis.caches = { default: { match: async () => undefined, put: async () => {} } };
const record = { gene: { hgnc_symbol: "GENEX" }, filters: { surface_accessibility: "high" },
                 executive_summary: {}, evidence: [{ id: "e1" }] };
const meta = { study_id: "deep_dive_concordance_v1", gene_symbol: "GENEX", hgnc_id: "HGNC:1",
  uniprot_acc: "P00001", sample_batch: 1, compared_against_run_id: "cu_v3_sonnet_2026_06",
  schema_version: "2.14.4", prompt_corpus_version: "2.50.2", record_generated_at: "2026-09-27" };
const rows = [
  { ...meta, replicate_kind: "full_rerun", run_id: "deep_dive_concordance_v1" },
  { ...meta, replicate_kind: "published_snapshot", run_id: "cu_v3_sonnet_2026_06" },
];
let reads = 0;
const env = {
  CF_VERSION_METADATA: { id: "test" },
  DB: { prepare(sql) {
    let args = [];
    return {
      bind(...v) { args = v; return this; },
      async all() {
        reads++;
        assert.match(sql, /FROM deep_dive_replicate/);
        assert.doesNotMatch(sql, /annotation_json/, "list routes must not read record JSON");
        if (sql.includes("WHERE gene_symbol")) {
          assert.match(sql, /COLLATE NOCASE/);
          return { results: args[0] === "GENEX" ? rows : [] };
        }
        return { results: rows };
      },
      async first() {
        reads++;
        const [sym, study, kind] = args;
        const hit = rows.find(r => r.gene_symbol === sym && r.study_id === study && r.replicate_kind === kind);
        return hit ? { ...hit, annotation_json: JSON.stringify(record) } : null;
      },
    };
  } },
};
async function call(path) {
  const pending = [];
  const r = await worker.fetch(new Request("https://api.deliverome.org/surfaceome" + path),
                               env, { waitUntil(p) { pending.push(p); } });
  await Promise.all(pending);
  return r;
}

const idx = await (await call("/v1/replicates")).json();
assert.match(idx.notice, /not the published record/);
assert.equal(idx.studies[0].n_genes, 1);
assert.equal(idx.studies[0].kinds.full_rerun.n, 1);

const list = await call("/v1/genes/genex/replicates");
assert.equal(list.status, 200);
const lj = await list.json();
assert.equal(lj.reproducibility_replicate, true);
assert.equal(lj.replicates.length, 2);
assert.match(lj.replicates[0].url, /\/genes\/GENEX\/replicates\/deep_dive_concordance_v1\//);
assert.equal((await call("/v1/genes/NONE/replicates")).status, 404);

const one = await call("/v1/genes/GENEX/replicates/deep_dive_concordance_v1/full_rerun");
assert.equal(one.status, 200);
const oj = await one.json();
assert.equal(oj.reproducibility_replicate, true);
assert.equal(oj.replicate_kind, "full_rerun");
assert.equal(oj.deep_dive_tier, "likely");
assert.deepEqual(oj.record, record);            // stored record untouched, evidence kept
assert.match(one.headers.get("Cache-Control"), /max-age=86400/);
assert.equal((await call("/v1/genes/GENEX/replicates/deep_dive_concordance_v1/fixed_evidence_replay")).status, 404);

const before = reads;
assert.equal((await call("/v1/genes/GENEX/replicates/deep_dive_concordance_v1/bogus")).status, 400);
assert.equal((await call("/v1/genes/GENEX/replicates/Bad-Study!/full_rerun")).status, 400);
assert.equal((await call("/v1/genes/bad!sym/replicates")).status, 400);
assert.equal(reads, before, "invalid input must be rejected before D1 is read");

const v1 = await (await call("/v1")).json();
assert(JSON.stringify(v1).includes("/v1/genes/{symbol}/replicates/{study}/{kind}"));
''')
    result = subprocess.run([node, str(tmp_path / "test.mjs")], capture_output=True, text=True)
    assert result.returncode == 0, result.stderr
