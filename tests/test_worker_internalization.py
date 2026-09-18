"""Exercise the real Worker router and internalization catalog projection offline."""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

import pytest


def test_internalization_routes_and_catalog(tmp_path: Path) -> None:
    node = shutil.which("node")
    if node is None:
        pytest.skip("Node is required for Worker tests")
    root = Path(__file__).resolve().parents[1]
    source = (root / "cloudflare/workers/surfaceome_api/src/index.js").read_text()
    # Classification is unrelated to this fixture, which has no deep-dive filters.
    source = source.replace(
        'import { deepDiveTier, isLowLiteratureSurface } from "../../../../viewer/lib/catalog-presets";',
        "const deepDiveTier = () => ({tier: 'no', facet: null}); "
        "const isLowLiteratureSurface = () => false;",
    )
    (tmp_path / "worker.mjs").write_text(source)
    (tmp_path / "test.mjs").write_text(r'''
import assert from "node:assert/strict";
import worker from "./worker.mjs";

const record = {
  gene_symbol: "TMEM123",
  model_priors: [{ overall_grade: "moderate" }],
  literature: { overall_grade: "moderate", observations: [{ id: "observation-1" }],
    sources: [{ spans: [{ source: { source_id: "DOI:10.1234/preprint" } }] }],
  },
};
const keys = [];
globalThis.caches = { default: {
  match: async (key) => { keys.push(key.url); return undefined; },
  put: async () => {},
} };
let reads = 0;
const env = {
  CF_VERSION_METADATA: { id: "restored-deployment" },
  DB: {
    async batch(statements) {
      assert.equal(statements.length, 1);
      return [{ results: [{ source_id: "DOI:10.1234/preprint", title: "An uptake assay",
        authors_short: "Smith et al.", journal: "bioRxiv (preprint)", year: 2025 }] }];
    },
    prepare(sql) {
    let args = [];
    return {
      bind(...values) { args = values; return this; },
      async first() {
        if (sql.includes("FROM candidate_universe_release")) return { universe_version: "test" };
        return null;
      },
      async all() {
        reads++;
        if (sql.includes("SELECT record_json FROM surface_internalization")) {
          assert.match(sql, /COLLATE NOCASE/);
          assert.match(sql, /ORDER BY schema_version DESC LIMIT 1/);
          return { results: args[0] === "TMEM123" ? [{ record_json: JSON.stringify(record) }] : [] };
        }
        if (sql.includes("FROM candidate_universe_public u")) return { results: [{
          gene_symbol: "TMEM123", n_sources_surface: 1, has_deep_dive: 1,
          intern_grade: "moderate", intern_has_lit: 1, intern_lit_grade: "moderate",
        }, { gene_symbol: "UNSWEPT", n_sources_surface: 0 }] };
        if (sql.includes("FROM surface_annotation sa1")) return { results: [{
          gene_symbol: "ORPHAN", intern_grade: "high", intern_has_lit: 0,
        }] };
        return { results: [] };
      },
    };
  } },
};
async function call(path) {
  const pending = [];
  const response = await worker.fetch(
    new Request("https://api.deliverome.org/surfaceome" + path),
    env, { waitUntil(p) { pending.push(p); } },
  );
  await Promise.all(pending);
  return response;
}
const response = await call("/v1/internalization/tmem123");
assert.equal(response.status, 200);
const payload = await response.json();
const { papers, ...savedRecord } = payload;
assert.deepEqual(savedRecord, record);
assert.equal(papers["DOI:10.1234/preprint"].title, "An uptake assay");
assert.equal(papers["DOI:10.1234/preprint"].authors_short, "Smith et al.");
assert.equal(papers["DOI:10.1234/preprint"].journal, "bioRxiv (preprint)");
assert.equal(papers["DOI:10.1234/preprint"].year, 2025);
assert.equal(response.headers.get("Access-Control-Allow-Origin"), "*");
assert.match(response.headers.get("Cache-Control"), /max-age=86400/);
const missing = await call("/v1/internalization/UNSWEPT");
assert.equal(missing.status, 200);
assert.equal(await missing.json(), null);
const beforeInvalid = reads;
assert.equal((await call("/v1/internalization/invalid!symbol")).status, 400);
assert.equal(reads, beforeInvalid);
const catalog = await (await call("/v1/catalog")).json();
assert.equal(catalog.row_schema, 9);
const tmem = catalog.rows.find(r => r.symbol === "TMEM123");
assert.equal(tmem.intern, "moderate");
assert.equal(tmem.intern_lit, 1);
assert.equal(tmem.intern_lit_grade, "moderate");
assert.equal(catalog.rows.find(r => r.symbol === "ORPHAN").intern, "high");
assert.equal(catalog.rows.find(r => r.symbol === "UNSWEPT").intern, undefined);
assert(keys.every(key => new URL(key).pathname.startsWith("/restored-deployment/")));
''')
    subprocess.run([node, str(tmp_path / "test.mjs")], check=True, capture_output=True, text=True)
