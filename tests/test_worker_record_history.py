"""Exercise the record-history routes of the real Worker router offline."""

from __future__ import annotations

import os
import shutil
import subprocess
from pathlib import Path

import pytest


def test_record_history_routes(tmp_path: Path) -> None:
    node = shutil.which("node")
    if node is None:
        if os.environ.get("REQUIRE_WORKER_NODE") == "1":
            pytest.fail(
                "Shared API compatibility checks require Node; refusing to skip"
            )
        pytest.skip("Node is required for Worker tests")
    root = Path(__file__).resolve().parents[1]
    source = (root / "cloudflare/workers/surfaceome_api/src/index.js").read_text()
    source = source.replace(
        'import { deepDiveTier, isLowLiteratureSurface } from "../../../../viewer/lib/catalog-presets";',
        "const deepDiveTier = () => ({tier: 'no', facet: null}); const isLowLiteratureSurface = () => false;",
    )
    (tmp_path / "worker.mjs").write_text(source)
    (tmp_path / "test.mjs").write_text(r"""
import assert from "node:assert/strict";
import worker from "./worker.mjs";

let cacheReads = 0;
globalThis.caches = { default: { match: async () => { cacheReads++; return undefined; }, put: async () => {} } };

const revisions = [
  { gene_symbol: "EGFR", hgnc_id: "HGNC:3236", revision: 1, published_at: "2026-08-15T00:00:00Z",
    source: "seed:zenodo-1.0.0", json_hash: "j1", evidence_hash: null, md_hash: null,
    schema_version: "2.14.2", prompt_corpus_version: "2.50.2" },
  { gene_symbol: "EGFR", hgnc_id: "HGNC:3236", revision: 2, published_at: "2026-09-27T00:00:00Z",
    source: "sweep", json_hash: "j2", evidence_hash: "e2", md_hash: "m2",
    schema_version: "2.14.4", prompt_corpus_version: "2.50.2" },
];
const releases = [{ version: "1.0.0", cut_at: "2026-08-15T00:00:00Z", github_tag: null,
  zenodo_version_doi: "10.5281/zenodo.20805384", n_genes: 1, notes: null }];
const members = [{ version: "1.0.0", gene_symbol: "EGFR", revision: 1 }];
const blobs = { "records/sha256/j1.json": '{"v":1}', "records/sha256/j2.json": '{"v":2}',
                "records/sha256/e2.json": '{"evidence":[]}', "records/sha256/m2.md": "# EGFR" };

const up = (s) => (s || "").toUpperCase();
const env = {
  ARCHIVE_BYPASS_TOKEN: "secret",
  RECORD_HISTORY: { async get(key) { return key in blobs ? { body: blobs[key] } : null; } },
  DB: { prepare(sql) { let a = []; return {
    bind(...v) { a = v; return this; },
    async first() {
      if (sql.includes("FROM data_release_member m") && sql.includes("JOIN record_revision")) {
        const mem = members.find(m => m.version === a[0] && up(m.gene_symbol) === up(a[1]));
        return mem ? revisions.find(r => r.revision === mem.revision) : null;
      }
      if (sql.includes("FROM data_release")) return releases.find(r => r.version === a[0]) || null;
      if (sql.includes("FROM record_revision"))
        return revisions.find(r => up(r.gene_symbol) === up(a[0]) && r.revision === a[1]) || null;
      return null;
    },
    async all() {
      if (sql.includes("FROM record_revision r") && sql.includes("ORDER BY r.revision DESC")) {
        const rows = revisions.filter(r => up(r.gene_symbol) === up(a[0])).slice().reverse();
        return { results: rows.map(r => ({ ...r, releases: JSON.stringify(
          members.filter(m => m.revision === r.revision).map(m => ({
            version: m.version, zenodo_version_doi: releases[0].zenodo_version_doi }))) })) };
      }
      if (sql.includes("FROM data_release_member m")) return { results: members.map(m => ({
        gene_symbol: m.gene_symbol, hgnc_id: "HGNC:3236", revision: m.revision, json_hash: "j1",
        evidence_hash: null, md_hash: null })) };
      if (sql.includes("FROM data_release")) return { results: releases };
      return { results: [] };
    },
  }; } },
};
async function call(path, headers = {}) {
  const pending = [];
  const r = await worker.fetch(new Request("https://api.deliverome.org/surfaceome" + path, { headers }),
    env, { waitUntil(p) { pending.push(p); } });
  await Promise.all(pending);
  return r;
}

// revision list
const list = await (await call("/v1/genes/egfr/revisions")).json();
assert.equal(list.current_revision, 2);
assert.deepEqual(list.revisions.map(r => r.revision), [2, 1]);
assert.equal(list.revisions[1].releases[0].version, "1.0.0");
assert.equal(list.revisions[1].evidence_url, null);
assert.match(list.revisions[0].url, /\/v1\/genes\/EGFR\/revisions\/2$/);

// revision bodies
let r = await call("/v1/genes/EGFR/revisions/2");
assert.equal(r.status, 200);
assert.equal(await r.text(), '{"v":2}');
assert.equal(r.headers.get("ETag"), '"j2"');
assert.equal(r.headers.get("X-Surfaceome-Revision"), "2");
assert.match(r.headers.get("Cache-Control"), /immutable/);
assert.equal(await (await call("/v1/genes/EGFR/revisions/2/evidence")).text(), '{"evidence":[]}');
r = await call("/v1/genes/EGFR/revisions/2.md");
assert.equal(await r.text(), "# EGFR");
assert.match(r.headers.get("Content-Type"), /text\/markdown/);
assert.equal((await (await call("/v1/genes/EGFR/revisions/1/evidence")).json()).error, "evidence_not_archived");
assert.equal((await (await call("/v1/genes/EGFR/revisions/1.md")).json()).error, "markdown_not_archived");
assert.equal((await (await call("/v1/genes/EGFR/revisions/9")).json()).error, "revision_not_found");
assert.equal((await call("/v1/genes/EGFR/revisions/0")).status, 400);
assert.equal((await (await call("/v1/genes/NOPE/revisions")).json()).error, "gene_not_annotated");

// missing R2 object never falls back to live
delete blobs["records/sha256/j1.json"];
r = await call("/v1/genes/EGFR/revisions/1");
assert.equal(r.status, 500);
assert.equal((await r.json()).error, "archive_body_missing");
blobs["records/sha256/j1.json"] = '{"v":1}';

// releases
const rl = await (await call("/v1/releases")).json();
assert.equal(rl.releases[0].version, "1.0.0");
const one = await (await call("/v1/releases/v1.0.0")).json();   // v-prefix normalized
assert.equal(one.version, "1.0.0");
assert.equal(one.members[0].gene_symbol, "EGFR");
assert.equal((await call("/v1/releases/one")).status, 400);
assert.equal((await (await call("/v1/releases/9.9.9")).json()).error, "release_not_found");
assert.equal(await (await call("/v1/releases/1.0.0/genes/egfr")).text(), '{"v":1}');
assert.equal((await (await call("/v1/releases/1.0.0/genes/CD63")).json()).error, "gene_not_in_release");

// archive bypass skips the caches only with the right secret
cacheReads = 0;
await call("/v1/genes/EGFR/revisions", { "X-Archive-Bypass": "wrong" });
assert.equal(cacheReads, 1);
cacheReads = 0;
const bypassed = await call("/v1/genes/EGFR/revisions", { "X-Archive-Bypass": "secret" });
assert.equal(cacheReads, 0);
assert.equal(bypassed.headers.get("X-Archive-Bypass-Honored"), "1");
assert.equal((await call("/v1/genes/EGFR/revisions", { "X-Archive-Bypass": "wrong" })).headers.get("X-Archive-Bypass-Honored"), null);

// a bypassed 404 also carries the honoured header — the archiver's
// _fetch_record checks this on every status, including 404, before it
// trusts the body enough to tell gene_not_annotated apart from a stale cache.
const notFoundBypassed = await call("/v1/genes/NOPE/revisions", { "X-Archive-Bypass": "secret" });
assert.equal(notFoundBypassed.status, 404);
assert.equal(notFoundBypassed.headers.get("X-Archive-Bypass-Honored"), "1");

// index lists the new endpoints
const idx = await (await call("/v1")).json();
const paths = idx.endpoints.map(e => e.path);
for (const p of ["/v1/genes/{symbol}/revisions", "/v1/genes/{symbol}/revisions/{n}",
                 "/v1/releases", "/v1/releases/{version}", "/v1/releases/{version}/genes/{symbol}"])
  assert(paths.includes(p), p);
console.log("ok");
""")
    out = subprocess.run(
        [node, str(tmp_path / "test.mjs")], capture_output=True, text=True
    )
    assert out.returncode == 0, out.stderr + out.stdout
    assert out.stdout.strip().endswith("ok")
